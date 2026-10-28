use super::{
    AccountError, AccountResult, AppState, Identity, authenticate, id, lock_identity, locked_user,
    security,
};
use image::{ImageFormat, ImageReader, Limits};
use salvo::prelude::*;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use sqlx::{MySql, Row, Transaction};
use std::{
    io::Cursor,
    path::Path,
    sync::{Arc, LazyLock},
};
use tokio::{io::AsyncWriteExt, sync::Semaphore};

static IMAGE_SLOTS: LazyLock<Arc<Semaphore>> = LazyLock::new(|| Arc::new(Semaphore::new(2)));
const QUOTA: u64 = 209715200;
const AVATAR_LIMIT: u64 = 2097152;

fn unsupported() -> AccountError {
    AccountError::new(
        StatusCode::UNSUPPORTED_MEDIA_TYPE,
        "UNSUPPORTED_FILE_TYPE",
        "文件类型或内容不正确；仅支持有效 JPEG、PNG、WebP 图片及无加密、无活动内容的帖子 PDF",
    )
}
fn storage_path(app: &AppState, key: &str) -> AccountResult<std::path::PathBuf> {
    if key.len() > 80
        || key.contains(['/', '\\'])
        || !key
            .bytes()
            .all(|v| v.is_ascii_alphanumeric() || b"-.".contains(&v))
    {
        return Err(AccountError::unavailable());
    }
    Ok(app.settings.accounts.uploads.join(key))
}

async fn decode(bytes: Vec<u8>) -> AccountResult<(String, String, u32, u32)> {
    let permit = IMAGE_SLOTS
        .clone()
        .try_acquire_owned()
        .map_err(|_| AccountError::busy())?;
    tokio::task::spawn_blocking(move || {
        let _permit = permit;
        let format = image::guess_format(&bytes).map_err(|_| unsupported())?;
        let (mime, ext) = match format {
            ImageFormat::Png => ("image/png", "png"),
            ImageFormat::Jpeg => ("image/jpeg", "jpg"),
            ImageFormat::WebP => ("image/webp", "webp"),
            _ => return Err(unsupported()),
        };
        let mut reader = ImageReader::with_format(Cursor::new(bytes), format);
        let mut limits = Limits::default();
        limits.max_image_width = Some(4096);
        limits.max_image_height = Some(4096);
        limits.max_alloc = Some(64 * 1024 * 1024);
        reader.limits(limits);
        let image = reader.decode().map_err(|_| unsupported())?;
        Ok((
            mime.to_owned(),
            ext.to_owned(),
            image.width(),
            image.height(),
        ))
    })
    .await
    .map_err(|_| AccountError::unavailable())?
}

pub(super) async fn upload(req: &mut Request, app: &AppState) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    if !req
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .is_some_and(|v| v.starts_with("multipart/form-data;"))
    {
        return Err(unsupported());
    }
    req.set_secure_max_size(10485760 + 65536);
    let form = req.form_data().await.map_err(|_| {
        AccountError::new(
            StatusCode::PAYLOAD_TOO_LARGE,
            "FILE_TOO_LARGE",
            "上传内容不完整或超过允许大小",
        )
    })?;
    if form.fields.len() != 1
        || form.fields.get_vec("purpose").is_none_or(|v| v.len() != 1)
        || form.files.len() != 1
        || form.files.get_vec("file").is_none_or(|v| v.len() != 1)
    {
        return Err(AccountError::validation(
            "purpose",
            "每次提交一个用途和一个文件",
        ));
    }
    let purpose = form.fields.get_vec("purpose").unwrap()[0].as_str();
    let limit = match purpose {
        "avatar" => AVATAR_LIMIT,
        "post_image" | "goods_image" => 5242880,
        "post_pdf" => 10485760,
        _ => return Err(AccountError::validation("purpose", "不支持该文件用途")),
    };
    let part = &form.files.get_vec("file").unwrap()[0];
    if part.size() == 0 || part.size() > limit {
        return Err(AccountError::new(
            StatusCode::PAYLOAD_TOO_LARGE,
            "FILE_TOO_LARGE",
            "文件超过该用途允许的大小",
        ));
    }
    let declared = part
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_owned();
    let name = part.name().unwrap_or("file").to_owned();
    if name.is_empty()
        || name.chars().count() > 255
        || name
            .chars()
            .any(|v| v.is_control() || v == '/' || v == '\\')
    {
        return Err(AccountError::validation("file", "文件名称不正确"));
    }
    let bytes = tokio::fs::read(part.path())
        .await
        .map_err(|_| AccountError::unavailable())?;
    let (mime, ext, width, height) = if purpose == "post_pdf" {
        validate_pdf(bytes.clone()).await?;
        ("application/pdf".to_owned(), "pdf".to_owned(), None, None)
    } else {
        let (mime, ext, w, h) = decode(bytes.clone()).await?;
        (mime, ext, Some(w), Some(h))
    };
    let declared_ext = Path::new(&name)
        .extension()
        .and_then(|v| v.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    if declared != mime || !(declared_ext == ext || (ext == "jpg" && declared_ext == "jpeg")) {
        return Err(unsupported());
    }
    let size = bytes.len() as u64;
    if size == 0 || size > limit {
        return Err(AccountError::new(
            StatusCode::PAYLOAD_TOO_LARGE,
            "FILE_TOO_LARGE",
            "文件超过该用途允许的大小",
        ));
    }
    let key = format!("{}.{}", uuid::Uuid::new_v4(), ext);
    let path = storage_path(app, &key)?;
    tokio::fs::create_dir_all(&app.settings.accounts.uploads)
        .await
        .map_err(|_| AccountError::unavailable())?;
    let mut tx = app.pool.begin().await?;
    let current = lock_identity(&mut tx, &identity).await?;
    if current.used_file_bytes > QUOTA - size {
        return Err(AccountError::new(
            StatusCode::UNPROCESSABLE_ENTITY,
            "FILE_QUOTA_EXCEEDED",
            "文件空间不足，请先清理未使用的文件",
        ));
    }
    let mut file = tokio::fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&path)
        .await
        .map_err(|_| AccountError::unavailable())?;
    if file.write_all(&bytes).await.is_err() || file.flush().await.is_err() {
        drop(file);
        let _ = tokio::fs::remove_file(&path).await;
        return Err(AccountError::unavailable());
    }
    drop(file);
    let saved=sqlx::query("INSERT INTO files(owner_id,purpose,storage_key,original_name,mime_type,size_bytes,sha256,width_px,height_px,expires_at) VALUES (?,?,?,?,?,?,?,?,?,DATE_ADD(UTC_TIMESTAMP(6),INTERVAL 24 HOUR))")
        .bind(current.id).bind(purpose).bind(&key).bind(&name).bind(&mime).bind(size).bind(Sha256::digest(&bytes).to_vec()).bind(width).bind(height).execute(&mut *tx).await;
    let saved = match saved {
        Ok(v) => v,
        Err(_) => {
            let _ = tokio::fs::remove_file(&path).await;
            return Err(AccountError::unavailable());
        }
    };
    if sqlx::query("UPDATE users SET used_file_bytes=used_file_bytes+? WHERE id=?")
        .bind(size)
        .bind(current.id)
        .execute(&mut *tx)
        .await
        .is_err()
        || tx.commit().await.is_err()
    {
        let _ = tokio::fs::remove_file(&path).await;
        return Err(AccountError::unavailable());
    }
    Ok(
        json!({"id":saved.last_insert_id().to_string(),"purpose":purpose,"mime_type":mime,"size_bytes":size,"name":name,"url":format!("/api/v1/files/{}/content",saved.last_insert_id()),"state":"staged","expires_at":super::iso(security::now()+86400)}),
    )
}

async fn validate_pdf(bytes: Vec<u8>) -> AccountResult<()> {
    let permit = IMAGE_SLOTS
        .clone()
        .try_acquire_owned()
        .map_err(|_| AccountError::busy())?;
    tokio::task::spawn_blocking(move || {
        let _permit = permit;
        if !bytes.starts_with(b"%PDF-")
            || !bytes[bytes.len().saturating_sub(4096)..]
                .windows(5)
                .any(|w| w == b"%%EOF")
        {
            return Err(unsupported());
        }
        let doc = lopdf::Document::load_mem_with_options(
            &bytes,
            lopdf::LoadOptions {
                max_decompressed_size: Some(64 * 1024 * 1024),
                ..Default::default()
            },
        )
        .map_err(|_| unsupported())?;
        if doc.is_encrypted() || doc.trailer.has(b"Encrypt") {
            return Err(unsupported());
        }
        // Parse the document, reject active/embedded content, and walk page references with cycle detection.
        let mut pending = doc.objects.values().collect::<Vec<_>>();
        while let Some(object) = pending.pop() {
            let dict = match object {
                lopdf::Object::Dictionary(d) => Some(d),
                lopdf::Object::Stream(s) => Some(&s.dict),
                lopdf::Object::Array(items) => {
                    pending.extend(items);
                    None
                }
                _ => None,
            };
            if let Some(dict) = dict {
                if [
                    b"JS".as_slice(),
                    b"JavaScript",
                    b"OpenAction",
                    b"AA",
                    b"EmbeddedFiles",
                    b"EF",
                    b"RichMedia",
                    b"XFA",
                ]
                .iter()
                .any(|key| dict.has(key))
                {
                    return Err(unsupported());
                }
                if dict.get(b"Type").ok().and_then(|v| v.as_name().ok())
                    == Some(b"EmbeddedFile".as_slice())
                {
                    return Err(unsupported());
                }
                if dict
                    .get(b"S")
                    .ok()
                    .and_then(|v| v.as_name().ok())
                    .is_some_and(|v| {
                        [
                            b"JavaScript".as_slice(),
                            b"Launch",
                            b"SubmitForm",
                            b"ImportData",
                            b"GoToR",
                            b"Rendition",
                            b"Sound",
                            b"Movie",
                        ]
                        .contains(&v)
                    })
                {
                    return Err(unsupported());
                }
                pending.extend(dict.iter().map(|(_, value)| value));
            }
        }
        let root = doc
            .trailer
            .get(b"Root")
            .and_then(|v| v.as_reference())
            .map_err(|_| unsupported())?;
        let catalog = doc.get_dictionary(root).map_err(|_| unsupported())?;
        let pages = catalog
            .get(b"Pages")
            .and_then(|v| v.as_reference())
            .map_err(|_| unsupported())?;
        let mut stack = vec![pages];
        let mut seen = std::collections::HashSet::new();
        let mut count = 0;
        while let Some(page) = stack.pop() {
            if !seen.insert(page) {
                return Err(unsupported());
            }
            let dict = doc.get_dictionary(page).map_err(|_| unsupported())?;
            match dict
                .get(b"Type")
                .and_then(|v| v.as_name())
                .map_err(|_| unsupported())?
            {
                b"Page" => count += 1,
                b"Pages" => {
                    for kid in dict
                        .get(b"Kids")
                        .and_then(|v| v.as_array())
                        .map_err(|_| unsupported())?
                    {
                        stack.push(kid.as_reference().map_err(|_| unsupported())?);
                    }
                }
                _ => return Err(unsupported()),
            }
        }
        if count == 0 {
            return Err(unsupported());
        }
        Ok(())
    })
    .await
    .map_err(|_| AccountError::unavailable())?
}

pub(super) async fn bind_avatar(
    tx: &mut Transaction<'_, MySql>,
    owner: u64,
    new_file: Option<u64>,
) -> AccountResult<()> {
    let old = sqlx::query_scalar::<_, u64>(
        "SELECT file_id FROM file_bindings WHERE avatar_user_id=? AND kind='avatar'",
    )
    .bind(owner)
    .fetch_optional(&mut **tx)
    .await?;
    if old == new_file {
        return Ok(());
    }
    if let Some(file) = new_file {
        let row=sqlx::query("SELECT owner_id,purpose,state,expires_at>UTC_TIMESTAMP(6) AS fresh FROM files WHERE id=? FOR UPDATE").bind(file).fetch_optional(&mut **tx).await?.ok_or_else(AccountError::missing)?;
        if row.get::<u64, _>("owner_id") != owner {
            return Err(AccountError::missing());
        }
        if row.get::<String, _>("purpose") != "avatar"
            || row.get::<String, _>("state") != "staged"
            || row.get::<Option<bool>, _>("fresh") != Some(true)
        {
            return Err(AccountError::validation(
                "avatar_file_id",
                "头像图片已绑定、失效或不可用，请重新上传",
            ));
        }
    }
    sqlx::query("DELETE FROM file_bindings WHERE avatar_user_id=? AND kind='avatar'")
        .bind(owner)
        .execute(&mut **tx)
        .await?;
    if let Some(old) = old {
        sqlx::query("UPDATE files SET state='cleanup_pending' WHERE id=?")
            .bind(old)
            .execute(&mut **tx)
            .await?;
    }
    if let Some(new_file) = new_file {
        sqlx::query("INSERT INTO file_bindings(file_id,kind,avatar_user_id) VALUES (?,'avatar',?)")
            .bind(new_file)
            .bind(owner)
            .execute(&mut **tx)
            .await?;
        sqlx::query("UPDATE files SET state='attached',expires_at=NULL WHERE id=?")
            .bind(new_file)
            .execute(&mut **tx)
            .await?;
    }
    Ok(())
}

pub(super) async fn read(req: &Request, app: &AppState) -> AccountResult<(String, Vec<u8>)> {
    let file = id(req
        .param::<String>("file_id")
        .as_deref()
        .ok_or_else(AccountError::missing)?)?;
    let row=sqlx::query("SELECT f.owner_id,CAST(f.storage_key AS CHAR CHARACTER SET utf8mb4) AS storage_key,f.mime_type,f.state,f.expires_at>UTC_TIMESTAMP(6) AS fresh,b.avatar_user_id,b.post_id,b.goods_id,p.author_id,p.board_id,p.visibility,p.deleted_at IS NOT NULL AS post_deleted,g.state AS goods_state,g.seller_id,g.moderation,g.deleted_at IS NOT NULL AS goods_deleted FROM files f LEFT JOIN file_bindings b ON b.file_id=f.id LEFT JOIN posts p ON p.id=b.post_id LEFT JOIN goods g ON g.id=b.goods_id WHERE f.id=?").bind(file).fetch_optional(&app.pool).await?.ok_or_else(AccountError::missing)?;
    let state = row.get::<String, _>("state");
    if state == "staged" && row.get::<Option<bool>, _>("fresh") == Some(true) {
        let identity = authenticate(req, app)
            .await
            .map_err(|_| AccountError::missing())?;
        if identity.user.id != row.get::<u64, _>("owner_id") {
            return Err(AccountError::missing());
        }
    } else if state == "attached" {
        if row.get::<Option<u64>, _>("avatar_user_id").is_some() {
            // Avatars are public.
        } else if row.get::<Option<u64>, _>("post_id").is_some()
            && !row.get::<bool, _>("post_deleted")
        {
            if row.get::<Option<String>, _>("visibility").as_deref() != Some("public") {
                let identity = authenticate(req, app)
                    .await
                    .map_err(|_| AccountError::missing())?;
                if Some(identity.user.id) != row.get::<Option<u64>, _>("author_id")
                    && !crate::forum::can_manage(&app.pool, &identity.user, row.get("board_id"))
                        .await?
                {
                    return Err(AccountError::missing());
                }
            }
        } else if row.get::<Option<u64>, _>("goods_id").is_some()
            && !row.get::<bool, _>("goods_deleted")
        {
            if row.get::<Option<String>, _>("moderation").as_deref() != Some("clear") {
                let viewer = authenticate(req, app)
                    .await
                    .map_err(|_| AccountError::missing())?;
                if Some(viewer.user.id) != row.get::<Option<u64>, _>("seller_id")
                    && viewer.user.role != "admin"
                {
                    return Err(AccountError::missing());
                }
            }
        } else {
            return Err(AccountError::missing());
        }
    } else {
        return Err(AccountError::missing());
    }
    let bytes = tokio::fs::read(storage_path(app, &row.get::<String, _>("storage_key"))?)
        .await
        .map_err(|_| AccountError::missing())?;
    Ok((row.get("mime_type"), bytes))
}

async fn remove_locked(
    app: &AppState,
    identity: Option<&Identity>,
    owner: u64,
    file: u64,
) -> AccountResult<()> {
    let mut tx = app.pool.begin().await?;
    if let Some(identity) = identity {
        lock_identity(&mut tx, identity).await?;
    } else {
        locked_user(&mut tx, owner).await?;
    }
    let row=sqlx::query("SELECT owner_id,CAST(storage_key AS CHAR CHARACTER SET utf8mb4) AS storage_key,state,size_bytes,expires_at<=UTC_TIMESTAMP(6) AS expired FROM files WHERE id=? FOR UPDATE").bind(file).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
    if row.get::<u64, _>("owner_id") != owner {
        return Err(AccountError::missing());
    }
    let state = row.get::<String, _>("state");
    if state == "cleaned" {
        return Ok(());
    }
    if state == "attached" {
        return Err(AccountError::validation(
            "file_id",
            "正在使用的文件不能直接删除",
        ));
    }
    if identity.is_none()
        && state != "cleanup_pending"
        && row.get::<Option<bool>, _>("expired") != Some(true)
    {
        return Ok(());
    }
    let path = storage_path(app, &row.get::<String, _>("storage_key"))?;
    match tokio::fs::remove_file(path).await {
        Ok(()) => {}
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(_) => {
            sqlx::query("UPDATE files SET state='cleanup_pending' WHERE id=?")
                .bind(file)
                .execute(&mut *tx)
                .await?;
            tx.commit().await?;
            return Err(AccountError::unavailable());
        }
    }
    let size = row.get::<u64, _>("size_bytes");
    sqlx::query("UPDATE files SET state='cleaned',cleaned_at=UTC_TIMESTAMP(6) WHERE id=?")
        .bind(file)
        .execute(&mut *tx)
        .await?;
    sqlx::query(
        "UPDATE users SET used_file_bytes=IF(used_file_bytes>=?,used_file_bytes-?,0) WHERE id=?",
    )
    .bind(size)
    .bind(size)
    .bind(owner)
    .execute(&mut *tx)
    .await?;
    tx.commit().await?;
    Ok(())
}
pub(super) async fn delete(req: &Request, app: &AppState) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let file = id(req
        .param::<String>("file_id")
        .as_deref()
        .ok_or_else(AccountError::missing)?)?;
    remove_locked(app, Some(&identity), identity.user.id, file).await?;
    Ok(json!({"ok":true}))
}
pub async fn cleanup_files(app: &AppState) -> AccountResult<()> {
    let rows=sqlx::query("SELECT id,owner_id FROM files WHERE state='cleanup_pending' OR (state='staged' AND expires_at<=UTC_TIMESTAMP(6)) ORDER BY id LIMIT 100").fetch_all(&app.pool).await?;
    for row in rows {
        let _ = remove_locked(app, None, row.get("owner_id"), row.get("id")).await;
    }
    Ok(())
}

pub(crate) async fn post_files(pool: &sqlx::MySqlPool, post: u64) -> AccountResult<Vec<Value>> {
    let rows=sqlx::query("SELECT f.id,f.purpose,f.mime_type,f.size_bytes,f.original_name FROM file_bindings b JOIN files f ON f.id=b.file_id WHERE b.post_id=? AND f.state='attached' ORDER BY b.kind,b.position_no").bind(post).fetch_all(pool).await?;
    Ok(rows.iter().map(|r|json!({"id":r.get::<u64,_>("id").to_string(),"purpose":r.get::<String,_>("purpose"),"mime_type":r.get::<String,_>("mime_type"),"size_bytes":r.get::<u64,_>("size_bytes"),"name":r.get::<String,_>("original_name"),"url":format!("/api/v1/files/{}/content",r.get::<u64,_>("id")),"state":"attached","expires_at":null})).collect())
}

pub(crate) async fn bind_post(
    tx: &mut Transaction<'_, MySql>,
    owner: u64,
    post: u64,
    images: Option<&[String]>,
    pdfs: Option<&[String]>,
) -> AccountResult<()> {
    let old = sqlx::query(
        "SELECT file_id,kind FROM file_bindings WHERE post_id=? ORDER BY file_id FOR UPDATE",
    )
    .bind(post)
    .fetch_all(&mut **tx)
    .await?;
    let resolve = |ids: Option<&[String]>, kind: &str| -> AccountResult<Vec<u64>> {
        if let Some(ids) = ids {
            ids.iter().map(|s| id(s)).collect()
        } else {
            Ok(old
                .iter()
                .filter(|r| r.get::<String, _>("kind") == kind)
                .map(|r| r.get("file_id"))
                .collect())
        }
    };
    let images = resolve(images, "post_image")?;
    let pdfs = resolve(pdfs, "post_pdf")?;
    if images.len() > 9 || pdfs.len() > 2 {
        return Err(AccountError::validation(
            "image_file_ids",
            "帖子最多 9 张图片和 2 个 PDF",
        ));
    }
    let all = images
        .iter()
        .chain(pdfs.iter())
        .copied()
        .collect::<std::collections::HashSet<_>>();
    if all.len() != images.len() + pdfs.len() {
        return Err(AccountError::validation(
            "image_file_ids",
            "同一文件不能重复绑定",
        ));
    }
    let mut sorted = all.iter().copied().collect::<Vec<_>>();
    sorted.sort_unstable();
    for file in sorted {
        let row=sqlx::query("SELECT f.owner_id,f.purpose,f.state,f.expires_at>UTC_TIMESTAMP(6) AS fresh,b.post_id FROM files f LEFT JOIN file_bindings b ON b.file_id=f.id WHERE f.id=? FOR UPDATE").bind(file).fetch_optional(&mut **tx).await?.ok_or_else(AccountError::missing)?;
        if row.get::<u64, _>("owner_id") != owner {
            return Err(AccountError::missing());
        }
        let expected = if images.contains(&file) {
            "post_image"
        } else {
            "post_pdf"
        };
        let state = row.get::<String, _>("state");
        let valid = (state == "staged"
            && row.get::<Option<bool>, _>("fresh") == Some(true)
            && row.get::<Option<u64>, _>("post_id").is_none())
            || (state == "attached" && row.get::<Option<u64>, _>("post_id") == Some(post));
        if row.get::<String, _>("purpose") != expected || !valid {
            return Err(AccountError::validation(
                "image_file_ids",
                "文件用途不符、已绑定其他内容或已过期，请重新上传",
            ));
        }
    }
    sqlx::query("DELETE FROM file_bindings WHERE post_id=?")
        .bind(post)
        .execute(&mut **tx)
        .await?;
    for row in &old {
        let file = row.get::<u64, _>("file_id");
        if !all.contains(&file) {
            sqlx::query("UPDATE files SET state='cleanup_pending' WHERE id=?")
                .bind(file)
                .execute(&mut **tx)
                .await?;
        }
    }
    for (kind, ids) in [("post_image", images), ("post_pdf", pdfs)] {
        for (index, file) in ids.iter().enumerate() {
            sqlx::query(
                "INSERT INTO file_bindings(file_id,kind,post_id,position_no) VALUES (?,?,?,?)",
            )
            .bind(file)
            .bind(kind)
            .bind(post)
            .bind((index + 1) as u32)
            .execute(&mut **tx)
            .await?;
            sqlx::query("UPDATE files SET state='attached',expires_at=NULL WHERE id=?")
                .bind(file)
                .execute(&mut **tx)
                .await?;
        }
    }
    Ok(())
}

pub(crate) async fn goods_files(pool: &sqlx::MySqlPool, goods: u64) -> AccountResult<Vec<Value>> {
    let rows=sqlx::query("SELECT f.id,f.purpose,f.mime_type,f.size_bytes,f.original_name FROM file_bindings b JOIN files f ON f.id=b.file_id WHERE b.goods_id=? AND f.state='attached' ORDER BY b.position_no").bind(goods).fetch_all(pool).await?;
    Ok(rows.iter().map(|r|json!({"id":r.get::<u64,_>("id").to_string(),"purpose":r.get::<String,_>("purpose"),"mime_type":r.get::<String,_>("mime_type"),"size_bytes":r.get::<u64,_>("size_bytes"),"name":r.get::<String,_>("original_name"),"url":format!("/api/v1/files/{}/content",r.get::<u64,_>("id")),"state":"attached","expires_at":null})).collect())
}
pub(crate) async fn bind_goods(
    tx: &mut Transaction<'_, MySql>,
    owner: u64,
    goods: u64,
    images: &[String],
) -> AccountResult<()> {
    if !(1..=6).contains(&images.len()) {
        return Err(AccountError::validation(
            "image_file_ids",
            "商品必须有1～6张图片",
        ));
    }
    let ids = images
        .iter()
        .map(|v| id(v))
        .collect::<AccountResult<Vec<_>>>()?;
    let mut sorted = ids.clone();
    sorted.sort_unstable();
    sorted.dedup();
    if sorted.len() != ids.len() {
        return Err(AccountError::validation(
            "image_file_ids",
            "商品图片不能重复",
        ));
    }
    let old = sqlx::query_scalar::<_, u64>(
        "SELECT file_id FROM file_bindings WHERE goods_id=? ORDER BY file_id FOR UPDATE",
    )
    .bind(goods)
    .fetch_all(&mut **tx)
    .await?;
    for file in &sorted {
        let row=sqlx::query("SELECT f.owner_id,f.purpose,f.state,f.expires_at>UTC_TIMESTAMP(6) AS fresh,b.id AS binding_id,b.goods_id FROM files f LEFT JOIN file_bindings b ON b.file_id=f.id WHERE f.id=? FOR UPDATE").bind(file).fetch_optional(&mut **tx).await?.ok_or_else(AccountError::missing)?;
        if row.get::<u64, _>("owner_id") != owner {
            return Err(AccountError::missing());
        }
        let state = row.get::<String, _>("state");
        let valid = (state == "staged"
            && row.get::<Option<bool>, _>("fresh") == Some(true)
            && row.get::<Option<u64>, _>("binding_id").is_none())
            || (state == "attached" && row.get::<Option<u64>, _>("goods_id") == Some(goods));
        if row.get::<String, _>("purpose") != "goods_image" || !valid {
            return Err(AccountError::validation(
                "image_file_ids",
                "商品图片用途不符、已绑定其他内容或已过期",
            ));
        }
    }
    sqlx::query("DELETE FROM file_bindings WHERE goods_id=?")
        .bind(goods)
        .execute(&mut **tx)
        .await?;
    for old in old {
        if !ids.contains(&old) {
            sqlx::query("UPDATE files SET state='cleanup_pending' WHERE id=?")
                .bind(old)
                .execute(&mut **tx)
                .await?;
        }
    }
    for (position, file) in ids.iter().enumerate() {
        sqlx::query("INSERT INTO file_bindings(file_id,kind,goods_id,position_no) VALUES (?,'goods_image',?,?)").bind(file).bind(goods).bind((position+1) as u32).execute(&mut **tx).await?;
        sqlx::query("UPDATE files SET state='attached',expires_at=NULL WHERE id=?")
            .bind(file)
            .execute(&mut **tx)
            .await?;
    }
    Ok(())
}

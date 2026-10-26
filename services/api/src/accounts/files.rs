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
        "头像只接受可正常解码的 JPEG、PNG、WebP 图片，类型和扩展名须一致",
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
    req.set_secure_max_size(AVATAR_LIMIT as usize + 65536);
    let form = req.form_data().await.map_err(|_| {
        AccountError::new(
            StatusCode::PAYLOAD_TOO_LARGE,
            "FILE_TOO_LARGE",
            "头像不能超过 2 MiB",
        )
    })?;
    if form.fields.len() != 1
        || form
            .fields
            .get_vec("purpose")
            .is_none_or(|v| v.len() != 1 || v[0] != "avatar")
        || form.files.len() != 1
        || form.files.get_vec("file").is_none_or(|v| v.len() != 1)
    {
        return Err(AccountError::validation(
            "purpose",
            "本阶段仅支持上传一张头像图片",
        ));
    }
    let part = &form.files.get_vec("file").unwrap()[0];
    if part.size() == 0 || part.size() > AVATAR_LIMIT {
        return Err(AccountError::new(
            StatusCode::PAYLOAD_TOO_LARGE,
            "FILE_TOO_LARGE",
            "头像大小须为 1 字节～2 MiB",
        ));
    }
    let declared = part
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_owned();
    let name = part
        .name()
        .unwrap_or("avatar")
        .rsplit(['/', '\\'])
        .next()
        .unwrap_or("avatar")
        .chars()
        .take(255)
        .collect::<String>();
    let source = part.path().clone();
    let bytes = tokio::fs::read(source)
        .await
        .map_err(|_| AccountError::unavailable())?;
    let (mime, ext, width, height) = decode(bytes.clone()).await?;
    let declared_ext = Path::new(&name)
        .extension()
        .and_then(|v| v.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    if declared != mime || !(declared_ext == ext || (ext == "jpg" && declared_ext == "jpeg")) {
        return Err(unsupported());
    }
    let size = bytes.len() as u64;
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
            "文件空间不足，请先清理未使用的图片",
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
    let saved=sqlx::query("INSERT INTO files(owner_id,purpose,storage_key,original_name,mime_type,size_bytes,sha256,width_px,height_px,expires_at) VALUES (?,'avatar',?,?,?,?,?,?,?,DATE_ADD(UTC_TIMESTAMP(6),INTERVAL 24 HOUR))")
        .bind(current.id).bind(&key).bind(&name).bind(&mime).bind(size).bind(Sha256::digest(&bytes).to_vec()).bind(width).bind(height).execute(&mut *tx).await;
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
        json!({"id":saved.last_insert_id().to_string(),"purpose":"avatar","mime_type":mime,"size_bytes":size,"name":name,"url":format!("/api/v1/files/{}/content",saved.last_insert_id()),"state":"staged","expires_at":super::iso(security::now()+86400)}),
    )
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
    let row=sqlx::query("SELECT f.owner_id,CAST(f.storage_key AS CHAR CHARACTER SET utf8mb4) AS storage_key,f.mime_type,f.state,f.expires_at>UTC_TIMESTAMP(6) AS fresh,b.avatar_user_id FROM files f LEFT JOIN file_bindings b ON b.file_id=f.id WHERE f.id=? AND f.purpose='avatar'").bind(file).fetch_optional(&app.pool).await?.ok_or_else(AccountError::missing)?;
    let state = row.get::<String, _>("state");
    if state == "attached" && row.get::<Option<u64>, _>("avatar_user_id").is_some() {
        // An attached avatar is public; an unbound upload never is.
    } else if state == "staged" && row.get::<Option<bool>, _>("fresh") == Some(true) {
        let viewer = authenticate(req, app)
            .await
            .map_err(|_| AccountError::missing())?;
        if viewer.user.id != row.get::<u64, _>("owner_id") {
            return Err(AccountError::missing());
        }
    } else {
        return Err(AccountError::missing());
    }
    let path = storage_path(app, &row.get::<String, _>("storage_key"))?;
    let bytes = tokio::fs::read(path)
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
            "正在使用的头像不能直接删除",
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

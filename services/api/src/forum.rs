use crate::{AppState, access::*, accounts::files, ok, state};
use salvo::prelude::*;
use serde::{Deserialize, Deserializer};
use serde_json::{Value, json};
use sqlx::{MySql, Row, Transaction, mysql::MySqlRow};

const AUTHOR: &str = "JSON_OBJECT('id',CAST(u.id AS CHAR),'nickname',u.nickname,'bio',u.bio,'avatar_url',(SELECT CONCAT('/api/v1/files/',file_id,'/content') FROM file_bindings WHERE avatar_user_id=u.id AND kind='avatar'))";
fn columns() -> String {
    format!(
        "p.id,p.board_id,p.author_id,p.title,p.body_markdown,p.visibility,p.pinned,p.version,DATE_FORMAT(p.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at,DATE_FORMAT(p.updated_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS updated_at,DATE_FORMAT(p.deleted_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS deleted_at,{AUTHOR} AS author,(SELECT COUNT(*) FROM post_likes l WHERE l.post_id=p.id) AS like_count,(SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id AND c.visibility='public' AND c.deleted_at IS NULL) AS comment_count,EXISTS(SELECT 1 FROM post_likes l WHERE l.post_id=p.id AND l.user_id=?) AS liked_by_me,EXISTS(SELECT 1 FROM post_favorites f WHERE f.post_id=p.id AND f.user_id=?) AS saved_by_me,(SELECT JSON_OBJECT('author',JSON_OBJECT('id',CAST(ru.id AS CHAR),'nickname',ru.nickname,'bio',ru.bio,'avatar_url',(SELECT CONCAT('/api/v1/files/',file_id,'/content') FROM file_bindings WHERE avatar_user_id=ru.id AND kind='avatar')),'created_at',DATE_FORMAT(rc.created_at,'%Y-%m-%dT%H:%i:%s.%fZ')) FROM comments rc JOIN users ru ON ru.id=rc.author_id WHERE rc.post_id=p.id AND rc.visibility='public' AND rc.deleted_at IS NULL ORDER BY rc.created_at DESC,rc.id DESC LIMIT 1) AS last_reply"
    )
}

fn base_post(row: &MySqlRow) -> Value {
    json!({"id":row.get::<u64,_>("id").to_string(),"board_id":row.get::<u64,_>("board_id").to_string(),"title":row.get::<String,_>("title"),"author":row.get::<Value,_>("author"),"pinned":row.get::<bool,_>("pinned"),"version":row.get::<u32,_>("version"),"like_count":row.get::<i64,_>("like_count"),"comment_count":row.get::<i64,_>("comment_count"),"liked_by_me":row.get::<bool,_>("liked_by_me"),"saved_by_me":row.get::<bool,_>("saved_by_me"),"created_at":row.get::<String,_>("created_at"),"updated_at":row.get::<String,_>("updated_at")})
}

fn summary(row: &MySqlRow) -> Value {
    let mut v = base_post(row);
    v["excerpt"] = json!(
        row.get::<String, _>("body_markdown")
            .chars()
            .take(300)
            .collect::<String>()
    );
    v["visibility"] = json!(row.get::<String, _>("visibility"));
    v["last_reply"] = row
        .get::<Option<Value>, _>("last_reply")
        .unwrap_or(Value::Null);
    v
}

fn number(req: &Request, name: &'static str, default: u64, max: u64) -> AccountResult<u64> {
    let raw = req.query::<String>(name);
    let value = match raw {
        None => default,
        Some(raw) => raw
            .parse()
            .map_err(|_| AccountError::validation(name, "分页参数不正确"))?,
    };
    if value == 0 || value > max {
        return Err(AccountError::validation(name, "分页参数不正确"));
    }
    Ok(value)
}
fn paging(req: &Request) -> AccountResult<(u64, u64)> {
    Ok((
        number(req, "page", 1, 1_000_000)?,
        number(req, "page_size", 20, 100)?,
    ))
}
fn param(req: &Request, name: &str) -> AccountResult<u64> {
    id(req
        .param::<String>(name)
        .as_deref()
        .ok_or_else(AccountError::missing)?)
}
fn page(items: Vec<Value>, page: u64, size: u64, total: i64) -> Value {
    json!({"items":items,"page":page,"page_size":size,"total":total})
}

pub(crate) async fn can_manage(
    pool: &sqlx::MySqlPool,
    user: &User,
    board: u64,
) -> AccountResult<bool> {
    if user.role == "admin" {
        return Ok(true);
    }
    if user.role != "moderator" {
        return Ok(false);
    }
    Ok(sqlx::query_scalar::<_, i64>(
        "SELECT COUNT(*) FROM board_moderators WHERE user_id=? AND board_id=?",
    )
    .bind(user.id)
    .bind(board)
    .fetch_one(pool)
    .await?
        == 1)
}

pub(crate) async fn management_check(
    tx: &mut Transaction<'_, MySql>,
    user: &User,
    board: u64,
) -> AccountResult<()> {
    if user.role == "admin" {
        return Ok(());
    }
    if user.role == "moderator"
        && sqlx::query(
            "SELECT user_id FROM board_moderators WHERE user_id=? AND board_id=? FOR SHARE",
        )
        .bind(user.id)
        .bind(board)
        .fetch_optional(&mut **tx)
        .await?
        .is_some()
    {
        return Ok(());
    }
    Err(AccountError::forbidden())
}

async fn read_post(app: &AppState, req: &Request, post: u64, mode: &str) -> AccountResult<Value> {
    let identity = optional_identity(req, app).await?;
    let viewer = identity.as_ref().map(|i| i.user.id).unwrap_or(0);
    let sql = format!(
        "SELECT {} FROM posts p JOIN users u ON u.id=p.author_id WHERE p.id=?",
        columns()
    );
    let row = sqlx::query(&sql)
        .bind(viewer)
        .bind(viewer)
        .bind(post)
        .fetch_optional(&app.pool)
        .await?
        .ok_or_else(AccountError::missing)?;
    let deleted = row.get::<Option<String>, _>("deleted_at").is_some();
    match mode {
        "owner" => {
            if deleted || viewer == 0 || viewer != row.get::<u64, _>("author_id") {
                return Err(AccountError::missing());
            }
        }
        "admin" => {
            let identity = identity.as_ref().ok_or_else(AccountError::auth)?;
            if !can_manage(&app.pool, &identity.user, row.get("board_id")).await? {
                return Err(AccountError::forbidden());
            }
        }
        _ => {
            if deleted || row.get::<String, _>("visibility") != "public" {
                return Err(AccountError::missing());
            }
        }
    }
    let mut value = base_post(&row);
    value["body_markdown"] = json!(row.get::<String, _>("body_markdown"));
    let attachments = files::post_files(&app.pool, post).await?;
    value["image_files"] = json!(
        attachments
            .iter()
            .filter(|v| v["purpose"] == "post_image")
            .collect::<Vec<_>>()
    );
    value["pdf_files"] = json!(
        attachments
            .iter()
            .filter(|v| v["purpose"] == "post_pdf")
            .collect::<Vec<_>>()
    );
    if mode != "public" {
        value["visibility"] = json!(row.get::<String, _>("visibility"));
    }
    if mode == "admin" {
        value["deleted_at"] = json!(row.get::<Option<String>, _>("deleted_at"));
    }
    Ok(value)
}

async fn list_posts(req: &Request, app: &AppState, mode: &str) -> AccountResult<Value> {
    let (page_no, size) = paging(req)?;
    let identity = optional_identity(req, app).await?;
    let viewer = identity.as_ref().map(|i| i.user.id).unwrap_or(0);
    if mode != "public" && viewer == 0 {
        return Err(AccountError::auth());
    }
    if mode == "admin"
        && !["admin", "moderator"].contains(&identity.as_ref().unwrap().user.role.as_str())
    {
        return Err(AccountError::forbidden());
    }
    let board = req
        .query::<String>("board_id")
        .map(|s| id(&s))
        .transpose()?;
    let sort = req
        .query::<String>("sort")
        .unwrap_or_else(|| "latest".into());
    if !["latest", "popular"].contains(&sort.as_str()) {
        return Err(AccountError::validation("sort", "排序方式不正确"));
    }
    let mut condition = "p.deleted_at IS NULL".to_owned();
    match mode {
        "mine"=>condition.push_str(" AND p.author_id=?"),
        "admin"=>condition.push_str(" AND (?='admin' OR EXISTS(SELECT 1 FROM board_moderators bm WHERE bm.board_id=p.board_id AND bm.user_id=?))"),
        _=>condition.push_str(" AND p.visibility='public'"),
    }
    if mode == "favorites" {
        condition.push_str(" AND EXISTS(SELECT 1 FROM post_favorites fav WHERE fav.post_id=p.id AND fav.user_id=?)");
    }
    if board.is_some() {
        condition.push_str(" AND p.board_id=?");
    }
    let total_sql = format!("SELECT COUNT(*) FROM posts p WHERE {condition}");
    let order = if sort == "popular" {
        "p.pinned DESC,like_count DESC,comment_count DESC,p.created_at DESC,p.id DESC"
    } else {
        "p.pinned DESC,p.created_at DESC,p.id DESC"
    };
    let sql = format!(
        "SELECT {} FROM posts p JOIN users u ON u.id=p.author_id WHERE {condition} ORDER BY {order} LIMIT ? OFFSET ?",
        columns()
    );
    let mut count = sqlx::query_scalar::<_, i64>(&total_sql);
    let mut query = sqlx::query(&sql).bind(viewer).bind(viewer);
    match mode {
        "mine" | "favorites" => {
            count = count.bind(viewer);
            query = query.bind(viewer);
        }
        "admin" => {
            let role = &identity.as_ref().unwrap().user.role;
            count = count.bind(role).bind(viewer);
            query = query.bind(role).bind(viewer);
        }
        _ => {}
    }
    if let Some(board) = board {
        count = count.bind(board);
        query = query.bind(board);
    }
    let total = count.fetch_one(&app.pool).await?;
    let rows = query
        .bind(size)
        .bind((page_no - 1) * size)
        .fetch_all(&app.pool)
        .await?;
    Ok(page(
        rows.iter().map(summary).collect(),
        page_no,
        size,
        total,
    ))
}

fn some<'de, D: Deserializer<'de>, T: Deserialize<'de>>(d: D) -> Result<Option<T>, D::Error> {
    T::deserialize(d).map(Some)
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct NewPost {
    board_id: String,
    title: String,
    body_markdown: String,
    #[serde(default)]
    image_file_ids: Vec<String>,
    #[serde(default)]
    pdf_file_ids: Vec<String>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct EditPost {
    version: u32,
    #[serde(default, deserialize_with = "some")]
    board_id: Option<String>,
    #[serde(default, deserialize_with = "some")]
    title: Option<String>,
    #[serde(default, deserialize_with = "some")]
    body_markdown: Option<String>,
    #[serde(default, deserialize_with = "some")]
    image_file_ids: Option<Vec<String>>,
    #[serde(default, deserialize_with = "some")]
    pdf_file_ids: Option<Vec<String>>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Version {
    version: u32,
}

async fn board_enabled(tx: &mut Transaction<'_, MySql>, board: u64) -> AccountResult<()> {
    let enabled = sqlx::query_scalar::<_, bool>("SELECT enabled FROM boards WHERE id=? FOR SHARE")
        .bind(board)
        .fetch_optional(&mut **tx)
        .await?;
    if enabled != Some(true) {
        return Err(AccountError::validation("board_id", "板块不存在或已停用"));
    }
    Ok(())
}
async fn locked_post(tx: &mut Transaction<'_, MySql>, post: u64) -> AccountResult<MySqlRow> {
    let row=sqlx::query("SELECT id,author_id,board_id,title,body_markdown,visibility,pinned,version,deleted_at IS NOT NULL AS deleted FROM posts WHERE id=? FOR UPDATE").bind(post).fetch_optional(&mut **tx).await?.ok_or_else(AccountError::missing)?;
    if row.get::<bool, _>("deleted") {
        return Err(AccountError::missing());
    }
    Ok(row)
}
async fn content_change(
    tx: &mut Transaction<'_, MySql>,
    post: u64,
    version: u32,
    operation: &str,
) -> AccountResult<()> {
    crate::content::change(tx, "post", post, version, operation).await
}
fn next_version(version: u32) -> AccountResult<u32> {
    version.checked_add(1).ok_or_else(AccountError::conflict)
}

async fn write_post(req: &mut Request, app: &AppState, post: Option<u64>) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    if let Some(post) = post {
        let input: EditPost = parse(req).await?;
        if input.version == 0
            || (input.board_id.is_none()
                && input.title.is_none()
                && input.body_markdown.is_none()
                && input.image_file_ids.is_none()
                && input.pdf_file_ids.is_none())
        {
            return Err(AccountError::validation(
                "version",
                "请提供版本和需要修改的内容",
            ));
        }
        let title = input
            .title
            .as_deref()
            .map(|s| field_text(s, 2, 100, "title"))
            .transpose()?;
        let body = input
            .body_markdown
            .as_deref()
            .map(|s| field_text(s, 1, 20000, "body_markdown"))
            .transpose()?;
        let new_board = input.board_id.as_deref().map(id).transpose()?;
        let mut tx = app.pool.begin().await?;
        let current = lock_identity(&mut tx, &identity).await?;
        let old = locked_post(&mut tx, post).await?;
        if old.get::<u64, _>("author_id") != current.id {
            return Err(AccountError::forbidden());
        }
        if old.get::<String, _>("visibility") != "public" {
            return Err(AccountError::forbidden());
        }
        if old.get::<u32, _>("version") != input.version {
            return Err(AccountError::conflict());
        }
        let old_board = old.get::<u64, _>("board_id");
        let board = new_board.unwrap_or(old_board);
        if board != old_board {
            board_enabled(&mut tx, board).await?;
        }
        if input.image_file_ids.is_some() || input.pdf_file_ids.is_some() {
            files::bind_post(
                &mut tx,
                current.id,
                post,
                input.image_file_ids.as_deref(),
                input.pdf_file_ids.as_deref(),
            )
            .await?;
        }
        let version = next_version(input.version)?;
        sqlx::query("UPDATE posts SET board_id=?,title=?,body_markdown=?,pinned=?,version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
            .bind(board).bind(title.unwrap_or_else(||old.get("title"))).bind(body.unwrap_or_else(||old.get("body_markdown")))
            .bind(board==old_board&&old.get::<bool,_>("pinned")).bind(version).bind(post).execute(&mut *tx).await?;
        content_change(&mut tx, post, version, "upsert").await?;
        tx.commit().await?;
        read_post(app, req, post, "public").await
    } else {
        let input: NewPost = parse(req).await?;
        let board = id(&input.board_id)?;
        let title = field_text(&input.title, 2, 100, "title")?;
        let body = field_text(&input.body_markdown, 1, 20000, "body_markdown")?;
        let mut tx = app.pool.begin().await?;
        let current = lock_identity(&mut tx, &identity).await?;
        board_enabled(&mut tx, board).await?;
        let saved = sqlx::query(
            "INSERT INTO posts(author_id,board_id,title,body_markdown) VALUES (?,?,?,?)",
        )
        .bind(current.id)
        .bind(board)
        .bind(title)
        .bind(body)
        .execute(&mut *tx)
        .await?;
        let post = saved.last_insert_id();
        files::bind_post(
            &mut tx,
            current.id,
            post,
            Some(&input.image_file_ids),
            Some(&input.pdf_file_ids),
        )
        .await?;
        content_change(&mut tx, post, 1, "upsert").await?;
        tx.commit().await?;
        read_post(app, req, post, "public").await
    }
}

async fn delete_post(req: &mut Request, app: &AppState, post: u64) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input: Version = parse(req).await?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    let old = locked_post(&mut tx, post).await?;
    if old.get::<u64, _>("author_id") != user.id {
        return Err(AccountError::forbidden());
    }
    if old.get::<u32, _>("version") != input.version {
        return Err(AccountError::conflict());
    }
    let version = next_version(input.version)?;
    sqlx::query("UPDATE posts SET deleted_at=UTC_TIMESTAMP(6),updated_at=UTC_TIMESTAMP(6),version=? WHERE id=?").bind(version).bind(post).execute(&mut *tx).await?;
    sqlx::query("UPDATE files f JOIN file_bindings b ON b.file_id=f.id SET f.state='cleanup_pending' WHERE b.post_id=? AND f.state='attached'").bind(post).execute(&mut *tx).await?;
    content_change(&mut tx, post, version, "remove").await?;
    tx.commit().await?;
    Ok(json!({"ok":true}))
}

async fn reaction(
    req: &Request,
    app: &AppState,
    post: u64,
    favorite: bool,
    add: bool,
) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let mut tx = app.pool.begin().await?;
    let current = lock_identity(&mut tx, &identity).await?;
    let row = locked_post(&mut tx, post).await?;
    if row.get::<String, _>("visibility") != "public" {
        return Err(AccountError::missing());
    }
    let table = if favorite {
        "post_favorites"
    } else {
        "post_likes"
    };
    let sql = if add {
        format!(
            "INSERT INTO {table}(post_id,user_id) VALUES (?,?) ON DUPLICATE KEY UPDATE user_id=user_id"
        )
    } else {
        format!("DELETE FROM {table} WHERE post_id=? AND user_id=?")
    };
    sqlx::query(&sql)
        .bind(post)
        .bind(current.id)
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    Ok(json!({"ok":true}))
}

fn comment_json(row: &MySqlRow) -> Value {
    let deleted = row.get::<bool, _>("deleted");
    let hidden = row.get::<String, _>("visibility") != "public";
    let visible = !deleted && !hidden;
    json!({"id":row.get::<u64,_>("id").to_string(),"post_id":row.get::<u64,_>("post_id").to_string(),"parent_id":row.get::<Option<u64>,_>("parent_id").map(|v|v.to_string()),"author":if visible {row.get::<Value,_>("author")}else{Value::Null},"body":if visible {json!(row.get::<String,_>("body"))}else{Value::Null},"state":if deleted {"deleted"}else if hidden {"hidden"}else{"public"},"created_at":row.get::<String,_>("created_at")})
}
fn comment_columns() -> String {
    format!(
        "c.id,c.post_id,c.parent_id,c.body,c.visibility,c.deleted_at IS NOT NULL AS deleted,DATE_FORMAT(c.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at,{AUTHOR} AS author"
    )
}
async fn list_comments(req: &Request, app: &AppState, post: u64) -> AccountResult<Value> {
    let (page_no, size) = paging(req)?;
    let public:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM posts WHERE id=? AND visibility='public' AND deleted_at IS NULL)").bind(post).fetch_one(&app.pool).await?;
    if !public {
        return Err(AccountError::missing());
    }
    let total: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM comments WHERE post_id=?")
        .bind(post)
        .fetch_one(&app.pool)
        .await?;
    let sql = format!(
        "SELECT {} FROM comments c JOIN users u ON u.id=c.author_id WHERE c.post_id=? ORDER BY c.created_at,c.id LIMIT ? OFFSET ?",
        comment_columns()
    );
    let rows = sqlx::query(&sql)
        .bind(post)
        .bind(size)
        .bind((page_no - 1) * size)
        .fetch_all(&app.pool)
        .await?;
    Ok(page(
        rows.iter().map(comment_json).collect(),
        page_no,
        size,
        total,
    ))
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct NewComment {
    body: String,
    parent_id: Option<String>,
}
async fn create_comment(req: &mut Request, app: &AppState, post: u64) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input: NewComment = parse(req).await?;
    let body = field_text(&input.body, 1, 2000, "body")?;
    let parent = input.parent_id.as_deref().map(id).transpose()?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    let row = locked_post(&mut tx, post).await?;
    if row.get::<String, _>("visibility") != "public" {
        return Err(AccountError::missing());
    }
    if let Some(parent) = parent
        && sqlx::query("SELECT id FROM comments WHERE id=? AND post_id=? AND visibility='public' AND deleted_at IS NULL FOR SHARE").bind(parent).bind(post).fetch_optional(&mut *tx).await?.is_none() {return Err(AccountError::validation("parent_id","只能回复同一帖子中可见的评论"));}
    let saved =
        sqlx::query("INSERT INTO comments(post_id,author_id,parent_id,body) VALUES (?,?,?,?)")
            .bind(post)
            .bind(user.id)
            .bind(parent)
            .bind(body)
            .execute(&mut *tx)
            .await?;
    let sql = format!(
        "SELECT {} FROM comments c JOIN users u ON u.id=c.author_id WHERE c.id=?",
        comment_columns()
    );
    let row = sqlx::query(&sql)
        .bind(saved.last_insert_id())
        .fetch_one(&mut *tx)
        .await?;
    let value = comment_json(&row);
    tx.commit().await?;
    Ok(value)
}

async fn comment_action(
    req: &mut Request,
    depot: &Depot,
    app: &AppState,
    comment: u64,
    moderate: bool,
) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input = if moderate {
        Some(parse::<CommentModeration>(req).await?)
    } else {
        None
    };
    let post: u64 = sqlx::query_scalar("SELECT post_id FROM comments WHERE id=?")
        .bind(comment)
        .fetch_optional(&app.pool)
        .await?
        .ok_or_else(AccountError::missing)?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    let parent = locked_post(&mut tx, post).await?;
    let row=sqlx::query("SELECT author_id,visibility,deleted_at IS NOT NULL AS deleted FROM comments WHERE id=? AND post_id=? FOR UPDATE").bind(comment).bind(post).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
    if row.get::<bool, _>("deleted") {
        return if moderate {
            Err(AccountError::missing())
        } else if row.get::<u64, _>("author_id") == user.id {
            Ok(json!({"ok":true}))
        } else {
            Err(AccountError::forbidden())
        };
    }
    if let Some(input) = input {
        management_check(&mut tx, &user, parent.get("board_id")).await?;
        let reason = reason(&input.reason)?;
        let visibility = match input.action.as_str() {
            "hide" => "hidden",
            "restore" => "public",
            _ => return Err(AccountError::validation("action", "评论只支持隐藏或恢复")),
        };
        sqlx::query("UPDATE comments SET visibility=? WHERE id=?")
            .bind(visibility)
            .bind(comment)
            .execute(&mut *tx)
            .await?;
        record_audit(
            &mut tx,
            user.id,
            comment,
            "comment",
            "comment.moderate",
            &reason,
            json!({"visibility":visibility}),
            depot,
        )
        .await?;
    } else {
        if row.get::<u64, _>("author_id") != user.id {
            return Err(AccountError::forbidden());
        }
        sqlx::query("UPDATE comments SET deleted_at=UTC_TIMESTAMP(6) WHERE id=?")
            .bind(comment)
            .execute(&mut *tx)
            .await?;
    }
    tx.commit().await?;
    Ok(json!({"ok":true}))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Moderation {
    action: String,
    version: u32,
    reason: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct CommentModeration {
    action: String,
    reason: String,
}
#[allow(clippy::too_many_arguments)]
async fn record_audit(
    tx: &mut Transaction<'_, MySql>,
    actor: u64,
    target: u64,
    kind: &str,
    action: &str,
    reason: &str,
    changes: Value,
    depot: &Depot,
) -> AccountResult<()> {
    sqlx::query("INSERT INTO audit_logs(actor_id,action,target_type,target_id,reason,safe_changes,request_id) VALUES (?,?,?,?,?,?,?)").bind(actor).bind(action).bind(kind).bind(target).bind(reason).bind(changes).bind(depot.get::<String>("request_id").expect("request id")).execute(&mut **tx).await?;
    Ok(())
}
async fn moderate_post(
    req: &mut Request,
    depot: &Depot,
    app: &AppState,
    post: u64,
) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input: Moderation = parse(req).await?;
    let reason = reason(&input.reason)?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    let row = locked_post(&mut tx, post).await?;
    management_check(&mut tx, &user, row.get("board_id")).await?;
    if row.get::<u32, _>("version") != input.version {
        return Err(AccountError::conflict());
    }
    let mut visibility = row.get::<String, _>("visibility");
    let mut pinned = row.get::<bool, _>("pinned");
    match input.action.as_str() {
        "pin" => pinned = true,
        "unpin" => pinned = false,
        "hide" => visibility = "hidden".into(),
        "restore" => visibility = "public".into(),
        _ => return Err(AccountError::validation("action", "不支持这项管理操作")),
    }
    let version = next_version(input.version)?;
    sqlx::query(
        "UPDATE posts SET visibility=?,pinned=?,version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",
    )
    .bind(&visibility)
    .bind(pinned)
    .bind(version)
    .bind(post)
    .execute(&mut *tx)
    .await?;
    content_change(
        &mut tx,
        post,
        version,
        if visibility == "public" {
            "upsert"
        } else {
            "remove"
        },
    )
    .await?;
    record_audit(
        &mut tx,
        user.id,
        post,
        "post",
        "post.moderate",
        &reason,
        json!({"visibility":visibility,"pinned":pinned,"version":version}),
        depot,
    )
    .await?;
    tx.commit().await?;
    Ok(json!({"ok":true}))
}

async fn action(
    req: &mut Request,
    depot: &Depot,
    app: &AppState,
) -> AccountResult<(StatusCode, Value)> {
    let method = req.method().as_str().to_owned();
    let path = req.uri().path().to_owned();
    if !["GET", "HEAD"].contains(&method.as_str()) {
        csrf_check(req, app)?;
    }
    let mut status = StatusCode::OK;
    let value = match (method.as_str(), path.as_str()) {
        ("GET", "/api/v1/posts") => list_posts(req, app, "public").await?,
        ("POST", "/api/v1/posts") => {
            status = StatusCode::CREATED;
            write_post(req, app, None).await?
        }
        ("GET", "/api/v1/me/posts") => list_posts(req, app, "mine").await?,
        ("GET", "/api/v1/me/favorites") => list_posts(req, app, "favorites").await?,
        ("GET", "/api/v1/admin/posts") => list_posts(req, app, "admin").await?,
        _ if req.param::<String>("comment_id").is_some() => {
            comment_action(
                req,
                depot,
                app,
                param(req, "comment_id")?,
                path.starts_with("/api/v1/admin/"),
            )
            .await?
        }
        _ => {
            let post = param(req, "post_id")?;
            if path.ends_with("/moderation") {
                moderate_post(req, depot, app, post).await?
            } else if path.ends_with("/comments") {
                if method == "GET" {
                    list_comments(req, app, post).await?
                } else {
                    status = StatusCode::CREATED;
                    create_comment(req, app, post).await?
                }
            } else if path.ends_with("/like") || path.ends_with("/favorite") {
                reaction(req, app, post, path.ends_with("/favorite"), method == "PUT").await?
            } else if method == "GET" {
                read_post(
                    app,
                    req,
                    post,
                    if path.starts_with("/api/v1/admin/") {
                        "admin"
                    } else if path.starts_with("/api/v1/me/") {
                        "owner"
                    } else {
                        "public"
                    },
                )
                .await?
            } else if method == "PATCH" {
                write_post(req, app, Some(post)).await?
            } else {
                delete_post(req, app, post).await?
            }
        }
    };
    Ok((status, value))
}
#[handler]
async fn dispatch(req: &mut Request, depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    res.add_header("Cache-Control", "private, no-store", true)
        .ok();
    match action(req, depot, &app).await {
        Ok((status, data)) => ok(res, depot, status, data),
        Err(error) => render_error(error, depot, res),
    }
}
pub fn routes() -> Router {
    Router::with_path("api/v1")
        .push(Router::with_path("posts").get(dispatch).post(dispatch))
        .push(
            Router::with_path("posts/{post_id}")
                .get(dispatch)
                .patch(dispatch)
                .delete(dispatch),
        )
        .push(
            Router::with_path("posts/{post_id}/comments")
                .get(dispatch)
                .post(dispatch),
        )
        .push(
            Router::with_path("posts/{post_id}/like")
                .put(dispatch)
                .delete(dispatch),
        )
        .push(
            Router::with_path("posts/{post_id}/favorite")
                .put(dispatch)
                .delete(dispatch),
        )
        .push(Router::with_path("comments/{comment_id}").delete(dispatch))
        .push(Router::with_path("me/posts").get(dispatch))
        .push(Router::with_path("me/posts/{post_id}").get(dispatch))
        .push(Router::with_path("me/favorites").get(dispatch))
        .push(Router::with_path("admin/posts").get(dispatch))
        .push(Router::with_path("admin/posts/{post_id}").get(dispatch))
        .push(Router::with_path("admin/posts/{post_id}/moderation").patch(dispatch))
        .push(Router::with_path("admin/comments/{comment_id}/moderation").patch(dispatch))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn patch_null_and_forged_fields_are_rejected() {
        for value in [
            json!({"version":1,"title":null}),
            json!({"version":1,"image_file_ids":null}),
            json!({"version":1,"author_id":"2"}),
        ] {
            assert!(serde_json::from_value::<EditPost>(value).is_err());
        }
    }
    #[test]
    fn unicode_and_version_boundaries() {
        assert!(field_text(&"邮".repeat(20000), 1, 20000, "body_markdown").is_ok());
        assert!(field_text(&"邮".repeat(20001), 1, 20000, "body_markdown").is_err());
        assert!(next_version(u32::MAX).is_err());
    }
}

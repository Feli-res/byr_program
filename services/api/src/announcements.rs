use crate::{AppState, access::*, goods::paging, ok, state};
use salvo::prelude::*;
use serde::Deserialize;
use serde_json::{Value, json};
use sqlx::Row;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct NewAnnouncement {
    title: String,
    body_markdown: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct EditAnnouncement {
    action: String,
    version: u32,
    reason: Option<String>,
    title: Option<String>,
    body_markdown: Option<String>,
}

fn text(title: &str, body: &str) -> AccountResult<(String, String)> {
    Ok((
        field_text(title, 2, 100, "title")?,
        field_text(body, 1, 20_000, "body_markdown")?,
    ))
}

async fn public_list(req: &Request, app: &AppState) -> AccountResult<Value> {
    let (page, size) = paging(req)?;
    let total: i64 =
        sqlx::query_scalar("SELECT COUNT(*) FROM announcements WHERE state='published'")
            .fetch_one(&app.pool)
            .await?;
    let rows=sqlx::query("SELECT id,title,LEFT(body_markdown,300) AS excerpt,DATE_FORMAT(published_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS published_at,DATE_FORMAT(created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at FROM announcements WHERE state='published' ORDER BY published_at DESC,id DESC LIMIT ? OFFSET ?")
        .bind(size)
        .bind((page - 1) * size)
        .fetch_all(&app.pool)
        .await?;
    let items: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({"id":r.get::<u64,_>("id").to_string(),"title":r.get::<String,_>("title"),"excerpt":r.get::<String,_>("excerpt"),"published_at":r.get::<Option<String>,_>("published_at"),"created_at":r.get::<String,_>("created_at")})
        })
        .collect();
    Ok(json!({"items":items,"total":total,"page":page,"page_size":size}))
}

async fn public_get(app: &AppState, id: u64) -> AccountResult<Value> {
    let r=sqlx::query("SELECT id,title,body_markdown,DATE_FORMAT(published_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS published_at,DATE_FORMAT(created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at,DATE_FORMAT(updated_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS updated_at FROM announcements WHERE id=? AND state='published'").bind(id).fetch_optional(&app.pool).await?.ok_or_else(AccountError::missing)?;
    Ok(
        json!({"id":r.get::<u64,_>("id").to_string(),"title":r.get::<String,_>("title"),"body_markdown":r.get::<String,_>("body_markdown"),"published_at":r.get::<Option<String>,_>("published_at"),"created_at":r.get::<String,_>("created_at"),"updated_at":r.get::<String,_>("updated_at")}),
    )
}

async fn admin_list(req: &Request, app: &AppState) -> AccountResult<Value> {
    let user = authenticate(req, app).await?.user;
    if user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let (page, size) = paging(req)?;
    let state = req.query::<String>("state").unwrap_or_default();
    if !state.is_empty() && !["draft", "published", "retracted"].contains(&state.as_str()) {
        return Err(AccountError::validation("state", "公告状态不正确"));
    }
    let total: i64 =
        sqlx::query_scalar("SELECT COUNT(*) FROM announcements WHERE (?='' OR state=?)")
            .bind(&state)
            .bind(&state)
            .fetch_one(&app.pool)
            .await?;
    let rows=sqlx::query("SELECT a.id,a.title,LEFT(a.body_markdown,300) AS excerpt,a.state,a.version,DATE_FORMAT(a.published_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS published_at,DATE_FORMAT(a.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at,DATE_FORMAT(a.updated_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS updated_at,u.nickname AS created_by FROM announcements a JOIN users u ON u.id=a.created_by WHERE (?='' OR a.state=?) ORDER BY a.id DESC LIMIT ? OFFSET ?")
        .bind(&state)
        .bind(&state)
        .bind(size)
        .bind((page - 1) * size)
        .fetch_all(&app.pool)
        .await?;
    let items: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({"id":r.get::<u64,_>("id").to_string(),"title":r.get::<String,_>("title"),"excerpt":r.get::<String,_>("excerpt"),"state":r.get::<String,_>("state"),"version":r.get::<u32,_>("version"),"created_by":r.get::<String,_>("created_by"),"published_at":r.get::<Option<String>,_>("published_at"),"created_at":r.get::<String,_>("created_at"),"updated_at":r.get::<String,_>("updated_at")})
        })
        .collect();
    Ok(json!({"items":items,"total":total,"page":page,"page_size":size}))
}

async fn value(app: &AppState, id: u64) -> AccountResult<Value> {
    let r=sqlx::query("SELECT a.id,a.title,a.body_markdown,a.state,a.version,DATE_FORMAT(a.published_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS published_at,DATE_FORMAT(a.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at,DATE_FORMAT(a.updated_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS updated_at,u.nickname AS created_by FROM announcements a JOIN users u ON u.id=a.created_by WHERE a.id=?").bind(id).fetch_optional(&app.pool).await?.ok_or_else(AccountError::missing)?;
    Ok(
        json!({"id":r.get::<u64,_>("id").to_string(),"title":r.get::<String,_>("title"),"body_markdown":r.get::<String,_>("body_markdown"),"state":r.get::<String,_>("state"),"version":r.get::<u32,_>("version"),"created_by":r.get::<String,_>("created_by"),"published_at":r.get::<Option<String>,_>("published_at"),"created_at":r.get::<String,_>("created_at"),"updated_at":r.get::<String,_>("updated_at")}),
    )
}

async fn admin_get(req: &Request, app: &AppState, id: u64) -> AccountResult<Value> {
    let user = authenticate(req, app).await?.user;
    if user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    value(app, id).await
}

async fn create(req: &mut Request, depot: &Depot, app: &AppState) -> AccountResult<Value> {
    csrf_check(req, app)?;
    let identity = authenticate(req, app).await?;
    let input: NewAnnouncement = parse(req).await?;
    let (title, body) = text(&input.title, &input.body_markdown)?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    if user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let saved = sqlx::query(
        "INSERT INTO announcements(title,body_markdown,state,created_by) VALUES (?,?,'draft',?)",
    )
    .bind(&title)
    .bind(&body)
    .bind(user.id)
    .execute(&mut *tx)
    .await?;
    let id = saved.last_insert_id();
    sqlx::query("INSERT INTO audit_logs(actor_id,action,target_type,target_id,reason,safe_changes,request_id) VALUES (?,'announcement.create','announcement',?,?,?,?)")
        .bind(user.id)
        .bind(id)
        .bind("创建公告草稿")
        .bind(json!({"state":"draft"}))
        .bind(depot.get::<String>("request_id").expect("request id"))
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    value(app, id).await
}

async fn update(req: &mut Request, depot: &Depot, app: &AppState, id: u64) -> AccountResult<Value> {
    csrf_check(req, app)?;
    let identity = authenticate(req, app).await?;
    let input: EditAnnouncement = parse(req).await?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    if user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let r = sqlx::query(
        "SELECT title,body_markdown,state,version FROM announcements WHERE id=? FOR UPDATE",
    )
    .bind(id)
    .fetch_optional(&mut *tx)
    .await?
    .ok_or_else(AccountError::missing)?;
    if r.get::<u32, _>("version") != input.version {
        return Err(AccountError::conflict());
    }
    let current_state: String = r.get("state");
    let (next_state, next_version, reason, action) = match input.action.as_str() {
        "save" => {
            if current_state == "published" {
                return Err(AccountError::conflict());
            }
            if input.title.is_none() && input.body_markdown.is_none() {
                return Err(AccountError::validation("title", "请提供需要修改的内容"));
            }
            let title = match input.title {
                Some(value) => field_text(&value, 2, 100, "title")?,
                None => r.get::<String, _>("title"),
            };
            let body = match input.body_markdown {
                Some(value) => field_text(&value, 1, 20_000, "body_markdown")?,
                None => r.get::<String, _>("body_markdown"),
            };
            let version = input
                .version
                .checked_add(1)
                .ok_or_else(AccountError::conflict)?;
            sqlx::query("UPDATE announcements SET title=?,body_markdown=?,version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?").bind(&title).bind(&body).bind(version).bind(id).execute(&mut *tx).await?;
            (
                current_state.clone(),
                version,
                "编辑公告内容".to_owned(),
                "announcement.update",
            )
        }
        "publish" => {
            if current_state == "published" {
                return Err(AccountError::conflict());
            }
            let why = reason(&input.reason.unwrap_or_default())?;
            let version = input
                .version
                .checked_add(1)
                .ok_or_else(AccountError::conflict)?;
            sqlx::query("UPDATE announcements SET state='published',published_at=UTC_TIMESTAMP(6),version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?").bind(version).bind(id).execute(&mut *tx).await?;
            ("published".to_owned(), version, why, "announcement.publish")
        }
        "retract" => {
            if current_state != "published" {
                return Err(AccountError::conflict());
            }
            let why = reason(&input.reason.unwrap_or_default())?;
            let version = input
                .version
                .checked_add(1)
                .ok_or_else(AccountError::conflict)?;
            sqlx::query("UPDATE announcements SET state='retracted',version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?").bind(version).bind(id).execute(&mut *tx).await?;
            ("retracted".to_owned(), version, why, "announcement.retract")
        }
        _ => return Err(AccountError::validation("action", "公告操作不正确")),
    };
    sqlx::query("INSERT INTO audit_logs(actor_id,action,target_type,target_id,reason,safe_changes,request_id) VALUES (?,?, 'announcement',?,?,?,?)")
        .bind(user.id)
        .bind(action)
        .bind(id)
        .bind(&reason)
        .bind(json!({"state":next_state,"version":next_version}))
        .bind(depot.get::<String>("request_id").expect("request id"))
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    value(app, id).await
}

#[handler]
async fn dispatch(req: &mut Request, depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    let path = req.uri().path().to_owned();
    let method = req.method().as_str().to_owned();
    let result = if path == "/api/v1/announcements" {
        match method.as_str() {
            "GET" => public_list(req, &app).await,
            _ => Err(AccountError::missing()),
        }
    } else if path == "/api/v1/admin/announcements" {
        match method.as_str() {
            "GET" => admin_list(req, &app).await,
            "POST" => create(req, depot, &app).await,
            _ => Err(AccountError::missing()),
        }
    } else {
        match req
            .param::<String>("announcement_id")
            .and_then(|x| x.parse::<u64>().ok())
        {
            Some(id) if path.starts_with("/api/v1/admin/announcements/") && method == "GET" => {
                admin_get(req, &app, id).await
            }
            Some(id) if path.starts_with("/api/v1/admin/announcements/") && method == "PATCH" => {
                update(req, depot, &app, id).await
            }
            Some(id) if method == "GET" => public_get(&app, id).await,
            _ => Err(AccountError::missing()),
        }
    };
    res.add_header("Cache-Control", "private, no-store", true)
        .ok();
    match result {
        Ok(v) => {
            let status = if method == "POST" && path == "/api/v1/admin/announcements" {
                StatusCode::CREATED
            } else {
                StatusCode::OK
            };
            ok(res, depot, status, v)
        }
        Err(e) => render_error(e, depot, res),
    }
}

pub fn routes() -> Router {
    Router::with_path("api/v1")
        .push(Router::with_path("announcements").get(dispatch))
        .push(Router::with_path("announcements/{announcement_id}").get(dispatch))
        .push(
            Router::with_path("admin/announcements")
                .get(dispatch)
                .post(dispatch),
        )
        .push(
            Router::with_path("admin/announcements/{announcement_id}")
                .get(dispatch)
                .patch(dispatch),
        )
}

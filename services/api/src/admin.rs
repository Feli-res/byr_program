use crate::{AppState, access::*, goods::paging, ok, state};
use salvo::prelude::*;
use serde::Deserialize;
use serde_json::{Value, json};
use sqlx::Row;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct NewBoard {
    name: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    reason: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct EditBoard {
    version: u32,
    reason: String,
    name: Option<String>,
    description: Option<String>,
    enabled: Option<bool>,
}

async fn list_boards(req: &Request, app: &AppState) -> AccountResult<Value> {
    let user = authenticate(req, app).await?.user;
    if user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let (page, size) = paging(req)?;
    let total: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM boards")
        .fetch_one(&app.pool)
        .await?;
    let rows=sqlx::query("SELECT b.id,b.name,b.description,b.enabled,b.version,(SELECT COUNT(*) FROM posts p WHERE p.board_id=b.id AND p.deleted_at IS NULL) AS post_count FROM boards b ORDER BY b.id LIMIT ? OFFSET ?")
        .bind(size)
        .bind((page - 1) * size)
        .fetch_all(&app.pool)
        .await?;
    let items: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({"id":r.get::<u64,_>("id").to_string(),"name":r.get::<String,_>("name"),"description":r.get::<String,_>("description"),"enabled":r.get::<bool,_>("enabled"),"version":r.get::<u32,_>("version"),"post_count":r.get::<i64,_>("post_count")})
        })
        .collect();
    Ok(json!({"items":items,"total":total,"page":page,"page_size":size}))
}

async fn create_board(req: &mut Request, depot: &Depot, app: &AppState) -> AccountResult<Value> {
    csrf_check(req, app)?;
    let identity = authenticate(req, app).await?;
    let input: NewBoard = parse(req).await?;
    let name = field_text(&input.name, 2, 30, "name")?;
    let description = field_text(&input.description, 0, 300, "description")?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    if user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    if sqlx::query_scalar::<_, u64>("SELECT id FROM boards WHERE name=?")
        .bind(&name)
        .fetch_optional(&mut *tx)
        .await?
        .is_some()
    {
        return Err(AccountError::validation("name", "板块名称已存在"));
    }
    let saved = sqlx::query("INSERT INTO boards(name,description,enabled) VALUES (?,?,TRUE)")
        .bind(&name)
        .bind(&description)
        .execute(&mut *tx)
        .await?;
    let id = saved.last_insert_id();
    let why = if input.reason.trim().is_empty() {
        "创建板块".to_owned()
    } else {
        reason(&input.reason)?
    };
    sqlx::query("INSERT INTO audit_logs(actor_id,action,target_type,target_id,reason,safe_changes,request_id) VALUES (?,'board.create','board',?,?,?,?)")
        .bind(user.id)
        .bind(id)
        .bind(&why)
        .bind(json!({"name":name,"enabled":true}))
        .bind(depot.get::<String>("request_id").expect("request id"))
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    Ok(
        json!({"id":id.to_string(),"name":name,"description":description,"enabled":true,"version":1}),
    )
}

async fn update_board(
    req: &mut Request,
    depot: &Depot,
    app: &AppState,
    id: u64,
) -> AccountResult<Value> {
    csrf_check(req, app)?;
    let identity = authenticate(req, app).await?;
    let input: EditBoard = parse(req).await?;
    let why = reason(&input.reason)?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    if user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let r =
        sqlx::query("SELECT name,description,enabled,version FROM boards WHERE id=? FOR UPDATE")
            .bind(id)
            .fetch_optional(&mut *tx)
            .await?
            .ok_or_else(AccountError::missing)?;
    if r.get::<u32, _>("version") != input.version {
        return Err(AccountError::conflict());
    }
    let name = match input.name {
        Some(value) => field_text(&value, 2, 30, "name")?,
        None => r.get::<String, _>("name"),
    };
    let description = match input.description {
        Some(value) => field_text(&value, 0, 300, "description")?,
        None => r.get::<String, _>("description"),
    };
    let enabled = input.enabled.unwrap_or(r.get::<bool, _>("enabled"));
    if sqlx::query_scalar::<_, u64>("SELECT id FROM boards WHERE name=? AND id<>?")
        .bind(&name)
        .bind(id)
        .fetch_optional(&mut *tx)
        .await?
        .is_some()
    {
        return Err(AccountError::validation("name", "板块名称已存在"));
    }
    let version = input
        .version
        .checked_add(1)
        .ok_or_else(AccountError::conflict)?;
    sqlx::query("UPDATE boards SET name=?,description=?,enabled=?,version=? WHERE id=?")
        .bind(&name)
        .bind(&description)
        .bind(enabled)
        .bind(version)
        .bind(id)
        .execute(&mut *tx)
        .await?;
    let was_enabled: bool = r.get("enabled");
    let action = if was_enabled != enabled {
        if enabled {
            "board.enable"
        } else {
            "board.disable"
        }
    } else {
        "board.update"
    };
    sqlx::query("INSERT INTO audit_logs(actor_id,action,target_type,target_id,reason,safe_changes,request_id) VALUES (?,?,'board',?,?,?,?)")
        .bind(user.id)
        .bind(action)
        .bind(id)
        .bind(&why)
        .bind(json!({"name":name,"enabled":enabled,"version":version}))
        .bind(depot.get::<String>("request_id").expect("request id"))
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    Ok(
        json!({"id":id.to_string(),"name":name,"description":description,"enabled":enabled,"version":version}),
    )
}

async fn audit_logs(req: &Request, app: &AppState) -> AccountResult<Value> {
    let user = authenticate(req, app).await?.user;
    if user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let (page, size) = paging(req)?;
    let target_type = req.query::<String>("target_type").unwrap_or_default();
    let action = req.query::<String>("action").unwrap_or_default();
    if target_type.chars().count() > 40 || action.chars().count() > 64 {
        return Err(AccountError::validation("target_type", "筛选条件过长"));
    }
    let total: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM audit_logs WHERE (?='' OR target_type=?) AND (?='' OR action=?)",
    )
    .bind(&target_type)
    .bind(&target_type)
    .bind(&action)
    .bind(&action)
    .fetch_one(&app.pool)
    .await?;
    let rows=sqlx::query("SELECT a.id,a.actor_id,u.nickname,a.action,a.target_type,a.target_id,a.reason,a.safe_changes,DATE_FORMAT(a.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at FROM audit_logs a JOIN users u ON u.id=a.actor_id WHERE (?='' OR a.target_type=?) AND (?='' OR a.action=?) ORDER BY a.id DESC LIMIT ? OFFSET ?")
        .bind(&target_type)
        .bind(&target_type)
        .bind(&action)
        .bind(&action)
        .bind(size)
        .bind((page - 1) * size)
        .fetch_all(&app.pool)
        .await?;
    let items: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({"id":r.get::<u64,_>("id").to_string(),"actor":{"id":r.get::<u64,_>("actor_id").to_string(),"nickname":r.get::<String,_>("nickname")},"action":r.get::<String,_>("action"),"target_type":r.get::<String,_>("target_type"),"target_id":r.get::<Option<u64>,_>("target_id").map(|v|v.to_string()),"reason":r.get::<String,_>("reason"),"changes":r.get::<Value,_>("safe_changes"),"created_at":r.get::<String,_>("created_at")})
        })
        .collect();
    Ok(json!({"items":items,"total":total,"page":page,"page_size":size}))
}

#[handler]
async fn dispatch(req: &mut Request, depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    let path = req.uri().path().to_owned();
    let method = req.method().as_str().to_owned();
    let result = if path == "/api/v1/admin/boards" {
        match method.as_str() {
            "GET" => list_boards(req, &app).await,
            "POST" => create_board(req, depot, &app).await,
            _ => Err(AccountError::missing()),
        }
    } else if path == "/api/v1/admin/audit-logs" {
        match method.as_str() {
            "GET" => audit_logs(req, &app).await,
            _ => Err(AccountError::missing()),
        }
    } else {
        match req
            .param::<String>("board_id")
            .and_then(|x| x.parse::<u64>().ok())
        {
            Some(id) if method == "PATCH" => update_board(req, depot, &app, id).await,
            _ => Err(AccountError::missing()),
        }
    };
    res.add_header("Cache-Control", "private, no-store", true)
        .ok();
    match result {
        Ok(v) => {
            let status = if method == "POST" && path == "/api/v1/admin/boards" {
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
    Router::with_path("api/v1/admin")
        .push(
            Router::with_path("boards")
                .get(dispatch)
                .post(dispatch)
                .push(Router::with_path("{board_id}").patch(dispatch)),
        )
        .push(Router::with_path("audit-logs").get(dispatch))
}

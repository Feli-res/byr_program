use crate::{AppState, access::*, chat::notifications, content, forum, goods::paging, ok, state};
use salvo::prelude::*;
use serde::Deserialize;
use serde_json::{Value, json};
use sqlx::Row;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct NewReport {
    post_id: String,
    reason: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Decision {
    action: String,
    reason: String,
    version: u32,
    post_version: u32,
}

async fn submit(req: &mut Request, app: &AppState) -> AccountResult<Value> {
    csrf_check(req, app)?;
    let identity = authenticate(req, app).await?;
    let input: NewReport = parse(req).await?;
    let post = id(&input.post_id)?;
    let why = field_text(&input.reason, 1, 1000, "reason")?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    let row=sqlx::query("SELECT board_id,author_id,title,body_markdown,version,visibility,deleted_at IS NOT NULL AS deleted FROM posts WHERE id=? FOR UPDATE").bind(post).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
    if row.get::<String, _>("visibility") != "public" || row.get::<bool, _>("deleted") {
        return Err(AccountError::missing());
    }
    if let Some(existing)=sqlx::query_scalar::<_,u64>("SELECT id FROM reports WHERE reporter_id=? AND target_type='post' AND post_id=? AND state='pending' LIMIT 1").bind(user.id).bind(post).fetch_optional(&mut *tx).await? {tx.commit().await?;return Ok(json!({"id":existing.to_string(),"already_exists":true}));}
    let files = sqlx::query("SELECT file_id,CAST(kind AS CHAR CHARACTER SET utf8mb4) AS kind FROM file_bindings WHERE post_id=? ORDER BY kind,position_no").bind(post).fetch_all(&mut *tx).await?;
    let attachments: Vec<Value> = files.iter().map(|f| json!({"id":f.get::<u64,_>("file_id").to_string(),"kind":f.get::<String,_>("kind")})).collect();
    let captured_at: String =
        sqlx::query_scalar("SELECT DATE_FORMAT(UTC_TIMESTAMP(6),'%Y-%m-%dT%H:%i:%s.%fZ')")
            .fetch_one(&mut *tx)
            .await?;
    let context = json!({"post_id":post.to_string(),"version":row.get::<u32,_>("version"),"board_id":row.get::<u64,_>("board_id").to_string(),"title":row.get::<String,_>("title"),"body":row.get::<String,_>("body_markdown"),"attachments":attachments,"captured_at":captured_at});
    let result=sqlx::query("INSERT INTO reports(reporter_id,target_type,post_id,reason,necessary_context) VALUES (?,'post',?,?,?)").bind(user.id).bind(post).bind(why).bind(context).execute(&mut *tx).await?;
    let report = result.last_insert_id();
    sqlx::query("INSERT INTO report_ai_jobs(report_id,post_version) VALUES (?,?)")
        .bind(report)
        .bind(row.get::<u32, _>("version"))
        .execute(&mut *tx)
        .await?;
    let admins=sqlx::query_scalar::<_,u64>("SELECT id FROM users WHERE role='admin' AND status='active' AND password_reset_required=0 ORDER BY id").fetch_all(&mut *tx).await?;
    for admin in admins {
        notifications::create(
            &mut tx,
            admin,
            "system",
            "none",
            None,
            "有新的帖子举报，请在举报处理页面查看。",
            None,
        )
        .await?;
    }
    tx.commit().await?;
    Ok(json!({"id":report.to_string(),"already_exists":false}))
}

async fn list(req: &Request, app: &AppState, admin: bool) -> AccountResult<Value> {
    let who = authenticate(req, app).await?.user;
    let (page, size) = paging(req)?;
    if admin && !["admin", "moderator"].contains(&who.role.as_str()) {
        return Err(AccountError::forbidden());
    }
    let rows = if admin {
        sqlx::query("SELECT r.id,r.post_id,r.reason,r.state,r.version,r.resolution,DATE_FORMAT(r.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at,DATE_FORMAT(r.resolved_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS resolved_at,p.title,p.board_id,p.version AS post_version FROM reports r JOIN posts p ON p.id=r.post_id WHERE r.target_type='post' AND (?='admin' OR EXISTS(SELECT 1 FROM board_moderators m WHERE m.board_id=p.board_id AND m.user_id=?)) ORDER BY r.id DESC LIMIT ? OFFSET ?").bind(&who.role).bind(who.id).bind(size).bind((page-1)*size).fetch_all(&app.pool).await?
    } else {
        sqlx::query("SELECT r.id,r.post_id,r.reason,r.state,r.version,r.resolution,DATE_FORMAT(r.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at,DATE_FORMAT(r.resolved_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS resolved_at,CAST(JSON_UNQUOTE(JSON_EXTRACT(r.necessary_context,'$.title')) AS CHAR CHARACTER SET utf8mb4) AS title,p.board_id,p.version AS post_version FROM reports r JOIN posts p ON p.id=r.post_id WHERE r.target_type='post' AND r.reporter_id=? ORDER BY r.id DESC LIMIT ? OFFSET ?").bind(who.id).bind(size).bind((page-1)*size).fetch_all(&app.pool).await?
    };
    let total: i64 = if admin {
        sqlx::query_scalar("SELECT COUNT(*) FROM reports r JOIN posts p ON p.id=r.post_id WHERE r.target_type='post' AND (?='admin' OR EXISTS(SELECT 1 FROM board_moderators m WHERE m.board_id=p.board_id AND m.user_id=?))").bind(&who.role).bind(who.id).fetch_one(&app.pool).await?
    } else {
        sqlx::query_scalar(
            "SELECT COUNT(*) FROM reports WHERE target_type='post' AND reporter_id=?",
        )
        .bind(who.id)
        .fetch_one(&app.pool)
        .await?
    };
    let items:Vec<Value>=rows.iter().map(|r|json!({"id":r.get::<u64,_>("id").to_string(),"target_type":"post","target_id":r.get::<u64,_>("post_id").to_string(),"post_title":r.get::<String,_>("title"),"reason":r.get::<String,_>("reason"),"state":r.get::<String,_>("state"),"version":r.get::<u32,_>("version"),"resolution":r.get::<Option<String>,_>("resolution"),"created_at":r.get::<String,_>("created_at"),"resolved_at":r.get::<Option<String>,_>("resolved_at")})).collect();
    Ok(json!({"items":items,"total":total,"page":page,"page_size":size}))
}

async fn detail(req: &Request, app: &AppState, rid: u64) -> AccountResult<Value> {
    let user = authenticate(req, app).await?.user;
    let r=sqlx::query("SELECT r.post_id,r.reporter_id,r.reason,r.necessary_context,r.state,r.resolution,r.version,p.board_id,p.title,p.body_markdown,p.version AS post_version,p.visibility,p.deleted_at IS NOT NULL AS deleted FROM reports r JOIN posts p ON p.id=r.post_id WHERE r.id=? AND r.target_type='post'").bind(rid).fetch_optional(&app.pool).await?.ok_or_else(AccountError::missing)?;
    let manage = forum::can_manage(&app.pool, &user, r.get("board_id")).await?;
    if !manage && user.id != r.get::<u64, _>("reporter_id") {
        return Err(AccountError::missing());
    }
    let mut value = json!({"id":rid.to_string(),"post_id":r.get::<u64,_>("post_id").to_string(),"state":r.get::<String,_>("state"),"reason":r.get::<String,_>("reason"),"resolution":r.get::<Option<String>,_>("resolution"),"version":r.get::<u32,_>("version")});
    if manage {
        if let Some(job) =
            sqlx::query("SELECT state,result,post_version FROM report_ai_jobs WHERE report_id=?")
                .bind(rid)
                .fetch_optional(&app.pool)
                .await?
        {
            let stale = job.get::<u32, _>("post_version") != r.get::<u32, _>("post_version");
            let state = job.get::<String, _>("state");
            let state =
                if state == "pending" && std::env::var("AI_ENABLED").as_deref() != Ok("true") {
                    "disabled"
                } else {
                    state.as_str()
                };
            value["ai"] =
                json!({"state":state,"result":job.get::<Option<Value>,_>("result"),"stale":stale});
        }
        value["snapshot"] = r.get::<Value, _>("necessary_context");
        value["current"] = json!({"title":r.get::<String,_>("title"),"body":r.get::<String,_>("body_markdown"),"version":r.get::<u32,_>("post_version"),"visibility":r.get::<String,_>("visibility"),"deleted":r.get::<bool,_>("deleted")});
    }
    Ok(value)
}

async fn decide(
    req: &mut Request,
    depot: &Depot,
    app: &AppState,
    rid: u64,
) -> AccountResult<Value> {
    csrf_check(req, app)?;
    let identity = authenticate(req, app).await?;
    let input: Decision = parse(req).await?;
    let reason = field_text(&input.reason, 1, 1000, "reason")?;
    if !["hide", "keep", "dismiss"].contains(&input.action.as_str()) {
        return Err(AccountError::validation("action", "处理方式不正确"));
    }
    let mut tx = app.pool.begin().await?;
    let actor = lock_identity(&mut tx, &identity).await?;
    let r=sqlx::query("SELECT post_id,reporter_id,state,version FROM reports WHERE id=? AND target_type='post' FOR UPDATE").bind(rid).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
    let post: u64 = r.get("post_id");
    let reporter: u64 = r.get("reporter_id");
    let p=sqlx::query("SELECT board_id,author_id,version,visibility,deleted_at IS NOT NULL AS deleted FROM posts WHERE id=? FOR UPDATE").bind(post).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
    forum::management_check(&mut tx, &actor, p.get("board_id")).await?;
    if r.get::<u32, _>("version") != input.version
        || p.get::<u32, _>("version") != input.post_version
        || r.get::<String, _>("state") != "pending"
    {
        return Err(AccountError::conflict());
    }
    let mut hidden = false;
    if input.action == "hide"
        && !p.get::<bool, _>("deleted")
        && p.get::<String, _>("visibility") == "public"
    {
        let version = input
            .post_version
            .checked_add(1)
            .ok_or_else(AccountError::unavailable)?;
        sqlx::query(
            "UPDATE posts SET visibility='hidden',version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",
        )
        .bind(version)
        .bind(post)
        .execute(&mut *tx)
        .await?;
        content::change(&mut tx, "post", post, version, "remove").await?;
        hidden = true;
    }
    let state = if input.action == "dismiss" {
        "dismissed"
    } else {
        "resolved"
    };
    sqlx::query("UPDATE reports SET state=?,resolution=?,resolved_by=?,resolved_at=UTC_TIMESTAMP(6),version=version+1 WHERE id=?").bind(state).bind(&reason).bind(actor.id).bind(rid).execute(&mut *tx).await?;
    sqlx::query("INSERT INTO audit_logs(actor_id,action,target_type,target_id,reason,safe_changes,request_id) VALUES (?,'report.resolve','report',?,?,?,?)").bind(actor.id).bind(rid).bind(&reason).bind(json!({"state":state,"post_hidden":hidden})).bind(depot.get::<String>("request_id").expect("request id")).execute(&mut *tx).await?;
    notifications::create(
        &mut tx,
        reporter,
        "report_result",
        "report",
        Some(rid),
        "你的帖子举报已处理。",
        None,
    )
    .await?;
    if hidden {
        notifications::create(
            &mut tx,
            p.get("author_id"),
            "system",
            "none",
            None,
            "你的帖子已被管理员隐藏，请在我的帖子查看。",
            None,
        )
        .await?;
    }
    tx.commit().await?;
    Ok(json!({"state":state,"post_hidden":hidden}))
}

#[handler]
async fn dispatch(req: &mut Request, depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    let path = req.uri().path().to_owned();
    let method = req.method().as_str().to_owned();
    let result = match (method.as_str(), path.as_str()) {
        ("POST", "/api/v1/post-reports") => submit(req, &app).await,
        ("GET", "/api/v1/me/reports") => list(req, &app, false).await,
        ("GET", "/api/v1/admin/reports") => list(req, &app, true).await,
        _ => match req
            .param::<String>("report_id")
            .and_then(|x| x.parse::<u64>().ok())
        {
            Some(rid) if method == "GET" => detail(req, &app, rid).await,
            Some(rid) if method == "PATCH" => decide(req, depot, &app, rid).await,
            _ => Err(AccountError::missing()),
        },
    };
    res.add_header("Cache-Control", "private, no-store", true)
        .ok();
    match result {
        Ok(v) => ok(res, depot, StatusCode::OK, v),
        Err(e) => render_error(e, depot, res),
    }
}
pub fn routes() -> Router {
    Router::with_path("api/v1")
        .push(Router::with_path("post-reports").post(dispatch))
        .push(Router::with_path("me/reports").get(dispatch))
        .push(Router::with_path("admin/reports").get(dispatch))
        .push(
            Router::with_path("reports/{report_id}")
                .get(dispatch)
                .patch(dispatch),
        )
}

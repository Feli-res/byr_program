use crate::{AppState, access::*, chat::notifications, content, forum, goods::paging, ok, state};
use salvo::prelude::*;
use serde::Deserialize;
use serde_json::{Value, json};
use sqlx::{MySql, QueryBuilder, Row, Transaction};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct NewReport {
    target_type: String,
    target_id: String,
    reason: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct NewPostReport {
    post_id: String,
    reason: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Decision {
    action: String,
    reason: String,
    version: u32,
    target_version: Option<u32>,
    post_version: Option<u32>,
}

const KINDS: [&str; 4] = ["post", "comment", "goods", "message"];

fn kind_name(kind: &str) -> &'static str {
    match kind {
        "post" => "帖子",
        "comment" => "评论",
        "goods" => "商品",
        _ => "私信",
    }
}

async fn captured(tx: &mut Transaction<'_, MySql>) -> AccountResult<String> {
    Ok(
        sqlx::query_scalar("SELECT DATE_FORMAT(UTC_TIMESTAMP(6),'%Y-%m-%dT%H:%i:%s.%fZ')")
            .fetch_one(&mut **tx)
            .await?,
    )
}

async fn pending(
    tx: &mut Transaction<'_, MySql>,
    reporter: u64,
    kind: &str,
    target: u64,
) -> AccountResult<Option<u64>> {
    let sql = match kind {
        "post" => {
            "SELECT id FROM reports WHERE reporter_id=? AND target_type='post' AND post_id=? AND state='pending' LIMIT 1"
        }
        "comment" => {
            "SELECT id FROM reports WHERE reporter_id=? AND target_type='comment' AND comment_id=? AND state='pending' LIMIT 1"
        }
        "goods" => {
            "SELECT id FROM reports WHERE reporter_id=? AND target_type='goods' AND goods_id=? AND state='pending' LIMIT 1"
        }
        _ => {
            "SELECT id FROM reports WHERE reporter_id=? AND target_type='message' AND message_id=? AND state='pending' LIMIT 1"
        }
    };
    Ok(sqlx::query_scalar::<_, u64>(sql)
        .bind(reporter)
        .bind(target)
        .fetch_optional(&mut **tx)
        .await?)
}

async fn notify_managers(
    tx: &mut Transaction<'_, MySql>,
    kind: &str,
    board: Option<u64>,
    reporter: u64,
) -> AccountResult<()> {
    let mut ids = sqlx::query_scalar::<_, u64>(
        "SELECT id FROM users WHERE role='admin' AND status='active' AND password_reset_required=0",
    )
    .fetch_all(&mut **tx)
    .await?;
    if let Some(board) = board {
        ids.extend(
            sqlx::query_scalar::<_, u64>("SELECT user_id FROM board_moderators WHERE board_id=?")
                .bind(board)
                .fetch_all(&mut **tx)
                .await?,
        );
    }
    ids.sort_unstable();
    ids.dedup();
    let summary = format!("有新的{}举报，请在举报处理页面查看。", kind_name(kind));
    for id in ids.into_iter().filter(|id| *id != reporter) {
        notifications::create(tx, id, "system", "none", None, &summary, None).await?;
    }
    Ok(())
}

async fn submit(req: &mut Request, app: &AppState, forced: Option<&str>) -> AccountResult<Value> {
    csrf_check(req, app)?;
    let identity = authenticate(req, app).await?;
    let (kind, target, why) = match forced {
        Some("post") => {
            let input: NewPostReport = parse(req).await?;
            (
                "post".to_owned(),
                id(&input.post_id)?,
                field_text(&input.reason, 1, 1000, "reason")?,
            )
        }
        _ => {
            let input: NewReport = parse(req).await?;
            if !KINDS.contains(&input.target_type.as_str()) {
                return Err(AccountError::validation("target_type", "举报类型不正确"));
            }
            (
                input.target_type,
                id(&input.target_id)?,
                field_text(&input.reason, 1, 1000, "reason")?,
            )
        }
    };
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    if let Some(existing) = pending(&mut tx, user.id, &kind, target).await? {
        tx.commit().await?;
        return Ok(json!({"id":existing.to_string(),"already_exists":true}));
    }
    let at = captured(&mut tx).await?;
    let (context, board, ai_version) = match kind.as_str() {
        "post" => {
            let row=sqlx::query("SELECT board_id,author_id,title,body_markdown,version,visibility,deleted_at IS NOT NULL AS deleted FROM posts WHERE id=? FOR UPDATE").bind(target).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
            if row.get::<bool, _>("deleted") || row.get::<String, _>("visibility") != "public" {
                return Err(AccountError::missing());
            }
            let files = sqlx::query("SELECT file_id,CAST(kind AS CHAR CHARACTER SET utf8mb4) AS kind FROM file_bindings WHERE post_id=? ORDER BY kind,position_no").bind(target).fetch_all(&mut *tx).await?;
            let attachments: Vec<Value> = files.iter().map(|f| json!({"id":f.get::<u64,_>("file_id").to_string(),"kind":f.get::<String,_>("kind")})).collect();
            let version = row.get::<u32, _>("version");
            (
                json!({"post_id":target.to_string(),"version":version,"board_id":row.get::<u64,_>("board_id").to_string(),"title":row.get::<String,_>("title"),"body":row.get::<String,_>("body_markdown"),"attachments":attachments,"captured_at":at}),
                Some(row.get::<u64, _>("board_id")),
                Some(version),
            )
        }
        "comment" => {
            let row=sqlx::query("SELECT c.post_id,c.author_id,c.body,c.visibility,c.deleted_at IS NOT NULL AS deleted,c.parent_id,p.title AS post_title,p.board_id,p.visibility AS post_visibility,p.deleted_at IS NOT NULL AS post_deleted FROM comments c JOIN posts p ON p.id=c.post_id WHERE c.id=? FOR UPDATE").bind(target).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
            if row.get::<bool, _>("deleted")
                || row.get::<String, _>("visibility") != "public"
                || row.get::<bool, _>("post_deleted")
                || row.get::<String, _>("post_visibility") != "public"
            {
                return Err(AccountError::missing());
            }
            let parent: Option<String> = match row.get::<Option<u64>, _>("parent_id") {
                Some(parent) => sqlx::query_scalar::<_, String>(
                    "SELECT body FROM comments WHERE id=? AND visibility='public' AND deleted_at IS NULL",
                )
                .bind(parent)
                .fetch_optional(&mut *tx)
                .await?,
                None => None,
            };
            let board = row.get::<u64, _>("board_id");
            (
                json!({"comment_id":target.to_string(),"post_id":row.get::<u64,_>("post_id").to_string(),"post_title":row.get::<String,_>("post_title"),"board_id":board.to_string(),"comment_body":row.get::<String,_>("body"),"parent_body":parent,"author_id":row.get::<u64,_>("author_id").to_string(),"captured_at":at}),
                Some(board),
                None,
            )
        }
        "goods" => {
            let row=sqlx::query("SELECT seller_id,title,description,price_cents,CAST(campus_code AS CHAR CHARACTER SET utf8mb4) AS campus_code,condition_code,state,moderation,version,deleted_at IS NOT NULL AS deleted FROM goods WHERE id=? FOR UPDATE").bind(target).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
            if row.get::<bool, _>("deleted") || row.get::<String, _>("moderation") != "clear" {
                return Err(AccountError::missing());
            }
            let images = sqlx::query_scalar::<_, u64>(
                "SELECT file_id FROM file_bindings WHERE goods_id=? ORDER BY position_no",
            )
            .bind(target)
            .fetch_all(&mut *tx)
            .await?;
            (
                json!({"goods_id":target.to_string(),"seller_id":row.get::<u64,_>("seller_id").to_string(),"title":row.get::<String,_>("title"),"description":row.get::<String,_>("description"),"price_cents":row.get::<u32,_>("price_cents"),"campus_code":row.get::<String,_>("campus_code"),"condition_code":row.get::<String,_>("condition_code"),"state":row.get::<String,_>("state"),"images":images.iter().map(|id|id.to_string()).collect::<Vec<_>>(),"captured_at":at}),
                None,
                None,
            )
        }
        _ => {
            let row=sqlx::query("SELECT m.id,m.conversation_id,m.sender_id,m.sequence_no,m.body,c.user_low_id,c.user_high_id FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.id=? FOR UPDATE").bind(target).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
            let sender: u64 = row.get("sender_id");
            let low: u64 = row.get("user_low_id");
            let high: u64 = row.get("user_high_id");
            if user.id != low && user.id != high {
                return Err(AccountError::missing());
            }
            if sender == user.id {
                return Err(AccountError::forbidden());
            }
            let conversation: u64 = row.get("conversation_id");
            let sequence: u64 = row.get("sequence_no");
            let rows=sqlx::query("SELECT id,sequence_no,sender_id,body,DATE_FORMAT(created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at FROM messages WHERE conversation_id=? AND sequence_no<=? ORDER BY sequence_no DESC LIMIT 5").bind(conversation).bind(sequence).fetch_all(&mut *tx).await?;
            let mut messages: Vec<Value> = rows
                .iter()
                .map(|m| {
                    json!({"id":m.get::<u64,_>("id").to_string(),"sequence":m.get::<u64,_>("sequence_no").to_string(),"mine":m.get::<u64,_>("sender_id")==user.id,"body":m.get::<String,_>("body"),"created_at":m.get::<String,_>("created_at")})
                })
                .collect();
            messages.reverse();
            (
                json!({"message_id":target.to_string(),"messages":messages,"captured_at":at}),
                None,
                None,
            )
        }
    };
    let saved = match kind.as_str() {
        "post" => sqlx::query("INSERT INTO reports(reporter_id,target_type,post_id,reason,necessary_context) VALUES (?,'post',?,?,?)").bind(user.id).bind(target).bind(&why).bind(&context).execute(&mut *tx).await?,
        "comment" => sqlx::query("INSERT INTO reports(reporter_id,target_type,comment_id,reason,necessary_context) VALUES (?,'comment',?,?,?)").bind(user.id).bind(target).bind(&why).bind(&context).execute(&mut *tx).await?,
        "goods" => sqlx::query("INSERT INTO reports(reporter_id,target_type,goods_id,reason,necessary_context) VALUES (?,'goods',?,?,?)").bind(user.id).bind(target).bind(&why).bind(&context).execute(&mut *tx).await?,
        _ => sqlx::query("INSERT INTO reports(reporter_id,target_type,message_id,reason,necessary_context) VALUES (?,'message',?,?,?)").bind(user.id).bind(target).bind(&why).bind(&context).execute(&mut *tx).await?,
    };
    let report = saved.last_insert_id();
    if let Some(version) = ai_version {
        sqlx::query("INSERT INTO report_ai_jobs(report_id,post_version) VALUES (?,?)")
            .bind(report)
            .bind(version)
            .execute(&mut *tx)
            .await?;
    }
    notify_managers(&mut tx, &kind, board, user.id).await?;
    tx.commit().await?;
    Ok(json!({"id":report.to_string(),"already_exists":false}))
}

fn filters(
    q: &mut QueryBuilder<'_, MySql>,
    scope: &str,
    viewer: u64,
    target_type: &str,
    state: &str,
    board: u64,
) {
    if scope == "mine" {
        q.push(" AND r.reporter_id=").push_bind(viewer);
    } else if scope == "moderator" {
        q.push(" AND r.target_type IN ('post','comment') AND EXISTS(SELECT 1 FROM board_moderators m WHERE m.user_id=")
            .push_bind(viewer)
            .push(" AND m.board_id=COALESCE(p.board_id,cp.board_id))");
    }
    if !target_type.is_empty() {
        q.push(" AND r.target_type=")
            .push_bind(target_type.to_owned());
    }
    if !state.is_empty() {
        q.push(" AND r.state=").push_bind(state.to_owned());
    }
    if board != 0 {
        q.push(" AND COALESCE(p.board_id,cp.board_id)=")
            .push_bind(board);
    }
}

async fn list(req: &Request, app: &AppState, admin: bool) -> AccountResult<Value> {
    let who = authenticate(req, app).await?.user;
    let (page, size) = paging(req)?;
    if admin && !["admin", "moderator"].contains(&who.role.as_str()) {
        return Err(AccountError::forbidden());
    }
    let target_type = req.query::<String>("target_type").unwrap_or_default();
    if !target_type.is_empty() && !KINDS.contains(&target_type.as_str()) {
        return Err(AccountError::validation("target_type", "举报类型不正确"));
    }
    let state = req.query::<String>("state").unwrap_or_default();
    if !state.is_empty() && !["pending", "resolved", "dismissed"].contains(&state.as_str()) {
        return Err(AccountError::validation("state", "举报状态不正确"));
    }
    let board = match req.query::<String>("board_id") {
        None => 0,
        Some(raw) => id(&raw)?,
    };
    let scope = if !admin {
        "mine"
    } else if who.role == "admin" {
        "all"
    } else {
        "moderator"
    };
    let joins = " FROM reports r LEFT JOIN posts p ON p.id=r.post_id LEFT JOIN comments c ON c.id=r.comment_id LEFT JOIN posts cp ON cp.id=c.post_id LEFT JOIN goods g ON g.id=r.goods_id JOIN users u ON u.id=r.reporter_id WHERE 1=1";
    let mut count = QueryBuilder::<MySql>::new(format!("SELECT COUNT(*){joins}"));
    filters(&mut count, scope, who.id, &target_type, &state, board);
    let total: i64 = count.build_query_scalar().fetch_one(&app.pool).await?;
    let mut query = QueryBuilder::<MySql>::new(format!(
        "SELECT r.id,r.target_type,r.reason,r.state,r.version,r.resolution,DATE_FORMAT(r.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at,DATE_FORMAT(r.resolved_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS resolved_at,COALESCE(p.title,cp.title,g.title) AS target_title,COALESCE(p.board_id,cp.board_id) AS board_id,CAST(COALESCE(r.post_id,r.comment_id,r.goods_id,r.message_id) AS CHAR) AS target_id,u.nickname AS reporter_nickname{joins}"
    ));
    filters(&mut query, scope, who.id, &target_type, &state, board);
    query
        .push(" ORDER BY r.id DESC LIMIT ")
        .push_bind(size)
        .push(" OFFSET ")
        .push_bind((page - 1) * size);
    let rows = query.build().fetch_all(&app.pool).await?;
    let items: Vec<Value> = rows
        .iter()
        .map(|r| {
            json!({
                "id":r.get::<u64,_>("id").to_string(),
                "target_type":r.get::<String,_>("target_type"),
                "target_id":r.get::<String,_>("target_id"),
                "target_title":r.get::<Option<String>,_>("target_title"),
                "reporter_nickname":r.get::<String,_>("reporter_nickname"),
                "reason":r.get::<String,_>("reason"),
                "state":r.get::<String,_>("state"),
                "version":r.get::<u32,_>("version"),
                "resolution":r.get::<Option<String>,_>("resolution"),
                "created_at":r.get::<String,_>("created_at"),
                "resolved_at":r.get::<Option<String>,_>("resolved_at"),
            })
        })
        .collect();
    Ok(json!({"items":items,"total":total,"page":page,"page_size":size}))
}

async fn detail(req: &Request, app: &AppState, rid: u64) -> AccountResult<Value> {
    let user = authenticate(req, app).await?.user;
    let r=sqlx::query("SELECT r.id,r.reporter_id,r.target_type,r.post_id,r.comment_id,r.goods_id,r.message_id,r.reason,r.necessary_context,r.state,r.resolution,r.version,DATE_FORMAT(r.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at,DATE_FORMAT(r.resolved_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS resolved_at,u.nickname AS reporter_nickname FROM reports r JOIN users u ON u.id=r.reporter_id WHERE r.id=?").bind(rid).fetch_optional(&app.pool).await?.ok_or_else(AccountError::missing)?;
    let kind: String = r.get("target_type");
    let board: Option<u64> = match kind.as_str() {
        "post" => {
            sqlx::query_scalar("SELECT board_id FROM posts WHERE id=?")
                .bind(r.get::<Option<u64>, _>("post_id"))
                .fetch_optional(&app.pool)
                .await?
        }
        "comment" => {
            sqlx::query_scalar(
                "SELECT p.board_id FROM comments c JOIN posts p ON p.id=c.post_id WHERE c.id=?",
            )
            .bind(r.get::<Option<u64>, _>("comment_id"))
            .fetch_optional(&app.pool)
            .await?
        }
        _ => None,
    };
    let manage = match kind.as_str() {
        "post" | "comment" => match board {
            Some(board) => forum::can_manage(&app.pool, &user, board).await?,
            None => false,
        },
        _ => user.role == "admin",
    };
    if !manage && user.id != r.get::<u64, _>("reporter_id") {
        return Err(AccountError::missing());
    }
    let mut value = json!({
        "id":rid.to_string(),
        "target_type":kind,
        "target_id":match kind.as_str() {
            "post" => r.get::<Option<u64>,_>("post_id"),
            "comment" => r.get::<Option<u64>,_>("comment_id"),
            "goods" => r.get::<Option<u64>,_>("goods_id"),
            _ => r.get::<Option<u64>,_>("message_id"),
        }.map(|v|v.to_string()),
        "state":r.get::<String,_>("state"),
        "reason":r.get::<String,_>("reason"),
        "resolution":r.get::<Option<String>,_>("resolution"),
        "version":r.get::<u32,_>("version"),
        "created_at":r.get::<String,_>("created_at"),
        "resolved_at":r.get::<Option<String>,_>("resolved_at"),
    });
    if manage {
        value["reporter"] = json!({"id":r.get::<u64,_>("reporter_id").to_string(),"nickname":r.get::<String,_>("reporter_nickname")});
        value["snapshot"] = r.get::<Value, _>("necessary_context");
        value["current"] = match kind.as_str() {
            "post" => match sqlx::query("SELECT title,body_markdown,version,visibility,deleted_at IS NOT NULL AS deleted FROM posts WHERE id=?").bind(r.get::<Option<u64>,_>("post_id")).fetch_optional(&app.pool).await? {
                Some(p) => json!({"title":p.get::<String,_>("title"),"body":p.get::<String,_>("body_markdown"),"version":p.get::<u32,_>("version"),"visibility":p.get::<String,_>("visibility"),"deleted":p.get::<bool,_>("deleted")}),
                None => Value::Null,
            },
            "comment" => match sqlx::query("SELECT c.body,c.visibility,c.deleted_at IS NOT NULL AS deleted,c.post_id,p.title AS post_title,p.visibility AS post_visibility,p.deleted_at IS NOT NULL AS post_deleted,p.version AS post_version FROM comments c JOIN posts p ON p.id=c.post_id WHERE c.id=?").bind(r.get::<Option<u64>,_>("comment_id")).fetch_optional(&app.pool).await? {
                Some(c) => json!({"body":c.get::<String,_>("body"),"visibility":c.get::<String,_>("visibility"),"deleted":c.get::<bool,_>("deleted"),"post_id":c.get::<u64,_>("post_id").to_string(),"post_title":c.get::<String,_>("post_title"),"post_visibility":c.get::<String,_>("post_visibility"),"post_deleted":c.get::<bool,_>("post_deleted"),"post_version":c.get::<u32,_>("post_version")}),
                None => Value::Null,
            },
            "goods" => match sqlx::query("SELECT title,description,price_cents,state,moderation,version,deleted_at IS NOT NULL AS deleted FROM goods WHERE id=?").bind(r.get::<Option<u64>,_>("goods_id")).fetch_optional(&app.pool).await? {
                Some(g) => json!({"title":g.get::<String,_>("title"),"description":g.get::<String,_>("description"),"price_cents":g.get::<u32,_>("price_cents"),"state":g.get::<String,_>("state"),"moderation":g.get::<String,_>("moderation"),"version":g.get::<u32,_>("version"),"deleted":g.get::<bool,_>("deleted")}),
                None => Value::Null,
            },
            _ => Value::Null,
        };
        if kind == "post" {
            let post_version = value["current"]["version"].as_u64().unwrap_or(0) as u32;
            if let Some(job) = sqlx::query(
                "SELECT state,result,post_version FROM report_ai_jobs WHERE report_id=?",
            )
            .bind(rid)
            .fetch_optional(&app.pool)
            .await?
            {
                let stale = job.get::<u32, _>("post_version") != post_version;
                let state = job.get::<String, _>("state");
                let state =
                    if state == "pending" && std::env::var("AI_ENABLED").as_deref() != Ok("true") {
                        "disabled"
                    } else {
                        state.as_str()
                    };
                value["ai"] = json!({"state":state,"result":job.get::<Option<Value>,_>("result"),"stale":stale});
            }
        } else {
            value["ai"] = json!({"state":"not_applicable"});
        }
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
    let why = field_text(&input.reason, 1, 1000, "reason")?;
    let mut tx = app.pool.begin().await?;
    let actor = lock_identity(&mut tx, &identity).await?;
    let r=sqlx::query("SELECT target_type,post_id,comment_id,goods_id,message_id,reporter_id,state,version FROM reports WHERE id=? FOR UPDATE").bind(rid).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
    if r.get::<u32, _>("version") != input.version || r.get::<String, _>("state") != "pending" {
        return Err(AccountError::conflict());
    }
    let kind: String = r.get("target_type");
    let reporter: u64 = r.get("reporter_id");
    let expected = input.target_version.or(input.post_version);
    let mut hidden = false;
    let mut restricted = false;
    let mut affected: Option<u64> = None;
    match kind.as_str() {
        "post" => {
            let post: u64 = r.get("post_id");
            let p=sqlx::query("SELECT board_id,author_id,version,visibility,deleted_at IS NOT NULL AS deleted FROM posts WHERE id=? FOR UPDATE").bind(post).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
            forum::management_check(&mut tx, &actor, p.get("board_id")).await?;
            let expected = expected
                .ok_or_else(|| AccountError::validation("target_version", "请提供帖子版本"))?;
            if p.get::<u32, _>("version") != expected {
                return Err(AccountError::conflict());
            }
            match input.action.as_str() {
                "hide" => {
                    if p.get::<bool, _>("deleted") {
                        return Err(AccountError::conflict());
                    }
                    if p.get::<String, _>("visibility") == "public" {
                        let version = expected.checked_add(1).ok_or_else(AccountError::conflict)?;
                        sqlx::query("UPDATE posts SET visibility='hidden',version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?").bind(version).bind(post).execute(&mut *tx).await?;
                        content::change(&mut tx, "post", post, version, "remove").await?;
                        hidden = true;
                    }
                }
                "keep" | "dismiss" => {}
                _ => {
                    return Err(AccountError::validation(
                        "action",
                        "帖子举报只支持隐藏、保留或不成立",
                    ));
                }
            }
            affected = Some(p.get::<u64, _>("author_id"));
        }
        "comment" => {
            let comment: u64 = r.get("comment_id");
            let c=sqlx::query("SELECT c.post_id,c.author_id,c.visibility,c.deleted_at IS NOT NULL AS deleted,p.board_id FROM comments c JOIN posts p ON p.id=c.post_id WHERE c.id=? FOR UPDATE").bind(comment).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
            forum::management_check(&mut tx, &actor, c.get("board_id")).await?;
            match input.action.as_str() {
                "hide" => {
                    if c.get::<bool, _>("deleted") {
                        return Err(AccountError::conflict());
                    }
                    if c.get::<String, _>("visibility") == "public" {
                        sqlx::query("UPDATE comments SET visibility='hidden' WHERE id=?")
                            .bind(comment)
                            .execute(&mut *tx)
                            .await?;
                        hidden = true;
                    }
                }
                "keep" | "dismiss" => {}
                _ => {
                    return Err(AccountError::validation(
                        "action",
                        "评论举报只支持隐藏、保留或不成立",
                    ));
                }
            }
            affected = Some(c.get::<u64, _>("author_id"));
        }
        "goods" => {
            if actor.role != "admin" {
                return Err(AccountError::forbidden());
            }
            let goods: u64 = r.get("goods_id");
            let g=sqlx::query("SELECT seller_id,state,moderation,version,deleted_at IS NOT NULL AS deleted FROM goods WHERE id=? FOR UPDATE").bind(goods).fetch_optional(&mut *tx).await?.ok_or_else(AccountError::missing)?;
            let expected = expected
                .ok_or_else(|| AccountError::validation("target_version", "请提供商品版本"))?;
            if g.get::<u32, _>("version") != expected {
                return Err(AccountError::conflict());
            }
            match input.action.as_str() {
                "restrict" => {
                    if g.get::<bool, _>("deleted") {
                        return Err(AccountError::conflict());
                    }
                    if g.get::<String, _>("moderation") == "clear" {
                        let state = if g.get::<String, _>("state") == "sold" {
                            "sold".to_owned()
                        } else {
                            "off_shelf".to_owned()
                        };
                        let version = expected.checked_add(1).ok_or_else(AccountError::conflict)?;
                        sqlx::query("UPDATE goods SET moderation='restricted',state=?,version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?").bind(&state).bind(version).bind(goods).execute(&mut *tx).await?;
                        content::change(&mut tx, "goods", goods, version, "remove").await?;
                        restricted = true;
                    }
                }
                "keep" | "dismiss" => {}
                _ => {
                    return Err(AccountError::validation(
                        "action",
                        "商品举报只支持下架、保留或不成立",
                    ));
                }
            }
            affected = Some(g.get::<u64, _>("seller_id"));
        }
        "message" => {
            if actor.role != "admin" {
                return Err(AccountError::forbidden());
            }
            match input.action.as_str() {
                "uphold" | "keep" | "dismiss" => {}
                _ => {
                    return Err(AccountError::validation(
                        "action",
                        "私信举报只支持成立或不成立",
                    ));
                }
            }
        }
        _ => return Err(AccountError::missing()),
    }
    let state = if input.action == "dismiss" {
        "dismissed"
    } else {
        "resolved"
    };
    sqlx::query("UPDATE reports SET state=?,resolution=?,resolved_by=?,resolved_at=UTC_TIMESTAMP(6),version=version+1 WHERE id=?").bind(state).bind(&why).bind(actor.id).bind(rid).execute(&mut *tx).await?;
    sqlx::query("INSERT INTO audit_logs(actor_id,action,target_type,target_id,reason,safe_changes,request_id) VALUES (?,'report.resolve','report',?,?,?,?)")
        .bind(actor.id)
        .bind(rid)
        .bind(&why)
        .bind(json!({"target_type":kind,"action":input.action,"hidden":hidden,"restricted":restricted}))
        .bind(depot.get::<String>("request_id").expect("request id"))
        .execute(&mut *tx)
        .await?;
    notifications::create(
        &mut tx,
        reporter,
        "report_result",
        "report",
        Some(rid),
        "你的举报已处理，可在“我的举报”查看结果。",
        None,
    )
    .await?;
    if let Some(author) = affected {
        if hidden && kind == "comment" {
            notifications::create(
                &mut tx,
                author,
                "system",
                "none",
                None,
                "你的评论已被管理员隐藏，请在我的帖子查看。",
                None,
            )
            .await?;
        } else if hidden && kind == "post" {
            notifications::create(
                &mut tx,
                author,
                "system",
                "none",
                None,
                "你的帖子已被管理员隐藏，请在我的帖子查看。",
                None,
            )
            .await?;
        } else if restricted && kind == "goods" {
            notifications::create(
                &mut tx,
                author,
                "system",
                "none",
                None,
                "你的商品已被管理员下架，请在我的商品查看。",
                None,
            )
            .await?;
        }
    }
    tx.commit().await?;
    Ok(json!({"state":state,"hidden":hidden,"restricted":restricted}))
}

#[handler]
async fn dispatch(req: &mut Request, depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    let path = req.uri().path().to_owned();
    let method = req.method().as_str().to_owned();
    let result = match (method.as_str(), path.as_str()) {
        ("POST", "/api/v1/reports") => submit(req, &app, None).await,
        ("POST", "/api/v1/post-reports") => submit(req, &app, Some("post")).await,
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
        Ok(v) => {
            let status = if method == "POST" && path == "/api/v1/reports" {
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
        .push(Router::with_path("reports").post(dispatch))
        .push(Router::with_path("post-reports").post(dispatch))
        .push(Router::with_path("me/reports").get(dispatch))
        .push(Router::with_path("me/reports/{report_id}").get(dispatch))
        .push(Router::with_path("admin/reports").get(dispatch))
        .push(
            Router::with_path("reports/{report_id}")
                .get(dispatch)
                .patch(dispatch),
        )
}

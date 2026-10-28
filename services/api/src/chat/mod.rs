pub(crate) mod notifications;
pub(crate) mod realtime;
use crate::{AppState, access::*, accounts, goods, ok, state};
use salvo::prelude::*;
use serde::Deserialize;
use serde_json::{Value, json};
use sqlx::{MySql, Row, Transaction, mysql::MySqlRow};
use std::sync::Arc;

const MESSAGE_COLUMNS: &str = "m.id,m.conversation_id,m.sequence_no,m.sender_id,CAST(m.client_message_id AS CHAR CHARACTER SET utf8mb4) AS client_message_id,m.body,DATE_FORMAT(m.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at";
pub(crate) fn message(row: &MySqlRow) -> Value {
    json!({"id":row.get::<u64,_>("id").to_string(),"conversation_id":row.get::<u64,_>("conversation_id").to_string(),"sequence":row.get::<u64,_>("sequence_no").to_string(),"sender_id":row.get::<u64,_>("sender_id").to_string(),"client_message_id":row.get::<String,_>("client_message_id"),"body":row.get::<String,_>("body"),"created_at":row.get::<String,_>("created_at")})
}
pub(crate) fn sequence(raw: &str) -> AccountResult<u64> {
    if raw.is_empty() || raw.len() > 20 || !raw.bytes().all(|b| b.is_ascii_digit()) {
        return Err(AccountError::validation(
            "sequence",
            "消息位置须为非负整数字符串",
        ));
    }
    raw.parse()
        .map_err(|_| AccountError::validation("sequence", "消息位置超出范围"))
}
pub(crate) fn uuid(raw: &str) -> AccountResult<String> {
    let parsed = uuid::Uuid::parse_str(raw)
        .map_err(|_| AccountError::validation("client_message_id", "消息标识须为 UUID"))?;
    if raw.len() != 36 {
        return Err(AccountError::validation(
            "client_message_id",
            "消息标识须为 UUID",
        ));
    }
    Ok(parsed.to_string())
}
fn param(req: &Request, name: &str) -> AccountResult<u64> {
    id(req
        .param::<String>(name)
        .as_deref()
        .ok_or_else(AccountError::missing)?)
}
async fn conversation_row(
    pool: &sqlx::MySqlPool,
    cid: u64,
    viewer: u64,
) -> AccountResult<MySqlRow> {
    sqlx::query("SELECT id,user_low_id,user_high_id,last_sequence,context_goods_id,DATE_FORMAT(updated_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS updated_at FROM conversations WHERE id=? AND (user_low_id=? OR user_high_id=?)").bind(cid).bind(viewer).bind(viewer).fetch_optional(pool).await?.ok_or_else(AccountError::missing)
}
pub(crate) async fn message_for(app: &AppState, mid: u64, viewer: u64) -> AccountResult<Value> {
    let sql = format!(
        "SELECT {MESSAGE_COLUMNS} FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.id=? AND (c.user_low_id=? OR c.user_high_id=?)"
    );
    let row = sqlx::query(&sql)
        .bind(mid)
        .bind(viewer)
        .bind(viewer)
        .fetch_optional(&app.pool)
        .await?
        .ok_or_else(AccountError::missing)?;
    Ok(message(&row))
}
async fn conversation(app: &AppState, cid: u64, viewer: u64) -> AccountResult<Value> {
    let row = conversation_row(&app.pool, cid, viewer).await?;
    let peer = if row.get::<u64, _>("user_low_id") == viewer {
        row.get::<u64, _>("user_high_id")
    } else {
        row.get("user_low_id")
    };
    let user = accounts::user(&app.pool, peer).await?;
    let peer = accounts::public_user(&app.pool, &user).await?;
    let read:u64=sqlx::query_scalar("SELECT CAST(COALESCE((SELECT last_read_sequence FROM conversation_reads WHERE conversation_id=? AND user_id=?),0) AS UNSIGNED)").bind(cid).bind(viewer).fetch_one(&app.pool).await?;
    let unread: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM messages WHERE conversation_id=? AND sender_id<>? AND sequence_no>?",
    )
    .bind(cid)
    .bind(viewer)
    .bind(read)
    .fetch_one(&app.pool)
    .await?;
    let last = sqlx::query_scalar::<_, u64>(
        "SELECT id FROM messages WHERE conversation_id=? ORDER BY sequence_no DESC LIMIT 1",
    )
    .bind(cid)
    .fetch_optional(&app.pool)
    .await?;
    let last = if let Some(mid) = last {
        message_for(app, mid, viewer).await?
    } else {
        Value::Null
    };
    let context = if let Some(gid) = row.get::<Option<u64>, _>("context_goods_id") {
        goods::context(app, gid, viewer).await?
    } else {
        None
    };
    Ok(
        json!({"id":cid.to_string(),"peer":peer,"last_message":last,"last_sequence":row.get::<u64,_>("last_sequence").to_string(),"last_read_sequence":read.to_string(),"unread_count":unread,"context_goods":context,"updated_at":row.get::<String,_>("updated_at")}),
    )
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Open {
    goods_id: String,
}
async fn lock_users(
    tx: &mut Transaction<'_, MySql>,
    identity: &Identity,
    low: u64,
    high: u64,
) -> AccountResult<()> {
    let a = accounts::locked_user(tx, low).await?;
    let b = accounts::locked_user(tx, high).await?;
    lock_identity(tx, identity).await?;
    let peer = if a.id == identity.user.id { b } else { a };
    if peer.status != "active" || peer.password_reset_required {
        return Err(AccountError::new(
            StatusCode::CONFLICT,
            "PEER_UNAVAILABLE",
            "对方暂时不可联系",
        ));
    }
    Ok(())
}
async fn open(req: &mut Request, app: &AppState) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input: Open = parse(req).await?;
    let gid = id(&input.goods_id)?;
    let seller: u64 = sqlx::query_scalar(
        "SELECT seller_id FROM goods WHERE id=? AND deleted_at IS NULL AND moderation='clear'",
    )
    .bind(gid)
    .fetch_optional(&app.pool)
    .await?
    .ok_or_else(AccountError::missing)?;
    if seller == identity.user.id {
        return Err(AccountError::validation("goods_id", "不能联系自己"));
    }
    let low = seller.min(identity.user.id);
    let high = seller.max(identity.user.id);
    let mut tx = app.pool.begin().await?;
    lock_users(&mut tx, &identity, low, high).await?;
    if sqlx::query("SELECT id FROM goods WHERE id=? AND seller_id=? AND deleted_at IS NULL AND moderation='clear' FOR SHARE").bind(gid).bind(seller).fetch_optional(&mut *tx).await?.is_none(){return Err(AccountError::missing());}
    let saved=sqlx::query("INSERT INTO conversations(user_low_id,user_high_id,context_goods_id) VALUES (?,?,?) ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)").bind(low).bind(high).bind(gid).execute(&mut *tx).await?;
    let cid = saved.last_insert_id();
    for uid in [low, high] {
        sqlx::query("INSERT IGNORE INTO conversation_reads(conversation_id,user_id) VALUES (?,?)")
            .bind(cid)
            .bind(uid)
            .execute(&mut *tx)
            .await?;
    }
    tx.commit().await?;
    conversation(app, cid, identity.user.id).await
}
async fn list(req: &Request, app: &AppState, identity: &Identity) -> AccountResult<Value> {
    let (page, size) = goods::paging(req)?;
    let viewer = identity.user.id;
    let total: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM conversations WHERE user_low_id=? OR user_high_id=?",
    )
    .bind(viewer)
    .bind(viewer)
    .fetch_one(&app.pool)
    .await?;
    let ids=sqlx::query_scalar::<_,u64>("SELECT id FROM conversations WHERE user_low_id=? OR user_high_id=? ORDER BY updated_at DESC,id DESC LIMIT ? OFFSET ?").bind(viewer).bind(viewer).bind(size).bind((page-1)*size).fetch_all(&app.pool).await?;
    let mut items = Vec::new();
    for cid in ids {
        items.push(conversation(app, cid, viewer).await?);
    }
    Ok(json!({"items":items,"page":page,"page_size":size,"total":total}))
}
async fn history(
    req: &Request,
    app: &AppState,
    identity: &Identity,
    cid: u64,
) -> AccountResult<Value> {
    conversation_row(&app.pool, cid, identity.user.id).await?;
    let after = req
        .query::<String>("after_sequence")
        .map(|v| sequence(&v))
        .transpose()?;
    let before = req
        .query::<String>("before_sequence")
        .map(|v| sequence(&v))
        .transpose()?;
    if after.is_some() && before.is_some() {
        return Err(AccountError::validation(
            "after_sequence",
            "前后消息位置不能同时填写",
        ));
    }
    let limit = goods::integer(req, "limit", 20, 1, 100)?;
    let sql = format!(
        "SELECT {MESSAGE_COLUMNS} FROM messages m WHERE m.conversation_id=? AND m.sequence_no {} ? ORDER BY m.sequence_no {} LIMIT ?",
        if after.is_some() { ">" } else { "<" },
        if after.is_some() { "ASC" } else { "DESC" }
    );
    let cursor = after.or(before).unwrap_or(u64::MAX);
    let mut rows = sqlx::query(&sql)
        .bind(cid)
        .bind(cursor)
        .bind(limit + 1)
        .fetch_all(&app.pool)
        .await?;
    let more = rows.len() > limit as usize;
    rows.truncate(limit as usize);
    if after.is_none() {
        rows.reverse();
    }
    let next_after = rows
        .last()
        .map(|r| r.get::<u64, _>("sequence_no"))
        .unwrap_or(after.unwrap_or(0));
    let next_before = if after.is_none() && more {
        rows.first()
            .map(|r| r.get::<u64, _>("sequence_no").to_string())
    } else {
        None
    };
    Ok(
        json!({"items":rows.iter().map(message).collect::<Vec<_>>(),"next_after_sequence":next_after.to_string(),"next_before_sequence":next_before,"has_more":more}),
    )
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct MessageWrite {
    pub client_message_id: String,
    pub body: String,
}
pub(crate) async fn enqueue(
    tx: &mut Transaction<'_, MySql>,
    recipient: u64,
    kind: &str,
    source: u64,
    reference: Value,
) -> AccountResult<()> {
    sqlx::query("INSERT INTO outbox_events(recipient_id,event_type,source_id,safe_reference,next_due_at) VALUES (?,?,?,?,UTC_TIMESTAMP(6)) ON DUPLICATE KEY UPDATE safe_reference=VALUES(safe_reference),state='pending',attempts=0,next_due_at=UTC_TIMESTAMP(6)").bind(recipient).bind(kind).bind(source).bind(reference).execute(&mut **tx).await?;
    Ok(())
}
pub(crate) async fn send_message(
    app: &AppState,
    identity: &Identity,
    cid: u64,
    input: MessageWrite,
) -> AccountResult<(Value, bool)> {
    let client_id = uuid(&input.client_message_id)?;
    let body = field_text(&input.body, 1, 2000, "body")?;
    let row = conversation_row(&app.pool, cid, identity.user.id).await?;
    let low = row.get::<u64, _>("user_low_id");
    let high = row.get::<u64, _>("user_high_id");
    let mut tx = app.pool.begin().await?;
    lock_users(&mut tx, identity, low, high).await?;
    let sequence: u64 =
        sqlx::query_scalar("SELECT last_sequence FROM conversations WHERE id=? FOR UPDATE")
            .bind(cid)
            .fetch_one(&mut *tx)
            .await?;
    let existing=sqlx::query("SELECT id,body_hash FROM messages WHERE conversation_id=? AND sender_id=? AND client_message_id=?").bind(cid).bind(identity.user.id).bind(&client_id).fetch_optional(&mut *tx).await?;
    if let Some(existing) = existing {
        if existing.get::<Vec<u8>, _>("body_hash") != accounts::security::digest(&body) {
            return Err(AccountError::new(
                StatusCode::CONFLICT,
                "MESSAGE_CONFLICT",
                "同一发送标识不能用于不同正文",
            ));
        }
        let mid = existing.get::<u64, _>("id");
        tx.commit().await?;
        return Ok((message_for(app, mid, identity.user.id).await?, false));
    }
    let next = sequence
        .checked_add(1)
        .ok_or_else(AccountError::unavailable)?;
    let saved=sqlx::query("INSERT INTO messages(conversation_id,sequence_no,sender_id,client_message_id,body,body_hash) VALUES (?,?,?,?,?,?)").bind(cid).bind(next).bind(identity.user.id).bind(client_id).bind(body.clone()).bind(accounts::security::digest(&body)).execute(&mut *tx).await?;
    let mid = saved.last_insert_id();
    sqlx::query("UPDATE conversations SET last_sequence=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
        .bind(next)
        .bind(cid)
        .execute(&mut *tx)
        .await?;
    for uid in [low, high] {
        enqueue(
            &mut tx,
            uid,
            "message.created",
            mid,
            json!({"conversation_id":cid.to_string()}),
        )
        .await?;
    }
    let sql = format!("SELECT {MESSAGE_COLUMNS} FROM messages m WHERE m.id=?");
    let row = sqlx::query(&sql).bind(mid).fetch_one(&mut *tx).await?;
    let result = message(&row);
    tx.commit().await?;
    Ok((result, true))
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Read {
    through_sequence: String,
}
pub(crate) async fn mark_read(
    app: &AppState,
    identity: &Identity,
    cid: u64,
    through: u64,
) -> AccountResult<()> {
    let row = conversation_row(&app.pool, cid, identity.user.id).await?;
    let mut tx = app.pool.begin().await?;
    lock_identity(&mut tx, identity).await?;
    let last: u64 =
        sqlx::query_scalar("SELECT last_sequence FROM conversations WHERE id=? FOR UPDATE")
            .bind(cid)
            .fetch_one(&mut *tx)
            .await?;
    if through > last {
        return Err(AccountError::validation(
            "through_sequence",
            "已读位置不能超过实际消息",
        ));
    }
    sqlx::query("INSERT INTO conversation_reads(conversation_id,user_id,last_read_sequence) VALUES (?,?,?) ON DUPLICATE KEY UPDATE last_read_sequence=GREATEST(last_read_sequence,VALUES(last_read_sequence)),updated_at=UTC_TIMESTAMP(6)").bind(cid).bind(identity.user.id).bind(through).execute(&mut *tx).await?;
    for uid in [row.get::<u64, _>("user_low_id"), row.get("user_high_id")] {
        enqueue(
            &mut tx,
            uid,
            "conversation.read",
            cid,
            json!({"reader_id":identity.user.id.to_string()}),
        )
        .await?;
    }
    tx.commit().await?;
    Ok(())
}
async fn action(req: &mut Request, app: &AppState) -> AccountResult<(StatusCode, Value)> {
    let method = req.method().as_str().to_owned();
    let path = req.uri().path().to_owned();
    if method != "GET" {
        csrf_check(req, app)?;
    }
    if method == "POST" && path == "/api/v1/conversations" {
        return Ok((StatusCode::OK, open(req, app).await?));
    }
    let identity = authenticate(req, app).await?;
    let result = match (method.as_str(), path.as_str()) {
        ("GET", "/api/v1/conversations") => list(req, app, &identity).await?,
        ("POST", "/api/v1/ws-tickets") => realtime::ticket(app, &identity).await?,
        ("GET", "/api/v1/notifications") => notifications::list(req, app, &identity).await?,
        ("PUT", "/api/v1/notifications/read-all") => {
            notifications::read(app, &identity, None).await?;
            json!({"ok":true})
        }
        _ if req.param::<String>("notification_id").is_some() => {
            notifications::read(app, &identity, Some(param(req, "notification_id")?)).await?;
            json!({"ok":true})
        }
        _ => {
            let cid = param(req, "conversation_id")?;
            if path.ends_with("/messages") && method == "GET" {
                history(req, app, &identity, cid).await?
            } else if path.ends_with("/messages") {
                let input = parse(req).await?;
                let (message, created) = send_message(app, &identity, cid, input).await?;
                return Ok((
                    if created {
                        StatusCode::CREATED
                    } else {
                        StatusCode::OK
                    },
                    message,
                ));
            } else if path.ends_with("/read") {
                let input: Read = parse(req).await?;
                mark_read(app, &identity, cid, sequence(&input.through_sequence)?).await?;
                json!({"ok":true})
            } else {
                conversation(app, cid, identity.user.id).await?
            }
        }
    };
    Ok((StatusCode::OK, result))
}
#[handler]
async fn dispatch(req: &mut Request, depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    match action(req, &app).await {
        Ok((status, value)) => ok(res, depot, status, value),
        Err(error) => render_error(error, depot, res),
    }
}
pub fn routes() -> Router {
    Router::with_path("api/v1")
        .push(
            Router::with_path("conversations")
                .get(dispatch)
                .post(dispatch),
        )
        .push(Router::with_path("conversations/{conversation_id}").get(dispatch))
        .push(
            Router::with_path("conversations/{conversation_id}/messages")
                .get(dispatch)
                .post(dispatch),
        )
        .push(Router::with_path("conversations/{conversation_id}/read").put(dispatch))
        .push(Router::with_path("notifications").get(dispatch))
        .push(Router::with_path("notifications/read-all").put(dispatch))
        .push(Router::with_path("notifications/{notification_id}/read").put(dispatch))
        .push(Router::with_path("ws-tickets").post(dispatch))
        .push(Router::with_path("ws").get(realtime::upgrade))
}

pub fn start_workers(app: AppState) {
    let app = Arc::new(app);
    tokio::spawn(realtime::outbox_worker(app));
}
pub async fn seed_verification_notification(app: &AppState, input: &str) -> anyhow::Result<()> {
    anyhow::ensure!(
        std::env::var("CHAT_TEST_FIXTURES").as_deref() == Ok("1"),
        "test fixtures are disabled"
    );
    let database: String = sqlx::query_scalar("SELECT DATABASE()")
        .fetch_one(&app.pool)
        .await?;
    anyhow::ensure!(
        database
            .strip_prefix("byr_accounts_")
            .is_some_and(|v| v.len() == 16 && v.bytes().all(|b| b.is_ascii_hexdigit())),
        "test fixtures require an isolated verification database"
    );
    #[derive(Deserialize)]
    #[serde(deny_unknown_fields)]
    struct Fixture {
        recipient_id: String,
        summary: String,
        target_type: String,
        target_id: Option<String>,
    }
    let f: Fixture = serde_json::from_str(input)?;
    let recipient = id(&f.recipient_id).map_err(|_| anyhow::anyhow!("invalid recipient"))?;
    let target = f
        .target_id
        .as_deref()
        .map(id)
        .transpose()
        .map_err(|_| anyhow::anyhow!("invalid target"))?;
    let mut tx = app.pool.begin().await?;
    notifications::create(
        &mut tx,
        recipient,
        "system",
        &f.target_type,
        target,
        &f.summary,
        None,
    )
    .await
    .map_err(|_| anyhow::anyhow!("fixture unavailable"))?;
    tx.commit().await?;
    println!("Verification notification saved.");
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cursor_and_uuid_boundaries() {
        assert_eq!(sequence("0").unwrap(), 0);
        for s in ["-1", "1.0", "+1", "18446744073709551616"] {
            assert!(sequence(s).is_err());
        }
        assert!(uuid("00000000000000000000000000000000").is_err());
        assert!(uuid("00000000-0000-4000-8000-000000000000").is_ok());
    }
}

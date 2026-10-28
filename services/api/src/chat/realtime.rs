use super::*;
use futures_util::{SinkExt, StreamExt, stream::SplitSink};
use salvo::websocket::{Message as WsMessage, WebSocket, WebSocketUpgrade};
use std::{
    collections::HashMap,
    sync::Mutex,
    time::{Duration, Instant},
};
use tokio::sync::{mpsc, watch};
use tokio::time::timeout;

#[derive(Clone)]
pub(crate) enum Event {
    Message(u64),
    Notification(u64),
    Read { conversation: u64, reader: u64 },
    Unread,
}
struct Connection {
    user: u64,
    session: u64,
    tx: mpsc::Sender<Event>,
    stop: watch::Sender<bool>,
}
#[derive(Default)]
pub struct Hub {
    connections: Mutex<HashMap<uuid::Uuid, Connection>>,
}
struct Lease {
    hub: Arc<Hub>,
    id: uuid::Uuid,
}
impl Drop for Lease {
    fn drop(&mut self) {
        self.hub
            .connections
            .lock()
            .expect("live registry")
            .remove(&self.id);
    }
}
impl Hub {
    fn register(
        self: &Arc<Self>,
        identity: &Identity,
    ) -> AccountResult<(Lease, mpsc::Receiver<Event>, watch::Receiver<bool>)> {
        let mut entries = self.connections.lock().expect("live registry");
        if entries.len() >= 128
            || entries
                .values()
                .filter(|e| e.session == identity.session_id)
                .count()
                >= 16
        {
            return Err(AccountError::busy());
        }
        let (tx, rx) = mpsc::channel(64);
        let (stop, closed) = watch::channel(false);
        let id = uuid::Uuid::new_v4();
        entries.insert(
            id,
            Connection {
                user: identity.user.id,
                session: identity.session_id,
                tx,
                stop,
            },
        );
        Ok((
            Lease {
                hub: self.clone(),
                id,
            },
            rx,
            closed,
        ))
    }
    fn enqueue(&self, user: u64, event: Event) -> AccountResult<()> {
        let mut entries = self.connections.lock().expect("live registry");
        let mut failed = Vec::new();
        for (id, entry) in entries.iter() {
            if entry.user == user && entry.tx.try_send(event.clone()).is_err() {
                let _ = entry.stop.send(true);
                failed.push(*id);
            }
        }
        for id in &failed {
            entries.remove(id);
        }
        if failed.is_empty() {
            Ok(())
        } else {
            Err(AccountError::unavailable())
        }
    }
}
fn key(ticket: &str) -> String {
    let digest = accounts::security::digest(ticket);
    format!(
        "byr:ws:{}",
        digest
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect::<String>()
    )
}
pub(crate) async fn ticket(app: &AppState, identity: &Identity) -> AccountResult<Value> {
    let mut tx = app.pool.begin().await?;
    lock_identity(&mut tx, identity).await?;
    let ticket = accounts::security::random_token();
    let binding = format!("{}:{}", identity.user.id, identity.session_id);
    timeout(Duration::from_secs(2), async {
        let mut connection = app.redis.get_multiplexed_async_connection().await?;
        redis::cmd("SET")
            .arg(key(&ticket))
            .arg(binding)
            .arg("EX")
            .arg(30)
            .arg("NX")
            .query_async::<String>(&mut connection)
            .await
    })
    .await
    .map_err(|_| AccountError::unavailable())?
    .map_err(|_| AccountError::unavailable())?;
    tx.commit().await?;
    Ok(json!({"ticket":ticket,"expires_at":accounts::iso(accounts::security::now()+30)}))
}
async fn consume(app: &AppState, identity: &Identity, ticket: &str) -> AccountResult<()> {
    if !accounts::security::token_valid(ticket) {
        return Err(AccountError::auth());
    }
    let value = timeout(Duration::from_secs(2), async {
        let mut connection = app.redis.get_multiplexed_async_connection().await?;
        redis::cmd("GETDEL")
            .arg(key(ticket))
            .query_async::<Option<String>>(&mut connection)
            .await
    })
    .await
    .map_err(|_| AccountError::unavailable())?
    .map_err(|_| AccountError::unavailable())?;
    if value != Some(format!("{}:{}", identity.user.id, identity.session_id)) {
        return Err(AccountError::auth());
    }
    Ok(())
}
pub(crate) async fn session_state(
    app: &AppState,
    identity: &Identity,
) -> AccountResult<Option<String>> {
    let row=sqlx::query("SELECT s.revoked_at IS NOT NULL AS revoked,s.expires_at<=UTC_TIMESTAMP(6) AS expired,s.revocation_reason,u.status,u.password_reset_required FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id=? AND s.user_id=?").bind(identity.session_id).bind(identity.user.id).fetch_optional(&app.pool).await?;
    let Some(row) = row else {
        return Ok(Some("logout".into()));
    };
    if row.get::<String, _>("status") == "banned" {
        return Ok(Some("banned".into()));
    }
    if row.get::<bool, _>("password_reset_required") {
        return Ok(Some("password_reset".into()));
    }
    if row.get::<bool, _>("expired") {
        return Ok(Some("expired".into()));
    }
    if row.get::<bool, _>("revoked") {
        return Ok(Some(
            row.get::<Option<String>, _>("revocation_reason")
                .unwrap_or_else(|| "logout".into()),
        ));
    }
    Ok(None)
}
pub(crate) fn wire(
    kind: &str,
    data: Value,
    request: Option<&str>,
    stable: Option<String>,
) -> Value {
    json!({"type":kind,"request_id":request,"data":data,"event_id":stable.unwrap_or_else(||uuid::Uuid::new_v4().to_string()),"occurred_at":chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Micros,true)})
}
async fn error(
    sink: &mut SplitSink<WebSocket, WsMessage>,
    error: AccountError,
    request: Option<&str>,
) {
    let payload = wire(
        "error",
        json!({"code":error.code,"message":error.message,"retryable":error.status==StatusCode::SERVICE_UNAVAILABLE||error.status==StatusCode::TOO_MANY_REQUESTS}),
        request,
        None,
    );
    let _ = send(sink, payload).await;
}
async fn send(sink: &mut SplitSink<WebSocket, WsMessage>, payload: Value) -> bool {
    matches!(
        timeout(
            Duration::from_millis(500),
            sink.send(WsMessage::text(payload.to_string()))
        )
        .await,
        Ok(Ok(()))
    )
}
async fn close(sink: &mut SplitSink<WebSocket, WsMessage>, code: u16) {
    let _ = timeout(
        Duration::from_millis(250),
        sink.send(WsMessage::close_with(code, "connection closed")),
    )
    .await;
}
async fn unread(app: &AppState, user: u64) -> AccountResult<Value> {
    timeout(Duration::from_secs(1), async {
    let messages:i64=sqlx::query_scalar("SELECT COUNT(*) FROM messages m JOIN conversations c ON c.id=m.conversation_id LEFT JOIN conversation_reads r ON r.conversation_id=c.id AND r.user_id=? WHERE (c.user_low_id=? OR c.user_high_id=?) AND m.sender_id<>? AND m.sequence_no>COALESCE(r.last_read_sequence,0)").bind(user).bind(user).bind(user).bind(user).fetch_one(&app.pool).await?;
    let notifications: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM notifications WHERE recipient_id=? AND read_at IS NULL",
    )
    .bind(user)
    .fetch_one(&app.pool)
    .await?;
    Ok(wire(
        "unread.updated",
        json!({"conversation_id":null,"message_unread_count":messages,"notification_unread_count":notifications}),
        None,
        None,
    ))
    }).await.map_err(|_|AccountError::unavailable())?
}
async fn payload(app: &AppState, user: u64, event: &Event) -> AccountResult<Value> {
    match *event {
        Event::Message(mid) => Ok(wire(
            "message.created",
            message_for(app, mid, user).await?,
            None,
            Some(format!("message:{mid}")),
        )),
        Event::Notification(nid) => Ok(wire(
            "notification.created",
            notifications::notification(app, nid, user).await?,
            None,
            Some(format!("notification:{nid}")),
        )),
        Event::Read {
            conversation: cid,
            reader,
        } => {
            let row = conversation_row(&app.pool, cid, user).await?;
            if ![row.get::<u64, _>("user_low_id"), row.get("user_high_id")].contains(&reader) {
                return Err(AccountError::forbidden());
            }
            let through:u64=sqlx::query_scalar("SELECT CAST(COALESCE((SELECT last_read_sequence FROM conversation_reads WHERE conversation_id=? AND user_id=?),0) AS UNSIGNED)").bind(cid).bind(reader).fetch_one(&app.pool).await?;
            Ok(wire(
                "conversation.read",
                json!({"conversation_id":cid.to_string(),"reader_id":reader.to_string(),"through_sequence":through.to_string()}),
                None,
                Some(format!("read:{cid}:{reader}:{through}")),
            ))
        }
        Event::Unread => unread(app, user).await,
    }
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Frame {
    r#type: String,
    request_id: String,
    data: Value,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Auth {
    ticket: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Send {
    conversation_id: String,
    client_message_id: String,
    body: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ReadFrame {
    conversation_id: String,
    through_sequence: String,
}
fn invalid() -> AccountError {
    AccountError::new(
        StatusCode::BAD_REQUEST,
        "INVALID_JSON",
        "实时消息格式不正确",
    )
}
fn frame(text: &str) -> AccountResult<Frame> {
    let f: Frame = serde_json::from_str(text).map_err(|_| invalid())?;
    uuid(&f.request_id)?;
    Ok(f)
}
async fn command(app: &AppState, identity: &Identity, frame: Frame) -> AccountResult<Value> {
    match frame.r#type.as_str() {
        "message.send" => {
            let input: Send = serde_json::from_value(frame.data).map_err(|_| invalid())?;
            let (value, _) = send_message(
                app,
                identity,
                id(&input.conversation_id)?,
                MessageWrite {
                    client_message_id: input.client_message_id,
                    body: input.body,
                },
            )
            .await?;
            let mid = value["id"].as_str().unwrap_or("unknown");
            let stable = format!("ack:{mid}");
            Ok(wire(
                "message.ack",
                value,
                Some(&frame.request_id),
                Some(stable),
            ))
        }
        "message.read" => {
            let input: ReadFrame = serde_json::from_value(frame.data).map_err(|_| invalid())?;
            let cid = id(&input.conversation_id)?;
            mark_read(app, identity, cid, sequence(&input.through_sequence)?).await?;
            let mut value = payload(
                app,
                identity.user.id,
                &Event::Read {
                    conversation: cid,
                    reader: identity.user.id,
                },
            )
            .await?;
            value["request_id"] = json!(frame.request_id);
            Ok(value)
        }
        "ping" if frame.data.as_object().is_some_and(|v| v.is_empty()) => Ok(wire(
            "pong",
            json!({"server_time":chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Micros,true)}),
            Some(&frame.request_id),
            None,
        )),
        _ => Err(invalid()),
    }
}
async fn valid(
    app: &AppState,
    identity: &Identity,
    sink: &mut SplitSink<WebSocket, WsMessage>,
) -> bool {
    match timeout(Duration::from_secs(1), session_state(app, identity)).await {
        Ok(Ok(None)) => true,
        Ok(Ok(Some(reason))) => {
            let _ = send(
                sink,
                wire("session.revoked", json!({"reason_code":reason}), None, None),
            )
            .await;
            close(sink, 4001).await;
            false
        }
        _ => {
            error(sink, AccountError::unavailable(), None).await;
            close(sink, 1013).await;
            false
        }
    }
}
async fn connection(socket: WebSocket, app: Arc<AppState>, identity: Identity) {
    let (mut sink, mut stream) = socket.split();
    let first = timeout(Duration::from_secs(5), stream.next()).await;
    let first = match first {
        Ok(Some(Ok(message))) if message.is_text() => message,
        _ => {
            close(&mut sink, 4008).await;
            return;
        }
    };
    let f = match frame(first.as_str().unwrap_or("")) {
        Ok(f) if f.r#type == "authenticate" => f,
        _ => {
            close(&mut sink, 4001).await;
            return;
        }
    };
    let auth = serde_json::from_value::<Auth>(f.data).map_err(|_| invalid());
    let result = match auth {
        Ok(auth) => consume(&app, &identity, &auth.ticket).await,
        Err(error) => Err(error),
    };
    if let Err(e) = result {
        let status = e.status;
        error(&mut sink, e, Some(&f.request_id)).await;
        close(
            &mut sink,
            if status == StatusCode::SERVICE_UNAVAILABLE {
                1013
            } else {
                4001
            },
        )
        .await;
        return;
    }
    if !valid(&app, &identity, &mut sink).await {
        return;
    }
    let (_lease, mut events, mut stopped) = match app.realtime.register(&identity) {
        Ok(v) => v,
        Err(e) => {
            error(&mut sink, e, None).await;
            close(&mut sink, 1013).await;
            return;
        }
    };
    if !send(
        &mut sink,
        wire(
            "ready",
            json!({"user_id":identity.user.id.to_string(),"session_expires_at":identity.expires}),
            Some(&f.request_id),
            None,
        ),
    )
    .await
    {
        return;
    }
    if let Ok(value) = unread(&app, identity.user.id).await
        && !send(&mut sink, value).await
    {
        return;
    }
    let mut check = tokio::time::interval(Duration::from_millis(500));
    check.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
    let mut window = Instant::now();
    let mut frames = 0;
    loop {
        tokio::select! {
            biased;
            _=stopped.changed()=>{close(&mut sink,1013).await;break;},
            _=check.tick()=>{if !valid(&app,&identity,&mut sink).await{break;}},
            event=events.recv()=>{
                let Some(event)=event else{break;};if !valid(&app,&identity,&mut sink).await{break;}
                match timeout(Duration::from_secs(1),payload(&app,identity.user.id,&event)).await{Ok(Ok(value))=>{if !send(&mut sink,value).await{break;}
                if !matches!(event,Event::Unread)&&let Ok(value)=unread(&app,identity.user.id).await&& !send(&mut sink,value).await{break;}},Ok(Err(e)) if e.status==StatusCode::NOT_FOUND||e.status==StatusCode::FORBIDDEN=>{},_=>{close(&mut sink,1013).await;break;}}
            },
            incoming=stream.next()=>{
                let Some(Ok(message))=incoming else{break;};if message.is_close(){break;}
                if window.elapsed()>Duration::from_secs(5){window=Instant::now();frames=0;}frames+=1;if frames>60{error(&mut sink,AccountError::rate(5),None).await;close(&mut sink,1013).await;break;}
                if message.is_ping(){let _=timeout(Duration::from_millis(500),sink.send(WsMessage::pong(message.as_bytes().to_vec()))).await;continue;}
                if message.is_pong(){continue;}
                if !message.is_text(){close(&mut sink,1003).await;break;}
                if !valid(&app,&identity,&mut sink).await{break;}
                let f=match frame(message.as_str().unwrap_or("")){Ok(f)=>f,Err(e)=>{error(&mut sink,e,None).await;continue;}};let request=f.request_id.clone();
                match timeout(Duration::from_secs(2),command(&app,&identity,f)).await{Ok(Ok(value))=>{if !send(&mut sink,value).await{break;}},Ok(Err(e))=>error(&mut sink,e,Some(&request)).await,Err(_)=>error(&mut sink,AccountError::unavailable(),Some(&request)).await}
            },
        }
    }
}
#[handler]
pub(crate) async fn upgrade(req: &mut Request, depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    if req.uri().query().is_some()
        || req.headers().get("origin").and_then(|v| v.to_str().ok())
            != Some(app.settings.web_origin.as_str())
    {
        render_error(AccountError::forbidden(), depot, res);
        return;
    }
    let identity = match authenticate(req, &app).await {
        Ok(v) => v,
        Err(e) => {
            render_error(e, depot, res);
            return;
        }
    };
    if WebSocketUpgrade::new()
        .max_message_size(32768)
        .max_frame_size(32768)
        .upgrade(req, res, move |socket| connection(socket, app, identity))
        .await
        .is_err()
    {
        render_error(invalid(), depot, res);
    }
}

async fn pump(app: &AppState) -> AccountResult<()> {
    let ids=sqlx::query_scalar::<_,u64>("SELECT id FROM outbox_events WHERE state='pending' AND next_due_at<=UTC_TIMESTAMP(6) ORDER BY next_due_at,id LIMIT 50").fetch_all(&app.pool).await?;
    for id in ids {
        let mut tx = app.pool.begin().await?;
        let Some(row)=sqlx::query("SELECT recipient_id,CAST(event_type AS CHAR CHARACTER SET utf8mb4) AS event_type,source_id,safe_reference,attempts FROM outbox_events WHERE id=? AND state='pending' AND next_due_at<=UTC_TIMESTAMP(6) FOR UPDATE SKIP LOCKED").bind(id).fetch_optional(&mut *tx).await? else{continue;};
        let recipient = row.get::<u64, _>("recipient_id");
        let source = row.get::<u64, _>("source_id");
        let kind = row.get::<String, _>("event_type");
        let reference = row.get::<Value, _>("safe_reference");
        let event = match kind.as_str() {
            "message.created" => Some(Event::Message(source)),
            "notification.created" => Some(Event::Notification(source)),
            "conversation.read" => reference["reader_id"]
                .as_str()
                .and_then(|s| id_from(s).ok())
                .map(|reader| Event::Read {
                    conversation: source,
                    reader,
                }),
            "unread.updated" => Some(Event::Unread),
            _ => None,
        };
        let result = if let Some(event) = event {
            match timeout(Duration::from_secs(2), payload(app, recipient, &event)).await {
                Ok(Ok(_)) => app.realtime.enqueue(recipient, event),
                Ok(Err(e)) => Err(e),
                Err(_) => Err(AccountError::unavailable()),
            }
        } else {
            Err(AccountError::missing())
        };
        match result {
            Ok(()) => {
                sqlx::query("UPDATE outbox_events SET state='sent' WHERE id=?")
                    .bind(id)
                    .execute(&mut *tx)
                    .await?;
            }
            Err(error) => {
                let attempt = row.get::<u32, _>("attempts") + 1;
                if attempt >= 6
                    || error.status == StatusCode::NOT_FOUND
                    || error.status == StatusCode::FORBIDDEN
                {
                    sqlx::query("UPDATE outbox_events SET state='expired',attempts=? WHERE id=?")
                        .bind(attempt)
                        .bind(id)
                        .execute(&mut *tx)
                        .await?;
                    tracing::warn!(
                        category = "push_expired",
                        "live hint deferred to persistent HTTP read"
                    );
                } else {
                    let delay = [1, 5, 15, 60, 300][(attempt - 1) as usize];
                    sqlx::query("UPDATE outbox_events SET attempts=?,next_due_at=DATE_ADD(UTC_TIMESTAMP(6),INTERVAL ? SECOND) WHERE id=?").bind(attempt).bind(delay).bind(id).execute(&mut *tx).await?;
                }
            }
        }
        tx.commit().await?;
    }
    Ok(())
}
fn id_from(raw: &str) -> AccountResult<u64> {
    id(raw)
}
pub(crate) async fn outbox_worker(app: Arc<AppState>) {
    let mut timer = tokio::time::interval(Duration::from_millis(250));
    timer.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
    loop {
        timer.tick().await;
        if pump(&app).await.is_err() {
            tracing::warn!(
                category = "push_dependency",
                "live hints unavailable; persistent reads remain authoritative"
            );
        }
    }
}

use super::*;
pub(crate) async fn create(
    tx: &mut Transaction<'_, MySql>,
    recipient: u64,
    kind: &str,
    target_type: &str,
    target: Option<u64>,
    summary: &str,
    match_id: Option<u64>,
) -> AccountResult<u64> {
    if !["system", "goods_match", "report_result"].contains(&kind)
        || !["goods", "post", "report", "announcement", "none"].contains(&target_type)
        || (target_type == "none") != target.is_none()
        || (kind == "goods_match") != match_id.is_some()
    {
        return Err(AccountError::validation("target_type", "通知目标不正确"));
    }
    let summary = field_text(summary, 1, 300, "summary")?;
    accounts::locked_user(tx, recipient).await?;
    let saved=sqlx::query("INSERT INTO notifications(recipient_id,kind,target_type,target_id,safe_summary,match_id) VALUES (?,?,?,?,?,?)").bind(recipient).bind(kind).bind(target_type).bind(target).bind(summary).bind(match_id).execute(&mut **tx).await?;
    let id = saved.last_insert_id();
    enqueue(tx, recipient, "notification.created", id, json!({})).await?;
    Ok(id)
}
pub(super) async fn notification(app: &AppState, nid: u64, viewer: u64) -> AccountResult<Value> {
    let row=sqlx::query("SELECT id,kind,target_type,target_id,safe_summary,DATE_FORMAT(read_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS read_at,DATE_FORMAT(created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at FROM notifications WHERE id=? AND recipient_id=?").bind(nid).bind(viewer).fetch_optional(&app.pool).await?.ok_or_else(AccountError::missing)?;
    let kind = row.get::<String, _>("kind");
    let target_type = row.get::<String, _>("target_type");
    let target = row.get::<Option<u64>, _>("target_id");
    let mut state: Option<String> = None;
    let mut summary = row.get::<String, _>("safe_summary");
    let mut available = target_type == "none";
    if let Some(target) = target {
        match target_type.as_str() {
            "goods" => {
                if let Some(g) = goods::context(app, target, viewer).await? {
                    available = true;
                    state = g["state"].as_str().map(str::to_owned);
                    summary = g["title"].as_str().unwrap_or("商品").to_owned();
                }
            }
            "post" => {
                if let Some(title)=sqlx::query_scalar::<_,String>("SELECT title FROM posts WHERE id=? AND visibility='public' AND deleted_at IS NULL").bind(target).fetch_optional(&app.pool).await?{available=true;state=Some("public".into());summary=title;}
            }
            "announcement" => {
                if let Some(title) = sqlx::query_scalar::<_, String>(
                    "SELECT title FROM announcements WHERE id=? AND state='published'",
                )
                .bind(target)
                .fetch_optional(&app.pool)
                .await?
                {
                    available = true;
                    state = Some("published".into());
                    summary = title;
                }
            }
            "report" => {
                if let Some(current) = sqlx::query_scalar::<_, String>(
                    "SELECT state FROM reports WHERE id=? AND reporter_id=?",
                )
                .bind(target)
                .bind(viewer)
                .fetch_optional(&app.pool)
                .await?
                {
                    available = true;
                    summary = format!("举报处理状态：{current}");
                    state = Some(current);
                }
            }
            _ => {}
        }
    }
    let title = if !available {
        summary = "相关内容当前不可访问".into();
        "内容已不可用"
    } else {
        match kind.as_str() {
            "goods_match" => "商品匹配提醒",
            "report_result" => "举报处理结果",
            _ => "系统通知",
        }
    };
    Ok(
        json!({"id":nid.to_string(),"kind":kind,"title":title,"summary":summary,"target_type":target_type,"target_id":target.map(|v|v.to_string()),"target_available":available,"target_state":state,"read_at":row.get::<Option<String>,_>("read_at"),"created_at":row.get::<String,_>("created_at")}),
    )
}
pub(super) async fn list(
    req: &Request,
    app: &AppState,
    identity: &Identity,
) -> AccountResult<Value> {
    let (page, size) = goods::paging(req)?;
    let unread = match req.query::<String>("unread_only").as_deref() {
        None | Some("false") => false,
        Some("true") => true,
        _ => {
            return Err(AccountError::validation(
                "unread_only",
                "未读筛选须为true或false",
            ));
        }
    };
    let total: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM notifications WHERE recipient_id=? AND (?=false OR read_at IS NULL)",
    )
    .bind(identity.user.id)
    .bind(unread)
    .fetch_one(&app.pool)
    .await?;
    let ids=sqlx::query_scalar::<_,u64>("SELECT id FROM notifications WHERE recipient_id=? AND (?=false OR read_at IS NULL) ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?").bind(identity.user.id).bind(unread).bind(size).bind((page-1)*size).fetch_all(&app.pool).await?;
    let mut items = Vec::new();
    for id in ids {
        items.push(notification(app, id, identity.user.id).await?);
    }
    Ok(json!({"items":items,"total":total,"page":page,"page_size":size}))
}
pub(super) async fn read(
    app: &AppState,
    identity: &Identity,
    nid: Option<u64>,
) -> AccountResult<()> {
    let mut tx = app.pool.begin().await?;
    lock_identity(&mut tx, identity).await?;
    if let Some(nid) = nid {
        if sqlx::query("SELECT id FROM notifications WHERE id=? AND recipient_id=? FOR UPDATE")
            .bind(nid)
            .bind(identity.user.id)
            .fetch_optional(&mut *tx)
            .await?
            .is_none()
        {
            return Err(AccountError::missing());
        }
        sqlx::query("UPDATE notifications SET read_at=COALESCE(read_at,UTC_TIMESTAMP(6)) WHERE id=? AND recipient_id=?").bind(nid).bind(identity.user.id).execute(&mut *tx).await?;
    } else {
        let boundary: Option<u64> =
            sqlx::query_scalar("SELECT MAX(id) FROM notifications WHERE recipient_id=?")
                .bind(identity.user.id)
                .fetch_one(&mut *tx)
                .await?;
        if let Some(boundary) = boundary {
            sqlx::query("UPDATE notifications SET read_at=UTC_TIMESTAMP(6) WHERE recipient_id=? AND id<=? AND read_at IS NULL").bind(identity.user.id).bind(boundary).execute(&mut *tx).await?;
        }
    }
    enqueue(
        &mut tx,
        identity.user.id,
        "unread.updated",
        identity.user.id,
        json!({}),
    )
    .await?;
    tx.commit().await?;
    Ok(())
}

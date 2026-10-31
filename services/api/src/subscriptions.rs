//! Product subscriptions: saved conditions, periodic checks, deduplicated notifications.
use crate::{AppState, access::*, accounts, chat, goods, ok, state};
use salvo::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sqlx::{MySql, QueryBuilder, Row, Transaction, mysql::MySqlRow};
use std::time::Duration;

pub(crate) const CAMPUSES: [&str; 3] = ["shahe", "xitucheng", "other"];
const MAX_TASKS: i64 = 10;
const MIN_INTERVAL: u16 = 5;
const MAX_INTERVAL: u16 = 1440;
const LEASE_SECONDS: u32 = 120;
const RUN_SECONDS: u64 = 60;

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct RequiredAttributes {
    #[serde(default)]
    stylus_support: Option<bool>,
    #[serde(default)]
    storage_gb: Option<u32>,
}

impl RequiredAttributes {
    fn is_empty(&self) -> bool {
        self.stylus_support.is_none() && self.storage_gb.is_none()
    }
    fn validate(&self) -> AccountResult<()> {
        if self.storage_gb.is_some_and(|v| !(1..=100_000).contains(&v)) {
            return Err(AccountError::validation(
                "conditions.required_attributes.storage_gb",
                "容量须在 1～100000 之间",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Conditions {
    schema_version: u32,
    min_price_cents: Option<u32>,
    max_price_cents: Option<u32>,
    campus_code: Option<String>,
    category_id: Option<String>,
    brand: Option<String>,
    model: Option<String>,
    min_condition: Option<String>,
    required_attributes: RequiredAttributes,
    purpose: Option<String>,
}

fn clean_optional(
    value: Option<String>,
    max: usize,
    field: &'static str,
) -> AccountResult<Option<String>> {
    let Some(value) = value else { return Ok(None) };
    let value = value.trim();
    if value.is_empty() {
        return Ok(None);
    }
    if value.chars().count() > max || value.chars().any(char::is_control) {
        return Err(AccountError::validation(field, "文字长度或字符不符合要求"));
    }
    Ok(Some(value.to_owned()))
}

fn condition_id(value: &str) -> Option<u64> {
    if value.starts_with('0') || value.is_empty() || value.len() > 20 {
        return None;
    }
    value.parse::<u64>().ok().filter(|v| *v > 0)
}

impl Conditions {
    fn validate_shape(&mut self) -> AccountResult<()> {
        if self.schema_version != 1 {
            return Err(AccountError::validation(
                "conditions.schema_version",
                "条件版本不正确",
            ));
        }
        if self.min_price_cents.is_some_and(|v| v > 9_999_999)
            || self.max_price_cents.is_some_and(|v| v > 9_999_999)
        {
            return Err(AccountError::validation("conditions", "价格超出允许范围"));
        }
        if let (Some(min), Some(max)) = (self.min_price_cents, self.max_price_cents)
            && min > max
        {
            return Err(AccountError::validation(
                "conditions.min_price_cents",
                "最低价格不能高于最高价格",
            ));
        }
        if let Some(campus) = &self.campus_code
            && !CAMPUSES.contains(&campus.as_str())
        {
            return Err(AccountError::validation(
                "conditions.campus_code",
                "交易校区不正确",
            ));
        }
        if let Some(category) = &self.category_id
            && condition_id(category).is_none()
        {
            return Err(AccountError::validation(
                "conditions.category_id",
                "类别编号不正确",
            ));
        }
        self.brand = clean_optional(self.brand.take(), 100, "conditions.brand")?;
        self.model = clean_optional(self.model.take(), 100, "conditions.model")?;
        self.purpose = clean_optional(self.purpose.take(), 100, "conditions.purpose")?;
        if let Some(condition) = &self.min_condition
            && !["new", "like_new", "good", "fair"].contains(&condition.as_str())
        {
            return Err(AccountError::validation(
                "conditions.min_condition",
                "最低成色不正确",
            ));
        }
        self.required_attributes.validate()?;
        let empty = self.category_id.is_none()
            && self.brand.is_none()
            && self.model.is_none()
            && self.min_price_cents.is_none()
            && self.max_price_cents.is_none()
            && self.campus_code.is_none()
            && self.min_condition.is_none()
            && self.purpose.is_none()
            && self.required_attributes.is_empty();
        if empty {
            return Err(AccountError::validation(
                "conditions",
                "请至少填写一个商品条件",
            ));
        }
        Ok(())
    }

    async fn validate_dictionaries(&self, tx: &mut Transaction<'_, MySql>) -> AccountResult<()> {
        if let Some(category) = &self.category_id {
            let category = condition_id(category).expect("validated category");
            let found: i64 = sqlx::query_scalar(
                "SELECT COUNT(*) FROM goods_categories WHERE id=? AND enabled=true",
            )
            .bind(category)
            .fetch_one(&mut **tx)
            .await?;
            if found != 1 {
                return Err(AccountError::validation(
                    "conditions.category_id",
                    "类别不存在或已停用",
                ));
            }
        }
        if let Some(campus) = &self.campus_code {
            let found: i64 =
                sqlx::query_scalar("SELECT COUNT(*) FROM campuses WHERE code=? AND enabled=true")
                    .bind(campus)
                    .fetch_one(&mut **tx)
                    .await?;
            if found != 1 {
                return Err(AccountError::validation(
                    "conditions.campus_code",
                    "校区不存在或已停用",
                ));
            }
        }
        Ok(())
    }

    fn append(&self, q: &mut QueryBuilder<'_, MySql>, alias: &str) {
        if let Some(category) = &self.category_id {
            q.push(format!(" AND {alias}.category_id="))
                .push_bind(condition_id(category).expect("validated category"));
        }
        if let Some(campus) = &self.campus_code {
            q.push(format!(" AND {alias}.campus_code="))
                .push_bind(campus.clone());
        }
        if let Some(min) = self.min_price_cents {
            q.push(format!(" AND {alias}.price_cents>=")).push_bind(min);
        }
        if let Some(max) = self.max_price_cents {
            q.push(format!(" AND {alias}.price_cents<=")).push_bind(max);
        }
        if let Some(brand) = &self.brand {
            q.push(format!(" AND LOWER(TRIM({alias}.brand))=LOWER("))
                .push_bind(brand.clone())
                .push(")");
        }
        if let Some(model) = &self.model {
            q.push(format!(" AND LOWER(TRIM({alias}.model))=LOWER("))
                .push_bind(model.clone())
                .push(")");
        }
        if let Some(condition) = &self.min_condition {
            let rank = match condition.as_str() {
                "new" => 4,
                "like_new" => 3,
                "good" => 2,
                _ => 1,
            };
            q.push(format!(" AND CASE {alias}.condition_code WHEN 'new' THEN 4 WHEN 'like_new' THEN 3 WHEN 'good' THEN 2 WHEN 'fair' THEN 1 ELSE 0 END >= ")).push_bind(rank);
        }
        if let Some(stylus) = self.required_attributes.stylus_support {
            q.push(format!(
                " AND JSON_UNQUOTE(JSON_EXTRACT({alias}.attributes, '$.stylus_support'))="
            ))
            .push_bind(if stylus { "true" } else { "false" });
        }
        if let Some(storage) = self.required_attributes.storage_gb {
            q.push(format!(
                " AND JSON_UNQUOTE(JSON_EXTRACT({alias}.attributes, '$.storage_gb'))="
            ))
            .push_bind(storage.to_string());
        }
    }
}

const COLUMNS: &str = "s.id,s.name,s.original_query,s.conditions,s.interval_minutes,s.state,s.config_version,DATE_FORMAT(s.last_checked_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS last_checked_at,DATE_FORMAT(s.next_due_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS next_due_at,s.last_error_code,DATE_FORMAT(s.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at,(SELECT COUNT(*) FROM subscription_matches m WHERE m.subscription_id=s.id) AS match_count";

fn subscription(row: &MySqlRow) -> Value {
    json!({
        "id": row.get::<u64, _>("id").to_string(),
        "name": row.get::<String, _>("name"),
        "original_query": row.get::<Option<String>, _>("original_query"),
        "conditions": row.get::<Value, _>("conditions"),
        "interval_minutes": row.get::<u16, _>("interval_minutes"),
        "state": row.get::<String, _>("state"),
        "config_version": row.get::<u32, _>("config_version"),
        "last_checked_at": row.get::<Option<String>, _>("last_checked_at"),
        "next_due_at": row.get::<Option<String>, _>("next_due_at"),
        "last_error_code": row.get::<Option<String>, _>("last_error_code"),
        "match_count": row.get::<i64, _>("match_count"),
        "created_at": row.get::<String, _>("created_at"),
    })
}

fn param(req: &Request) -> AccountResult<u64> {
    id(req
        .param::<String>("subscription_id")
        .as_deref()
        .ok_or_else(AccountError::missing)?)
}

fn checked_interval(value: u16) -> AccountResult<u16> {
    if !(MIN_INTERVAL..=MAX_INTERVAL).contains(&value) {
        return Err(AccountError::validation(
            "interval_minutes",
            "检查周期须在 5～1440 分钟之间",
        ));
    }
    Ok(value)
}

async fn list(req: &Request, app: &AppState) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let (page, size) = goods::paging(req)?;
    let state = req.query::<String>("state");
    if let Some(state) = &state
        && !["active", "paused", "error"].contains(&state.as_str())
    {
        return Err(AccountError::validation("state", "任务状态不正确"));
    }
    let mut count =
        QueryBuilder::<MySql>::new("SELECT COUNT(*) FROM subscriptions s WHERE s.owner_id=");
    count
        .push_bind(identity.user.id)
        .push(" AND s.state<>'deleted'");
    if let Some(state) = &state {
        count.push(" AND s.state=").push_bind(state.clone());
    }
    let total: i64 = count.build_query_scalar().fetch_one(&app.pool).await?;
    let mut query = QueryBuilder::<MySql>::new(format!(
        "SELECT {COLUMNS} FROM subscriptions s WHERE s.owner_id="
    ));
    query
        .push_bind(identity.user.id)
        .push(" AND s.state<>'deleted'");
    if let Some(state) = &state {
        query.push(" AND s.state=").push_bind(state.clone());
    }
    query
        .push(" ORDER BY s.created_at DESC,s.id DESC LIMIT ")
        .push_bind(size)
        .push(" OFFSET ")
        .push_bind((page - 1) * size);
    let rows = query.build().fetch_all(&app.pool).await?;
    Ok(json!({
        "items": rows.iter().map(subscription).collect::<Vec<_>>(),
        "total": total,
        "page": page,
        "page_size": size,
    }))
}

async fn get(req: &Request, app: &AppState, sid: u64) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let row = sqlx::query(&format!(
        "SELECT {COLUMNS} FROM subscriptions s WHERE s.id=? AND s.owner_id=? AND s.state<>'deleted'"
    ))
    .bind(sid)
    .bind(identity.user.id)
    .fetch_optional(&app.pool)
    .await?
    .ok_or_else(AccountError::missing)?;
    Ok(subscription(&row))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct CreateSubscription {
    name: String,
    original_query: Option<String>,
    conditions: Conditions,
    interval_minutes: u16,
    confirmed: bool,
}

fn new_name(value: &str) -> AccountResult<String> {
    let value = field_text(value, 1, 100, "name")?;
    if value.chars().any(char::is_control) {
        return Err(AccountError::validation("name", "名称含有不允许的字符"));
    }
    Ok(value)
}

fn original_query(value: Option<String>) -> AccountResult<Option<String>> {
    let Some(value) = value else { return Ok(None) };
    let value = value.trim();
    if value.is_empty() {
        return Ok(None);
    }
    if value.chars().count() > 1000 {
        return Err(AccountError::validation(
            "original_query",
            "原始需求不能超过 1000 字",
        ));
    }
    Ok(Some(value.to_owned()))
}

async fn create(req: &mut Request, app: &AppState) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let mut input: CreateSubscription = parse(req).await?;
    if !input.confirmed {
        return Err(AccountError::validation("confirmed", "请先确认保存的条件"));
    }
    input.name = new_name(&input.name)?;
    let original_query = original_query(input.original_query)?;
    let interval = checked_interval(input.interval_minutes)?;
    input.conditions.validate_shape()?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    input.conditions.validate_dictionaries(&mut tx).await?;
    let count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM subscriptions WHERE owner_id=? AND state<>'deleted'",
    )
    .bind(user.id)
    .fetch_one(&mut *tx)
    .await?;
    if count >= MAX_TASKS {
        return Err(AccountError::new(
            StatusCode::CONFLICT,
            "TASK_LIMIT_REACHED",
            "最多保存 10 个商品提醒，请先删除不再使用的任务",
        ));
    }
    let saved = sqlx::query("INSERT INTO subscriptions(owner_id,name,original_query,conditions,conditions_schema_version,interval_minutes,state,needs_full_scan,next_due_at) VALUES (?,?,?,?,1,?,'active',TRUE,UTC_TIMESTAMP(6))")
        .bind(user.id)
        .bind(&input.name)
        .bind(&original_query)
        .bind(json!(input.conditions))
        .bind(interval)
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    let row = sqlx::query(&format!(
        "SELECT {COLUMNS} FROM subscriptions s WHERE s.id=?"
    ))
    .bind(saved.last_insert_id())
    .fetch_one(&app.pool)
    .await?;
    Ok(subscription(&row))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct UpdateSubscription {
    name: String,
    original_query: Option<String>,
    conditions: Conditions,
    interval_minutes: u16,
    version: u32,
    confirmed: bool,
    resume_after_save: bool,
}

async fn update(req: &mut Request, app: &AppState, sid: u64) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let mut input: UpdateSubscription = parse(req).await?;
    if !input.confirmed {
        return Err(AccountError::validation("confirmed", "请先确认保存的条件"));
    }
    input.name = new_name(&input.name)?;
    let original_query = original_query(input.original_query)?;
    let interval = checked_interval(input.interval_minutes)?;
    input.conditions.validate_shape()?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    let current = sqlx::query(
        "SELECT owner_id,state,config_version FROM subscriptions WHERE id=? AND state<>'deleted' FOR UPDATE",
    )
    .bind(sid)
    .fetch_optional(&mut *tx)
    .await?
    .ok_or_else(AccountError::missing)?;
    if current.get::<u64, _>("owner_id") != user.id {
        return Err(AccountError::missing());
    }
    if current.get::<String, _>("state") != "paused" {
        return Err(AccountError::new(
            StatusCode::CONFLICT,
            "STATE_CONFLICT",
            "请先暂停任务再编辑条件",
        ));
    }
    if current.get::<u32, _>("config_version") != input.version {
        return Err(AccountError::conflict());
    }
    input.conditions.validate_dictionaries(&mut tx).await?;
    let next_state = if input.resume_after_save {
        "active"
    } else {
        "paused"
    };
    sqlx::query("UPDATE subscriptions SET name=?,original_query=?,conditions=?,conditions_schema_version=1,interval_minutes=?,state=?,config_version=config_version+1,needs_full_scan=TRUE,cursor_change_seq=0,next_due_at=IF(?='active',UTC_TIMESTAMP(6),NULL),retry_count=0,cycle_key=NULL,last_error_code=NULL,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
        .bind(&input.name)
        .bind(&original_query)
        .bind(json!(input.conditions))
        .bind(interval)
        .bind(next_state)
        .bind(next_state)
        .bind(sid)
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    let row = sqlx::query(&format!(
        "SELECT {COLUMNS} FROM subscriptions s WHERE s.id=?"
    ))
    .bind(sid)
    .fetch_one(&app.pool)
    .await?;
    Ok(subscription(&row))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct StateChange {
    state: String,
    version: u32,
}

async fn change_state(req: &mut Request, app: &AppState, sid: u64) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input: StateChange = parse(req).await?;
    if !["active", "paused"].contains(&input.state.as_str()) {
        return Err(AccountError::validation("state", "任务状态不正确"));
    }
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    let current = sqlx::query(
        "SELECT owner_id,state,config_version FROM subscriptions WHERE id=? AND state<>'deleted' FOR UPDATE",
    )
    .bind(sid)
    .fetch_optional(&mut *tx)
    .await?
    .ok_or_else(AccountError::missing)?;
    if current.get::<u64, _>("owner_id") != user.id {
        return Err(AccountError::missing());
    }
    if current.get::<u32, _>("config_version") != input.version {
        return Err(AccountError::conflict());
    }
    let state = current.get::<String, _>("state");
    if input.state == "active" {
        if !["paused", "error", "active"].contains(&state.as_str()) {
            return Err(AccountError::new(
                StatusCode::CONFLICT,
                "STATE_CONFLICT",
                "任务当前状态不能恢复",
            ));
        }
        sqlx::query("UPDATE subscriptions SET state='active',config_version=config_version+1,next_due_at=UTC_TIMESTAMP(6),retry_count=0,cycle_key=NULL,last_error_code=NULL,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
            .bind(sid)
            .execute(&mut *tx)
            .await?;
    } else {
        if !["active", "paused", "error"].contains(&state.as_str()) {
            return Err(AccountError::new(
                StatusCode::CONFLICT,
                "STATE_CONFLICT",
                "任务当前状态不能暂停",
            ));
        }
        sqlx::query("UPDATE subscriptions SET state='paused',config_version=config_version+1,next_due_at=NULL,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
            .bind(sid)
            .execute(&mut *tx)
            .await?;
    }
    tx.commit().await?;
    let row = sqlx::query(&format!(
        "SELECT {COLUMNS} FROM subscriptions s WHERE s.id=?"
    ))
    .bind(sid)
    .fetch_one(&app.pool)
    .await?;
    Ok(subscription(&row))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Version {
    version: u32,
}

async fn delete(req: &mut Request, app: &AppState, sid: u64) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input: Version = parse(req).await?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    let current = sqlx::query(
        "SELECT owner_id,config_version FROM subscriptions WHERE id=? AND state<>'deleted' FOR UPDATE",
    )
    .bind(sid)
    .fetch_optional(&mut *tx)
    .await?
    .ok_or_else(AccountError::missing)?;
    if current.get::<u64, _>("owner_id") != user.id {
        return Err(AccountError::missing());
    }
    if current.get::<u32, _>("config_version") != input.version {
        return Err(AccountError::conflict());
    }
    sqlx::query("UPDATE subscriptions SET state='deleted',config_version=config_version+1,next_due_at=NULL,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
        .bind(sid)
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    Ok(json!({"ok": true}))
}

async fn runs(req: &Request, app: &AppState, sid: u64) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let owned: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM subscriptions WHERE id=? AND owner_id=? AND state<>'deleted'",
    )
    .bind(sid)
    .bind(identity.user.id)
    .fetch_one(&app.pool)
    .await?;
    if owned != 1 {
        return Err(AccountError::missing());
    }
    let (page, size) = goods::paging(req)?;
    let total: i64 =
        sqlx::query_scalar("SELECT COUNT(*) FROM subscription_runs WHERE subscription_id=?")
            .bind(sid)
            .fetch_one(&app.pool)
            .await?;
    let rows = sqlx::query("SELECT id,state,attempt_no,DATE_FORMAT(started_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS started_at,DATE_FORMAT(finished_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS finished_at,error_code FROM subscription_runs WHERE subscription_id=? ORDER BY started_at DESC,id DESC LIMIT ? OFFSET ?")
        .bind(sid)
        .bind(size)
        .bind((page - 1) * size)
        .fetch_all(&app.pool)
        .await?;
    let items = rows
        .iter()
        .map(|row| {
            json!({
                "id": row.get::<u64, _>("id").to_string(),
                "state": row.get::<String, _>("state"),
                "attempt_no": row.get::<u8, _>("attempt_no"),
                "started_at": row.get::<String, _>("started_at"),
                "finished_at": row.get::<Option<String>, _>("finished_at"),
                "error_code": row.get::<Option<String>, _>("error_code"),
            })
        })
        .collect::<Vec<_>>();
    Ok(json!({"items":items,"total":total,"page":page,"page_size":size}))
}

async fn matches(req: &Request, app: &AppState, sid: u64) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let owned: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM subscriptions WHERE id=? AND owner_id=? AND state<>'deleted'",
    )
    .bind(sid)
    .bind(identity.user.id)
    .fetch_one(&app.pool)
    .await?;
    if owned != 1 {
        return Err(AccountError::missing());
    }
    let (page, size) = goods::paging(req)?;
    let total: i64 =
        sqlx::query_scalar("SELECT COUNT(*) FROM subscription_matches WHERE subscription_id=?")
            .bind(sid)
            .fetch_one(&app.pool)
            .await?;
    let rows = sqlx::query("SELECT id,goods_id,DATE_FORMAT(created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at FROM subscription_matches WHERE subscription_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?")
        .bind(sid)
        .bind(size)
        .bind((page - 1) * size)
        .fetch_all(&app.pool)
        .await?;
    let mut items = Vec::new();
    for row in &rows {
        let gid = row.get::<u64, _>("goods_id");
        let goods = goods::context(app, gid, identity.user.id).await?;
        items.push(json!({
            "id": row.get::<u64, _>("id").to_string(),
            "goods_id": gid.to_string(),
            "goods": goods,
            "target_available": goods.is_some(),
            "created_at": row.get::<String, _>("created_at"),
        }));
    }
    Ok(json!({"items":items,"total":total,"page":page,"page_size":size}))
}

async fn admin_list(req: &Request, app: &AppState) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    if identity.user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let (page, size) = goods::paging(req)?;
    let state = req.query::<String>("state");
    if let Some(state) = &state
        && !["active", "paused", "error"].contains(&state.as_str())
    {
        return Err(AccountError::validation("state", "任务状态不正确"));
    }
    let mut count =
        QueryBuilder::<MySql>::new("SELECT COUNT(*) FROM subscriptions s WHERE s.state<>'deleted'");
    if let Some(state) = &state {
        count.push(" AND s.state=").push_bind(state.clone());
    }
    let total: i64 = count.build_query_scalar().fetch_one(&app.pool).await?;
    let mut query = QueryBuilder::<MySql>::new(
        "SELECT s.id,u.nickname AS owner_label,s.state,s.interval_minutes,DATE_FORMAT(s.last_checked_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS last_checked_at,DATE_FORMAT(s.next_due_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS next_due_at,s.last_error_code FROM subscriptions s JOIN users u ON u.id=s.owner_id WHERE s.state<>'deleted'",
    );
    if let Some(state) = &state {
        query.push(" AND s.state=").push_bind(state.clone());
    }
    query
        .push(" ORDER BY s.created_at DESC,s.id DESC LIMIT ")
        .push_bind(size)
        .push(" OFFSET ")
        .push_bind((page - 1) * size);
    let rows = query.build().fetch_all(&app.pool).await?;
    let items = rows
        .iter()
        .map(|row| {
            json!({
                "id": row.get::<u64, _>("id").to_string(),
                "owner_label": row.get::<String, _>("owner_label"),
                "state": row.get::<String, _>("state"),
                "interval_minutes": row.get::<u16, _>("interval_minutes"),
                "last_checked_at": row.get::<Option<String>, _>("last_checked_at"),
                "next_due_at": row.get::<Option<String>, _>("next_due_at"),
                "last_error_code": row.get::<Option<String>, _>("last_error_code"),
            })
        })
        .collect::<Vec<_>>();
    Ok(json!({"items":items,"total":total,"page":page,"page_size":size}))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct AdminPause {
    reason: String,
}

async fn admin_pause(
    req: &mut Request,
    depot: &Depot,
    app: &AppState,
    sid: u64,
) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    if identity.user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let input: AdminPause = parse(req).await?;
    let why = reason(&input.reason)?;
    let mut tx = app.pool.begin().await?;
    let actor = lock_identity(&mut tx, &identity).await?;
    let current = sqlx::query(
        "SELECT owner_id,state,config_version FROM subscriptions WHERE id=? AND state<>'deleted' FOR UPDATE",
    )
    .bind(sid)
    .fetch_optional(&mut *tx)
    .await?
    .ok_or_else(AccountError::missing)?;
    if !["active", "error"].contains(&current.get::<String, _>("state").as_str()) {
        return Err(AccountError::new(
            StatusCode::CONFLICT,
            "STATE_CONFLICT",
            "任务当前状态不需要暂停",
        ));
    }
    sqlx::query("UPDATE subscriptions SET state='paused',config_version=config_version+1,next_due_at=NULL,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
        .bind(sid)
        .execute(&mut *tx)
        .await?;
    let request_id = depot
        .get::<String>("request_id")
        .map(|value| value.to_owned())
        .unwrap_or_else(|_| uuid::Uuid::new_v4().to_string());
    sqlx::query("INSERT INTO audit_logs(actor_id,action,target_type,target_id,reason,safe_changes,request_id) VALUES (?,'subscription.pause','subscription',?,?,?,?)")
        .bind(actor.id)
        .bind(sid)
        .bind(why)
        .bind(json!({"state":"paused","config_version":current.get::<u32, _>("config_version") + 1}))
        .bind(request_id)
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    Ok(json!({"ok": true}))
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
    if path == "/api/v1/subscriptions" {
        return match method.as_str() {
            "GET" => Ok((StatusCode::OK, list(req, app).await?)),
            "POST" => Ok((StatusCode::CREATED, create(req, app).await?)),
            _ => Err(AccountError::missing()),
        };
    }
    if path == "/api/v1/admin/subscriptions" {
        if method != "GET" {
            return Err(AccountError::missing());
        }
        return Ok((StatusCode::OK, admin_list(req, app).await?));
    }
    let sid = param(req)?;
    if path.ends_with("/pause") {
        return Ok((StatusCode::OK, admin_pause(req, depot, app, sid).await?));
    }
    if path.ends_with("/state") {
        return Ok((StatusCode::OK, change_state(req, app, sid).await?));
    }
    if path.ends_with("/runs") {
        if method != "GET" {
            return Err(AccountError::missing());
        }
        return Ok((StatusCode::OK, runs(req, app, sid).await?));
    }
    if path.ends_with("/matches") {
        if method != "GET" {
            return Err(AccountError::missing());
        }
        return Ok((StatusCode::OK, matches(req, app, sid).await?));
    }
    match method.as_str() {
        "GET" => Ok((StatusCode::OK, get(req, app, sid).await?)),
        "PATCH" => Ok((StatusCode::OK, update(req, app, sid).await?)),
        "DELETE" => Ok((StatusCode::OK, delete(req, app, sid).await?)),
        _ => Err(AccountError::missing()),
    }
}

#[handler]
async fn dispatch(req: &mut Request, depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    res.add_header("Cache-Control", "private, no-store", true)
        .ok();
    match action(req, depot, &app).await {
        Ok((status, value)) => ok(res, depot, status, value),
        Err(error) => render_error(error, depot, res),
    }
}

pub fn routes() -> Router {
    Router::with_path("api/v1")
        .push(
            Router::with_path("subscriptions")
                .get(dispatch)
                .post(dispatch)
                .push(
                    Router::with_path("{subscription_id}")
                        .get(dispatch)
                        .patch(dispatch)
                        .delete(dispatch)
                        .push(Router::with_path("state").patch(dispatch))
                        .push(Router::with_path("runs").get(dispatch))
                        .push(Router::with_path("matches").get(dispatch)),
                ),
        )
        .push(
            Router::with_path("admin/subscriptions")
                .get(dispatch)
                .push(Router::with_path("{subscription_id}/pause").post(dispatch)),
        )
}

// ---------------------------------------------------------------------------
// Worker
// ---------------------------------------------------------------------------

#[derive(Debug)]
struct RunFailure {
    code: &'static str,
    retryable: bool,
    cancelled: bool,
}

impl RunFailure {
    fn transient(code: &'static str) -> Self {
        Self {
            code,
            retryable: true,
            cancelled: false,
        }
    }
    fn permanent(code: &'static str) -> Self {
        Self {
            code,
            retryable: false,
            cancelled: false,
        }
    }
    fn cancelled(code: &'static str) -> Self {
        Self {
            code,
            retryable: false,
            cancelled: true,
        }
    }
}

#[derive(Debug)]
struct Claim {
    id: u64,
    owner_id: u64,
    config_version: u32,
    interval_minutes: u16,
    conditions: Value,
    cursor: u64,
    full_scan: bool,
    lease_token: String,
    slot_no: u8,
    upper: u64,
    run_id: u64,
}

#[derive(Debug)]
struct Candidate {
    id: u64,
    title: String,
    price_cents: u32,
    campus_code: String,
}

fn campus_label(code: &str) -> &'static str {
    match code {
        "shahe" => "沙河",
        "xitucheng" => "西土城",
        _ => "其他地点",
    }
}

fn price_label(cents: u32) -> String {
    if cents == 0 {
        "免费".into()
    } else {
        format!("¥{}.{:02}", cents / 100, cents % 100)
    }
}

fn clip(value: &str, max: usize) -> String {
    if value.chars().count() <= max {
        value.to_owned()
    } else {
        value.chars().take(max).collect()
    }
}

fn summary(name: &str, candidate: &Candidate) -> String {
    clip(
        &format!(
            "找到符合「{}」的商品：{}，{}，{}",
            name,
            candidate.title,
            price_label(candidate.price_cents),
            campus_label(&candidate.campus_code)
        ),
        300,
    )
}

async fn upper_change_seq(app: &AppState) -> Result<u64, sqlx::Error> {
    Ok(sqlx::query_scalar::<_, u64>(
        "SELECT counter_value FROM system_counters WHERE counter_key='content_changes'",
    )
    .fetch_optional(&app.pool)
    .await?
    .unwrap_or(0))
}

async fn claim_due(app: &AppState) -> Result<Option<Claim>, sqlx::Error> {
    let mut tx = app.pool.begin().await?;
    let row = sqlx::query(
        "SELECT id,owner_id,config_version,interval_minutes,conditions,cursor_change_seq,needs_full_scan,retry_count,cycle_key FROM subscriptions WHERE state='active' AND next_due_at<=UTC_TIMESTAMP(6) AND (lease_until IS NULL OR lease_until<UTC_TIMESTAMP(6)) ORDER BY next_due_at,id LIMIT 1 FOR UPDATE SKIP LOCKED",
    )
    .fetch_optional(&mut *tx)
    .await?;
    let Some(row) = row else {
        tx.rollback().await?;
        return Ok(None);
    };
    let slot = sqlx::query(
        "SELECT slot_no FROM scheduler_slots WHERE (lease_until IS NULL OR lease_until<UTC_TIMESTAMP(6)) ORDER BY slot_no LIMIT 1 FOR UPDATE SKIP LOCKED",
    )
    .fetch_optional(&mut *tx)
    .await?;
    let Some(slot) = slot else {
        tx.rollback().await?;
        return Ok(None);
    };
    let id: u64 = row.get("id");
    let owner_id: u64 = row.get("owner_id");
    let config_version: u32 = row.get("config_version");
    let interval_minutes: u16 = row.get("interval_minutes");
    let conditions: Value = row.get("conditions");
    let cursor: u64 = row.get("cursor_change_seq");
    let full_scan: bool = row.get("needs_full_scan");
    let retry_count: u8 = row.get("retry_count");
    let cycle_key = row
        .get::<Option<String>, _>("cycle_key")
        .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
    let lease_token = uuid::Uuid::new_v4().to_string();
    let slot_no: u8 = slot.get("slot_no");
    let upper = upper_change_seq(app).await?;

    sqlx::query("UPDATE subscriptions SET lease_token=?,lease_until=DATE_ADD(UTC_TIMESTAMP(6),INTERVAL ? SECOND),cycle_key=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
        .bind(&lease_token)
        .bind(LEASE_SECONDS)
        .bind(&cycle_key)
        .bind(id)
        .execute(&mut *tx)
        .await?;
    sqlx::query("UPDATE scheduler_slots SET subscription_id=?,lease_token=?,lease_until=DATE_ADD(UTC_TIMESTAMP(6),INTERVAL ? SECOND) WHERE slot_no=?")
        .bind(id)
        .bind(&lease_token)
        .bind(LEASE_SECONDS)
        .bind(slot_no)
        .execute(&mut *tx)
        .await?;
    let run = match sqlx::query("INSERT INTO subscription_runs(subscription_id,cycle_key,attempt_no,config_version,lease_token,upper_change_seq,state,started_at) VALUES (?,?,?,?,?,?,'running',UTC_TIMESTAMP(6))")
        .bind(id)
        .bind(&cycle_key)
        .bind(retry_count)
        .bind(config_version)
        .bind(&lease_token)
        .bind(upper)
        .execute(&mut *tx)
        .await
    {
        Ok(run) => run,
        Err(error) => {
            tx.rollback().await?;
            tracing::warn!(error_kind = %error, "subscription run insert failed");
            return Ok(None);
        }
    };
    let run_id = run.last_insert_id();
    tx.commit().await?;
    Ok(Some(Claim {
        id,
        owner_id,
        config_version,
        interval_minutes,
        conditions,
        cursor,
        full_scan,
        lease_token,
        slot_no,
        upper,
        run_id,
    }))
}

async fn candidates(
    app: &AppState,
    claim: &Claim,
    conditions: &Conditions,
    full_scan: bool,
) -> Result<Vec<Candidate>, sqlx::Error> {
    let mut query = QueryBuilder::<MySql>::new(
        "SELECT g.id,g.title,g.price_cents,CAST(g.campus_code AS CHAR CHARACTER SET utf8mb4) AS campus_code FROM goods g JOIN users u ON u.id=g.seller_id",
    );
    if !full_scan {
        query
            .push(" JOIN (SELECT goods_id,MAX(change_seq) AS change_seq FROM content_changes WHERE kind='goods' AND change_seq>")
            .push_bind(claim.cursor)
            .push(" AND change_seq<=")
            .push_bind(claim.upper)
            .push(" GROUP BY goods_id) c ON c.goods_id=g.id");
    }
    query
        .push(" WHERE g.deleted_at IS NULL AND g.state='on_sale' AND g.moderation='clear' AND u.status='active' AND g.seller_id<>")
        .push_bind(claim.owner_id);
    conditions.append(&mut query, "g");
    query.push(" ORDER BY g.updated_at DESC,g.id DESC LIMIT 5000");
    let rows = query.build().fetch_all(&app.pool).await?;
    Ok(rows
        .iter()
        .map(|row| Candidate {
            id: row.get("id"),
            title: row.get("title"),
            price_cents: row.get("price_cents"),
            campus_code: row.get("campus_code"),
        })
        .collect())
}

async fn commit_matches(
    app: &AppState,
    claim: &Claim,
    candidates: &[Candidate],
    conditions: &Conditions,
    name: &str,
) -> Result<usize, RunFailure> {
    let mut tx = app
        .pool
        .begin()
        .await
        .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?;
    let owner = accounts::locked_user(&mut tx, claim.owner_id)
        .await
        .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?;
    if owner.status != "active" {
        return Err(RunFailure::cancelled("ACCOUNT_INACTIVE"));
    }
    let sub = sqlx::query(
        "SELECT state,config_version,lease_token,lease_until>UTC_TIMESTAMP(6) AS lease_valid FROM subscriptions WHERE id=? FOR UPDATE",
    )
    .bind(claim.id)
    .fetch_optional(&mut *tx)
    .await
    .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?
    .ok_or_else(|| RunFailure::cancelled("TASK_DELETED"))?;
    if sub.get::<String, _>("state") != "active"
        || sub.get::<u32, _>("config_version") != claim.config_version
        || sub.get::<Option<String>, _>("lease_token").as_deref() != Some(&claim.lease_token)
        || !sub.get::<bool, _>("lease_valid")
    {
        return Err(RunFailure::cancelled("LEASE_LOST"));
    }
    let slot = sqlx::query(
        "SELECT subscription_id,lease_token,lease_until>UTC_TIMESTAMP(6) AS lease_valid FROM scheduler_slots WHERE slot_no=? FOR UPDATE",
    )
    .bind(claim.slot_no)
    .fetch_optional(&mut *tx)
    .await
    .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?
    .ok_or_else(|| RunFailure::cancelled("SLOT_LOST"))?;
    if slot.get::<Option<u64>, _>("subscription_id") != Some(claim.id)
        || slot.get::<Option<String>, _>("lease_token").as_deref() != Some(&claim.lease_token)
        || !slot.get::<bool, _>("lease_valid")
    {
        return Err(RunFailure::cancelled("SLOT_LOST"));
    }

    let mut confirmed = Vec::new();
    if !candidates.is_empty() {
        let mut query = QueryBuilder::<MySql>::new(
            "SELECT g.id,g.title,g.price_cents,CAST(g.campus_code AS CHAR CHARACTER SET utf8mb4) AS campus_code FROM goods g JOIN users u ON u.id=g.seller_id WHERE g.id IN (",
        );
        let mut separated = query.separated(",");
        for candidate in candidates {
            separated.push_bind(candidate.id);
        }
        query
            .push(") AND g.deleted_at IS NULL AND g.state='on_sale' AND g.moderation='clear' AND u.status='active' AND g.seller_id<>")
            .push_bind(claim.owner_id);
        conditions.append(&mut query, "g");
        query.push(" FOR UPDATE");
        let rows = query
            .build()
            .fetch_all(&mut *tx)
            .await
            .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?;
        confirmed = rows
            .iter()
            .map(|row| Candidate {
                id: row.get("id"),
                title: row.get("title"),
                price_cents: row.get("price_cents"),
                campus_code: row.get("campus_code"),
            })
            .collect();
    }

    let mut created = 0usize;
    for candidate in &confirmed {
        let inserted = sqlx::query(
            "INSERT IGNORE INTO subscription_matches(subscription_id,goods_id,run_id) VALUES (?,?,?)",
        )
        .bind(claim.id)
        .bind(candidate.id)
        .bind(claim.run_id)
        .execute(&mut *tx)
        .await
        .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?;
        if inserted.rows_affected() != 1 {
            continue;
        }
        let match_id = inserted.last_insert_id();
        chat::notifications::create(
            &mut tx,
            claim.owner_id,
            "goods_match",
            "goods",
            Some(candidate.id),
            &summary(name, candidate),
            Some(match_id),
        )
        .await
        .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?;
        created += 1;
    }

    sqlx::query("UPDATE subscriptions SET cursor_change_seq=?,last_checked_at=UTC_TIMESTAMP(6),next_due_at=DATE_ADD(UTC_TIMESTAMP(6),INTERVAL ? MINUTE),needs_full_scan=FALSE,retry_count=0,cycle_key=NULL,last_error_code=NULL,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
        .bind(claim.upper)
        .bind(claim.interval_minutes)
        .bind(claim.id)
        .execute(&mut *tx)
        .await
        .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?;
    sqlx::query("UPDATE subscription_runs SET state='succeeded',finished_at=UTC_TIMESTAMP(6),error_code=NULL WHERE id=?")
        .bind(claim.run_id)
        .execute(&mut *tx)
        .await
        .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?;
    sqlx::query("UPDATE scheduler_slots SET subscription_id=NULL,lease_token=NULL,lease_until=NULL WHERE slot_no=? AND lease_token=?")
        .bind(claim.slot_no)
        .bind(&claim.lease_token)
        .execute(&mut *tx)
        .await
        .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?;
    tx.commit()
        .await
        .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?;
    Ok(created)
}

async fn finish_failure(app: &AppState, claim: &Claim, failure: &RunFailure) {
    let result = async {
        let mut tx = app.pool.begin().await?;
        let sub = sqlx::query(
            "SELECT state,config_version,lease_token,retry_count,cycle_key,lease_until>UTC_TIMESTAMP(6) AS lease_valid FROM subscriptions WHERE id=? FOR UPDATE",
        )
        .bind(claim.id)
        .fetch_optional(&mut *tx)
        .await?;
        if let Some(sub) = sub {
            let owned = sub.get::<String, _>("state") == "active"
                && sub.get::<u32, _>("config_version") == claim.config_version
                && sub.get::<Option<String>, _>("lease_token").as_deref()
                    == Some(&claim.lease_token);
            if owned && !failure.cancelled {
                let retry: u8 = sub.get("retry_count");
                if failure.retryable && retry < 3 {
                    let next = retry + 1;
                    let delay = match next {
                        1 => 1,
                        2 => 5,
                        _ => 15,
                    };
                    sqlx::query("UPDATE subscriptions SET retry_count=?,next_due_at=DATE_ADD(UTC_TIMESTAMP(6),INTERVAL ? MINUTE),last_error_code=?,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
                        .bind(next)
                        .bind(delay)
                        .bind(failure.code)
                        .bind(claim.id)
                        .execute(&mut *tx)
                        .await?;
                    sqlx::query("UPDATE subscription_runs SET state='retry_wait',finished_at=UTC_TIMESTAMP(6),error_code=? WHERE id=?")
                        .bind(failure.code)
                        .bind(claim.run_id)
                        .execute(&mut *tx)
                        .await?;
                } else {
                    sqlx::query("UPDATE subscriptions SET state='error',retry_count=3,next_due_at=NULL,last_error_code=?,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
                        .bind(failure.code)
                        .bind(claim.id)
                        .execute(&mut *tx)
                        .await?;
                    sqlx::query("UPDATE subscription_runs SET state='failed',finished_at=UTC_TIMESTAMP(6),error_code=? WHERE id=?")
                        .bind(failure.code)
                        .bind(claim.run_id)
                        .execute(&mut *tx)
                        .await?;
                }
            } else {
                if owned {
                    sqlx::query("UPDATE subscriptions SET lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
                        .bind(claim.id)
                        .execute(&mut *tx)
                        .await?;
                }
                sqlx::query("UPDATE subscription_runs SET state='cancelled',finished_at=UTC_TIMESTAMP(6),error_code=? WHERE id=?")
                    .bind(failure.code)
                    .bind(claim.run_id)
                    .execute(&mut *tx)
                    .await?;
            }
        } else {
            sqlx::query("UPDATE subscription_runs SET state='cancelled',finished_at=UTC_TIMESTAMP(6),error_code=? WHERE id=?")
                .bind(failure.code)
                .bind(claim.run_id)
                .execute(&mut *tx)
                .await?;
        }
        sqlx::query("UPDATE scheduler_slots SET subscription_id=NULL,lease_token=NULL,lease_until=NULL WHERE slot_no=? AND lease_token=?")
            .bind(claim.slot_no)
            .bind(&claim.lease_token)
            .execute(&mut *tx)
            .await?;
        tx.commit().await
    }
    .await;
    if result.is_err() {
        tracing::warn!(
            subscription_id = claim.id,
            run_id = claim.run_id,
            "subscription failure state was not saved"
        );
    }
}

async fn run_claim(app: AppState, claim: Claim) {
    let started = std::time::Instant::now();
    let conditions: Conditions = match serde_json::from_value(claim.conditions.clone()) {
        Ok(conditions) => conditions,
        Err(_) => {
            finish_failure(&app, &claim, &RunFailure::permanent("INVALID_CONDITIONS")).await;
            return;
        }
    };
    let name: String = sqlx::query_scalar("SELECT name FROM subscriptions WHERE id=?")
        .bind(claim.id)
        .fetch_optional(&app.pool)
        .await
        .ok()
        .flatten()
        .unwrap_or_else(|| "商品提醒".into());
    let full_scan = claim.full_scan || claim.upper < claim.cursor;
    let outcome = tokio::time::timeout(Duration::from_secs(RUN_SECONDS), async {
        let found = candidates(&app, &claim, &conditions, full_scan)
            .await
            .map_err(|_| RunFailure::transient("DEPENDENCY_UNAVAILABLE"))?;
        commit_matches(&app, &claim, &found, &conditions, &name).await
    })
    .await;
    match outcome {
        Ok(Ok(created)) => {
            tracing::info!(
                subscription_id = claim.id,
                run_id = claim.run_id,
                created,
                elapsed_ms = started.elapsed().as_millis() as u64,
                "subscription check completed"
            );
        }
        Ok(Err(failure)) => {
            if !failure.cancelled {
                tracing::warn!(
                    subscription_id = claim.id,
                    run_id = claim.run_id,
                    code = failure.code,
                    "subscription check failed"
                );
            }
            finish_failure(&app, &claim, &failure).await;
        }
        Err(_) => {
            tracing::warn!(
                subscription_id = claim.id,
                run_id = claim.run_id,
                "subscription check timed out"
            );
            finish_failure(&app, &claim, &RunFailure::transient("MATCH_TIMEOUT")).await;
        }
    }
}

async fn recover_stale(app: &AppState) -> Result<(), sqlx::Error> {
    let mut tx = app.pool.begin().await?;
    let rows = sqlx::query(
        "SELECT id,subscription_id,cycle_key,attempt_no FROM subscription_runs WHERE state='running' AND started_at<DATE_SUB(UTC_TIMESTAMP(6),INTERVAL ? SECOND) ORDER BY id LIMIT 100 FOR UPDATE SKIP LOCKED",
    )
    .bind(LEASE_SECONDS)
    .fetch_all(&mut *tx)
    .await?;
    for row in &rows {
        let run_id: u64 = row.get("id");
        let sid: u64 = row.get("subscription_id");
        sqlx::query("UPDATE subscription_runs SET state='failed',finished_at=UTC_TIMESTAMP(6),error_code='LEASE_EXPIRED' WHERE id=?")
            .bind(run_id)
            .execute(&mut *tx)
            .await?;
        let sub = sqlx::query("SELECT state,retry_count FROM subscriptions WHERE id=? FOR UPDATE")
            .bind(sid)
            .fetch_optional(&mut *tx)
            .await?;
        if let Some(sub) = sub
            && sub.get::<String, _>("state") == "active"
        {
            let retry: u8 = sub.get("retry_count");
            if retry < 3 {
                let next = retry + 1;
                let delay = match next {
                    1 => 1,
                    2 => 5,
                    _ => 15,
                };
                sqlx::query("UPDATE subscriptions SET retry_count=?,next_due_at=DATE_ADD(UTC_TIMESTAMP(6),INTERVAL ? MINUTE),last_error_code='LEASE_EXPIRED',lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
                    .bind(next)
                    .bind(delay)
                    .bind(sid)
                    .execute(&mut *tx)
                    .await?;
            } else {
                sqlx::query("UPDATE subscriptions SET state='error',retry_count=3,next_due_at=NULL,last_error_code='LEASE_EXPIRED',lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
                    .bind(sid)
                    .execute(&mut *tx)
                    .await?;
            }
        }
    }
    sqlx::query("UPDATE scheduler_slots SET subscription_id=NULL,lease_token=NULL,lease_until=NULL WHERE lease_until<UTC_TIMESTAMP(6)")
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    if !rows.is_empty() {
        tracing::warn!(count = rows.len(), "stale subscription runs recovered");
    }
    Ok(())
}

pub fn start_worker(app: AppState) {
    tokio::spawn(async move {
        if recover_stale(&app).await.is_err() {
            tracing::warn!("subscription recovery deferred");
        }
        let mut timer = tokio::time::interval(Duration::from_secs(5));
        timer.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
        let mut recovered_at = std::time::Instant::now();
        loop {
            timer.tick().await;
            if recovered_at.elapsed() >= Duration::from_secs(60) {
                recovered_at = std::time::Instant::now();
                if recover_stale(&app).await.is_err() {
                    tracing::warn!("subscription recovery deferred");
                }
            }
            for _ in 0..2 {
                match claim_due(&app).await {
                    Ok(Some(claim)) => {
                        let worker = app.clone();
                        tokio::spawn(async move { run_claim(worker, claim).await });
                    }
                    Ok(None) => break,
                    Err(error) => {
                        tracing::warn!(error_kind = %error, "subscription claim deferred");
                        break;
                    }
                }
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn conditions(value: Value) -> Conditions {
        serde_json::from_value(value).expect("conditions")
    }

    #[test]
    fn conditions_require_a_real_constraint() {
        let mut empty = conditions(json!({
            "schema_version":1,"min_price_cents":null,"max_price_cents":null,
            "campus_code":null,"category_id":null,"brand":null,"model":null,
            "min_condition":null,"required_attributes":{},"purpose":null
        }));
        assert!(empty.validate_shape().is_err());
        empty.max_price_cents = Some(250_000);
        assert!(empty.validate_shape().is_ok());
    }

    #[test]
    fn conditions_reject_price_order_and_unknown_attributes() {
        let mut bad = conditions(json!({
            "schema_version":1,"min_price_cents":300_000,"max_price_cents":200_000,
            "campus_code":null,"category_id":null,"brand":null,"model":null,
            "min_condition":null,"required_attributes":{},"purpose":null
        }));
        assert!(bad.validate_shape().is_err());
        bad.min_price_cents = Some(100);
        assert!(bad.validate_shape().is_ok());
        let unknown = json!({
            "schema_version":1,"min_price_cents":null,"max_price_cents":100,
            "campus_code":null,"category_id":null,"brand":null,"model":null,
            "min_condition":null,"required_attributes":{"camera":true},"purpose":null
        });
        assert!(serde_json::from_value::<Conditions>(unknown).is_err());
    }

    #[test]
    fn summary_is_bounded_and_uses_actual_facts() {
        let candidate = Candidate {
            id: 1,
            title: "二手平板".into(),
            price_cents: 180_000,
            campus_code: "shahe".into(),
        };
        let text = summary("学习平板", &candidate);
        assert!(text.contains("¥1800.00"));
        assert!(text.contains("沙河"));
        let long = summary(&"很长的任务名".repeat(60), &candidate);
        assert!(long.chars().count() <= 300);
    }
}

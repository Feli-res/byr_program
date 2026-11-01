use crate::{AppState, access::*, accounts::files, content, ok, state};
use salvo::prelude::*;
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::{Value, json};
use sqlx::{MySql, QueryBuilder, Row, Transaction, mysql::MySqlRow};

const COLUMNS: &str = "g.id,g.seller_id,g.category_id,CAST(g.campus_code AS CHAR CHARACTER SET utf8mb4) AS campus_code,g.title,g.description,g.brand,g.model,g.purpose,g.condition_code,g.price_cents,g.location_text,g.attributes,g.state,g.moderation,g.version,DATE_FORMAT(g.created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at,DATE_FORMAT(g.updated_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS updated_at,DATE_FORMAT(g.deleted_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS deleted_at,u.status AS seller_status,u.password_reset_required,JSON_OBJECT('id',CAST(u.id AS CHAR),'nickname',u.nickname,'bio',u.bio,'avatar_url',(SELECT CONCAT('/api/v1/files/',file_id,'/content') FROM file_bindings WHERE avatar_user_id=u.id AND kind='avatar')) AS seller";
pub(crate) const STATES: [&str; 4] = ["on_sale", "reserved", "sold", "off_shelf"];
pub(crate) const CAMPUSES: [&str; 3] = ["shahe", "xitucheng", "other"];

pub(crate) fn integer(
    req: &Request,
    name: &'static str,
    default: u64,
    min: u64,
    max: u64,
) -> AccountResult<u64> {
    let value = match req.query::<String>(name) {
        None => default,
        Some(raw) => {
            if raw.is_empty() || !raw.bytes().all(|b| b.is_ascii_digit()) {
                return Err(AccountError::validation(name, "请输入有效整数"));
            }
            raw.parse::<u64>()
                .map_err(|_| AccountError::validation(name, "整数超出允许范围"))?
        }
    };
    if !(min..=max).contains(&value) {
        return Err(AccountError::validation(name, "数值超出允许范围"));
    }
    Ok(value)
}
pub(crate) fn paging(req: &Request) -> AccountResult<(u64, u64)> {
    Ok((
        integer(req, "page", 1, 1, 1_000_000)?,
        integer(req, "page_size", 20, 1, 100)?,
    ))
}
pub(crate) fn like_pattern(q: &str) -> String {
    format!(
        "%{}%",
        q.replace('!', "!!").replace('%', "!%").replace('_', "!_")
    )
}
fn enum_value(value: &str, allowed: &[&str], field: &'static str) -> AccountResult<String> {
    if allowed.contains(&value) {
        Ok(value.into())
    } else {
        Err(AccountError::validation(field, "选项不正确"))
    }
}
pub(crate) fn next_version(version: u32) -> AccountResult<u32> {
    version.checked_add(1).ok_or_else(AccountError::conflict)
}
fn param(req: &Request) -> AccountResult<u64> {
    id(req
        .param::<String>("goods_id")
        .as_deref()
        .ok_or_else(AccountError::missing)?)
}

#[derive(Default)]
pub(crate) struct Filters {
    pub q: Option<String>,
    pub category: Option<u64>,
    pub campus: Option<String>,
    pub max_price: Option<u32>,
    pub brand: Option<String>,
    pub stylus_support: Option<bool>,
    pub min_condition: Option<String>,
    pub state: Option<String>,
}
impl Filters {
    pub(crate) fn parse(req: &Request) -> AccountResult<Self> {
        let q = req
            .query::<String>("q")
            .map(|s| field_text(&s, 1, 200, "q"))
            .transpose()?;
        let category = req
            .query::<String>("category_id")
            .map(|s| id(&s).map_err(|_| AccountError::validation("category_id", "类别编号不正确")))
            .transpose()?;
        let campus = req
            .query::<String>("campus_code")
            .map(|s| enum_value(&s, &CAMPUSES, "campus_code"))
            .transpose()?;
        let max_price = if req.query::<String>("max_price_cents").is_some() {
            Some(integer(req, "max_price_cents", 0, 0, 9999999)? as u32)
        } else {
            None
        };
        let brand = req
            .query::<String>("brand")
            .map(|s| field_text(&s, 1, 100, "brand"))
            .transpose()?;
        let stylus_support = match req.query::<String>("stylus_support").as_deref() {
            None => None,
            Some("true") => Some(true),
            Some("false") => Some(false),
            _ => {
                return Err(AccountError::validation(
                    "stylus_support",
                    "手写笔选项不正确",
                ));
            }
        };
        let min_condition = req
            .query::<String>("min_condition")
            .map(|s| enum_value(&s, &["new", "like_new", "good", "fair"], "min_condition"))
            .transpose()?;
        let state = req
            .query::<String>("state")
            .map(|s| enum_value(&s, &STATES, "state"))
            .transpose()?;
        Ok(Self {
            q,
            category,
            campus,
            max_price,
            brand,
            stylus_support,
            min_condition,
            state,
        })
    }
    pub(crate) fn has_goods_filter(&self) -> bool {
        self.category.is_some()
            || self.campus.is_some()
            || self.max_price.is_some()
            || self.brand.is_some()
            || self.stylus_support.is_some()
            || self.min_condition.is_some()
    }
    pub(crate) fn append(&self, q: &mut QueryBuilder<'_, MySql>, alias: &str, keyword: bool) {
        if let Some(category) = self.category {
            q.push(format!(" AND {alias}.category_id="))
                .push_bind(category);
        }
        if let Some(campus) = &self.campus {
            q.push(format!(" AND {alias}.campus_code="))
                .push_bind(campus.clone());
        }
        if let Some(price) = self.max_price {
            q.push(format!(" AND {alias}.price_cents<="))
                .push_bind(price);
        }
        if let Some(brand) = &self.brand {
            q.push(format!(" AND {alias}.brand="))
                .push_bind(brand.clone());
        }
        if let Some(support) = self.stylus_support {
            q.push(format!(
                " AND JSON_EXTRACT({alias}.attributes, '$.stylus_support') = CAST("
            ));
            q.push_bind(if support { "true" } else { "false" })
                .push(" AS JSON)");
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
        if keyword && let Some(text) = &self.q {
            q.push(format!(" AND CONCAT_WS(' ',{alias}.title,{alias}.description,{alias}.brand,{alias}.model,{alias}.purpose,{alias}.location_text) LIKE ")).push_bind(like_pattern(text)).push(" ESCAPE '!'");
        }
    }
}

fn filtered(select: &str, f: &Filters, mode: &str, viewer: u64) -> QueryBuilder<'static, MySql> {
    let mut q = QueryBuilder::new(format!(
        "SELECT {select} FROM goods g JOIN users u ON u.id=g.seller_id WHERE g.deleted_at IS NULL"
    ));
    match mode {
        "owner" => {
            q.push(" AND g.seller_id=").push_bind(viewer);
        }
        "admin" => {}
        _ => {
            q.push(" AND g.moderation='clear' AND g.state=")
                .push_bind(f.state.clone().unwrap_or_else(|| "on_sale".into()));
        }
    }
    if mode != "public"
        && let Some(state) = &f.state
    {
        q.push(" AND g.state=").push_bind(state.clone());
    }
    f.append(&mut q, "g", true);
    q
}

async fn dto(row: &MySqlRow, app: &AppState, viewer: u64, private: bool) -> AccountResult<Value> {
    let gid = row.get::<u64, _>("id");
    let restricted = row.get::<String, _>("moderation") != "clear";
    let deleted = row.get::<Option<String>, _>("deleted_at").is_some();
    let mut value = json!({"id":gid.to_string(),"seller":row.get::<Value,_>("seller"),"category_id":row.get::<u64,_>("category_id").to_string(),"campus_code":row.get::<String,_>("campus_code"),"title":row.get::<String,_>("title"),"description":row.get::<String,_>("description"),"brand":row.get::<Option<String>,_>("brand"),"model":row.get::<Option<String>,_>("model"),"purpose":row.get::<Option<String>,_>("purpose"),"condition_code":row.get::<String,_>("condition_code"),"price_cents":row.get::<u32,_>("price_cents"),"location_text":row.get::<String,_>("location_text"),"attributes":row.get::<Option<Value>,_>("attributes").unwrap_or_else(||json!({})),"state":row.get::<String,_>("state"),"images":files::goods_files(&app.pool,gid).await?,"version":row.get::<u32,_>("version"),"created_at":row.get::<String,_>("created_at"),"updated_at":row.get::<String,_>("updated_at"),"can_contact":!restricted&&!deleted&&viewer!=row.get::<u64,_>("seller_id")&&row.get::<String,_>("seller_status")=="active"&&!row.get::<bool,_>("password_reset_required")});
    if private {
        value["moderation"] = json!(row.get::<String, _>("moderation"));
        value["deleted_at"] = json!(row.get::<Option<String>, _>("deleted_at"));
    }
    Ok(value)
}
async fn read(req: &Request, app: &AppState, gid: u64, mode: &str) -> AccountResult<Value> {
    let identity = if mode == "public" {
        optional_identity(req, app).await?
    } else {
        Some(authenticate(req, app).await?)
    };
    let viewer = identity.as_ref().map(|i| i.user.id).unwrap_or(0);
    if mode == "admin" && identity.as_ref().unwrap().user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let sql =
        format!("SELECT {COLUMNS} FROM goods g JOIN users u ON u.id=g.seller_id WHERE g.id=?");
    let row = sqlx::query(&sql)
        .bind(gid)
        .fetch_optional(&app.pool)
        .await?
        .ok_or_else(AccountError::missing)?;
    let deleted = row.get::<Option<String>, _>("deleted_at").is_some();
    if (mode == "public" && (deleted || row.get::<String, _>("moderation") != "clear"))
        || (mode == "owner" && (deleted || viewer != row.get::<u64, _>("seller_id")))
    {
        return Err(AccountError::missing());
    }
    dto(&row, app, viewer, mode != "public").await
}
async fn list(req: &Request, app: &AppState, mode: &str) -> AccountResult<Value> {
    let (page, size) = paging(req)?;
    let f = Filters::parse(req)?;
    let identity = if mode == "public" {
        optional_identity(req, app).await?
    } else {
        Some(authenticate(req, app).await?)
    };
    let viewer = identity.as_ref().map(|i| i.user.id).unwrap_or(0);
    if mode == "admin" && identity.as_ref().unwrap().user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let total: i64 = filtered("COUNT(*)", &f, mode, viewer)
        .build_query_scalar()
        .fetch_one(&app.pool)
        .await?;
    let mut query = filtered(COLUMNS, &f, mode, viewer);
    query
        .push(" ORDER BY g.created_at DESC,g.id DESC LIMIT ")
        .push_bind(size)
        .push(" OFFSET ")
        .push_bind((page - 1) * size);
    let rows = query.build().fetch_all(&app.pool).await?;
    let mut items = Vec::new();
    for row in &rows {
        items.push(dto(row, app, viewer, mode == "admin").await?);
    }
    Ok(json!({"items":items,"total":total,"page":page,"page_size":size}))
}

fn some<'de, D: Deserializer<'de>, T: Deserialize<'de>>(d: D) -> Result<Option<T>, D::Error> {
    T::deserialize(d).map(Some)
}
fn nullable<'de, D: Deserializer<'de>, T: Deserialize<'de>>(
    d: D,
) -> Result<Option<Option<T>>, D::Error> {
    Option::<T>::deserialize(d).map(Some)
}
#[derive(Clone, Default, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Attributes {
    #[serde(
        default,
        skip_serializing_if = "Option::is_none",
        deserialize_with = "nullable"
    )]
    stylus_support: Option<Option<bool>>,
    #[serde(
        default,
        skip_serializing_if = "Option::is_none",
        deserialize_with = "nullable"
    )]
    storage_gb: Option<Option<u32>>,
}
impl Attributes {
    fn validate(&self) -> AccountResult<()> {
        if let Some(Some(storage)) = self.storage_gb
            && !(1..=100000).contains(&storage)
        {
            return Err(AccountError::validation(
                "attributes.storage_gb",
                "容量须在1～100000之间",
            ));
        }
        Ok(())
    }
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct NewGoods {
    category_id: String,
    campus_code: String,
    title: String,
    description: String,
    condition_code: String,
    price_cents: u32,
    location_text: String,
    image_file_ids: Vec<String>,
    brand: Option<String>,
    model: Option<String>,
    purpose: Option<String>,
    #[serde(default)]
    attributes: Attributes,
}
#[derive(Default, Deserialize)]
#[serde(deny_unknown_fields)]
struct EditGoods {
    version: u32,
    #[serde(default, deserialize_with = "some")]
    category_id: Option<String>,
    #[serde(default, deserialize_with = "some")]
    campus_code: Option<String>,
    #[serde(default, deserialize_with = "some")]
    title: Option<String>,
    #[serde(default, deserialize_with = "some")]
    description: Option<String>,
    #[serde(default, deserialize_with = "some")]
    condition_code: Option<String>,
    #[serde(default, deserialize_with = "some")]
    price_cents: Option<u32>,
    #[serde(default, deserialize_with = "some")]
    location_text: Option<String>,
    #[serde(default, deserialize_with = "some")]
    image_file_ids: Option<Vec<String>>,
    #[serde(default, deserialize_with = "nullable")]
    brand: Option<Option<String>>,
    #[serde(default, deserialize_with = "nullable")]
    model: Option<Option<String>>,
    #[serde(default, deserialize_with = "nullable")]
    purpose: Option<Option<String>>,
    #[serde(default, deserialize_with = "some")]
    attributes: Option<Attributes>,
}
fn optional_text(value: Option<String>, field: &'static str) -> AccountResult<Option<String>> {
    value
        .map(|s| field_text(&s, 0, 100, field))
        .transpose()
        .map(|v| v.filter(|s| !s.is_empty()))
}
fn validate_value(input: &mut NewGoods) -> AccountResult<u64> {
    let category = id(&input.category_id)
        .map_err(|_| AccountError::validation("category_id", "请选择有效类别"))?;
    input.title = field_text(&input.title, 2, 100, "title")?;
    input.description = field_text(&input.description, 1, 5000, "description")?;
    input.campus_code = enum_value(&input.campus_code, &CAMPUSES, "campus_code")?;
    input.condition_code = enum_value(
        &input.condition_code,
        &["new", "like_new", "good", "fair"],
        "condition_code",
    )?;
    input.location_text = field_text(
        &input.location_text,
        if input.campus_code == "other" { 1 } else { 0 },
        100,
        "location_text",
    )?;
    if input.price_cents > 9999999 {
        return Err(AccountError::validation(
            "price_cents",
            "价格须在0～99999.99元之间",
        ));
    }
    input.brand = optional_text(input.brand.take(), "brand")?;
    input.model = optional_text(input.model.take(), "model")?;
    input.purpose = optional_text(input.purpose.take(), "purpose")?;
    input.attributes.validate()?;
    Ok(category)
}
async fn dictionaries(
    tx: &mut Transaction<'_, MySql>,
    category: u64,
    campus: &str,
) -> AccountResult<()> {
    if sqlx::query("SELECT id FROM goods_categories WHERE id=? AND enabled=true FOR SHARE")
        .bind(category)
        .fetch_optional(&mut **tx)
        .await?
        .is_none()
    {
        return Err(AccountError::validation(
            "category_id",
            "类别不存在或已停用",
        ));
    }
    if sqlx::query("SELECT code FROM campuses WHERE code=? AND enabled=true FOR SHARE")
        .bind(campus)
        .fetch_optional(&mut **tx)
        .await?
        .is_none()
    {
        return Err(AccountError::validation(
            "campus_code",
            "校区不存在或已停用",
        ));
    }
    Ok(())
}
async fn locked(tx: &mut Transaction<'_, MySql>, gid: u64) -> AccountResult<MySqlRow> {
    let row=sqlx::query("SELECT id,seller_id,category_id,CAST(campus_code AS CHAR CHARACTER SET utf8mb4) AS campus_code,title,description,brand,model,purpose,condition_code,price_cents,location_text,attributes,state,moderation,version,deleted_at IS NOT NULL AS deleted FROM goods WHERE id=? FOR UPDATE").bind(gid).fetch_optional(&mut **tx).await?.ok_or_else(AccountError::missing)?;
    if row.get::<bool, _>("deleted") {
        return Err(AccountError::missing());
    }
    Ok(row)
}
fn owner_check(row: &MySqlRow, user: &User, version: u32) -> AccountResult<()> {
    if row.get::<u64, _>("seller_id") != user.id {
        return Err(AccountError::forbidden());
    }
    if row.get::<u32, _>("version") != version {
        return Err(AccountError::conflict());
    }
    Ok(())
}
fn state_conflict() -> AccountError {
    AccountError::new(
        StatusCode::CONFLICT,
        "STATE_CONFLICT",
        "商品当前状态不允许该操作，请重新读取",
    )
}
async fn write(req: &mut Request, app: &AppState, gid: Option<u64>) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    if let Some(gid) = gid {
        let input: EditGoods = parse(req).await?;
        let provided = input.category_id.is_some()
            || input.campus_code.is_some()
            || input.title.is_some()
            || input.description.is_some()
            || input.condition_code.is_some()
            || input.price_cents.is_some()
            || input.location_text.is_some()
            || input.image_file_ids.is_some()
            || input.brand.is_some()
            || input.model.is_some()
            || input.purpose.is_some()
            || input.attributes.is_some();
        if input.version == 0 || !provided {
            return Err(AccountError::validation(
                "version",
                "请提供版本和需要修改的内容",
            ));
        }
        let mut tx = app.pool.begin().await?;
        let user = lock_identity(&mut tx, &identity).await?;
        let old = locked(&mut tx, gid).await?;
        owner_check(&old, &user, input.version)?;
        if old.get::<String, _>("state") == "sold" || old.get::<String, _>("moderation") != "clear"
        {
            return Err(state_conflict());
        }
        let mut value = NewGoods {
            category_id: input
                .category_id
                .unwrap_or_else(|| old.get::<u64, _>("category_id").to_string()),
            campus_code: input.campus_code.unwrap_or_else(|| old.get("campus_code")),
            title: input.title.unwrap_or_else(|| old.get("title")),
            description: input.description.unwrap_or_else(|| old.get("description")),
            condition_code: input
                .condition_code
                .unwrap_or_else(|| old.get("condition_code")),
            price_cents: input.price_cents.unwrap_or_else(|| old.get("price_cents")),
            location_text: input
                .location_text
                .unwrap_or_else(|| old.get("location_text")),
            image_file_ids: input.image_file_ids.clone().unwrap_or_default(),
            brand: input.brand.unwrap_or_else(|| old.get("brand")),
            model: input.model.unwrap_or_else(|| old.get("model")),
            purpose: input.purpose.unwrap_or_else(|| old.get("purpose")),
            attributes: match input.attributes {
                Some(v) => v,
                None => serde_json::from_value(
                    old.get::<Option<Value>, _>("attributes")
                        .unwrap_or_else(|| json!({})),
                )
                .map_err(|_| AccountError::unavailable())?,
            },
        };
        let category = validate_value(&mut value)?;
        dictionaries(&mut tx, category, &value.campus_code).await?;
        if input.image_file_ids.is_some() {
            files::bind_goods(&mut tx, user.id, gid, &value.image_file_ids).await?;
        }
        let version = next_version(input.version)?;
        sqlx::query("UPDATE goods SET category_id=?,campus_code=?,title=?,description=?,brand=?,model=?,purpose=?,condition_code=?,price_cents=?,location_text=?,attributes=?,version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
            .bind(category).bind(value.campus_code).bind(value.title).bind(value.description).bind(value.brand).bind(value.model).bind(value.purpose).bind(value.condition_code).bind(value.price_cents).bind(value.location_text).bind(json!(value.attributes)).bind(version).bind(gid).execute(&mut *tx).await?;
        content::change(&mut tx, "goods", gid, version, "upsert").await?;
        tx.commit().await?;
        read(req, app, gid, "public").await
    } else {
        let mut input: NewGoods = parse(req).await?;
        let category = validate_value(&mut input)?;
        let mut tx = app.pool.begin().await?;
        let user = lock_identity(&mut tx, &identity).await?;
        dictionaries(&mut tx, category, &input.campus_code).await?;
        let saved=sqlx::query("INSERT INTO goods(seller_id,category_id,campus_code,title,description,brand,model,purpose,condition_code,price_cents,location_text,attributes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)")
            .bind(user.id).bind(category).bind(input.campus_code).bind(input.title).bind(input.description).bind(input.brand).bind(input.model).bind(input.purpose).bind(input.condition_code).bind(input.price_cents).bind(input.location_text).bind(json!(input.attributes)).execute(&mut *tx).await?;
        let gid = saved.last_insert_id();
        files::bind_goods(&mut tx, user.id, gid, &input.image_file_ids).await?;
        content::change(&mut tx, "goods", gid, 1, "upsert").await?;
        tx.commit().await?;
        read(req, app, gid, "public").await
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Version {
    version: u32,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct StateChange {
    version: u32,
    state: String,
}
pub(crate) fn legal_transition(old: &str, new: &str) -> bool {
    matches!(
        (old, new),
        ("on_sale", "reserved" | "sold" | "off_shelf")
            | ("reserved", "on_sale" | "sold" | "off_shelf")
            | ("off_shelf", "on_sale")
    )
}
async fn change_state(req: &mut Request, app: &AppState, gid: u64) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input: StateChange = parse(req).await?;
    enum_value(&input.state, &STATES, "state")?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    let old = locked(&mut tx, gid).await?;
    owner_check(&old, &user, input.version)?;
    if old.get::<String, _>("moderation") != "clear"
        || !legal_transition(&old.get::<String, _>("state"), &input.state)
    {
        return Err(state_conflict());
    }
    let version = next_version(input.version)?;
    sqlx::query("UPDATE goods SET state=?,version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?")
        .bind(input.state)
        .bind(version)
        .bind(gid)
        .execute(&mut *tx)
        .await?;
    content::change(&mut tx, "goods", gid, version, "upsert").await?;
    tx.commit().await?;
    read(req, app, gid, "public").await
}
async fn delete(req: &mut Request, app: &AppState, gid: u64) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input: Version = parse(req).await?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    let old = locked(&mut tx, gid).await?;
    owner_check(&old, &user, input.version)?;
    let version = next_version(input.version)?;
    sqlx::query("UPDATE goods SET deleted_at=UTC_TIMESTAMP(6),version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?").bind(version).bind(gid).execute(&mut *tx).await?;
    sqlx::query("UPDATE files f JOIN file_bindings b ON b.file_id=f.id SET f.state='cleanup_pending' WHERE b.goods_id=? AND f.state='attached'").bind(gid).execute(&mut *tx).await?;
    content::change(&mut tx, "goods", gid, version, "remove").await?;
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
async fn moderate(
    req: &mut Request,
    depot: &Depot,
    app: &AppState,
    gid: u64,
) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input: Moderation = parse(req).await?;
    let reason = reason(&input.reason)?;
    let mut tx = app.pool.begin().await?;
    let user = lock_identity(&mut tx, &identity).await?;
    if user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let old = locked(&mut tx, gid).await?;
    if old.get::<u32, _>("version") != input.version {
        return Err(AccountError::conflict());
    }
    let (moderation, state) = match input.action.as_str() {
        "restrict" => (
            "restricted",
            if old.get::<String, _>("state") == "sold" {
                "sold".to_owned()
            } else {
                "off_shelf".to_owned()
            },
        ),
        "release" => ("clear", old.get::<String, _>("state")),
        _ => {
            return Err(AccountError::validation(
                "action",
                "仅支持下架限制或解除限制",
            ));
        }
    };
    let version = next_version(input.version)?;
    sqlx::query(
        "UPDATE goods SET moderation=?,state=?,version=?,updated_at=UTC_TIMESTAMP(6) WHERE id=?",
    )
    .bind(moderation)
    .bind(&state)
    .bind(version)
    .bind(gid)
    .execute(&mut *tx)
    .await?;
    content::change(
        &mut tx,
        "goods",
        gid,
        version,
        if moderation == "clear" {
            "upsert"
        } else {
            "remove"
        },
    )
    .await?;
    sqlx::query("INSERT INTO audit_logs(actor_id,action,target_type,target_id,reason,safe_changes,request_id) VALUES (?,'goods.moderate','goods',?,?,?,?)").bind(user.id).bind(gid).bind(reason).bind(json!({"moderation":moderation,"state":state,"version":version})).bind(depot.get::<String>("request_id").expect("request id")).execute(&mut *tx).await?;
    let summary = if moderation == "restricted" {
        "你的商品已被管理员下架，请在我的商品查看。"
    } else {
        "你的商品管理限制已解除，可自行决定是否重新上架。"
    };
    crate::chat::notifications::create(
        &mut tx,
        old.get::<u64, _>("seller_id"),
        "system",
        "none",
        None,
        summary,
        None,
    )
    .await?;
    tx.commit().await?;
    Ok(json!({"ok":true}))
}
async fn dictionary(app: &AppState, campus: bool) -> AccountResult<Value> {
    if campus {
        let rows=sqlx::query("SELECT CAST(code AS CHAR CHARACTER SET utf8mb4) AS code,name,enabled FROM campuses WHERE enabled=true ORDER BY FIELD(code,'shahe','xitucheng','other')").fetch_all(&app.pool).await?;
        Ok(json!(rows.iter().map(|r|json!({"code":r.get::<String,_>("code"),"name":r.get::<String,_>("name"),"enabled":r.get::<bool,_>("enabled")})).collect::<Vec<_>>()))
    } else {
        let rows=sqlx::query("SELECT id,CAST(code AS CHAR CHARACTER SET utf8mb4) AS code,name,enabled FROM goods_categories WHERE enabled=true ORDER BY id").fetch_all(&app.pool).await?;
        Ok(json!(rows.iter().map(|r|json!({"id":r.get::<u64,_>("id").to_string(),"code":r.get::<String,_>("code"),"name":r.get::<String,_>("name"),"enabled":r.get::<bool,_>("enabled")})).collect::<Vec<_>>()))
    }
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
        ("GET", "/api/v1/campuses") => dictionary(app, true).await?,
        ("GET", "/api/v1/goods-categories") => dictionary(app, false).await?,
        ("GET", "/api/v1/goods") => list(req, app, "public").await?,
        ("POST", "/api/v1/goods") => {
            status = StatusCode::CREATED;
            write(req, app, None).await?
        }
        ("GET", "/api/v1/me/goods") => list(req, app, "owner").await?,
        ("GET", "/api/v1/admin/goods") => list(req, app, "admin").await?,
        _ => {
            let gid = param(req)?;
            if path.ends_with("/moderation") {
                moderate(req, depot, app, gid).await?
            } else if path.ends_with("/state") {
                change_state(req, app, gid).await?
            } else if method == "GET" {
                read(
                    req,
                    app,
                    gid,
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
                write(req, app, Some(gid)).await?
            } else {
                delete(req, app, gid).await?
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
        Ok((status, value)) => ok(res, depot, status, value),
        Err(error) => render_error(error, depot, res),
    }
}
pub fn routes() -> Router {
    Router::with_path("api/v1")
        .push(Router::with_path("goods-categories").get(dispatch))
        .push(Router::with_path("campuses").get(dispatch))
        .push(Router::with_path("goods").get(dispatch).post(dispatch))
        .push(
            Router::with_path("goods/{goods_id}")
                .get(dispatch)
                .patch(dispatch)
                .delete(dispatch),
        )
        .push(Router::with_path("goods/{goods_id}/state").patch(dispatch))
        .push(Router::with_path("me/goods").get(dispatch))
        .push(Router::with_path("me/goods/{goods_id}").get(dispatch))
        .push(Router::with_path("admin/goods").get(dispatch))
        .push(Router::with_path("admin/goods/{goods_id}").get(dispatch))
        .push(Router::with_path("admin/goods/{goods_id}/moderation").patch(dispatch))
}
pub(crate) async fn context(app: &AppState, gid: u64, viewer: u64) -> AccountResult<Option<Value>> {
    let sql = format!(
        "SELECT {COLUMNS} FROM goods g JOIN users u ON u.id=g.seller_id WHERE g.id=? AND g.deleted_at IS NULL AND g.moderation='clear'"
    );
    let row = sqlx::query(&sql)
        .bind(gid)
        .fetch_optional(&app.pool)
        .await?;
    match row {
        Some(row) => Ok(Some(dto(&row, app, viewer, false).await?)),
        None => Ok(None),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn sold_is_terminal_and_off_shelf_has_one_exit() {
        for state in STATES {
            assert!(!legal_transition("sold", state));
        }
        assert!(legal_transition("off_shelf", "on_sale"));
        assert!(!legal_transition("off_shelf", "sold"));
    }
    #[test]
    fn strict_fields_preserve_nullable_attributes() {
        assert!(
            serde_json::from_value::<EditGoods>(json!({"version":1,"price_cents":null})).is_err()
        );
        assert!(serde_json::from_value::<EditGoods>(json!({"version":1,"seller_id":"2"})).is_err());
        let value: EditGoods = serde_json::from_value(json!({"version":1,"brand":null})).unwrap();
        assert_eq!(value.brand, Some(None));
        assert!(serde_json::from_value::<Attributes>(json!({"unknown":true})).is_err());
    }
    #[test]
    fn wildcard_characters_are_literal() {
        assert_eq!(like_pattern("20%_!"), "%20!%!_!!%");
    }
}

mod access;
pub mod accounts;
mod forum;
use anyhow::{Context, Result, ensure};
use salvo::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sqlx::{MySqlPool, mysql::MySqlPoolOptions};
use std::{
    net::SocketAddr,
    sync::Arc,
    time::{Duration, Instant},
};
static MIGRATIONS: sqlx::migrate::Migrator = sqlx::migrate!("../../migrations");

#[derive(Clone)]
pub struct Settings {
    pub bind: SocketAddr,
    pub dev_tools: bool,
    pub web_origin: String,
    pub accounts: accounts::AccountSettings,
    database_url: String,
    redis_url: String,
}

impl Settings {
    pub fn from_env() -> Result<Self> {
        let bind = std::env::var("API_BIND")
            .unwrap_or_else(|_| "127.0.0.1:8080".into())
            .parse()
            .context("invalid API_BIND")?;
        let dev_tools = match std::env::var("DEV_TOOLS_ENABLED")
            .as_deref()
            .unwrap_or("false")
        {
            "true" => true,
            "false" => false,
            _ => anyhow::bail!("DEV_TOOLS_ENABLED must be true or false"),
        };
        let value = Self {
            accounts: accounts::AccountSettings::from_env()?,
            bind,
            dev_tools,
            web_origin: std::env::var("WEB_ORIGIN")
                .unwrap_or_else(|_| "http://localhost:3000".into()),
            database_url: std::env::var("DATABASE_URL").context("DATABASE_URL is required")?,
            redis_url: std::env::var("REDIS_URL").context("REDIS_URL is required")?,
        };
        value.validate()?;
        Ok(value)
    }

    fn validate(&self) -> Result<()> {
        ensure!(
            !self.dev_tools || self.bind.ip().is_loopback(),
            "development tools require a loopback API_BIND"
        );
        ensure!(
            self.web_origin.starts_with("http://") || self.web_origin.starts_with("https://"),
            "invalid WEB_ORIGIN"
        );
        ensure!(
            !self.web_origin.ends_with('/'),
            "WEB_ORIGIN must not end with a slash"
        );
        Ok(())
    }
}

#[derive(Clone)]
pub struct AppState {
    pub pool: MySqlPool,
    redis: redis::Client,
    pub settings: Settings,
}

impl AppState {
    pub fn new(settings: Settings) -> Result<Self> {
        settings.validate()?;
        let pool = MySqlPoolOptions::new()
            .max_connections(5)
            .acquire_timeout(Duration::from_secs(2))
            .after_connect(|connection, _| {
                Box::pin(async move {
                    sqlx::query("SET time_zone = '+00:00'")
                        .execute(connection)
                        .await?;
                    Ok(())
                })
            })
            .connect_lazy(&settings.database_url)
            .map_err(|_| anyhow::anyhow!("invalid database configuration"))?;
        let redis = redis::Client::open(settings.redis_url.as_str())
            .map_err(|_| anyhow::anyhow!("invalid Redis configuration"))?;
        Ok(Self {
            pool,
            redis,
            settings,
        })
    }
}

pub async fn migrate(pool: &MySqlPool) -> Result<()> {
    MIGRATIONS.run(pool).await?;
    Ok(())
}

#[derive(Clone)]
struct ContextState(Arc<AppState>);

#[handler]
async fn request_context(
    req: &mut Request,
    depot: &mut Depot,
    res: &mut Response,
    ctrl: &mut FlowCtrl,
) {
    let id = uuid::Uuid::new_v4().to_string();
    depot.insert("request_id", id.clone());
    res.add_header("X-Request-ID", id.as_str(), true).ok();
    res.add_header("Cache-Control", "no-store", true).ok();
    let started = Instant::now();
    ctrl.call_next(req, depot, res).await;
    if res.status_code == Some(StatusCode::NOT_FOUND) && res.body.is_none() {
        fail(
            res,
            depot,
            StatusCode::NOT_FOUND,
            "NOT_FOUND",
            "请求的内容不存在",
            false,
        );
    }
    tracing::info!(request_id=%id, method=%req.method(), path=%req.matched_path(), status=res.status_code.unwrap_or(StatusCode::OK).as_u16(), elapsed_ms=started.elapsed().as_millis() as u64, "request completed");
}

fn state(depot: &Depot) -> Arc<AppState> {
    depot
        .obtain::<ContextState>()
        .expect("state middleware")
        .0
        .clone()
}

fn ok(res: &mut Response, depot: &Depot, status: StatusCode, data: Value) {
    res.status_code(status);
    res.render(Json(
        json!({"data":data,"meta":{"request_id":depot.get::<String>("request_id").ok()}}),
    ));
}

fn fail(
    res: &mut Response,
    depot: &Depot,
    status: StatusCode,
    code: &str,
    message: &str,
    retryable: bool,
) {
    res.status_code(status);
    res.render(Json(json!({"error":{"code":code,"message":message,"fields":[],"retryable":retryable},"meta":{"request_id":depot.get::<String>("request_id").ok()}})));
}

#[handler]
async fn live(depot: &mut Depot, res: &mut Response) {
    ok(
        res,
        depot,
        StatusCode::OK,
        json!({"service":"youzhihui-api","alive":true}),
    );
}

#[handler]
async fn ready(depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    let database = sqlx::query_scalar::<_, i32>("SELECT 1")
        .fetch_one(&app.pool)
        .await
        .is_ok();
    let schema = if database {
        sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM _sqlx_migrations WHERE success=1")
            .fetch_one(&app.pool)
            .await
            .map(|n| n == MIGRATIONS.iter().count() as i64)
            .unwrap_or(false)
    } else {
        false
    };
    let cache = tokio::time::timeout(Duration::from_secs(2), async {
        let mut connection = app.redis.get_multiplexed_async_connection().await?;
        redis::cmd("PING")
            .query_async::<String>(&mut connection)
            .await
    })
    .await
    .map(|v| v.is_ok())
    .unwrap_or(false);
    if database && schema && cache {
        ok(
            res,
            depot,
            StatusCode::OK,
            json!({"ready":true,"mysql":true,"redis":true,"migrations":true}),
        );
    } else {
        fail(
            res,
            depot,
            StatusCode::SERVICE_UNAVAILABLE,
            "DEPENDENCY_UNAVAILABLE",
            "数据库、缓存或建表版本尚未就绪",
            true,
        );
    }
}

#[handler]
async fn dev_guard(req: &mut Request, depot: &mut Depot, res: &mut Response, ctrl: &mut FlowCtrl) {
    let app = state(depot);
    if !app.settings.dev_tools {
        fail(
            res,
            depot,
            StatusCode::NOT_FOUND,
            "NOT_FOUND",
            "请求的内容不存在",
            false,
        );
        ctrl.skip_rest();
        return;
    }
    if req
        .headers()
        .get("origin")
        .is_some_and(|origin| origin.to_str().ok() != Some(app.settings.web_origin.as_str()))
    {
        fail(
            res,
            depot,
            StatusCode::FORBIDDEN,
            "FORBIDDEN",
            "请求来源不允许",
            false,
        );
        ctrl.skip_rest();
        return;
    }
    ctrl.call_next(req, depot, res).await;
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct NewRecord {
    body: String,
}

#[derive(Serialize, sqlx::FromRow)]
struct DevRecord {
    id: String,
    body: String,
    created_at: String,
}

fn validate_body(body: &str) -> Option<String> {
    let body = body.trim();
    if body.is_empty() || body.chars().count() > 500 {
        None
    } else {
        Some(body.to_owned())
    }
}

#[handler]
async fn create_record(req: &mut Request, depot: &mut Depot, res: &mut Response) {
    if req
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .map(|v| v.split(';').next().unwrap_or("").trim())
        != Some("application/json")
    {
        fail(
            res,
            depot,
            StatusCode::UNSUPPORTED_MEDIA_TYPE,
            "UNSUPPORTED_FILE_TYPE",
            "请使用 JSON 提交内容",
            false,
        );
        return;
    }
    let payload = match req.parse_json_with_max_size::<NewRecord>(8192).await {
        Ok(payload) => payload,
        Err(_) => {
            fail(
                res,
                depot,
                StatusCode::BAD_REQUEST,
                "INVALID_JSON",
                "提交内容格式不正确",
                false,
            );
            return;
        }
    };
    let Some(body) = validate_body(&payload.body) else {
        fail(
            res,
            depot,
            StatusCode::UNPROCESSABLE_ENTITY,
            "VALIDATION_FAILED",
            "请填写 1～500 字的内容",
            false,
        );
        return;
    };
    let app = state(depot);
    match sqlx::query("INSERT INTO dev_records(body) VALUES (?)")
        .bind(&body)
        .execute(&app.pool)
        .await
    {
        Ok(saved) => ok(
            res,
            depot,
            StatusCode::CREATED,
            json!({"id":saved.last_insert_id().to_string(),"body":body}),
        ),
        Err(error) => {
            tracing::warn!(request_id=?depot.get::<String>("request_id").ok(), error_kind=%error, "development record write failed");
            fail(
                res,
                depot,
                StatusCode::SERVICE_UNAVAILABLE,
                "DEPENDENCY_UNAVAILABLE",
                "暂时无法保存，请稍后重试",
                true,
            );
        }
    }
}

#[handler]
async fn list_records(depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    let result = sqlx::query_as::<_, DevRecord>("SELECT CAST(id AS CHAR) AS id, body, DATE_FORMAT(created_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS created_at FROM dev_records ORDER BY id DESC LIMIT 20").fetch_all(&app.pool).await;
    match result {
        Ok(items) => ok(res, depot, StatusCode::OK, json!({"items":items})),
        Err(_) => fail(
            res,
            depot,
            StatusCode::SERVICE_UNAVAILABLE,
            "DEPENDENCY_UNAVAILABLE",
            "暂时无法读取，请稍后重试",
            true,
        ),
    }
}

pub fn app(state: AppState) -> Service {
    let context = ContextState(Arc::new(state));
    let router = Router::new()
        .hoop(request_context)
        .hoop(salvo::affix_state::inject(context))
        .push(accounts::routes())
        .push(forum::routes())
        .push(Router::with_path("health/live").get(live))
        .push(Router::with_path("health/ready").get(ready))
        .push(
            Router::with_path("api/dev/records")
                .hoop(dev_guard)
                .get(list_records)
                .post(create_record),
        );
    Service::new(router)
}

#[cfg(test)]
mod tests {
    use super::*;
    use salvo::test::{ResponseExt, TestClient};

    fn settings(dev_tools: bool) -> Settings {
        Settings {
            bind: "127.0.0.1:8080".parse().unwrap(),
            dev_tools,
            web_origin: "http://localhost:3000".into(),
            accounts: accounts::AccountSettings::testing(),
            database_url: "mysql://unavailable:unavailable@127.0.0.1:1/unavailable".into(),
            redis_url: "redis://127.0.0.1:1/".into(),
        }
    }

    #[test]
    fn body_limits_count_characters_and_reject_whitespace() {
        assert!(validate_body(" \n\t").is_none());
        assert!(validate_body(&"邮".repeat(500)).is_some());
        assert!(validate_body(&"邮".repeat(501)).is_none());
        assert_eq!(validate_body(" 校园 "), Some("校园".into()));
    }

    #[test]
    fn development_tools_cannot_listen_publicly() {
        let mut config = settings(true);
        config.bind = "0.0.0.0:8080".parse().unwrap();
        assert!(config.validate().is_err());
        config.dev_tools = false;
        assert!(config.validate().is_ok());
    }

    #[tokio::test]
    async fn liveness_does_not_need_database() {
        let service = app(AppState::new(settings(false)).unwrap());
        let mut response = TestClient::get("http://localhost/health/live")
            .send(&service)
            .await;
        assert_eq!(response.status_code, Some(StatusCode::OK));
        assert!(
            uuid::Uuid::parse_str(
                response.take_json::<Value>().await.unwrap()["meta"]["request_id"]
                    .as_str()
                    .unwrap()
            )
            .is_ok()
        );
    }

    #[tokio::test]
    async fn dev_routes_disabled_by_default_and_origin_checked() {
        let disabled = app(AppState::new(settings(false)).unwrap());
        let response = TestClient::get("http://localhost/api/dev/records")
            .send(&disabled)
            .await;
        assert_eq!(response.status_code, Some(StatusCode::NOT_FOUND));
        let enabled = app(AppState::new(settings(true)).unwrap());
        let response = TestClient::get("http://localhost/api/dev/records")
            .add_header("Origin", "https://unrelated.example", true)
            .send(&enabled)
            .await;
        assert_eq!(response.status_code, Some(StatusCode::FORBIDDEN));
    }
}

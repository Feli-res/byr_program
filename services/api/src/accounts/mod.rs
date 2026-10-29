pub(crate) mod files;
pub(crate) mod security;

use crate::{AppState, fail, ok, state};
use chrono::SecondsFormat;
use salvo::prelude::*;
use serde::{Deserialize, de::DeserializeOwned};
use serde_json::{Value, json};
use sqlx::{MySql, MySqlPool, Row, Transaction};
use std::{collections::HashSet, path::PathBuf, sync::Arc};

pub use files::cleanup_files;

#[derive(Clone)]
pub struct AccountSettings {
    pub secret: String,
    pub secure_cookie: bool,
    pub uploads: PathBuf,
    pub proxy_key: Option<String>,
}
impl AccountSettings {
    pub fn from_env() -> anyhow::Result<Self> {
        let secret = std::env::var("AUTH_SECRET").unwrap_or_default();
        anyhow::ensure!(
            secret.len() >= 64 && secret.bytes().all(|v| v.is_ascii_hexdigit()),
            "AUTH_SECRET must contain at least 64 random hexadecimal characters; run Prepare-Dev.ps1"
        );
        let origin = std::env::var("WEB_ORIGIN").unwrap_or_else(|_| "http://localhost:3000".into());
        let secure = std::env::var("COOKIE_SECURE").unwrap_or_else(|_| "false".into());
        anyhow::ensure!(
            secure == "true" || secure == "false",
            "COOKIE_SECURE must be true or false"
        );
        let secure_cookie = secure == "true";
        anyhow::ensure!(
            secure_cookie
                || origin == "http://localhost:3000"
                || origin.starts_with("http://localhost:")
                || origin.starts_with("http://127.0.0.1:"),
            "HTTP cookies are allowed only for explicit local development origins"
        );
        anyhow::ensure!(
            !secure_cookie || origin.starts_with("https://"),
            "Secure cookies require an HTTPS WEB_ORIGIN"
        );
        let uploads = std::env::var_os("UPLOAD_ROOT")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(".local/uploads"));
        security::warmup();
        let proxy_key = std::env::var("TRUSTED_PROXY_KEY")
            .ok()
            .filter(|v| !v.is_empty());
        anyhow::ensure!(
            proxy_key
                .as_ref()
                .is_none_or(|v| v.len() >= 64 && v.bytes().all(|b| b.is_ascii_hexdigit())),
            "TRUSTED_PROXY_KEY must contain at least 64 hexadecimal characters"
        );
        Ok(Self {
            proxy_key,
            secret,
            secure_cookie,
            uploads,
        })
    }
    #[cfg(test)]
    pub fn testing() -> Self {
        Self {
            proxy_key: None,
            secret: "a".repeat(64),
            secure_cookie: false,
            uploads: std::env::temp_dir().join("byr-unit-upload-unused"),
        }
    }
}

pub type AccountResult<T> = Result<T, AccountError>;
#[derive(Debug)]
pub struct AccountError {
    pub(crate) status: StatusCode,
    pub(crate) code: &'static str,
    pub(crate) message: &'static str,
    pub(crate) field: Option<&'static str>,
    pub(crate) retry_after: Option<u64>,
}
impl AccountError {
    pub(crate) fn new(status: StatusCode, code: &'static str, message: &'static str) -> Self {
        Self {
            status,
            code,
            message,
            field: None,
            retry_after: None,
        }
    }
    pub(crate) fn validation(field: &'static str, message: &'static str) -> Self {
        let mut e = Self::new(
            StatusCode::UNPROCESSABLE_ENTITY,
            "VALIDATION_FAILED",
            message,
        );
        e.field = Some(field);
        e
    }
    pub(crate) fn auth() -> Self {
        Self::new(
            StatusCode::UNAUTHORIZED,
            "AUTH_REQUIRED",
            "请先登录，或重新登录后再试",
        )
    }
    pub(crate) fn forbidden() -> Self {
        Self::new(StatusCode::FORBIDDEN, "FORBIDDEN", "没有执行这项操作的权限")
    }
    pub(crate) fn missing() -> Self {
        Self::new(StatusCode::NOT_FOUND, "NOT_FOUND", "内容不存在或不可访问")
    }
    pub(crate) fn conflict() -> Self {
        Self::new(
            StatusCode::CONFLICT,
            "VERSION_CONFLICT",
            "资料已经变化，请重新读取后再修改",
        )
    }
    pub(crate) fn unavailable() -> Self {
        Self::new(
            StatusCode::SERVICE_UNAVAILABLE,
            "DEPENDENCY_UNAVAILABLE",
            "服务暂时不可用，请稍后重试",
        )
    }
    pub(crate) fn busy() -> Self {
        Self::rate(2)
    }
    pub(crate) fn rate(seconds: u64) -> Self {
        let mut e = Self::new(
            StatusCode::TOO_MANY_REQUESTS,
            "RATE_LIMITED",
            "尝试次数过多，请按提示稍后再试",
        );
        e.retry_after = Some(seconds.max(1));
        e
    }
}
impl From<sqlx::Error> for AccountError {
    fn from(error: sqlx::Error) -> Self {
        // Log only static column names / error categories, never SQL, bound values or secrets.
        match &error {
            sqlx::Error::ColumnDecode { index, .. } => {
                tracing::warn!(column=%index,category="column_decode","account storage unavailable")
            }
            sqlx::Error::ColumnNotFound(column) => {
                tracing::warn!(%column,category="column_missing","account storage unavailable")
            }
            sqlx::Error::Database(database) => {
                tracing::warn!(code=?database.code(),category="database","account storage unavailable")
            }
            sqlx::Error::PoolTimedOut => {
                tracing::warn!(category = "pool_timeout", "account storage unavailable")
            }
            _ => tracing::warn!(
                category = "storage_or_connection",
                "account storage unavailable"
            ),
        }
        Self::unavailable()
    }
}

#[derive(Clone, sqlx::FromRow)]
pub(crate) struct User {
    pub(crate) id: u64,
    pub(crate) account_norm: String,
    pub(crate) password_hash: String,
    pub(crate) nickname: String,
    pub(crate) bio: String,
    pub(crate) role: String,
    pub(crate) status: String,
    pub(crate) password_reset_required: bool,
    pub(crate) used_file_bytes: u64,
    pub(crate) version: u32,
}
const USER_COLUMNS: &str = "id,CAST(account_norm AS CHAR CHARACTER SET utf8mb4) AS account_norm,CAST(password_hash AS CHAR CHARACTER SET utf8mb4) AS password_hash,nickname,bio,role,status,password_reset_required,used_file_bytes,version";

pub(crate) async fn user(pool: &MySqlPool, id: u64) -> AccountResult<User> {
    sqlx::query_as(&format!("SELECT {USER_COLUMNS} FROM users WHERE id=?"))
        .bind(id)
        .fetch_optional(pool)
        .await?
        .ok_or_else(AccountError::missing)
}
pub(crate) async fn locked_user(tx: &mut Transaction<'_, MySql>, id: u64) -> AccountResult<User> {
    sqlx::query_as(&format!(
        "SELECT {USER_COLUMNS} FROM users WHERE id=? FOR UPDATE"
    ))
    .bind(id)
    .fetch_optional(&mut **tx)
    .await?
    .ok_or_else(AccountError::missing)
}
fn active(user: &User) -> AccountResult<()> {
    if user.status != "active" {
        return Err(AccountError::new(
            StatusCode::FORBIDDEN,
            "ACCOUNT_BANNED",
            "账号已被封禁，请联系管理员",
        ));
    }
    if user.password_reset_required {
        return Err(AccountError::new(
            StatusCode::FORBIDDEN,
            "PASSWORD_RESET_REQUIRED",
            "请使用管理员提供的凭据先重置密码",
        ));
    }
    Ok(())
}

fn cookie(req: &Request, name: &str) -> Option<String> {
    let value = req.headers().get("cookie")?.to_str().ok()?;
    let values = value
        .split(';')
        .filter_map(|part| part.trim().split_once('='))
        .filter(|(key, _)| *key == name)
        .map(|(_, v)| v)
        .collect::<Vec<_>>();
    (values.len() == 1).then(|| values[0].to_owned())
}
fn set_cookie(
    res: &mut Response,
    config: &AccountSettings,
    name: &str,
    value: &str,
    max_age: u64,
    http_only: bool,
) {
    let value = format!(
        "{name}={value}; Path=/; Max-Age={max_age}; SameSite=Lax{}{}",
        if http_only { "; HttpOnly" } else { "" },
        if config.secure_cookie { "; Secure" } else { "" }
    );
    res.add_header("Set-Cookie", value, false).ok();
}
fn clear_login(res: &mut Response, config: &AccountSettings) {
    set_cookie(res, config, "byr_session", "", 0, true);
    set_cookie(res, config, "byr_csrf", "", 0, false);
}
fn csrf_context(req: &Request) -> Option<String> {
    if let Some(token) = cookie(req, "byr_session").filter(|v| security::token_valid(v)) {
        return Some(format!("session:{token}"));
    }
    cookie(req, "byr_anon")
        .filter(|v| security::token_valid(v))
        .map(|v| format!("anonymous:{v}"))
}
pub(crate) fn csrf_check(req: &Request, app: &AppState) -> AccountResult<()> {
    let valid_origin = req.headers().get("origin").and_then(|v| v.to_str().ok())
        == Some(app.settings.web_origin.as_str());
    let header = req
        .headers()
        .get("x-csrf-token")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let valid = valid_origin
        && cookie(req, "byr_csrf").as_deref() == Some(header)
        && csrf_context(req).is_some_and(|context| {
            security::csrf_valid(&app.settings.accounts.secret, &context, header)
        });
    if valid {
        Ok(())
    } else {
        Err(AccountError::new(
            StatusCode::FORBIDDEN,
            "CSRF_INVALID",
            "请求保护已失效，请刷新页面后重试",
        ))
    }
}
pub(crate) fn iso(seconds: u64) -> String {
    chrono::DateTime::from_timestamp(seconds as i64, 0)
        .expect("generated timestamp")
        .to_rfc3339_opts(SecondsFormat::Secs, true)
}
fn csrf(req: &Request, res: &mut Response, app: &AppState) -> Value {
    if csrf_context(req).is_none() {
        set_cookie(
            res,
            &app.settings.accounts,
            "byr_anon",
            &security::random_token(),
            604800,
            true,
        );
    }
    let context = csrf_context(req).unwrap_or_else(|| {
        // Read the newly set anonymous value without trusting any client-provided replacement.
        let header = res
            .headers()
            .get_all("set-cookie")
            .iter()
            .filter_map(|v| v.to_str().ok())
            .find(|v| v.starts_with("byr_anon="))
            .expect("new anonymous cookie");
        format!(
            "anonymous:{}",
            header
                .split(';')
                .next()
                .unwrap()
                .trim_start_matches("byr_anon=")
        )
    });
    let token = cookie(req, "byr_csrf")
        .filter(|v| security::csrf_valid(&app.settings.accounts.secret, &context, v))
        .unwrap_or_else(|| security::csrf_token(&app.settings.accounts.secret, &context));
    set_cookie(res, &app.settings.accounts, "byr_csrf", &token, 3600, false);
    let expiry = token
        .split('.')
        .next()
        .and_then(|v| v.parse::<u64>().ok())
        .expect("generated CSRF expiry");
    json!({"csrf_token":token,"expires_at":iso(expiry)})
}

pub(crate) struct Identity {
    pub(crate) user: User,
    pub(crate) session_id: u64,
    pub(crate) expires: String,
}
pub(crate) async fn authenticate(req: &Request, app: &AppState) -> AccountResult<Identity> {
    let token = cookie(req, "byr_session")
        .filter(|v| security::token_valid(v))
        .ok_or_else(AccountError::auth)?;
    let row=sqlx::query("SELECT id,user_id,DATE_FORMAT(expires_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS expiry FROM sessions WHERE token_hash=? AND revoked_at IS NULL AND expires_at>UTC_TIMESTAMP(6)")
        .bind(security::digest(&token)).fetch_optional(&app.pool).await?.ok_or_else(AccountError::auth)?;
    let user = user(&app.pool, row.try_get("user_id")?).await?;
    active(&user)?;
    Ok(Identity {
        user,
        session_id: row.try_get("id")?,
        expires: row.try_get("expiry")?,
    })
}
pub(crate) async fn lock_identity(
    tx: &mut Transaction<'_, MySql>,
    identity: &Identity,
) -> AccountResult<User> {
    let user = locked_user(tx, identity.user.id).await?;
    active(&user)?;
    let valid=sqlx::query_scalar::<_,i64>("SELECT COUNT(*) FROM sessions WHERE id=? AND user_id=? AND revoked_at IS NULL AND expires_at>UTC_TIMESTAMP(6)").bind(identity.session_id).bind(user.id).fetch_one(&mut **tx).await?;
    if valid != 1 {
        return Err(AccountError::auth());
    }
    Ok(user)
}
async fn board_ids(pool: &MySqlPool, id: u64) -> AccountResult<Vec<String>> {
    Ok(sqlx::query_scalar::<_, u64>(
        "SELECT board_id FROM board_moderators WHERE user_id=? ORDER BY board_id",
    )
    .bind(id)
    .fetch_all(pool)
    .await?
    .into_iter()
    .map(|v| v.to_string())
    .collect())
}
pub(crate) async fn public_user(pool: &MySqlPool, u: &User) -> AccountResult<Value> {
    let avatar = sqlx::query_scalar::<_, u64>(
        "SELECT file_id FROM file_bindings WHERE avatar_user_id=? AND kind='avatar'",
    )
    .bind(u.id)
    .fetch_optional(pool)
    .await?;
    Ok(
        json!({"id":u.id.to_string(),"nickname":u.nickname,"bio":u.bio,"avatar_url":avatar.map(|id|format!("/api/v1/files/{id}/content"))}),
    )
}
async fn me(app: &AppState, identity: &Identity) -> AccountResult<Value> {
    let u = &identity.user;
    let mut value = public_user(&app.pool, u).await?;
    value.as_object_mut().unwrap().extend(json!({"account":u.account_norm,"role":u.role,"board_ids":board_ids(&app.pool,u.id).await?,"version":u.version,"used_file_bytes":u.used_file_bytes,"file_quota_bytes":209715200,"session_expires_at":identity.expires}).as_object().unwrap().clone());
    Ok(value)
}
async fn admin_user(pool: &MySqlPool, u: &User) -> AccountResult<Value> {
    Ok(
        json!({"id":u.id.to_string(),"nickname":u.nickname,"role":u.role,"status":u.status,"password_reset_required":u.password_reset_required,"board_ids":board_ids(pool,u.id).await?,"version":u.version}),
    )
}
async fn parse<T: DeserializeOwned>(req: &mut Request) -> AccountResult<T> {
    if req
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.split(';').next())
        .map(str::trim)
        != Some("application/json")
    {
        return Err(AccountError::new(
            StatusCode::UNSUPPORTED_MEDIA_TYPE,
            "UNSUPPORTED_FILE_TYPE",
            "请使用 JSON 提交内容",
        ));
    }
    req.parse_json_with_max_size(8192).await.map_err(|_| {
        AccountError::new(
            StatusCode::BAD_REQUEST,
            "INVALID_JSON",
            "提交格式不正确，或包含不允许的字段",
        )
    })
}
pub(crate) fn id(value: &str) -> AccountResult<u64> {
    if value.starts_with('0') || value.len() > 20 || !value.bytes().all(|b| b.is_ascii_digit()) {
        return Err(AccountError::missing());
    }
    value
        .parse::<u64>()
        .ok()
        .filter(|v| *v > 0)
        .ok_or_else(AccountError::missing)
}
pub(crate) fn field_text(
    value: &str,
    min: usize,
    max: usize,
    field: &'static str,
) -> AccountResult<String> {
    let value = value.trim();
    if !(min..=max).contains(&value.chars().count()) {
        return Err(AccountError::validation(field, "文字长度不符合要求"));
    }
    Ok(value.to_owned())
}
pub(crate) fn reason(value: &str) -> AccountResult<String> {
    field_text(value, 1, 1000, "reason")
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Registration {
    pub account: String,
    pub nickname: String,
    pub password: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Login {
    account: String,
    password: String,
}

async fn register(req: &mut Request, app: &AppState) -> AccountResult<Value> {
    let input: Registration = parse(req).await?;
    let account = security::account(&input.account).ok_or_else(|| {
        AccountError::validation(
            "account",
            "账号为 4～24 位英文字母、数字或下划线，首位须为字母，区分大小写",
        )
    })?;
    let nickname = field_text(&input.nickname, 2, 20, "nickname")?;
    let password = security::hash_password(input.password).await?;
    let result =
        sqlx::query("INSERT INTO users(account_norm,password_hash,nickname) VALUES (?,?,?)")
            .bind(account)
            .bind(password)
            .bind(nickname)
            .execute(&app.pool)
            .await;
    let result = match result {
        Ok(v) => v,
        Err(sqlx::Error::Database(e)) if e.is_unique_violation() => {
            return Err(AccountError::new(
                StatusCode::CONFLICT,
                "ACCOUNT_TAKEN",
                "账号已存在，请换一个账号",
            ));
        }
        Err(_) => return Err(AccountError::unavailable()),
    };
    public_user(&app.pool, &user(&app.pool, result.last_insert_id()).await?).await
}

// Only the private gateway possessing the server-only key may supply a client IP.
fn trusted_client_ip(
    key: Option<&str>,
    supplied: Option<&str>,
    ip: Option<&str>,
) -> Option<std::net::IpAddr> {
    let (expected, actual) = (key?, supplied?);
    if expected.len() != actual.len()
        || expected
            .bytes()
            .zip(actual.bytes())
            .fold(0u8, |d, (a, b)| d | (a ^ b))
            != 0
    {
        return None;
    }
    ip?.parse().ok()
}
fn login_keys(req: &Request, account: &str, app: &AppState) -> Vec<Vec<u8>> {
    let header = |name| req.headers().get(name).and_then(|v| v.to_str().ok());
    let forwarded = trusted_client_ip(
        app.settings.accounts.proxy_key.as_deref(),
        header("x-yzh-proxy-key"),
        header("x-yzh-client-ip"),
    );
    let peer = forwarded
        .map(|a| a.to_string())
        .or_else(|| req.remote_addr().as_ipv4().map(|a| a.ip().to_string()))
        .or_else(|| req.remote_addr().as_ipv6().map(|a| a.ip().to_string()))
        .unwrap_or_else(|| "local-client".into());
    let mut keys = vec![
        security::digest(&format!("account:{account}")),
        security::digest(&format!("ip:{peer}")),
    ];
    keys.sort();
    keys
}
async fn login_limits(app: &AppState, keys: &[Vec<u8>], failure: bool) -> AccountResult<()> {
    let mut tx = app.pool.begin().await?;
    for key in keys {
        sqlx::query("INSERT INTO auth_login_limits(key_hash,window_started_at) VALUES (?,UTC_TIMESTAMP(6)) ON DUPLICATE KEY UPDATE key_hash=key_hash").bind(key).execute(&mut *tx).await?;
        let row=sqlx::query("SELECT failures, TIMESTAMPDIFF(SECOND,UTC_TIMESTAMP(6),locked_until) AS wait_seconds, TIMESTAMPDIFF(SECOND,window_started_at,UTC_TIMESTAMP(6)) AS window_age FROM auth_login_limits WHERE key_hash=? FOR UPDATE").bind(key).fetch_one(&mut *tx).await?;
        let wait: Option<i64> = row.try_get("wait_seconds")?;
        if wait.unwrap_or(0) > 0 {
            return Err(AccountError::rate(wait.unwrap() as u64));
        }
        let age: i64 = row.try_get("window_age")?;
        if age >= 900 || wait.is_some() {
            sqlx::query("UPDATE auth_login_limits SET failures=0,window_started_at=UTC_TIMESTAMP(6),locked_until=NULL WHERE key_hash=?").bind(key).execute(&mut *tx).await?;
        }
        if failure {
            sqlx::query("UPDATE auth_login_limits SET failures=failures+1,locked_until=IF(failures>=5,DATE_ADD(UTC_TIMESTAMP(6),INTERVAL 15 MINUTE),NULL) WHERE key_hash=?").bind(key).execute(&mut *tx).await?;
        }
    }
    tx.commit().await?;
    Ok(())
}
async fn login(req: &mut Request, res: &mut Response, app: &AppState) -> AccountResult<Value> {
    let input: Login = parse(req).await?;
    let account = security::account(&input.account)
        .ok_or_else(|| AccountError::validation("account", "账号格式不正确"))?;
    if !security::password_valid(&input.password) {
        return Err(AccountError::validation("password", "密码为 8～64 个字符"));
    }
    let keys = login_keys(req, &account, app);
    login_limits(app, &keys, false).await?;
    let found = sqlx::query_as::<_, User>(&format!(
        "SELECT {USER_COLUMNS} FROM users WHERE account_norm=?"
    ))
    .bind(account)
    .fetch_optional(&app.pool)
    .await?;
    let hash = found.as_ref().map(|v| v.password_hash.clone());
    let verified = security::verify_password(input.password, hash.clone()).await?;
    if !verified || found.is_none() {
        login_limits(app, &keys, true).await?;
        return Err(AccountError::new(
            StatusCode::UNAUTHORIZED,
            "INVALID_CREDENTIALS",
            "账号或密码不正确",
        ));
    }
    login_limits(app, &keys, false).await?;
    let found = found.unwrap();
    let mut tx = app.pool.begin().await?;
    let current = locked_user(&mut tx, found.id).await?;
    active(&current)?;
    if Some(&current.password_hash) != hash.as_ref() {
        return Err(AccountError::auth());
    }
    let token = security::random_token();
    let saved=sqlx::query("INSERT INTO sessions(user_id,token_hash,expires_at) VALUES (?,?,DATE_ADD(UTC_TIMESTAMP(6),INTERVAL 7 DAY))").bind(current.id).bind(security::digest(&token)).execute(&mut *tx).await?;
    let expires: String = sqlx::query_scalar(
        "SELECT DATE_FORMAT(expires_at,'%Y-%m-%dT%H:%i:%s.%fZ') FROM sessions WHERE id=?",
    )
    .bind(saved.last_insert_id())
    .fetch_one(&mut *tx)
    .await?;
    tx.commit().await?;
    let current = me(
        app,
        &Identity {
            user: current,
            session_id: saved.last_insert_id(),
            expires: expires.clone(),
        },
    )
    .await?;
    set_cookie(
        res,
        &app.settings.accounts,
        "byr_session",
        &token,
        604800,
        true,
    );
    set_cookie(res, &app.settings.accounts, "byr_csrf", "", 0, false);
    Ok(json!({"user":current,"expires_at":expires}))
}

fn present<'de, D: serde::Deserializer<'de>>(
    deserializer: D,
) -> Result<Option<Option<String>>, D::Error> {
    Option::<String>::deserialize(deserializer).map(Some)
}
fn non_null<'de, D: serde::Deserializer<'de>>(deserializer: D) -> Result<Option<String>, D::Error> {
    String::deserialize(deserializer).map(Some)
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Profile {
    #[serde(default, deserialize_with = "non_null")]
    nickname: Option<String>,
    #[serde(default, deserialize_with = "non_null")]
    bio: Option<String>,
    #[serde(default, deserialize_with = "present")]
    avatar_file_id: Option<Option<String>>,
    version: u32,
}

async fn update_profile(req: &mut Request, app: &AppState) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input: Profile = parse(req).await?;
    let nickname = input
        .nickname
        .as_deref()
        .map(|v| field_text(v, 2, 20, "nickname"))
        .transpose()?;
    let bio = input
        .bio
        .as_deref()
        .map(|v| field_text(v, 0, 300, "bio"))
        .transpose()?;
    let avatar = input
        .avatar_file_id
        .as_ref()
        .map(|v| v.as_ref().map(|v| id(v)).transpose())
        .transpose()?;
    let mut tx = app.pool.begin().await?;
    let u = lock_identity(&mut tx, &identity).await?;
    if u.version != input.version {
        return Err(AccountError::conflict());
    }
    if let Some(new_avatar) = avatar {
        files::bind_avatar(&mut tx, u.id, new_avatar).await?;
    }
    sqlx::query("UPDATE users SET nickname=?,bio=?,version=version+1 WHERE id=?")
        .bind(nickname.unwrap_or(u.nickname))
        .bind(bio.unwrap_or(u.bio))
        .bind(u.id)
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    me(app, &authenticate(req, app).await?).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ChangePassword {
    current_password: String,
    new_password: String,
}
async fn change_password(
    req: &mut Request,
    res: &mut Response,
    app: &AppState,
) -> AccountResult<Value> {
    let identity = authenticate(req, app).await?;
    let input: ChangePassword = parse(req).await?;
    if !security::password_valid(&input.current_password)
        || !security::verify_password(
            input.current_password,
            Some(identity.user.password_hash.clone()),
        )
        .await?
    {
        return Err(AccountError::validation("current_password", "原密码不正确"));
    }
    let hash = security::hash_password(input.new_password).await?;
    let mut tx = app.pool.begin().await?;
    let u = lock_identity(&mut tx, &identity).await?;
    if u.password_hash != identity.user.password_hash {
        return Err(AccountError::conflict());
    }
    sqlx::query("UPDATE users SET password_hash=?,version=version+1 WHERE id=?")
        .bind(hash)
        .bind(u.id)
        .execute(&mut *tx)
        .await?;
    revoke_sessions(&mut tx, u.id, "password_changed").await?;
    tx.commit().await?;
    clear_login(res, &app.settings.accounts);
    Ok(json!({"ok":true}))
}
async fn revoke_sessions(
    tx: &mut Transaction<'_, MySql>,
    id: u64,
    reason: &str,
) -> AccountResult<()> {
    sqlx::query(
        "UPDATE sessions SET revoked_at=UTC_TIMESTAMP(6),revocation_reason=? WHERE user_id=? AND revoked_at IS NULL",
    )
    .bind(reason)
    .bind(id)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

async fn admin_lock(tx: &mut Transaction<'_, MySql>) -> AccountResult<()> {
    sqlx::query("SELECT lock_key FROM system_locks WHERE lock_key='administrators' FOR UPDATE")
        .fetch_one(&mut **tx)
        .await?;
    Ok(())
}
async fn audit(
    tx: &mut Transaction<'_, MySql>,
    actor: u64,
    target: u64,
    action: &str,
    reason: &str,
    changes: Value,
    depot: &Depot,
) -> AccountResult<()> {
    sqlx::query("INSERT INTO audit_logs(actor_id,action,target_type,target_id,reason,safe_changes,request_id) VALUES (?,?,'user',?,?,?,?)")
        .bind(actor).bind(action).bind(target).bind(reason).bind(changes).bind(depot.get::<String>("request_id").expect("request id")).execute(&mut **tx).await?;
    Ok(())
}
async fn protect_last_admin(tx: &mut Transaction<'_, MySql>, u: &User) -> AccountResult<()> {
    if u.role == "admin" && u.status == "active" && !u.password_reset_required {
        let count:i64=sqlx::query_scalar("SELECT COUNT(*) FROM users WHERE role='admin' AND status='active' AND password_reset_required=false").fetch_one(&mut **tx).await?;
        if count <= 1 {
            return Err(AccountError::new(
                StatusCode::CONFLICT,
                "STATE_CONFLICT",
                "必须保留至少一位可用管理员",
            ));
        }
    }
    Ok(())
}
async fn require_admin(req: &Request, app: &AppState) -> AccountResult<Identity> {
    let identity = authenticate(req, app).await?;
    if identity.user.role != "admin" {
        return Err(AccountError::forbidden());
    }
    Ok(identity)
}
async fn list_users(req: &Request, app: &AppState) -> AccountResult<Value> {
    require_admin(req, app).await?;
    let page = req.query::<u64>("page").unwrap_or(1);
    let size = req.query::<u64>("page_size").unwrap_or(20);
    if page == 0 || !(1..=100).contains(&size) || page > 1_000_000 {
        return Err(AccountError::validation("page", "分页参数不正确"));
    }
    let rows = sqlx::query_as::<_, User>(&format!(
        "SELECT {USER_COLUMNS} FROM users ORDER BY id DESC LIMIT ? OFFSET ?"
    ))
    .bind(size)
    .bind((page - 1) * size)
    .fetch_all(&app.pool)
    .await?;
    let total: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM users")
        .fetch_one(&app.pool)
        .await?;
    let mut items = vec![];
    for row in rows {
        items.push(admin_user(&app.pool, &row).await?);
    }
    Ok(json!({"items":items,"page":page,"page_size":size,"total":total}))
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct StatusChange {
    status: String,
    version: u32,
    reason: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RoleChange {
    role: String,
    board_ids: Vec<String>,
    version: u32,
    reason: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ResetIssue {
    version: u32,
    reason: String,
}

async fn admin_change(
    req: &mut Request,
    depot: &Depot,
    app: &AppState,
    kind: &str,
) -> AccountResult<Value> {
    let identity = require_admin(req, app).await?;
    let target = id(req
        .param::<String>("user_id")
        .as_deref()
        .ok_or_else(AccountError::missing)?)?;
    let payload: Value = parse(req).await?;
    let mut tx = app.pool.begin().await?;
    admin_lock(&mut tx).await?;
    let actor = lock_identity(&mut tx, &identity).await?;
    if actor.role != "admin" {
        return Err(AccountError::forbidden());
    }
    let u = locked_user(&mut tx, target).await?;
    let invalid = || {
        AccountError::new(
            StatusCode::BAD_REQUEST,
            "INVALID_JSON",
            "提交格式不正确，或包含不允许的字段",
        )
    };
    match kind {
        "status" => {
            let p: StatusChange = serde_json::from_value(payload).map_err(|_| invalid())?;
            let reason = reason(&p.reason)?;
            if p.version != u.version {
                return Err(AccountError::conflict());
            }
            if !["active", "banned"].contains(&p.status.as_str()) {
                return Err(AccountError::validation("status", "状态不正确"));
            }
            if p.status == "banned" {
                protect_last_admin(&mut tx, &u).await?;
                revoke_sessions(&mut tx, u.id, "banned").await?;
                sqlx::query("UPDATE subscriptions SET state='paused',config_version=config_version+1,lease_token=NULL,lease_until=NULL WHERE owner_id=? AND state='active'").bind(u.id).execute(&mut *tx).await?;
            }
            sqlx::query("UPDATE users SET status=?,version=version+1 WHERE id=?")
                .bind(&p.status)
                .bind(u.id)
                .execute(&mut *tx)
                .await?;
            audit(
                &mut tx,
                actor.id,
                u.id,
                "user.status",
                &reason,
                json!({"status":p.status}),
                depot,
            )
            .await?;
        }
        "role" => {
            let p: RoleChange = serde_json::from_value(payload).map_err(|_| invalid())?;
            let reason = reason(&p.reason)?;
            if p.version != u.version {
                return Err(AccountError::conflict());
            }
            if !["user", "moderator", "admin"].contains(&p.role.as_str())
                || (p.role != "moderator" && !p.board_ids.is_empty())
            {
                return Err(AccountError::validation("role", "角色与板块授权不匹配"));
            }
            let ids = p
                .board_ids
                .iter()
                .map(|v| id(v))
                .collect::<AccountResult<Vec<_>>>()?;
            if ids.len() > 100 || ids.iter().collect::<HashSet<_>>().len() != ids.len() {
                return Err(AccountError::validation(
                    "board_ids",
                    "板块授权重复或数量过多",
                ));
            }
            if p.role != "admin" {
                protect_last_admin(&mut tx, &u).await?;
            }
            for board in &ids {
                let exists: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM boards WHERE id=?")
                    .bind(board)
                    .fetch_one(&mut *tx)
                    .await?;
                if exists != 1 {
                    return Err(AccountError::validation("board_ids", "板块不存在"));
                }
            }
            sqlx::query("DELETE FROM board_moderators WHERE user_id=?")
                .bind(u.id)
                .execute(&mut *tx)
                .await?;
            for board in &ids {
                sqlx::query("INSERT INTO board_moderators(board_id,user_id) VALUES (?,?)")
                    .bind(board)
                    .bind(u.id)
                    .execute(&mut *tx)
                    .await?;
            }
            sqlx::query("UPDATE users SET role=?,version=version+1 WHERE id=?")
                .bind(&p.role)
                .bind(u.id)
                .execute(&mut *tx)
                .await?;
            audit(
                &mut tx,
                actor.id,
                u.id,
                "user.role",
                &reason,
                json!({"role":p.role,"board_ids":p.board_ids}),
                depot,
            )
            .await?;
        }
        "password-reset" => {
            let p: ResetIssue = serde_json::from_value(payload).map_err(|_| invalid())?;
            let reason = reason(&p.reason)?;
            if p.version != u.version {
                return Err(AccountError::conflict());
            }
            if actor.id == u.id {
                return Err(AccountError::validation(
                    "user_id",
                    "请使用本人修改密码功能",
                ));
            }
            protect_last_admin(&mut tx, &u).await?;
            let credential = security::random_token();
            sqlx::query("UPDATE password_resets SET revoked_at=UTC_TIMESTAMP(6) WHERE user_id=? AND consumed_at IS NULL AND revoked_at IS NULL").bind(u.id).execute(&mut *tx).await?;
            sqlx::query("INSERT INTO password_resets(user_id,issued_by,credential_hash,expires_at) VALUES (?,?,?,DATE_ADD(UTC_TIMESTAMP(6),INTERVAL 30 MINUTE))").bind(u.id).bind(actor.id).bind(security::digest(&credential)).execute(&mut *tx).await?;
            sqlx::query(
                "UPDATE users SET password_reset_required=true,version=version+1 WHERE id=?",
            )
            .bind(u.id)
            .execute(&mut *tx)
            .await?;
            revoke_sessions(&mut tx, u.id, "password_reset").await?;
            audit(
                &mut tx,
                actor.id,
                u.id,
                "user.password-reset",
                &reason,
                json!({"password_reset_required":true}),
                depot,
            )
            .await?;
            tx.commit().await?;
            return Ok(
                json!({"credential":credential,"expires_at":iso(security::now()+1800),"user_id":u.id.to_string()}),
            );
        }
        _ => return Err(AccountError::missing()),
    }
    tx.commit().await?;
    admin_user(&app.pool, &user(&app.pool, target).await?).await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ResetComplete {
    credential: String,
    new_password: String,
}
async fn complete_reset(
    req: &mut Request,
    res: &mut Response,
    app: &AppState,
) -> AccountResult<Value> {
    let p: ResetComplete = parse(req).await?;
    if !security::token_valid(&p.credential) {
        return Err(AccountError::validation(
            "credential",
            "重置凭据无效或已过期",
        ));
    }
    let digest = security::digest(&p.credential);
    let target=sqlx::query_scalar::<_,u64>("SELECT user_id FROM password_resets WHERE credential_hash=? AND consumed_at IS NULL AND revoked_at IS NULL AND expires_at>UTC_TIMESTAMP(6)").bind(&digest).fetch_optional(&app.pool).await?.ok_or_else(||AccountError::validation("credential","重置凭据无效或已过期"))?;
    let hash = security::hash_password(p.new_password).await?;
    let mut tx = app.pool.begin().await?;
    let u = locked_user(&mut tx, target).await?;
    if u.status != "active" {
        return Err(AccountError::forbidden());
    }
    let reset=sqlx::query_scalar::<_,u64>("SELECT id FROM password_resets WHERE credential_hash=? AND consumed_at IS NULL AND revoked_at IS NULL AND expires_at>UTC_TIMESTAMP(6) FOR UPDATE").bind(digest).fetch_optional(&mut *tx).await?.ok_or_else(||AccountError::validation("credential","重置凭据无效或已过期"))?;
    sqlx::query("UPDATE password_resets SET consumed_at=UTC_TIMESTAMP(6) WHERE id=?")
        .bind(reset)
        .execute(&mut *tx)
        .await?;
    sqlx::query("UPDATE users SET password_hash=?,password_reset_required=false,version=version+1 WHERE id=?").bind(hash).bind(target).execute(&mut *tx).await?;
    revoke_sessions(&mut tx, target, "password_reset").await?;
    tx.commit().await?;
    clear_login(res, &app.settings.accounts);
    Ok(json!({"ok":true}))
}

pub async fn initialize_admin(pool: &MySqlPool, input: Registration) -> anyhow::Result<()> {
    let account = security::account(&input.account)
        .ok_or_else(|| anyhow::anyhow!("invalid administrator account"))?;
    let nickname = field_text(&input.nickname, 2, 20, "nickname")
        .map_err(|_| anyhow::anyhow!("invalid nickname"))?;
    let hash = security::hash_password(input.password)
        .await
        .map_err(|_| anyhow::anyhow!("invalid password or password service busy"))?;
    let mut tx = pool.begin().await?;
    admin_lock(&mut tx)
        .await
        .map_err(|_| anyhow::anyhow!("administrator lock unavailable"))?;
    let count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM users WHERE role='admin'")
        .fetch_one(&mut *tx)
        .await?;
    anyhow::ensure!(
        count == 0,
        "an administrator already exists; initialization is disabled"
    );
    let result = sqlx::query(
        "INSERT INTO users(account_norm,password_hash,nickname,role) VALUES (?,?,?,'admin')",
    )
    .bind(account)
    .bind(hash)
    .bind(nickname)
    .execute(&mut *tx)
    .await?;
    let rid = uuid::Uuid::new_v4().to_string();
    sqlx::query("INSERT INTO audit_logs(actor_id,action,target_type,target_id,reason,safe_changes,request_id) VALUES (?,'user.bootstrap','user',?,'Local administrator initialization',JSON_OBJECT('role','admin'),?)").bind(result.last_insert_id()).bind(result.last_insert_id()).bind(rid).execute(&mut *tx).await?;
    tx.commit().await?;
    Ok(())
}

enum Reply {
    Json(StatusCode, Value),
    Bytes(String, Vec<u8>),
}
async fn action(
    req: &mut Request,
    depot: &Depot,
    res: &mut Response,
    app: Arc<AppState>,
) -> AccountResult<Reply> {
    let method = req.method().as_str().to_owned();
    let path = req.uri().path().to_owned();
    if !["GET", "HEAD"].contains(&method.as_str()) {
        csrf_check(req, &app)?;
    }
    if [
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/reset-password",
    ]
    .contains(&path.as_str())
        && cookie(req, "byr_session").is_some()
    {
        match authenticate(req, &app).await {
            Ok(_) => {
                return Err(AccountError::new(
                    StatusCode::FORBIDDEN,
                    "FORBIDDEN",
                    "请先退出当前账号",
                ));
            }
            Err(error) if error.status == StatusCode::UNAUTHORIZED => {}
            Err(error) => return Err(error),
        }
    }
    let mut status = StatusCode::OK;
    let value = match (method.as_str(), path.as_str()) {
        ("GET", "/api/v1/csrf") => csrf(req, res, &app),
        ("POST", "/api/v1/auth/register") => {
            status = StatusCode::CREATED;
            register(req, &app).await?
        }
        ("POST", "/api/v1/auth/login") => login(req, res, &app).await?,
        ("POST", "/api/v1/auth/logout") => {
            let identity = authenticate(req, &app).await?;
            let mut tx = app.pool.begin().await?;
            lock_identity(&mut tx, &identity).await?;
            sqlx::query("UPDATE sessions SET revoked_at=UTC_TIMESTAMP(6),revocation_reason='logout' WHERE id=?")
                .bind(identity.session_id)
                .execute(&mut *tx)
                .await?;
            tx.commit().await?;
            clear_login(res, &app.settings.accounts);
            json!({"ok":true})
        }
        ("GET", "/api/v1/me") => me(&app, &authenticate(req, &app).await?).await?,
        ("PATCH", "/api/v1/me") => update_profile(req, &app).await?,
        ("POST", "/api/v1/me/password") => change_password(req, res, &app).await?,
        ("POST", "/api/v1/auth/reset-password") => complete_reset(req, res, &app).await?,
        ("GET", "/api/v1/me/file-quota") => {
            let identity = authenticate(req, &app).await?;
            json!({"used_bytes":identity.user.used_file_bytes,"quota_bytes":209715200})
        }
        ("POST", "/api/v1/files") => {
            status = StatusCode::CREATED;
            files::upload(req, &app).await?
        }
        ("GET", "/api/v1/boards") => {
            let page = req.query::<u64>("page").unwrap_or(1);
            let size = req.query::<u64>("page_size").unwrap_or(20);
            if page == 0 || !(1..=100).contains(&size) || page > 1_000_000 {
                return Err(AccountError::validation("page", "分页参数不正确"));
            }
            let rows=sqlx::query("SELECT id,name,description,enabled,version FROM boards WHERE enabled=true ORDER BY id LIMIT ? OFFSET ?").bind(size).bind((page-1)*size).fetch_all(&app.pool).await?;
            let total: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM boards WHERE enabled=true")
                .fetch_one(&app.pool)
                .await?;
            json!({"items":rows.iter().map(|r|json!({"id":r.get::<u64,_>("id").to_string(),"name":r.get::<String,_>("name"),"description":r.get::<String,_>("description"),"enabled":r.get::<bool,_>("enabled"),"version":r.get::<u32,_>("version")})).collect::<Vec<_>>(),"page":page,"page_size":size,"total":total})
        }
        ("GET", "/api/v1/admin/users") => list_users(req, &app).await?,
        _ if path.starts_with("/api/v1/admin/users/") => {
            let kind = path.rsplit('/').next().unwrap_or("");
            admin_change(req, depot, &app, kind).await?
        }
        _ if path.starts_with("/api/v1/files/") && path.ends_with("/content") => {
            let (mime, bytes) = files::read(req, &app).await?;
            return Ok(Reply::Bytes(mime, bytes));
        }
        _ if path.starts_with("/api/v1/files/") && method == "DELETE" => {
            files::delete(req, &app).await?
        }
        _ => return Err(AccountError::missing()),
    };
    Ok(Reply::Json(status, value))
}
#[handler]
async fn dispatch(req: &mut Request, depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    match action(req, depot, res, app).await {
        Ok(Reply::Json(status, value)) => ok(res, depot, status, value),
        Ok(Reply::Bytes(mime, bytes)) => {
            res.add_header("Content-Type", &mime, true).ok();
            res.add_header("X-Content-Type-Options", "nosniff", true)
                .ok();
            res.add_header("Cache-Control", "private, no-cache", true)
                .ok();
            if mime == "application/pdf" {
                res.add_header(
                    "Content-Disposition",
                    "attachment; filename=attachment.pdf",
                    true,
                )
                .ok();
                res.add_header(
                    "Content-Security-Policy",
                    "sandbox; default-src 'none'",
                    true,
                )
                .ok();
            }
            res.status_code(StatusCode::OK);
            res.write_body(bytes).ok();
        }
        Err(e) => render_error(e, depot, res),
    }
}

pub(crate) fn render_error(e: AccountError, depot: &Depot, res: &mut Response) {
    if e.status == StatusCode::UNAUTHORIZED
        || ["ACCOUNT_BANNED", "PASSWORD_RESET_REQUIRED"].contains(&e.code)
    {
        clear_login(res, &state(depot).settings.accounts);
    }
    if let Some(seconds) = e.retry_after {
        res.add_header("Retry-After", seconds.to_string(), true)
            .ok();
    }
    if let Some(field) = e.field {
        res.status_code(e.status);
        res.render(Json(json!({"error":{"code":e.code,"message":e.message,"fields":[{"path":field,"message":e.message}],"retryable":false},"meta":{"request_id":depot.get::<String>("request_id").ok()}})));
    } else {
        fail(
            res,
            depot,
            e.status,
            e.code,
            e.message,
            e.status == StatusCode::SERVICE_UNAVAILABLE,
        );
    }
}

pub fn routes() -> Router {
    Router::with_path("api/v1")
        .push(Router::with_path("csrf").get(dispatch))
        .push(Router::with_path("auth/register").post(dispatch))
        .push(Router::with_path("auth/login").post(dispatch))
        .push(Router::with_path("auth/logout").post(dispatch))
        .push(Router::with_path("auth/reset-password").post(dispatch))
        .push(Router::with_path("me").get(dispatch).patch(dispatch))
        .push(Router::with_path("me/password").post(dispatch))
        .push(Router::with_path("me/file-quota").get(dispatch))
        .push(Router::with_path("files").post(dispatch))
        .push(Router::with_path("files/{file_id}/content").get(dispatch))
        .push(Router::with_path("files/{file_id}").delete(dispatch))
        .push(Router::with_path("boards").get(dispatch))
        .push(Router::with_path("admin/users").get(dispatch))
        .push(Router::with_path("admin/users/{user_id}/role").patch(dispatch))
        .push(Router::with_path("admin/users/{user_id}/status").patch(dispatch))
        .push(Router::with_path("admin/users/{user_id}/password-reset").post(dispatch))
}

#[cfg(test)]
mod contract_tests {
    use super::*;
    #[test]
    fn profile_null_is_allowed_only_for_explicit_avatar_removal() {
        assert!(serde_json::from_value::<Profile>(json!({"version":1,"nickname":null})).is_err());
        assert!(serde_json::from_value::<Profile>(json!({"version":1,"bio":null})).is_err());
        let remove =
            serde_json::from_value::<Profile>(json!({"version":1,"avatar_file_id":null})).unwrap();
        assert_eq!(remove.avatar_file_id, Some(None));
        let unchanged = serde_json::from_value::<Profile>(json!({"version":1})).unwrap();
        assert_eq!(unchanged.avatar_file_id, None);
    }
}

#[cfg(test)]
mod proxy_tests {
    use super::trusted_client_ip;
    #[test]
    fn gateway_identity_requires_secret_and_single_valid_ip() {
        assert_eq!(
            trusted_client_ip(Some("secret"), Some("secret"), Some("203.0.113.7"))
                .unwrap()
                .to_string(),
            "203.0.113.7"
        );
        assert!(trusted_client_ip(None, Some("secret"), Some("203.0.113.7")).is_none());
        assert!(trusted_client_ip(Some("secret"), Some("forged"), Some("203.0.113.7")).is_none());
        assert!(
            trusted_client_ip(
                Some("secret"),
                Some("secret"),
                Some("203.0.113.7, 203.0.113.8")
            )
            .is_none()
        );
        assert!(trusted_client_ip(Some("secret"), None, Some("203.0.113.7")).is_none());
        assert!(trusted_client_ip(Some("secret"), Some("secret"), Some("::1")).is_some());
    }
}

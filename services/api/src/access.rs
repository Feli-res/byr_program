//! Shared account checks: all business modules use the same session and error rules.
use crate::AppState;
pub(crate) use crate::accounts::{
    AccountError, AccountResult, Identity, User, authenticate, csrf_check, field_text, id,
    lock_identity, reason, render_error,
};
use salvo::prelude::*;
use serde::de::DeserializeOwned;

pub(crate) async fn optional_identity(
    req: &Request,
    app: &AppState,
) -> AccountResult<Option<Identity>> {
    if !req.headers().contains_key("cookie") {
        return Ok(None);
    }
    match authenticate(req, app).await {
        Ok(identity) => Ok(Some(identity)),
        Err(error) if [StatusCode::UNAUTHORIZED, StatusCode::FORBIDDEN].contains(&error.status) => {
            Ok(None)
        }
        Err(error) => Err(error),
    }
}

pub(crate) async fn parse<T: DeserializeOwned>(req: &mut Request) -> AccountResult<T> {
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
    req.parse_json_with_max_size(131072).await.map_err(|_| {
        AccountError::new(
            StatusCode::BAD_REQUEST,
            "INVALID_JSON",
            "提交格式不正确，或包含不允许的字段",
        )
    })
}

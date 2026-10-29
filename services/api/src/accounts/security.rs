use super::{AccountError, AccountResult};
use argon2::{
    Algorithm, Argon2, Params, PasswordHash, PasswordHasher, PasswordVerifier, Version,
    password_hash::SaltString,
};
use base64::{Engine, engine::general_purpose::URL_SAFE_NO_PAD};
use hmac::{Hmac, Mac};
use sha2::{Digest, Sha256};
use std::{
    sync::{Arc, LazyLock},
    time::{SystemTime, UNIX_EPOCH},
};
use tokio::sync::Semaphore;

static HASH_SLOTS: LazyLock<Arc<Semaphore>> = LazyLock::new(|| Arc::new(Semaphore::new(2)));
static DUMMY: LazyLock<String> =
    LazyLock::new(|| hash_sync("dummy-verification-password").expect("Argon2 configuration"));
pub fn warmup() {
    LazyLock::force(&DUMMY);
}

pub fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

pub fn random_token() -> String {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).expect("operating-system random source");
    URL_SAFE_NO_PAD.encode(bytes)
}

pub fn digest(value: &str) -> Vec<u8> {
    Sha256::digest(value.as_bytes()).to_vec()
}

pub fn token_valid(value: &str) -> bool {
    value.len() == 43 && URL_SAFE_NO_PAD.decode(value).is_ok_and(|v| v.len() == 32)
}

pub fn account(value: &str) -> Option<String> {
    let value = value.trim();
    (value.len() >= 4
        && value.len() <= 24
        && value.as_bytes()[0].is_ascii_alphabetic()
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'_'))
    .then(|| value.to_owned())
}

pub fn password_valid(value: &str) -> bool {
    (8..=64).contains(&value.chars().count())
}

fn argon() -> Argon2<'static> {
    Argon2::new(
        Algorithm::Argon2id,
        Version::V0x13,
        Params::new(19456, 2, 1, None).expect("Argon2 parameters"),
    )
}

fn hash_sync(password: &str) -> Result<String, String> {
    let token = random_token();
    let salt = SaltString::encode_b64(&digest(&token)[..16]).map_err(|_| "salt")?;
    argon()
        .hash_password(password.as_bytes(), &salt)
        .map(|v| v.to_string())
        .map_err(|_| "hash".into())
}

pub async fn hash_password(password: String) -> AccountResult<String> {
    if !password_valid(&password) {
        return Err(AccountError::validation(
            "password",
            "密码为 8～64 个字符，不自动去除空格",
        ));
    }
    let permit = HASH_SLOTS
        .clone()
        .try_acquire_owned()
        .map_err(|_| AccountError::busy())?;
    tokio::task::spawn_blocking(move || {
        let _permit = permit;
        hash_sync(&password)
    })
    .await
    .map_err(|_| AccountError::unavailable())?
    .map_err(|_| AccountError::unavailable())
}

pub async fn verify_password(password: String, hash: Option<String>) -> AccountResult<bool> {
    let permit = HASH_SLOTS
        .clone()
        .try_acquire_owned()
        .map_err(|_| AccountError::busy())?;
    tokio::task::spawn_blocking(move || {
        let _permit = permit;
        let encoded = hash.as_deref().unwrap_or(&DUMMY);
        PasswordHash::new(encoded)
            .ok()
            .is_some_and(|v| argon().verify_password(password.as_bytes(), &v).is_ok())
    })
    .await
    .map_err(|_| AccountError::unavailable())
}

fn csrf_message(context: &str, payload: &str) -> String {
    format!("{}:{context}:{}:{payload}", context.len(), payload.len())
}

pub fn csrf_token(secret: &str, context: &str) -> String {
    let payload = format!("{}.{}", now() + 3600, random_token());
    let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes()).expect("HMAC key");
    mac.update(csrf_message(context, &payload).as_bytes());
    format!(
        "{payload}.{}",
        URL_SAFE_NO_PAD.encode(mac.finalize().into_bytes())
    )
}

pub fn csrf_valid(secret: &str, context: &str, token: &str) -> bool {
    if token.len() > 200 {
        return false;
    }
    let Some((payload, signature)) = token.rsplit_once('.') else {
        return false;
    };
    let Some((expiry, nonce)) = payload.split_once('.') else {
        return false;
    };
    if !token_valid(nonce)
        || !expiry
            .parse::<u64>()
            .is_ok_and(|v| v >= now() && v <= now() + 3600)
    {
        return false;
    }
    let Ok(signature) = URL_SAFE_NO_PAD.decode(signature) else {
        return false;
    };
    let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes()).expect("HMAC key");
    mac.update(csrf_message(context, payload).as_bytes());
    mac.verify_slice(&signature).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn normalization_and_password_edges() {
        assert_eq!(account(" AbC_12 "), Some("AbC_12".into()));
        assert_ne!(account("TestUser001"), account("testuser001"));
        for invalid in ["1abc", "abc", "邮abc", "abc-def", &"a".repeat(25)] {
            assert!(account(invalid).is_none());
        }
        assert!(password_valid(&"邮".repeat(64)));
        assert!(!password_valid(&"邮".repeat(65)));
        assert!(password_valid("        "));
    }
    #[test]
    fn csrf_requires_signature_context_and_expiry() {
        let token = csrf_token("test-secret", "session-one");
        assert!(csrf_valid("test-secret", "session-one", &token));
        assert!(!csrf_valid("other-secret", "session-one", &token));
        assert!(!csrf_valid("test-secret", "session-two", &token));
        assert!(!csrf_valid(
            "test-secret",
            "session-one",
            &token.replace('.', "x")
        ));
        assert!(!csrf_valid(
            "test-secret",
            "session-one",
            "0.expired.signature"
        ));
    }
    #[tokio::test]
    async fn hashes_are_salted_and_password_spaces_preserved() {
        let a = hash_password(" password ".into()).await.unwrap();
        let b = hash_password(" password ".into()).await.unwrap();
        assert_ne!(a, b);
        assert!(a.starts_with("$argon2id$v=19$m=19456,t=2,p=1$"));
        assert!(
            verify_password(" password ".into(), Some(a.clone()))
                .await
                .unwrap()
        );
        assert!(!verify_password("password".into(), Some(a)).await.unwrap());
    }
}

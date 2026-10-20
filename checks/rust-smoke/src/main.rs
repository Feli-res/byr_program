use anyhow::{Context, Result, ensure};
use redis::AsyncCommands;
use salvo::prelude::*;
use salvo::test::ResponseExt;
use serde::Deserialize;
use sqlx::mysql::MySqlPoolOptions;

#[derive(Deserialize)]
struct Settings {
    service_name: String,
}

#[handler]
async fn ping(res: &mut Response) {
    res.render(Json(serde_json::json!({"status": "OK", "data": "pong"})));
}

#[tokio::main]
async fn main() -> Result<()> {
    let verify_only = std::env::args().any(|arg| arg == "--verify-only");
    let settings: Settings = toml::from_str("service_name = 'youzhihui-environment-check'")?;
    ensure!(!settings.service_name.is_empty(), "configuration parsing failed");
    let pool = MySqlPoolOptions::new()
        .max_connections(2)
        .connect(&std::env::var("MYSQL_CHECK_URL").context("missing MySQL check setting")?)
        .await?;
    let token = std::env::var("CHECK_TOKEN").context("missing check token")?;
    if !verify_only {
        sqlx::query("CREATE TABLE IF NOT EXISTS environment_probe (id INT PRIMARY KEY, token VARCHAR(64) NOT NULL)")
            .execute(&pool).await?;
        sqlx::query("INSERT INTO environment_probe (id, token) VALUES (1, ?) ON DUPLICATE KEY UPDATE token = VALUES(token)")
            .bind(&token).execute(&pool).await?;
    }
    let stored: String = sqlx::query_scalar("SELECT token FROM environment_probe WHERE id = 1")
        .fetch_one(&pool).await?;
    ensure!(stored == token, "MySQL persisted value mismatch");

    let client = redis::Client::open("redis://127.0.0.1:26379/")?;
    let mut cache = redis::aio::ConnectionManager::new(client).await?;
    if !verify_only {
        let _: () = cache.set("byr:environment:probe", &token).await?;
    }
    let cached: String = cache.get("byr:environment:probe").await?;
    ensure!(cached == token, "Redis persisted value mismatch");

    let service = Service::new(Router::new().push(Router::with_path("ping").get(ping)));
    let mut response = salvo::test::TestClient::get("http://127.0.0.1/ping").send(&service).await;
    ensure!(response.status_code == Some(StatusCode::OK), "Salvo handler status mismatch");
    let payload = response.take_json::<serde_json::Value>().await?;
    ensure!(payload["data"] == "pong", "Salvo handler response mismatch");
    println!("{}", serde_json::json!({
        "configuration": "passed", "mysql_read_write": "passed", "redis_read_write": "passed",
        "salvo_in_process_request": "passed", "restart_readback": verify_only
    }));
    pool.close().await;
    Ok(())
}

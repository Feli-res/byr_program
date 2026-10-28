use anyhow::{Context, Result};
use salvo::Listener;
use std::io::{self, IsTerminal, Read, Write};
use youzhihui_api::{AppState, Settings, accounts, app, chat, migrate};

fn administrator_input() -> Result<accounts::Registration> {
    if !io::stdin().is_terminal() {
        let mut input = String::new();
        io::stdin().read_to_string(&mut input)?;
        return serde_json::from_str(&input)
            .context("administrator input must be JSON on standard input");
    }
    let mut account = String::new();
    let mut nickname = String::new();
    print!("Administrator account: ");
    io::stdout().flush()?;
    io::stdin().read_line(&mut account)?;
    print!("Nickname: ");
    io::stdout().flush()?;
    io::stdin().read_line(&mut nickname)?;
    let password = rpassword::prompt_password("Password (not echoed): ")?;
    let confirm = rpassword::prompt_password("Confirm password: ")?;
    anyhow::ensure!(password == confirm, "passwords do not match");
    Ok(accounts::Registration {
        account: account.trim().into(),
        nickname: nickname.trim().into(),
        password,
    })
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .json()
        .with_env_filter(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info,sqlx::query=error".into()),
        )
        .init();
    let state = AppState::new(Settings::from_env()?)?;
    let arguments = std::env::args().collect::<Vec<_>>();
    if arguments.iter().any(|v| v == "--migrate") {
        migrate(&state.pool)
            .await
            .context("database migration failed")?;
        tracing::info!("database migrations completed");
        return Ok(());
    }
    if arguments.iter().any(|v| v == "--init-admin") {
        accounts::initialize_admin(&state.pool, administrator_input()?).await?;
        println!("Administrator initialized. Sign in with the account you entered.");
        return Ok(());
    }
    if arguments.iter().any(|v| v == "--cleanup-files") {
        accounts::cleanup_files(&state)
            .await
            .map_err(|_| anyhow::anyhow!("file cleanup unavailable"))?;
        return Ok(());
    }
    if arguments.iter().any(|v| v == "--seed-chat-notification") {
        let mut input = String::new();
        io::stdin().read_to_string(&mut input)?;
        chat::seed_verification_notification(&state, &input).await?;
        return Ok(());
    }
    chat::start_workers(state.clone());
    let cleanup = state.clone();
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(std::time::Duration::from_secs(3600));
        loop {
            interval.tick().await;
            if accounts::cleanup_files(&cleanup).await.is_err() {
                tracing::warn!("avatar cleanup deferred: dependency unavailable");
            }
        }
    });
    let bind = state.settings.bind;
    tracing::info!(%bind,dev_tools=state.settings.dev_tools,"API starting");
    let acceptor = salvo::conn::TcpListener::new(bind).bind().await;
    salvo::Server::new(acceptor).serve(app(state)).await;
    Ok(())
}

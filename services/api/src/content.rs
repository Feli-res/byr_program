use crate::access::*;
use sqlx::{MySql, Transaction};

/// Publish changes in commit order. Forum and goods share the same locked counter.
pub(crate) async fn change(
    tx: &mut Transaction<'_, MySql>,
    kind: &str,
    source: u64,
    version: u32,
    operation: &str,
) -> AccountResult<()> {
    let counter: u64 = sqlx::query_scalar(
        "SELECT counter_value FROM system_counters WHERE counter_key='content_changes' FOR UPDATE",
    )
    .fetch_one(&mut **tx)
    .await?;
    let next = counter
        .checked_add(1)
        .ok_or_else(AccountError::unavailable)?;
    sqlx::query("UPDATE system_counters SET counter_value=? WHERE counter_key='content_changes'")
        .bind(next)
        .execute(&mut **tx)
        .await?;
    sqlx::query("INSERT INTO content_changes(change_seq,kind,post_id,goods_id,source_version,operation) VALUES (?,?,?,?,?,?)")
        .bind(next).bind(kind).bind(if kind=="post"{Some(source)}else{None}).bind(if kind=="goods"{Some(source)}else{None}).bind(version).bind(operation).execute(&mut **tx).await?;
    sqlx::query(
        "INSERT INTO search_index_jobs(change_seq,next_due_at) VALUES (?,UTC_TIMESTAMP(6))",
    )
    .bind(next)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

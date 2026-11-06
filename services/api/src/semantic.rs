//! Local embedding index. Search always joins the current public source rows.
use crate::{
    AppState,
    access::*,
    goods::{Filters, paging},
};
use futures_util::StreamExt;
use salvo::prelude::*;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use sqlx::{MySql, QueryBuilder, Row};
use std::{sync::OnceLock, time::Duration};
use tokio::sync::Semaphore;

static QUERY_SLOTS: OnceLock<Semaphore> = OnceLock::new();
static INDEX_SLOTS: OnceLock<Semaphore> = OnceLock::new();
static EMBED_CLIENT: OnceLock<reqwest::Client> = OnceLock::new();

const MODEL: &str = "bge-small-zh-v1.5";
const DIMENSION: usize = 512;
const QUERY_SLOT_COUNT: usize = 4;
const INDEX_SLOT_COUNT: usize = 2;
const INDEX_BATCH: usize = 25;
const INDEX_CONCURRENCY: usize = 2;

fn endpoint() -> Option<String> {
    std::env::var("AI_EMBEDDING_URL")
        .ok()
        .filter(|v| v == "http://embedding:80" || v == "http://127.0.0.1:18084")
}

fn embedding_client() -> &'static reqwest::Client {
    EMBED_CLIENT.get_or_init(|| {
        reqwest::Client::builder()
            .redirect(reqwest::redirect::Policy::none())
            .timeout(Duration::from_secs(12))
            .build()
            .expect("embedding client")
    })
}

async fn embed(
    text: &str,
    query: bool,
    slots: &'static OnceLock<Semaphore>,
    slot_wait: Duration,
    request_timeout: Duration,
) -> Result<Vec<f64>, ()> {
    let base = endpoint().ok_or(())?;
    let limit = if query {
        QUERY_SLOT_COUNT
    } else {
        INDEX_SLOT_COUNT
    };
    let _slot = tokio::time::timeout(
        slot_wait,
        slots.get_or_init(|| Semaphore::new(limit)).acquire(),
    )
    .await
    .map_err(|_| ())?
    .map_err(|_| ())?;
    let text = if query {
        format!("为这个句子生成表示以用于检索相关文章：{text}")
    } else {
        text.to_owned()
    };
    let response = tokio::time::timeout(
        request_timeout,
        embedding_client()
            .post(format!("{base}/embed"))
            .json(&json!({"inputs":[text],"truncate":true}))
            .send(),
    )
    .await
    .map_err(|_| ())?
    .map_err(|_| ())?;
    if !response.status().is_success() || response.content_length().is_some_and(|n| n > 100_000) {
        return Err(());
    }
    let mut response = response;
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| ())? {
        if bytes.len().saturating_add(chunk.len()) > 100_000 {
            return Err(());
        }
        bytes.extend_from_slice(&chunk);
    }
    let vectors: Vec<Vec<f64>> = serde_json::from_slice(&bytes).map_err(|_| ())?;
    let vector = vectors.into_iter().next().ok_or(())?;
    if vector.len() != DIMENSION
        || vector.iter().any(|v| !v.is_finite())
        || vector.iter().all(|v| *v == 0.0)
    {
        return Err(());
    }
    Ok(vector)
}

fn cosine(a: &[f64], b: &[f64]) -> Option<f64> {
    if a.len() != DIMENSION || b.len() != DIMENSION {
        return None;
    }
    let (mut dot, mut aa, mut bb) = (0., 0., 0.);
    for (&x, &y) in a.iter().zip(b) {
        if !x.is_finite() || !y.is_finite() {
            return None;
        }
        dot += x * y;
        aa += x * x;
        bb += y * y;
    }
    if aa == 0. || bb == 0. {
        return None;
    }
    Some(dot / (aa.sqrt() * bb.sqrt()))
}

pub async fn search(req: &Request, app: &AppState) -> AccountResult<Value> {
    let text = field_text(
        &req.query::<String>("q")
            .ok_or_else(|| AccountError::validation("q", "请输入关键词"))?,
        1,
        200,
        "q",
    )?;
    let filters = Filters::parse(req)?;
    let (page, size) = paging(req)?;
    let kind = req.query::<String>("kind").unwrap_or_else(|| "all".into());
    if !["all", "post", "goods"].contains(&kind.as_str()) {
        return Err(AccountError::validation("kind", "内容类型不正确"));
    }
    let vector = embed(
        &text,
        true,
        &QUERY_SLOTS,
        Duration::from_millis(500),
        Duration::from_secs(3),
    )
    .await
    .map_err(|_| AccountError::unavailable())?;
    let mut q = QueryBuilder::<MySql>::new(
        "SELECT 'post' AS kind,p.id,p.title,LEFT(p.body_markdown,300) AS excerpt,CAST(NULL AS UNSIGNED) AS price_cents,CAST(NULL AS CHAR CHARACTER SET utf8mb4) AS campus_code,DATE_FORMAT(p.updated_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS updated_at,d.embedding FROM posts p JOIN search_documents d ON d.kind='post' AND d.source_id=p.id AND d.source_version=p.version AND d.state='ready' AND d.embedding_model=",
    );
    q.push_bind(MODEL)
        .push(" WHERE p.visibility='public' AND p.deleted_at IS NULL");
    if kind == "goods" || filters.has_goods_filter() {
        q.push(" AND FALSE");
    }
    q.push(" UNION ALL SELECT 'goods' AS kind,g.id,g.title,LEFT(g.description,300) AS excerpt,g.price_cents,CAST(g.campus_code AS CHAR CHARACTER SET utf8mb4) AS campus_code,DATE_FORMAT(g.updated_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS updated_at,d.embedding FROM goods g JOIN search_documents d ON d.kind='goods' AND d.source_id=g.id AND d.source_version=g.version AND d.state='ready' AND d.embedding_model=").push_bind(MODEL).push(" WHERE g.moderation='clear' AND g.deleted_at IS NULL AND g.state='on_sale'");
    if kind == "post" {
        q.push(" AND FALSE");
    }
    filters.append(&mut q, "g", false);
    let rows = q.build().fetch_all(&app.pool).await?;
    let mut scored = Vec::new();
    for row in rows {
        let raw: Value = row.try_get("embedding")?;
        let Ok(other) = serde_json::from_value::<Vec<f64>>(raw) else {
            continue;
        };
        let Some(score) = cosine(&vector, &other) else {
            continue;
        };
        let kind: String = row.get("kind");
        let price: Option<u64> = row.get("price_cents");
        let campus: Option<String> = row.get("campus_code");
        let reason = match (price, campus.as_deref()) {
            (Some(price), Some(campus)) => {
                let place = match campus {
                    "shahe" => "沙河",
                    "xitucheng" => "西土城",
                    _ => "其他地点",
                };
                format!(
                    "价格 {}.{:02} 元，交易校区{}；内容与需求语义相关",
                    price / 100,
                    price % 100,
                    place
                )
            }
            _ => "帖子内容与搜索语义相关".to_owned(),
        };
        let item = json!({"kind":kind,"id":row.get::<u64,_>("id").to_string(),"title":row.get::<String,_>("title"),"excerpt":row.get::<String,_>("excerpt"),"price_cents":row.get::<Option<u64>,_>("price_cents"),"campus_code":row.get::<Option<String>,_>("campus_code"),"updated_at":row.get::<String,_>("updated_at"),"reason":reason,"rank_score":score});
        scored.push((score, item));
    }
    scored.sort_by(|a, b| {
        b.0.total_cmp(&a.0)
            .then_with(|| a.1["kind"].as_str().cmp(&b.1["kind"].as_str()))
            .then_with(|| a.1["id"].as_str().cmp(&b.1["id"].as_str()))
    });
    let total = scored.len();
    let offset = ((page - 1) * size) as usize;
    let items: Vec<Value> = scored
        .into_iter()
        .skip(offset)
        .take(size as usize)
        .map(|(_, v)| v)
        .collect();
    Ok(
        json!({"items":items,"total":total,"page":page,"page_size":size,"mode_used":"semantic","degraded":false}),
    )
}

async fn pending_rows(
    app: &AppState,
    kind: &str,
    limit: usize,
) -> Result<Vec<sqlx::mysql::MySqlRow>, ()> {
    if limit == 0 {
        return Ok(Vec::new());
    }
    let sql = if kind == "goods" {
        "SELECT 'goods' AS kind,g.id,g.version,CONCAT_WS(' ',g.title,LEFT(g.description,1500),g.brand,g.model,g.purpose) AS body FROM goods g LEFT JOIN search_documents d ON d.kind='goods' AND d.source_id=g.id WHERE g.deleted_at IS NULL AND g.moderation='clear' AND g.state='on_sale' AND (d.id IS NULL OR d.source_version<>g.version OR d.state<>'ready' OR d.embedding_model<>?) ORDER BY g.updated_at ASC,g.id ASC LIMIT ?"
    } else {
        "SELECT 'post' AS kind,p.id,p.version,CONCAT_WS(' ',p.title,LEFT(p.body_markdown,1500)) AS body FROM posts p LEFT JOIN search_documents d ON d.kind='post' AND d.source_id=p.id WHERE p.visibility='public' AND p.deleted_at IS NULL AND (d.id IS NULL OR d.source_version<>p.version OR d.state<>'ready' OR d.embedding_model<>?) ORDER BY p.updated_at ASC,p.id ASC LIMIT ?"
    };
    sqlx::query(sql)
        .bind(MODEL)
        .bind(limit as u64)
        .fetch_all(&app.pool)
        .await
        .map_err(|_| ())
}

async fn index_row(app: &AppState, row: sqlx::mysql::MySqlRow) -> Result<(), ()> {
    let kind: String = row.get("kind");
    let id: u64 = row.get("id");
    let version: u32 = row.get("version");
    let body: String = row.get("body");
    let embedding = embed(
        &body,
        false,
        &INDEX_SLOTS,
        Duration::from_secs(2),
        Duration::from_secs(5),
    )
    .await?;
    let hash = Sha256::digest(body.as_bytes()).to_vec();
    sqlx::query("INSERT INTO search_documents(kind,source_id,source_version,content_hash,embedding_model,embedding_dimension,state,embedding,indexed_at) VALUES (?,?,?,?,?,?,'ready',?,UTC_TIMESTAMP(6)) ON DUPLICATE KEY UPDATE embedding=IF(source_version<=VALUES(source_version),VALUES(embedding),embedding),content_hash=IF(source_version<=VALUES(source_version),VALUES(content_hash),content_hash),embedding_model=IF(source_version<=VALUES(source_version),VALUES(embedding_model),embedding_model),embedding_dimension=IF(source_version<=VALUES(source_version),VALUES(embedding_dimension),embedding_dimension),state=IF(source_version<=VALUES(source_version),'ready',state),indexed_at=IF(source_version<=VALUES(source_version),UTC_TIMESTAMP(6),indexed_at),source_version=GREATEST(source_version,VALUES(source_version))")
        .bind(kind)
        .bind(id)
        .bind(version)
        .bind(hash)
        .bind(MODEL)
        .bind(DIMENSION as u32)
        .bind(json!(embedding))
        .execute(&app.pool)
        .await
        .map_err(|_| ())?;
    Ok(())
}

async fn update_index(app: &AppState) -> Result<(), ()> {
    // Version checks prevent a delayed vector from replacing newer content.
    sqlx::query("UPDATE search_documents d LEFT JOIN posts p ON d.kind='post' AND p.id=d.source_id LEFT JOIN goods g ON d.kind='goods' AND g.id=d.source_id SET d.state='removed',d.embedding=NULL WHERE d.state<>'removed' AND ((d.kind='post' AND (p.id IS NULL OR p.deleted_at IS NOT NULL OR p.visibility<>'public')) OR (d.kind='goods' AND (g.id IS NULL OR g.deleted_at IS NOT NULL OR g.state<>'on_sale' OR g.moderation<>'clear')))").execute(&app.pool).await.map_err(|_|())?;
    // Goods first: a post backlog must not delay a newly published product.
    let mut rows = pending_rows(app, "goods", INDEX_BATCH).await?;
    let remaining = INDEX_BATCH.saturating_sub(rows.len());
    rows.extend(pending_rows(app, "post", remaining).await?);
    let results = futures_util::stream::iter(rows)
        .map(|row| index_row(app, row))
        .buffer_unordered(INDEX_CONCURRENCY)
        .collect::<Vec<_>>()
        .await;
    let failures = results.iter().filter(|result| result.is_err()).count();
    // Mark queued changes complete only after the current version is indexed or no longer public.
    sqlx::query("UPDATE search_index_jobs j JOIN content_changes c ON c.change_seq=j.change_seq LEFT JOIN search_documents d ON d.kind=c.kind AND d.source_id=COALESCE(c.post_id,c.goods_id) LEFT JOIN posts p ON c.kind='post' AND p.id=c.post_id LEFT JOIN goods g ON c.kind='goods' AND g.id=c.goods_id SET j.state='succeeded',j.lease_until=NULL,j.error_code=NULL WHERE j.state IN ('pending','running') AND ((d.state='ready' AND d.source_version>=c.source_version) OR (c.kind='post' AND (p.id IS NULL OR p.visibility<>'public' OR p.deleted_at IS NOT NULL)) OR (c.kind='goods' AND (g.id IS NULL OR g.state<>'on_sale' OR g.moderation<>'clear' OR g.deleted_at IS NOT NULL)))").execute(&app.pool).await.map_err(|_| ())?;
    if failures > 0 {
        tracing::warn!(failures, "semantic index batch partially failed");
        return Err(());
    }
    Ok(())
}

pub fn start_worker(app: AppState) {
    if endpoint().is_none() {
        return;
    }
    tokio::spawn(async move {
        let mut timer = tokio::time::interval(Duration::from_secs(2));
        loop {
            timer.tick().await;
            if update_index(&app).await.is_err() {
                tracing::warn!("semantic index update deferred");
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cosine_rejects_bad_vectors() {
        let mut a = vec![0.; DIMENSION];
        a[0] = 1.;
        assert_eq!(cosine(&a, &a), Some(1.));
        assert_eq!(cosine(&a, &[1.]), None);
        assert_eq!(cosine(&a, &vec![0.; DIMENSION]), None);
    }
}

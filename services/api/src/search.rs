use crate::{
    AppState,
    access::*,
    goods::{Filters, like_pattern, paging},
    ok, state,
};
use salvo::prelude::*;
use serde_json::{Value, json};
use sqlx::{MySql, QueryBuilder, Row};

fn query(f: &Filters, kind: &str, text: &str, count: bool) -> QueryBuilder<'static, MySql> {
    let pattern = like_pattern(text);
    let mut q = QueryBuilder::<MySql>::new(if count {
        "SELECT COUNT(*) FROM ("
    } else {
        "SELECT kind,id,title,excerpt,price_cents,campus_code,rank_score,DATE_FORMAT(updated_at,'%Y-%m-%dT%H:%i:%s.%fZ') AS updated_at FROM ("
    });
    q.push("SELECT 'post' AS kind,p.id,p.title,LEFT(p.body_markdown,300) AS excerpt,CAST(NULL AS UNSIGNED) AS price_cents,CAST(NULL AS CHAR CHARACTER SET utf8mb4) AS campus_code,CASE WHEN p.title LIKE ").push_bind(pattern.clone()).push(" ESCAPE '!' THEN 2 ELSE 1 END AS rank_score,p.updated_at FROM posts p WHERE p.visibility='public' AND p.deleted_at IS NULL");
    if kind == "goods" || f.has_goods_filter() {
        q.push(" AND false");
    }
    q.push(" AND CONCAT_WS(' ',p.title,p.body_markdown) LIKE ")
        .push_bind(pattern.clone())
        .push(" ESCAPE '!'");
    q.push(" UNION ALL SELECT 'goods' AS kind,g.id,g.title,LEFT(g.description,300) AS excerpt,g.price_cents,CAST(g.campus_code AS CHAR CHARACTER SET utf8mb4) AS campus_code,CASE WHEN g.title LIKE ").push_bind(pattern.clone()).push(" ESCAPE '!' THEN 2 ELSE 1 END AS rank_score,g.updated_at FROM goods g WHERE g.moderation='clear' AND g.deleted_at IS NULL AND g.state='on_sale'");
    if kind == "post" {
        q.push(" AND false");
    }
    f.append(&mut q, "g", false);
    q.push(
        " AND CONCAT_WS(' ',g.title,g.description,g.brand,g.model,g.purpose,g.location_text) LIKE ",
    )
    .push_bind(pattern)
    .push(" ESCAPE '!') hits");
    q
}
async fn search(req: &Request, app: &AppState) -> AccountResult<Value> {
    let text = field_text(
        &req.query::<String>("q")
            .ok_or_else(|| AccountError::validation("q", "请输入关键词"))?,
        1,
        200,
        "q",
    )?;
    let f = Filters::parse(req)?;
    let (page, size) = paging(req)?;
    let mode = req
        .query::<String>("mode")
        .unwrap_or_else(|| "keyword".into());
    let kind = req.query::<String>("kind").unwrap_or_else(|| "all".into());
    if !["keyword", "semantic"].contains(&mode.as_str()) {
        return Err(AccountError::validation("mode", "搜索方式不正确"));
    }
    if !["all", "post", "goods"].contains(&kind.as_str()) {
        return Err(AccountError::validation("kind", "内容类型不正确"));
    }
    let total: i64 = query(&f, &kind, &text, true)
        .build_query_scalar()
        .fetch_one(&app.pool)
        .await?;
    let mut q = query(&f, &kind, &text, false);
    q.push(" ORDER BY rank_score DESC,updated_at DESC,kind ASC,id DESC LIMIT ")
        .push_bind(size)
        .push(" OFFSET ")
        .push_bind((page - 1) * size);
    let rows = q.build().fetch_all(&app.pool).await?;
    let items=rows.iter().map(|r|{let kind=r.get::<String,_>("kind");let score=r.get::<i64,_>("rank_score");json!({"kind":kind,"id":r.get::<u64,_>("id").to_string(),"title":r.get::<String,_>("title"),"excerpt":r.get::<String,_>("excerpt"),"price_cents":r.get::<Option<u64>,_>("price_cents"),"campus_code":r.get::<Option<String>,_>("campus_code"),"reason":if score==2{"标题包含关键词"}else if kind=="post"{"帖子正文包含关键词"}else{"商品信息包含关键词"},"rank_score":score,"updated_at":r.get::<String,_>("updated_at")})}).collect::<Vec<_>>();
    Ok(
        json!({"items":items,"total":total,"page":page,"page_size":size,"mode_used":"keyword","degraded":mode=="semantic"}),
    )
}
#[handler]
async fn dispatch(req: &mut Request, depot: &mut Depot, res: &mut Response) {
    let app = state(depot);
    res.add_header("Cache-Control", "no-store", true).ok();
    match search(req, &app).await {
        Ok(value) => ok(res, depot, StatusCode::OK, value),
        Err(error) => render_error(error, depot, res),
    }
}
pub fn routes() -> Router {
    Router::with_path("api/v1/search").get(dispatch)
}

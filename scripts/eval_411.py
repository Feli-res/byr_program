"""4.11.2 AI comparison and 40-query retrieval evaluation on the 411 stack."""
import asyncio
import csv
import json
import math
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path

import load_411 as l

WORK = l.WORK
DOCS = Path("/home/sunxiang/youzhihui/acceptance411-work")

TEMPLATES = [
    {"name": "iPad 学习平板", "cat": "数码设备", "brand": "Apple", "keyword": "记笔记", "max": 250000, "campus": "shahe"},
    {"name": "华为学习平板", "cat": "数码设备", "brand": "HUAWEI", "keyword": "网课", "max": 200000, "campus": "shahe"},
    {"name": "联想轻薄笔记本", "cat": "数码设备", "brand": "Lenovo", "keyword": "写代码", "max": 300000, "campus": "xitucheng"},
    {"name": "小米降噪耳机", "cat": "数码设备", "brand": "Xiaomi", "keyword": "通勤", "max": 50000, "campus": "shahe"},
    {"name": "考研数学复习书", "cat": "图书资料", "brand": None, "keyword": "考研", "max": 10000, "campus": "shahe"},
    {"name": "计算机网络教材", "cat": "图书资料", "brand": None, "keyword": "课程", "max": 5000, "campus": "xitucheng"},
    {"name": "宿舍台灯", "cat": "生活用品", "brand": None, "keyword": "宿舍", "max": 5000, "campus": "shahe"},
    {"name": "折叠自行车", "cat": "生活用品", "brand": None, "keyword": "校园", "max": 50000, "campus": "other"},
    {"name": "索尼降噪耳机", "cat": "数码设备", "brand": "Sony", "keyword": "自习", "max": 80000, "campus": "shahe"},
    {"name": "戴尔显示器", "cat": "数码设备", "brand": "Dell", "keyword": "外接屏", "max": 100000, "campus": "xitucheng"},
]
CAMPUS_NAMES = {"shahe": "沙河", "xitucheng": "西土城", "other": "其他"}
CONDITION_RANK = {"new": 4, "like_new": 3, "good": 2, "fair": 1}


def rows(sql):
    out = l.db(sql)
    return list(csv.reader(out.splitlines(), delimiter="\t")) if out else []


def load_goods():
    categories = {r[0]: r[1] for r in rows("SELECT id,name FROM goods_categories;")}
    raw = rows("""
      SELECT g.id,g.title,g.description,COALESCE(g.brand,''),COALESCE(g.purpose,''),
             g.price_cents,g.campus_code,g.condition_code,g.category_id,
             COALESCE(JSON_UNQUOTE(JSON_EXTRACT(g.attributes,'$.stylus_support')),'')
      FROM goods g WHERE g.id<=500 AND g.state='on_sale' AND g.moderation='clear' AND g.deleted_at IS NULL
      ORDER BY g.id;
    """)
    goods = {}
    for r in raw:
        if len(r) < 10:
            r = r + [""] * (10 - len(r))
        gid = r[0]
        goods[gid] = {
            "id": gid, "title": r[1], "description": r[2], "brand": r[3], "purpose": r[4],
            "price": int(r[5]), "campus": r[6], "condition": r[7], "category_id": r[8],
            "category": categories.get(r[8], ""), "stylus": r[9],
        }
    return goods, categories


def make_queries(goods, categories):
    cat_ids = {name: str(cid) for cid, name in categories.items()}
    queries = []

    # 10 exact structured queries.
    for i, t in enumerate(TEMPLATES):
        brand = t["brand"] or ""
        text = f"想收一台 {brand} 的{t['name']}，预算 {t['max'] // 100} 元以内，{CAMPUS_NAMES[t['campus']]}交易"
        queries.append({
            "id": f"E{i+1:02d}", "subset": "exact", "text": text.strip(),
            "expected": {"category": t["cat"], "brand": t["brand"], "max_price_cents": t["max"],
                         "campus_code": t["campus"], "stylus_support": None, "min_condition": None},
            "keyword": None, "no_result": False,
        })

    # 20 synonym / purpose queries.
    for i, t in enumerate(TEMPLATES):
        for n, (budget, campus) in enumerate([(t["max"], t["campus"]), (min(t["max"] + 50000, 900000), t["campus"])]):
            text = (f"想找适合{t['keyword']}用的{t['cat']}，价格不超过 {budget // 100} 元，"
                    f"{CAMPUS_NAMES[campus]}交易")
            queries.append({
                "id": f"S{i+1:02d}{n+1}", "subset": "synonym", "text": text,
                "expected": {"category": t["cat"], "brand": None, "max_price_cents": budget,
                             "campus_code": campus, "stylus_support": None, "min_condition": None},
                "keyword": t["keyword"], "no_result": False,
            })

    mixed = [
        ("M01", "预算 2000 元以内、沙河交易的平板，要求支持手写笔", {"category": "数码设备", "brand": None, "max_price_cents": 200000, "campus_code": "shahe", "stylus_support": True, "min_condition": None}, None),
        ("M02", "西土城交易、成色良好及以上的联想笔记本，3000 元以内", {"category": "数码设备", "brand": "Lenovo", "max_price_cents": 300000, "campus_code": "xitucheng", "stylus_support": None, "min_condition": "good"}, None),
        ("M03", "沙河交易的华为平板，预算 1800 元，支持手写笔", {"category": "数码设备", "brand": "HUAWEI", "max_price_cents": 180000, "campus_code": "shahe", "stylus_support": True, "min_condition": None}, None),
        ("M04", "想收 100 元以内的考研数学书，沙河面交", {"category": "图书资料", "brand": None, "max_price_cents": 10000, "campus_code": "shahe", "stylus_support": None, "min_condition": None}, "考研"),
        ("M05", "西土城的戴尔显示器，最高 900 元，成色良好以上", {"category": "数码设备", "brand": "Dell", "max_price_cents": 90000, "campus_code": "xitucheng", "stylus_support": None, "min_condition": "good"}, None),
        ("M06", "其他校区交易的折叠自行车，预算 500 元以内", {"category": "生活用品", "brand": None, "max_price_cents": 50000, "campus_code": "other", "stylus_support": None, "min_condition": None}, "校园"),
    ]
    for qid, text, expected, keyword in mixed:
        queries.append({"id": qid, "subset": "mixed", "text": text, "expected": expected, "keyword": keyword, "no_result": False})

    # 4 queries with no known relevant goods.
    for qid, text, expected in [
        ("N01", "想收一台尼康相机，预算 5000 元", {"category": "数码设备", "brand": "Nikon", "max_price_cents": 500000, "campus_code": None, "stylus_support": None, "min_condition": None}),
        ("N02", "求购佳能相机，西土城交易", {"category": "数码设备", "brand": "Canon", "max_price_cents": None, "campus_code": "xitucheng", "stylus_support": None, "min_condition": None}),
        ("N03", "收一台大疆无人机，3000 元以内", {"category": "数码设备", "brand": "DJI", "max_price_cents": 300000, "campus_code": None, "stylus_support": None, "min_condition": None}),
        ("N04", "求购一台二手钢琴，预算 8000 元", {"category": "其他", "brand": None, "max_price_cents": 800000, "campus_code": None, "stylus_support": None, "min_condition": None}),
    ]:
        queries.append({"id": qid, "subset": "no_result", "text": text, "expected": expected, "keyword": None, "no_result": True})

    for q in queries: q["expected"]["category_id"] = cat_ids.get(q["expected"]["category"])
    return queries


def matches(g, expected, keyword):
    if expected.get("category_id") and g["category_id"] != expected["category_id"]:
        return False
    if expected.get("brand") and g["brand"].lower() != expected["brand"].lower():
        return False
    if expected.get("max_price_cents") is not None and g["price"] > expected["max_price_cents"]:
        return False
    if expected.get("campus_code") and g["campus"] != expected["campus_code"]:
        return False
    if expected.get("stylus_support") is True and g["stylus"] != "true":
        return False
    if expected.get("min_condition"):
        if CONDITION_RANK.get(g["condition"], 0) < CONDITION_RANK[expected["min_condition"]]:
            return False
    if keyword:
        text = (g["title"] + " " + g["description"] + " " + g["purpose"]).lower()
        if keyword.lower() not in text:
            return False
    return True


def dcg(rels):
    return sum((1.0 if r else 0.0) / math.log2(i + 2) for i, r in enumerate(rels))


def score(result_ids, relevant):
    top = [str(x) in relevant for x in result_ids[:10]]
    p5 = sum(top[:5]) / 5.0
    r5 = sum(top[:5]) / len(relevant) if relevant else None
    ideal = [True] * min(10, len(relevant)) + [False] * max(0, 10 - min(10, len(relevant)))
    ndcg = dcg(top) / dcg(ideal) if relevant and dcg(ideal) > 0 else None
    return {"p5": p5, "r5": r5, "ndcg10": ndcg, "top": result_ids[:10]}


async def main():
    goods, categories = load_goods()
    queries = make_queries(goods, categories)
    with (DOCS / "queries-40.json").open("w", encoding="utf-8") as f:
        json.dump(queries, f, ensure_ascii=False, indent=2)
    labels = {}
    for q in queries:
        rel = {gid for gid, g in goods.items() if matches(g, q["expected"], q.get("keyword"))}
        labels[q["id"]] = sorted(rel, key=int)
    (DOCS / "labels-40.json").write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")
    print("queries", len(queries), "labels", {k: len(v) for k, v in labels.items()}, flush=True)

    password, _ = l.load_env()
    clients = []
    for account in ["l411u42", "l411u43", "l411u44", "l411u45", "l411u46"]:
        api = l.Api()
        await api.login(account, password)
        clients.append(api)

    async def intent(api, q, index):
        await asyncio.sleep(index * 20)
        last = None
        for attempt in range(3):
            try:
                data = await api.request("POST", "/api/v1/ai/goods-intent", {"text": q["text"]})
                return data.get("intent")
            except Exception as error:
                last = error
                await asyncio.sleep(15 * (attempt + 1))
        return {"error": f"{type(last).__name__}: {last}"}

    intents = {}
    tasks = []
    for i, q in enumerate(queries):
        tasks.append(intent(clients[i % len(clients)], q, i // len(clients)))
    results = await asyncio.gather(*tasks)
    for q, value in zip(queries, results):
        intents[q["id"]] = value
    (DOCS / "intent-raw-411.json").write_text(json.dumps(intents, ensure_ascii=False, indent=2), encoding="utf-8")
    print("intents done", sum(1 for v in intents.values() if v and "error" not in v), "/", len(queries), flush=True)

    # Field accuracy; normalize category names and brands.
    field_total = defaultdict(int)
    field_ok = defaultdict(int)
    hard_errors = 0
    for q in queries:
        exp = q["expected"]
        got = intents.get(q["id"]) or {}
        for field in ["category", "brand", "max_price_cents", "campus_code", "stylus_support", "min_condition"]:
            field_total[field] += 1
            if str(got.get(field)).lower() == str(exp.get(field)).lower():
                field_ok[field] += 1

    async def search(api, q, mode, extra):
        params = {"q": q["text"], "mode": mode, "kind": "goods", "page_size": "10"}
        params.update(extra)
        data = await api.get("/api/v1/search?" + urllib.parse.urlencode(params))
        return data

    sets = {"keyword": {}, "semantic": {}, "ai": {}}
    cat_ids = {name: str(cid) for cid, name in categories.items()}
    for index, q in enumerate(queries):
        api = clients[index % len(clients)]
        sets["keyword"][q["id"]] = await search(api, q, "keyword", {})
        sets["semantic"][q["id"]] = await search(api, q, "semantic", {})
        got = intents.get(q["id"]) or {}
        extra = {}
        cat = got.get("category")
        if cat in cat_ids:
            extra["category_id"] = cat_ids[cat]
        if got.get("brand"): extra["brand"] = got["brand"]
        if got.get("max_price_cents") is not None: extra["max_price_cents"] = str(got["max_price_cents"])
        if got.get("campus_code"): extra["campus_code"] = got["campus_code"]
        if got.get("stylus_support") is not None: extra["stylus_support"] = str(bool(got["stylus_support"])).lower()
        if got.get("min_condition"): extra["min_condition"] = got["min_condition"]
        sets["ai"][q["id"]] = await search(api, q, "semantic", extra)
        # Hard-constraint check against the user's stated conditions.
        bad = 0
        for item in sets["ai"][q["id"]]["items"]:
            g = goods.get(str(item["id"]))
            if g and not matches(g, q["expected"], None):
                bad += 1
        hard_errors += bad

    report = {"queries": len(queries), "labels": labels, "intents": intents, "sets": sets,
              "field_accuracy": {f: round(field_ok[f] / field_total[f], 4) for f in field_total},
              "hard_constraint_violations": hard_errors}
    metrics = {}
    for group in ["keyword", "semantic", "ai"]:
        vals = []
        syn = []
        for q in queries:
            if q["no_result"]: continue
            rel = set(labels[q["id"]])
            s = score([item["id"] for item in sets[group][q["id"]]["items"]], rel)
            vals.append(s)
            if q["subset"] == "synonym": syn.append(s)
        metrics[group] = {
            "n": len(vals),
            "p5": round(sum(x["p5"] for x in vals) / len(vals), 4),
            "r5": round(sum(x["r5"] for x in vals if x["r5"] is not None) / max(1, sum(1 for x in vals if x["r5"] is not None)), 4),
            "ndcg10": round(sum(x["ndcg10"] for x in vals if x["ndcg10"] is not None) / max(1, sum(1 for x in vals if x["ndcg10"] is not None)), 4),
            "synonym_n": len(syn),
            "synonym_r5": round(sum(x["r5"] for x in syn if x["r5"] is not None) / max(1, sum(1 for x in syn if x["r5"] is not None)), 4),
        }
    payload = {"date": "2026-11-03", "stack": "youzhihui-411", "metrics": metrics,
               "field_accuracy": report["field_accuracy"], "hard_constraint_violations": hard_errors,
               "dataset": {"goods": len(goods), "queries": len(queries),
                           "synonym": sum(q["subset"] == "synonym" for q in queries),
                           "no_result": sum(q["no_result"] for q in queries)}}
    (DOCS / "ai-eval-411.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (DOCS / "ai-eval-raw-411.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    for api in clients:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())

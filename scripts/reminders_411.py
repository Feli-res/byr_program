"""4.11.2 reminder precision test: 20 must-notify and 20 must-not scenarios."""
import asyncio
import json
import time
import uuid
from pathlib import Path

import load_411 as l

BUYERS = ["l411u43", "l411u44", "l411u45", "l411u46"]
SELLERS = ["l411u23", "l411u24", "l411u25", "l411u26", "l411u27"]


async def main():
    password, _ = l.load_env()
    apis = {}
    for account in set(BUYERS + SELLERS):
        api = l.Api()
        await api.login(account, password)
        apis[account] = api

    # Each buyer has at most ten non-deleted tasks: 5 positive + 5 negative.
    tasks = {}
    for b, buyer in enumerate(BUYERS):
        for i in range(10):
            positive = i < 5
            n = b * 10 + i + 1
            brand = f"REMP-{n:02d}" if positive else f"REMN-{n:02d}"
            data = await apis[buyer].request("POST", "/api/v1/subscriptions", {
                "name": f"4.11 提醒{'正例' if positive else '反例'} {n:02d}",
                "original_query": "4.11 提醒准确率测试",
                "conditions": {
                    "schema_version": 1, "min_price_cents": None, "max_price_cents": 200000,
                    "campus_code": "shahe", "category_id": "1", "brand": brand,
                    "model": None, "min_condition": None, "required_attributes": {},
                    "purpose": "4.11 提醒测试",
                },
                "interval_minutes": 5, "confirmed": True,
            }, expected=(201,))
            tasks[str(data["id"])] = {"brand": brand, "positive": positive, "buyer": buyer}
    print("tasks", len(tasks), flush=True)
    await asyncio.sleep(8)

    # Publish one matching positive and one near-miss negative per scenario.
    goods = {}
    gi = 0
    for task_id, info in tasks.items():
        seller = apis[SELLERS[gi % len(SELLERS)]]
        image = await seller.request("POST", "/api/v1/files", {"purpose": "goods_image"}, expected=(201,), files={
            "file": (f"rem{gi}.png", (l.WORK / "sample.png").read_bytes(), "image/png")
        })
        campus = "shahe" if info["positive"] else "xitucheng"
        price = 100000 if info["positive"] else 300000
        goods_data = await seller.request("POST", "/api/v1/goods", {
            "category_id": "1", "campus_code": campus,
            "title": f"4.11 提醒{'匹配' if info['positive'] else '不匹配'}商品 {gi:02d}",
            "description": "4.11 提醒准确率测试商品。",
            "condition_code": "good", "price_cents": price, "location_text": "沙河校区" if campus == "shahe" else "西土城校区",
            "image_file_ids": [str(image["id"])], "brand": info["brand"], "model": None,
            "purpose": "提醒测试", "attributes": {},
        }, expected=(201,))
        goods[str(goods_data["id"])] = {**info, "task_id": task_id, "created": time.time()}
        gi += 1
    print("goods", len(goods), flush=True)

    # Force the next check; this is a due-time simulation, recorded as such.
    ids = ",".join(tasks)
    l.db(f"UPDATE subscriptions SET next_due_at=UTC_TIMESTAMP(6),needs_full_scan=TRUE WHERE id IN ({ids});")
    print("forced due", flush=True)

    expected = {gid: info for gid, info in goods.items()}
    seen = {}
    deadline = time.monotonic() + 240
    started_wait = time.monotonic()
    while time.monotonic() < deadline:
        rows = l.db("SELECT id,recipient_id,target_id,created_at FROM notifications WHERE kind='goods_match' AND target_id IN (" + ",".join(expected) + ");")
        for line in rows.splitlines():
            nid, recipient, target, created = line.split("\t")
            seen.setdefault(target, []).append({"id": nid, "recipient": recipient, "created": created})
        if time.monotonic() - started_wait > 15 and all(target in seen for target, info in expected.items() if info["positive"]):
            break
        await asyncio.sleep(2)

    results = []
    for gid, info in expected.items():
        rows = seen.get(gid, [])
        results.append({
            "goods_id": gid, "task_id": info["task_id"], "positive": info["positive"],
            "brand": info["brand"], "recipient": info["buyer"],
            "notifications": len(rows),
            "expected": 1 if info["positive"] else 0,
        })
    positives = [r for r in results if r["positive"]]
    negatives = [r for r in results if not r["positive"]]
    tp = sum(1 for r in positives if r["notifications"] >= 1)
    fp = sum(max(0, r["notifications"] - 1) for r in positives) + sum(r["notifications"] for r in negatives)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / len(positives) if positives else 0.0
    dup = sum(max(0, r["notifications"] - 1) for r in results)

    latency = []
    for gid, info in expected.items():
        if not info["positive"] or gid not in seen:
            continue
        created = info["created"]
        for n in seen[gid]:
            # DB timestamps are UTC; compare in SQL below instead of parsing here.
            pass
    lat_rows = l.db("SELECT n.target_id,TIMESTAMPDIFF(MICROSECOND,g.created_at,n.created_at)/1000000 FROM notifications n JOIN goods g ON g.id=n.target_id WHERE n.kind='goods_match' AND n.target_id IN (" + ",".join(expected) + ");")
    for line in lat_rows.splitlines():
        gid, value = line.split("\t")
        if expected.get(gid, {}).get("positive"):
            latency.append(float(value))

    payload = {
        "date": "2026-11-03", "stack": "youzhihui-411",
        "scenarios": {"positive": 20, "negative": 20},
        "positive_with_notification": tp, "negative_with_notification": sum(1 for r in negatives if r["notifications"] > 0),
        "precision": round(precision, 4), "recall": round(recall, 4),
        "duplicate_notifications": dup,
        "latency_seconds": sorted(latency),
        "latency_p95": sorted(latency)[int((len(latency) - 1) * .95)] if latency else None,
        "results": results,
    }
    (l.WORK / "reminders-411.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "results"}, ensure_ascii=False), flush=True)
    for api in apis.values():
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())

"""Recompute reminder counts with DISTINCT notification ids (polling had double-counted)."""
import json
from pathlib import Path
import load_411 as l

text = (l.WORK / "reminders-411.json").read_text(encoding="utf-8")
old = json.loads(text)
results = []
for item in old["results"]:
    gid = item["goods_id"]
    row = l.db(
        "SELECT COUNT(DISTINCT n.id), "
        "COALESCE(MIN(TIMESTAMPDIFF(MICROSECOND,g.created_at,n.created_at)/1000000),0) "
        "FROM notifications n JOIN goods g ON g.id=n.target_id "
        f"WHERE n.kind='goods_match' AND n.target_id={gid};"
    )
    count, latency = (row.split("\t") + ["0", "0"])[:2]
    results.append({**item, "notifications": int(count), "latency_seconds": float(latency) if int(count) else None})
positives = [r for r in results if r["positive"]]
negatives = [r for r in results if not r["positive"]]
tp = sum(1 for r in positives if r["notifications"] >= 1)
fp = sum(max(0, r["notifications"] - 1) for r in positives) + sum(r["notifications"] for r in negatives)
dup = sum(max(0, r["notifications"] - 1) for r in results)
latency = sorted(r["latency_seconds"] for r in positives if r["latency_seconds"] is not None)
payload = {
    "date": old["date"], "stack": old["stack"],
    "scenarios": old["scenarios"],
    "positive_with_notification": tp,
    "negative_with_notification": sum(1 for r in negatives if r["notifications"] > 0),
    "precision": round(tp / (tp + fp), 4) if (tp + fp) else 1.0,
    "recall": round(tp / len(positives), 4),
    "duplicate_notifications": dup,
    "latency_seconds": [round(x, 4) for x in latency],
    "latency_p95": round(latency[int((len(latency) - 1) * .95)], 4) if latency else None,
    "results": results,
    "note": "原轮询按每 2 秒重复读取同一通知，导致计数重复；本文件按 notifications.id 去重并从数据库重算。",
}
(l.WORK / "reminders-411.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in payload.items() if k != "results"}, ensure_ascii=False), flush=True)

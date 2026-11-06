"""No-load single-item index latency probe for the patched 4.11 stack."""
import asyncio
import json
import time
import uuid
from pathlib import Path

import load_411 as l


async def main():
    password, _ = l.load_env()
    api = l.Api()
    await api.login("l411u23", password)
    token = "IDX" + uuid.uuid4().hex[:10]
    image = await api.request("POST", "/api/v1/files", {"purpose": "goods_image"}, expected=(201,), files={
        "file": ("probe.png", (l.WORK / "sample.png").read_bytes(), "image/png")
    })
    started = time.time()
    goods = await api.request("POST", "/api/v1/goods", {
        "category_id": "1", "campus_code": "shahe",
        "title": f"单条索引探针 {token}", "description": "无负载索引延迟检查",
        "condition_code": "good", "price_cents": 100000, "location_text": "沙河校区",
        "image_file_ids": [str(image["id"])], "brand": "PROBE411", "model": None,
        "purpose": "索引探针", "attributes": {},
    }, expected=(201,))
    gid = str(goods["id"])
    db_ready = None
    visible = None
    for _ in range(90):
        row = l.db(f"SELECT state FROM search_documents WHERE kind='goods' AND source_id={gid};")
        if row == "ready" and db_ready is None:
            db_ready = time.time() - started
        try:
            result = await api.get("/api/v1/search?q=" + token + "&mode=semantic&kind=goods&page_size=10")
            if gid in {str(v["id"]) for v in result["items"]}:
                visible = time.time() - started
                break
        except Exception:
            pass
        await asyncio.sleep(1)
    result = {"goods_id": gid, "token": token, "db_ready_seconds": round(db_ready, 2) if db_ready else None,
              "search_visible_seconds": round(visible, 2) if visible else None,
              "target_seconds": 60}
    Path(l.WORK / "probe-index-411.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    await api.close()


if __name__ == "__main__":
    asyncio.run(main())

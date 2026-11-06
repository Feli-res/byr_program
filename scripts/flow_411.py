"""4.11.1 AC20 full flow on the isolated 411 stack, including API restart."""
import asyncio
import json
import subprocess
import time
import uuid
from pathlib import Path

import load_411 as l


async def main():
    password, _ = l.load_env()
    buyer = l.Api()
    seller = l.Api()
    account = "flow411" + uuid.uuid4().hex[:8]
    await buyer.request("POST", "/api/v1/auth/register", {
        "account": account, "password": password, "nickname": "流程验收"
    }, expected=(201,))
    await buyer.login(account, password)
    await seller.login("l411u28", password)
    boards = await buyer.get("/api/v1/boards")
    board = boards["items"][0]["id"]
    post = await buyer.request("POST", "/api/v1/posts", {
        "board_id": board, "title": "4.11 全流程帖子 " + account,
        "body_markdown": "注册、发帖、商品、提醒、私聊和重启检查。",
        "image_file_ids": [], "pdf_file_ids": [],
    }, expected=(201,))
    await buyer.request("POST", f"/api/v1/posts/{post['id']}/comments", {"body": "4.11 全流程评论"}, expected=(201,))
    image = await seller.request("POST", "/api/v1/files", {"purpose": "goods_image"}, expected=(201,), files={
        "file": ("flow.png", (l.WORK / "sample.png").read_bytes(), "image/png")
    })
    goods = await seller.request("POST", "/api/v1/goods", {
        "category_id": "1", "campus_code": "shahe", "title": "4.11 全流程商品",
        "description": "全流程验收商品，沙河交易。", "condition_code": "good",
        "price_cents": 100000, "location_text": "沙河校区",
        "image_file_ids": [str(image["id"])], "brand": "FLOW411", "model": None,
        "purpose": "全流程", "attributes": {},
    }, expected=(201,))
    task = await buyer.request("POST", "/api/v1/subscriptions", {
        "name": "4.11 全流程提醒", "original_query": "全流程提醒",
        "conditions": {"schema_version": 1, "min_price_cents": None, "max_price_cents": 200000,
                       "campus_code": "shahe", "category_id": "1", "brand": "FLOW411",
                       "model": None, "min_condition": None, "required_attributes": {},
                       "purpose": "全流程"},
        "interval_minutes": 5, "confirmed": True,
    }, expected=(201,))
    conv = await buyer.request("POST", "/api/v1/conversations", {"goods_id": goods["id"]})
    message = await buyer.request("POST", f"/api/v1/conversations/{conv['id']}/messages", {
        "client_message_id": str(uuid.uuid4()), "body": "4.11 全流程私聊消息"
    }, expected=(201,))
    image2 = await seller.request("POST", "/api/v1/files", {"purpose": "goods_image"}, expected=(201,), files={
        "file": ("flow2.png", (l.WORK / "sample.png").read_bytes(), "image/png")
    })
    combined = await seller.request("POST", "/api/v1/goods", {
        "category_id": "1", "campus_code": "shahe", "title": "4.11 全流程匹配商品",
        "description": "提醒匹配商品。", "condition_code": "good", "price_cents": 100000,
        "location_text": "沙河校区", "image_file_ids": [str(image2["id"])],
        "brand": "FLOW411", "model": None, "purpose": "全流程", "attributes": {},
    }, expected=(201,))
    me = await buyer.get("/api/v1/me")
    l.db(f"UPDATE subscriptions SET next_due_at=UTC_TIMESTAMP(6),needs_full_scan=TRUE WHERE id={task['id']};")
    deadline = time.monotonic() + 120
    notified = False
    while time.monotonic() < deadline:
        rows = l.db(f"SELECT COUNT(*) FROM notifications WHERE kind='goods_match' AND recipient_id={me['id']} AND target_id={combined['id']};")
        if rows not in ("0", ""):
            notified = True
            break
        await asyncio.sleep(2)
    # Restart only the isolated API; sessions/data live in MySQL/Redis.
    subprocess.run(["docker", "restart", "youzhihui-411-api-1"], check=True, timeout=90, stdout=subprocess.DEVNULL)
    for _ in range(60):
        try:
            if (await buyer.get("/health/ready")):
                break
        except Exception:
            await asyncio.sleep(1)
    await asyncio.sleep(3)
    read_post = await buyer.get(f"/api/v1/posts/{post['id']}")
    read_messages = await buyer.get(f"/api/v1/conversations/{conv['id']}/messages")
    read_notices = await buyer.get("/api/v1/notifications?page_size=50")
    payload = {
        "account": account, "post_id": post["id"], "goods_id": goods["id"],
        "task_id": task["id"], "conversation_id": conv["id"], "message_id": message["id"],
        "reminder_notified": notified,
        "post_after_restart": read_post["title"].startswith("4.11 全流程帖子"),
        "message_after_restart": any(m["id"] == message["id"] for m in read_messages["items"]),
        "notification_after_restart": any(str(n.get("target_id")) == str(combined["id"]) for n in read_notices["items"]),
    }
    (l.WORK / "flow-411.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    await buyer.close()
    await seller.close()


if __name__ == "__main__":
    asyncio.run(main())

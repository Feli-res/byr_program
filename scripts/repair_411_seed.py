"""Finish the interrupted 4.11 seed without duplicating posts/comments/goods."""
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seed_411 import Client, WORK, load_password

MYSQL = "youzhihui-411-mysql-1"
DB = "youzhihui_411"


def db(sql):
    result = subprocess.run(
        ["docker", "exec", "-e", "SQL=" + sql, MYSQL, "sh", "-c",
         'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --batch --skip-column-names -D ' + DB + ' -e "$SQL"'],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-500:])
    return [line.split("\t") for line in result.stdout.strip().splitlines() if line]


def main():
    password, admin_account = load_password()
    base = "http://127.0.0.1:18092"
    origin = "http://localhost:18093"
    admin = Client(base, origin)
    admin.login(admin_account, password)
    post_ids = [r[0] for r in db("SELECT id FROM posts ORDER BY id;")]
    goods_ids = [r[0] for r in db("SELECT id FROM goods ORDER BY id;")]
    print("existing", len(post_ids), "posts", len(goods_ids), "goods", flush=True)
    if len(post_ids) < 1000 or len(goods_ids) < 500:
        raise SystemExit("base content incomplete; run full seed instead")

    users = {}
    for i in range(1, 50):
        account = f"l411u{i:02d}"
        client = Client(base, origin)
        client.login(account, password)
        users[account] = client

    existing_messages = int(db("SELECT COUNT(*) FROM messages;")[0][0])
    print("existing messages", existing_messages, flush=True)
    conversations = []
    for i in range(25):
        seller_idx, buyer_idx = 23 + (i % 5), 33 + (i % 5)
        seller = users[f"l411u{seller_idx:02d}"]
        buyer = users[f"l411u{buyer_idx:02d}"]
        gid = goods_ids[(i % 5) + 10 * (i // 5)]
        conv = buyer.write("POST", "/api/v1/conversations", {"goods_id": gid})
        cid = str(conv["id"])
        if i >= 5:
            for j in range(80):
                client = seller if j % 2 == 0 else buyer
                client.write("POST", f"/api/v1/conversations/{cid}/messages", {
                    "client_message_id": str(uuid.uuid4()),
                    "body": f"会话 {i + 1} 第 {j + 1} 条压测消息，用于历史与实时链路。",
                }, expected=201)
        conversations.append({"cid": cid, "seller": f"l411u{seller_idx:02d}", "buyer": f"l411u{buyer_idx:02d}", "goods_id": gid})
        if i >= 5:
            print("conversation", i + 1, "messages", (i - 4) * 80, flush=True)

    task_ids = [r[0] for r in db("SELECT id FROM subscriptions ORDER BY id;")]
    if len(task_ids) < 100:
        for i in range(len(task_ids), 100):
            buyer = users[f"l411u{33 + (i % 10):02d}"]
            brand = f"LOADMATCH-{i - 94:02d}" if i >= 95 else f"LOADNOMATCH-{i:03d}"
            conditions = {
                "schema_version": 1, "min_price_cents": None,
                "max_price_cents": 500000 if i >= 95 else 100000,
                "campus_code": "shahe", "category_id": "1",
                "brand": brand, "model": None, "min_condition": None,
                "required_attributes": {}, "purpose": "压测提醒",
            }
            task = buyer.write("POST", "/api/v1/subscriptions", {
                "name": f"4.11 压测任务 {i + 1:03d}", "original_query": "4.11 压测提醒任务",
                "conditions": conditions, "interval_minutes": 5, "confirmed": True,
            }, expected=201)
            task_ids.append(str(task["id"]))
            if (i + 1) % 20 == 0:
                print("tasks", i + 1, flush=True)
    else:
        print("tasks already", len(task_ids), flush=True)

    # Pull the canonical conversation/user mapping from the database.
    rows = db("""
      SELECT c.id, c.context_goods_id, ul.account, uh.account
      FROM conversations c
      JOIN users ul ON ul.id=c.user_low_id
      JOIN users uh ON uh.id=c.user_high_id
      ORDER BY c.id;
    """)
    conversations = []
    for cid, gid, low, high in rows:
        conversations.append({"cid": cid, "goods_id": gid, "seller": low, "buyer": high})
    out = {
        "base": base, "origin": origin, "admin": admin_account,
        "boards": ["1", "2"], "categories": ["1", "2", "3", "4"],
        "post_ids": post_ids, "goods_ids": goods_ids,
        "conversations": conversations, "task_ids": task_ids,
        "users": [f"l411u{i:02d}" for i in range(1, 50)],
        "counts": {"accounts": 50, "posts": 1000, "comments": 3000, "goods": 500, "messages": 2000, "tasks": 100},
        "elapsed_seconds": None,
    }
    Path(WORK / "seed_ids.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {name: db(f"SELECT COUNT(*) FROM {table};")[0][0] for name, table in [
        ("posts", "posts"), ("comments", "comments"), ("goods", "goods"),
        ("messages", "messages"), ("tasks", "subscriptions"), ("users", "users"),
        ("conversations", "conversations")]}
    print(json.dumps(counts, ensure_ascii=False), flush=True)
    print("SEED_REPAIR_OK", flush=True)
    for client in users.values():
        client.close()
    admin.close()


if __name__ == "__main__":
    main()

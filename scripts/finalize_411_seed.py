"""Write the 4.11 seed manifest from the isolated database after seeding."""
import json
import subprocess
from pathlib import Path

WORK = Path("/home/sunxiang/youzhihui/acceptance411-work")
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
    post_ids = [r[0] for r in db("SELECT id FROM posts ORDER BY id;")]
    goods_ids = [r[0] for r in db("SELECT id FROM goods ORDER BY id;")]
    task_ids = [r[0] for r in db("SELECT id FROM subscriptions ORDER BY id;")]
    rows = db("""
      SELECT c.id, c.context_goods_id, ul.account_norm, uh.account_norm
      FROM conversations c
      JOIN users ul ON ul.id=c.user_low_id
      JOIN users uh ON uh.id=c.user_high_id
      ORDER BY c.id;
    """)
    conversations = [{"cid": r[0], "goods_id": r[1], "seller": r[2], "buyer": r[3]} for r in rows]
    counts = {name: int(db(f"SELECT COUNT(*) FROM {table};")[0][0]) for name, table in [
        ("users", "users"), ("posts", "posts"), ("comments", "comments"), ("goods", "goods"),
        ("messages", "messages"), ("tasks", "subscriptions"), ("conversations", "conversations"),
    ]}
    payload = {
        "base": "http://127.0.0.1:18092",
        "origin": "http://localhost:18093",
        "admin": "load411admin",
        "boards": ["1", "2"],
        "categories": ["1", "2", "3", "4"],
        "post_ids": post_ids,
        "goods_ids": goods_ids,
        "conversations": conversations,
        "task_ids": task_ids,
        "users": [f"l411u{i:02d}" for i in range(1, 50)],
        "counts": {"accounts": 50, "posts": 1000, "comments": 3000, "goods": 500, "messages": 2000, "tasks": 100},
        "elapsed_seconds": None,
    }
    (WORK / "seed_ids.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False), flush=True)
    print("FINALIZE_OK", flush=True)


if __name__ == "__main__":
    main()

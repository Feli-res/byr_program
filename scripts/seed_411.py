"""Seed the isolated 4.11 load database through the real API.

Runs on the server against youzhihui-411 only. It refuses to target the trial API.
"""
import argparse
import json
import os
import random
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE_DEFAULT = "http://127.0.0.1:18092"
ORIGIN_DEFAULT = "http://localhost:18093"
PROJECT_BASE = Path(os.environ.get("YOUZHIHUI_BASE", "/srv/youzhihui"))
WORK = PROJECT_BASE / "acceptance411-work"
ENV_FILE = PROJECT_BASE / "acceptance411/test.env"


def load_password():
    text = ENV_FILE.read_text(encoding="utf-8")
    env = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    return env["LOAD411_PASSWORD"], env.get("LOAD411_ADMIN", "load411admin")


class Client:
    def __init__(self, base, origin):
        self.base = base
        self.origin = origin
        self.http = httpx.Client(base_url=base, timeout=30, headers={"Origin": origin})
        self.token = None

    def close(self):
        self.http.close()

    def csrf(self):
        if not self.token:
            r = self.http.get("/api/v1/csrf")
            self._check(r, 200)
            self.token = r.json()["data"]["csrf_token"]
        return self.token

    def _check(self, r, expected):
        if r.status_code != expected:
            raise RuntimeError(f"{r.request.method} {r.request.url} -> {r.status_code}: {r.text[:800]}")
        return r

    def get(self, path, expected=200):
        return self._check(self.http.get(path), expected).json()["data"]

    def write(self, method, path, body=None, files=None, expected=200):
        headers = {"X-CSRF-Token": self.csrf()}
        for attempt in range(2):
            if files is None:
                r = self.http.request(method, path, json=body, headers=headers)
            else:
                r = self.http.request(method, path, data=body or {}, files=files, headers=headers)
            if r.status_code == 403 and "CSRF" in r.text and attempt == 0:
                self.token = None
                headers["X-CSRF-Token"] = self.csrf()
                continue
            self._check(r, expected)
            return r.json()["data"]
        raise RuntimeError("CSRF retry failed")

    def login(self, account, password):
        result = self.write("POST", "/api/v1/auth/login", {"account": account, "password": password})
        self.token = None
        return result

    def register(self, account, password, nickname):
        try:
            result = self.write("POST", "/api/v1/auth/register", {"account": account, "password": password, "nickname": nickname}, expected=201)
            self.token = None
            self.login(account, password)
            return result
        except RuntimeError as error:
            if "-> 409" in str(error):
                return self.login(account, password)
            raise


POST_TOPICS = [
    ("课程学习", "这学期课程安排和复习资料整理，欢迎交流。"),
    ("校园生活", "宿舍附近吃饭和出行经验，分享一下。"),
    ("考研复习", "考研数学和英语复习方法，求建议。"),
    ("编程开发", "写代码和做课程项目时遇到的问题。"),
    ("数码设备", "平板、笔记本和耳机使用体验。"),
    ("二手交易", "出闲置物品和求购需求，注意当面交易。"),
]
GOODS = [
    ("数码设备", "Apple", "iPad 教育优惠平板", ["记笔记", "课堂", "手写笔"], 180000, "shahe", "good", {"stylus_support": True}),
    ("数码设备", "HUAWEI", "华为 MatePad 学习平板", ["记笔记", "网课", "轻办公"], 150000, "shahe", "like_new", {"stylus_support": True}),
    ("数码设备", "Lenovo", "联想小新轻薄笔记本", ["写代码", "课程作业", "便携"], 260000, "xitucheng", "good", {}),
    ("数码设备", "Xiaomi", "小米降噪耳机", ["通勤", "自习", "听网课"], 30000, "shahe", "new", {}),
    ("图书资料", None, "考研数学复习全书", ["考研", "复习", "数学"], 4000, "shahe", "good", {}),
    ("图书资料", None, "计算机网络教材", ["课程", "编程", "考试"], 2500, "xitucheng", "like_new", {}),
    ("生活用品", None, "宿舍台灯", ["宿舍", "学习", "夜间"], 3500, "shahe", "good", {}),
    ("生活用品", None, "折叠自行车", ["通勤", "校园", "出行"], 45000, "other", "fair", {}),
    ("数码设备", "Sony", "索尼降噪耳机", ["自习", "通勤", "音乐"], 60000, "shahe", "like_new", {}),
    ("数码设备", "Dell", "戴尔显示器", ["写代码", "宿舍", "外接屏"], 70000, "xitucheng", "good", {}),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE_DEFAULT)
    parser.add_argument("--origin", default=ORIGIN_DEFAULT)
    parser.add_argument("--image", default=str(WORK / "sample.png"))
    parser.add_argument("--out", default=str(WORK / "seed_ids.json"))
    args = parser.parse_args()
    if "18092" not in args.base and "411" not in args.base:
        raise SystemExit("refusing non-411 API target")
    password, admin_account = load_password()
    image = Path(args.image).read_bytes()
    if len(image) < 20:
        raise SystemExit("image fixture missing")
    rng = random.Random(411)
    started = time.time()
    admin = Client(args.base, args.origin)
    admin.login(admin_account, password)
    boards = admin.get("/api/v1/boards")["items"]
    if len(boards) < 2:
        raise SystemExit("need two boards")
    board_ids = [str(b["id"]) for b in boards[:2]]
    categories = admin.get("/api/v1/goods-categories")
    if len(categories) < 2:
        raise SystemExit("need categories")
    cat_by_name = {c["name"]: str(c["id"]) for c in categories}
    cat_ids = [str(c["id"]) for c in categories]
    print("boards", board_ids, "categories", cat_ids, flush=True)

    users = {}
    for i in range(1, 50):
        account = f"l411u{i:02d}"
        client = Client(args.base, args.origin)
        client.register(account, password, f"压测用户{i:02d}")
        users[account] = client
    print("registered", len(users), flush=True)

    # Two moderators, one per board.
    all_users = {u["account"]: u for u in admin.get("/api/v1/admin/users?page_size=100")["items"]}
    for idx, board in enumerate(board_ids):
        account = f"l411u{idx + 1:02d}"
        target = all_users[account]
        admin.write("PATCH", f"/api/v1/admin/users/{target['id']}/role", {
            "role": "moderator", "board_ids": [board], "version": target["version"], "reason": "4.11 压测角色准备"
        })
    print("moderators ready", flush=True)

    # 1,000 posts across two boards.
    post_ids = []
    authors = [users[f"l411u{i:02d}"] for i in range(3, 23)]
    for i in range(1000):
        client = authors[i % len(authors)]
        topic, body = POST_TOPICS[i % len(POST_TOPICS)]
        post = client.write("POST", "/api/v1/posts", {
            "board_id": board_ids[i % 2],
            "title": f"{topic} {i + 1:04d} 压测讨论",
            "body_markdown": f"{body} 第 {i + 1} 条，用于 4.11 混合负载和搜索测试。",
            "image_file_ids": [],
            "pdf_file_ids": [],
        }, expected=201)
        post_ids.append(str(post["id"]))
        if (i + 1) % 200 == 0:
            print("posts", i + 1, flush=True)
    print("posts done", len(post_ids), flush=True)

    # 3,000 comments, 30% replies.
    commenters = [users[f"l411u{i:02d}"] for i in range(20, 50)]
    last_comment = {}
    for i in range(3000):
        client = commenters[i % len(commenters)]
        pid = post_ids[(i * 7) % len(post_ids)]
        parent = None
        if i % 10 < 3 and last_comment.get(pid):
            parent = last_comment[pid]
        body = {"body": f"压测评论 {i + 1}，用于评论列表和回复关系检查。"}
        if parent:
            body["parent_id"] = parent
        reply = client.write("POST", f"/api/v1/posts/{pid}/comments", body, expected=201)
        last_comment[pid] = str(reply["id"])
        if (i + 1) % 500 == 0:
            print("comments", i + 1, flush=True)
    print("comments done", flush=True)

    # 500 goods, one unique image each.
    goods_ids = []
    sellers = [users[f"l411u{i:02d}"] for i in range(23, 33)]
    for i in range(500):
        seller = sellers[i % len(sellers)]
        name, brand, title, purposes, price, campus, condition, attrs = GOODS[i % len(GOODS)]
        category = cat_by_name.get(name, cat_ids[i % len(cat_ids)])
        image_data = seller.write("POST", "/api/v1/files", {"purpose": "goods_image"}, files={
            "file": (f"load{i:04d}.png", image, "image/png")
        }, expected=201)
        variant = i // len(GOODS)
        goods = seller.write("POST", "/api/v1/goods", {
            "category_id": category,
            "campus_code": campus,
            "title": f"{title} {variant + 1:02d} 压测商品",
            "description": "适合" + "、".join(purposes) + "；4.11 负载与语义检索测试数据。",
            "condition_code": condition,
            "price_cents": price + (i % 17) * 100,
            "location_text": "沙河校区" if campus == "shahe" else "西土城校区",
            "image_file_ids": [str(image_data["id"])],
            "brand": brand,
            "model": None,
            "purpose": "、".join(purposes),
            "attributes": attrs,
        }, expected=201)
        goods_ids.append(str(goods["id"]))
        if (i + 1) % 100 == 0:
            print("goods", i + 1, flush=True)
    print("goods done", len(goods_ids), flush=True)

    # 25 conversations x 80 messages = 2,000 messages.
    conversations = []
    pairs = [(23 + i, 33 + i) for i in range(5)]
    for i in range(25):
        seller_idx, buyer_idx = pairs[i % len(pairs)]
        seller = users[f"l411u{seller_idx:02d}"]
        buyer = users[f"l411u{buyer_idx:02d}"]
        gid = goods_ids[(i % 5) + 10 * (i // 5)]
        conv = buyer.write("POST", "/api/v1/conversations", {"goods_id": gid})
        cid = str(conv["id"])
        conversations.append({"cid": cid, "seller": f"l411u{seller_idx:02d}", "buyer": f"l411u{buyer_idx:02d}", "goods_id": gid})
        for j in range(80):
            client = seller if j % 2 == 0 else buyer
            client.write("POST", f"/api/v1/conversations/{cid}/messages", {
                "client_message_id": str(uuid.uuid4()),
                "body": f"会话 {i + 1} 第 {j + 1} 条压测消息，用于历史与实时链路。",
            }, expected=201)
        if (i + 1) % 5 == 0:
            print("conversations", i + 1, flush=True)
    print("messages done", len(conversations) * 80, flush=True)

    # 100 tasks: 95 no-match and 5 controlled positives.
    task_ids = []
    for i in range(100):
        buyer = users[f"l411u{33 + (i % 10):02d}"]
        brand = f"LOADMATCH-{i - 94:02d}" if i >= 95 else f"LOADNOMATCH-{i:03d}"
        conditions = {
            "schema_version": 1,
            "min_price_cents": None,
            "max_price_cents": 500000 if i >= 95 else 100000,
            "campus_code": "shahe",
            "category_id": cat_by_name.get("数码设备", cat_ids[0]),
            "brand": brand,
            "model": None,
            "min_condition": None,
            "required_attributes": {},
            "purpose": "压测提醒",
        }
        task = buyer.write("POST", "/api/v1/subscriptions", {
            "name": f"4.11 压测任务 {i + 1:03d}",
            "original_query": "4.11 压测提醒任务",
            "conditions": conditions,
            "interval_minutes": 5,
            "confirmed": True,
        }, expected=201)
        task_ids.append(str(task["id"]))
    print("tasks done", len(task_ids), flush=True)

    out = {
        "base": args.base,
        "origin": args.origin,
        "admin": admin_account,
        "boards": board_ids,
        "categories": cat_ids,
        "post_ids": post_ids,
        "goods_ids": goods_ids,
        "conversations": conversations,
        "task_ids": task_ids,
        "users": [f"l411u{i:02d}" for i in range(1, 50)],
        "counts": {"accounts": 50, "posts": 1000, "comments": 3000, "goods": 500, "messages": 2000, "tasks": 100},
        "elapsed_seconds": round(time.time() - started, 1),
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("post_ids", "goods_ids", "conversations", "task_ids", "users")}, ensure_ascii=False), flush=True)
    print("SEED_OK", flush=True)
    for client in users.values():
        client.close()
    admin.close()


if __name__ == "__main__":
    main()

"""Mixed load test for the isolated 4.11 stack.

Runs on the server, targets only 127.0.0.1:18092, and writes load-411.json.
"""
import argparse
import asyncio
import json
import os
import random
import statistics
import subprocess
import time
import uuid
from collections import defaultdict
from pathlib import Path

import httpx
import websockets

BASE = "http://127.0.0.1:18092"
ORIGIN = "http://localhost:18093"
WORK = Path("/home/sunxiang/youzhihui/acceptance411-work")
ENV_FILE = Path("/home/sunxiang/youzhihui/acceptance411/test.env")
MYSQL = "youzhihui-411-mysql-1"
DB = "youzhihui_411"
THRESHOLDS = {
    "list": 1.0,
    "detail": 1.0,
    "post_create": 1.0,
    "comment_create": 1.0,
    "keyword_search": 2.0,
    "semantic_search": 3.0,
    "chat_delivery": 2.0,
    "reminder_delivery": 420.0,
}

TOPICS = ["课程学习", "校园生活", "考研复习", "编程开发", "数码设备", "二手交易"]
SEARCH_TERMS = ["平板", "记笔记", "考研", "笔记本", "耳机", "自行车", "宿舍", "编程"]


def load_env():
    text = ENV_FILE.read_text(encoding="utf-8")
    env = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    return env["LOAD411_PASSWORD"], env.get("LOAD411_ADMIN", "load411admin")


def db(sql):
    result = subprocess.run(
        ["docker", "exec", "-e", "SQL=" + sql, MYSQL, "sh", "-c",
         'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 --batch --skip-column-names -D ' + DB + ' -e "$SQL"'],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError("db query failed: " + result.stderr[-500:])
    return result.stdout.strip()


class Api:
    def __init__(self):
        self.http = httpx.AsyncClient(base_url=BASE, timeout=25, headers={"Origin": ORIGIN})
        self.token = None

    async def close(self):
        await self.http.aclose()

    async def csrf(self):
        if not self.token:
            r = await self.http.get("/api/v1/csrf")
            if r.status_code != 200:
                raise RuntimeError("csrf failed")
            self.token = r.json()["data"]["csrf_token"]
        return self.token

    async def login(self, account, password):
        token = await self.csrf()
        r = await self.http.post("/api/v1/auth/login", json={"account": account, "password": password},
                                 headers={"X-CSRF-Token": token})
        if r.status_code != 200:
            raise RuntimeError(f"login {account}: {r.status_code} {r.text[:300]}")
        self.token = None
        return r.json()["data"]

    async def request(self, method, path, body=None, expected=(200,), files=None):
        token = await self.csrf()
        headers = {"X-CSRF-Token": token}
        for attempt in range(2):
            if files is None:
                r = await self.http.request(method, path, json=body, headers=headers)
            else:
                r = await self.http.request(method, path, data=body or {}, files=files, headers=headers)
            if r.status_code == 403 and "CSRF" in r.text and attempt == 0:
                self.token = None
                headers["X-CSRF-Token"] = await self.csrf()
                continue
            if r.status_code not in expected:
                raise RuntimeError(f"{method} {path}: {r.status_code} {r.text[:300]}")
            return r.json().get("data")
        raise RuntimeError("CSRF retry failed")

    async def get(self, path):
        r = await self.http.get(path)
        if r.status_code != 200:
            raise RuntimeError(f"GET {path}: {r.status_code}")
        return r.json()["data"]

    def cookie_header(self):
        return "; ".join(f"{k}={v}" for k, v in self.http.cookies.items())


async def wait_index():
    deadline = time.monotonic() + 1800
    last = None
    while time.monotonic() < deadline:
        try:
            total = int(db("SELECT COUNT(*) FROM search_documents WHERE state='ready';"))
            goods = int(db("SELECT COUNT(*) FROM search_documents WHERE state='ready' AND kind='goods';"))
            posts = int(db("SELECT COUNT(*) FROM search_documents WHERE state='ready' AND kind='post';"))
        except Exception as error:
            print("index query error", error, flush=True)
            await asyncio.sleep(5)
            continue
        last = (total, goods, posts)
        print(f"index ready total={total} goods={goods} posts={posts}", flush=True)
        if goods >= 500 and total >= 1500:
            return last
        await asyncio.sleep(5)
    raise RuntimeError(f"index not ready: {last}")


async def wait_task_first_scan(task_ids):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        checked = int(db("SELECT COUNT(*) FROM subscriptions WHERE id IN (" + ",".join(task_ids) + ") AND last_checked_at IS NOT NULL;"))
        print("tasks first scan", checked, "/", len(task_ids), flush=True)
        if checked == len(task_ids):
            return
        await asyncio.sleep(2)
    print("warning: not all tasks completed first scan", flush=True)


async def publish_reminder_goods(sellers):
    """Publish five goods matching the five controlled tasks."""
    created = []
    for index, seller in enumerate(sellers, start=1):
        image = await seller.request("POST", "/api/v1/files", {"purpose": "goods_image"}, expected=(201,), files={
            "file": (f"match{index}.png", (WORK / "sample.png").read_bytes(), "image/png")
        })
        goods = await seller.request("POST", "/api/v1/goods", {
            "category_id": "1",
            "campus_code": "shahe",
            "title": f"4.11 压测提醒匹配商品 {index}",
            "description": "4.11 提醒延迟测试商品，沙河交易。",
            "condition_code": "good",
            "price_cents": 100000,
            "location_text": "沙河校区",
            "image_file_ids": [str(image["id"])],
            "brand": f"LOADMATCH-{index:02d}",
            "model": None,
            "purpose": "压测提醒",
            "attributes": {},
        }, expected=(201,))
        created.append({"id": str(goods["id"]), "brand": f"LOADMATCH-{index:02d}", "created": time.time()})
        print("published reminder goods", index, goods["id"], flush=True)
    return created


async def publish_index_goods(seller):
    token = "INDEX411" + uuid.uuid4().hex[:8]
    image = await seller.request("POST", "/api/v1/files", {"purpose": "goods_image"}, expected=(201,), files={
        "file": ("index.png", (WORK / "sample.png").read_bytes(), "image/png")
    })
    goods = await seller.request("POST", "/api/v1/goods", {
        "category_id": "1", "campus_code": "shahe",
        "title": f"4.11 索引延迟 {token}",
        "description": "索引同步测试商品。",
        "condition_code": "good", "price_cents": 100000, "location_text": "沙河校区",
        "image_file_ids": [str(image["id"])], "brand": "INDEX411", "model": None,
        "purpose": "索引测试", "attributes": {},
    }, expected=(201,))
    return token, str(goods["id"]), time.time()


async def wait_index_visible(client, token, goods_id, started):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            result = await client.get("/api/v1/search?q=" + token + "&mode=semantic&kind=goods&page_size=10")
            ids = {str(v["id"]) for v in result["items"]}
            if goods_id in ids:
                return time.time() - started
        except Exception:
            pass
        await asyncio.sleep(1)
    return None


async def worker(api, wid, data, post_ids, stop, measure_start, samples, errors, semantic_modes):
    rng = random.Random(411 + wid)
    counter = 0
    while time.monotonic() < stop:
        counter += 1
        choice = rng.random()
        category = "list"
        start = time.perf_counter()
        try:
            if choice < 0.25:
                await api.get("/api/v1/posts?page=1&page_size=20")
                category = "list"
            elif choice < 0.45:
                pid = post_ids[(counter * 7 + wid) % len(post_ids)]
                await api.get("/api/v1/posts/" + pid)
                category = "detail"
            elif choice < 0.55:
                await api.request("POST", "/api/v1/posts", {
                    "board_id": data["boards"][wid % 2],
                    "title": f"压测实时帖子 {wid}-{counter}",
                    "body_markdown": f"混合负载写入 {wid}-{counter}",
                    "image_file_ids": [], "pdf_file_ids": [],
                }, expected=(201,))
                category = "post_create"
            elif choice < 0.65:
                pid = post_ids[(counter * 11 + wid) % len(post_ids)]
                await api.request("POST", f"/api/v1/posts/{pid}/comments", {
                    "body": f"压测实时评论 {wid}-{counter}"
                }, expected=(201,))
                category = "comment_create"
            elif choice < 0.80:
                term = SEARCH_TERMS[(counter + wid) % len(SEARCH_TERMS)]
                await api.get("/api/v1/search?q=" + term + "&mode=keyword&kind=all&page_size=10")
                category = "keyword_search"
            elif choice < 0.90:
                result = await api.get("/api/v1/search?q=%E9%80%82%E5%90%88%E4%B8%8A%E8%AF%BE%E8%AE%B0%E7%AC%94%E8%AE%B0%E7%9A%84%E5%B9%B3%E6%9D%BF&mode=semantic&kind=goods&page_size=10")
                key = f"{result.get('mode_used')}|degraded={bool(result.get('degraded'))}"
                semantic_modes[key] += 1
                category = "semantic_search"
            else:
                gid = data["goods_ids"][(counter * 13 + wid) % len(data["goods_ids"])]
                await api.get("/api/v1/goods/" + gid)
                category = "detail"
            elapsed = time.perf_counter() - start
            if time.monotonic() >= measure_start:
                samples[category].append(elapsed)
        except Exception as error:
            if time.monotonic() >= measure_start:
                errors[category].append(f"{type(error).__name__}: {error}")
            await asyncio.sleep(0.5)
        await asyncio.sleep(rng.uniform(0.20, 0.45))


async def ws_pair(index, seller, buyer, conv, stop, measure_start, samples, errors):
    try:
        st = await seller.request("POST", "/api/v1/ws-tickets", {}, expected=(200,))
        bt = await buyer.request("POST", "/api/v1/ws-tickets", {}, expected=(200,))
        ws_url = "ws://127.0.0.1:18092/api/v1/ws"
        s_ws = await websockets.connect(ws_url, origin=ORIGIN, additional_headers={"Cookie": seller.cookie_header()}, open_timeout=8)
        b_ws = await websockets.connect(ws_url, origin=ORIGIN, additional_headers={"Cookie": buyer.cookie_header()}, open_timeout=8)

        async def auth(ws, ticket):
            rid = str(uuid.uuid4())
            await ws.send(json.dumps({"type": "authenticate", "request_id": rid, "data": {"ticket": ticket}}))
            while True:
                frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
                if frame.get("type") == "ready":
                    return
                if frame.get("type") == "error":
                    raise RuntimeError(frame)
        await auth(s_ws, st["ticket"])
        await auth(b_ws, bt["ticket"])
        print("ws pair ready", index, flush=True)
        n = 0
        while time.monotonic() < stop:
            n += 1
            send_ws, recv_ws = (s_ws, b_ws) if n % 2 else (b_ws, s_ws)
            mid = str(uuid.uuid4())
            started = time.perf_counter()
            await send_ws.send(json.dumps({
                "type": "message.send", "request_id": str(uuid.uuid4()),
                "data": {"conversation_id": conv["cid"], "client_message_id": mid,
                         "body": f"ws 压测 {index}-{n}"},
            }))
            # Wait for the matching created event on the peer.
            got = False
            deadline = time.perf_counter() + 5
            while time.perf_counter() < deadline:
                try:
                    frame = json.loads(await asyncio.wait_for(recv_ws.recv(), timeout=max(0.1, deadline - time.perf_counter())))
                except asyncio.TimeoutError:
                    break
                if frame.get("type") == "message.created" and frame.get("data", {}).get("client_message_id") == mid:
                    got = True
                    break
            latency = time.perf_counter() - started
            if got and time.monotonic() >= measure_start:
                samples["chat_delivery"].append(latency)
            elif not got:
                errors["chat_delivery"].append("message.created timeout")
            await asyncio.sleep(8 + (index % 5))
        await s_ws.close()
        await b_ws.close()
    except Exception as error:
        errors["chat_delivery"].append(f"{type(error).__name__}: {error}")
        print("ws pair error", index, round(time.time() % 100000, 1), error, flush=True)


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default=str(WORK / "seed_ids.json"))
    parser.add_argument("--out", default=str(WORK / "load-411.json"))
    parser.add_argument("--http-workers", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--skip-reminders", action="store_true")
    parser.add_argument("--skip-index", action="store_true")
    args = parser.parse_args()
    if "18092" not in BASE:
        raise SystemExit("refusing non-411 target")
    data = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    password, _ = load_env()
    print("waiting for semantic index", flush=True)
    await wait_index()
    if not args.skip_reminders:
        await wait_task_first_scan(data["task_ids"][-5:])

    # Build worker and chat accounts.
    accounts = data["users"]
    apis = {}
    for account in accounts:
        api = Api()
        await api.login(account, password)
        apis[account] = api

    sellers = [apis[f"l411u{i:02d}"] for i in range(23, 28)]
    reminder_goods = [] if args.skip_reminders else await publish_reminder_goods(sellers)
    if args.skip_index:
        index_token = index_id = None
        index_started = None
    else:
        index_seller = apis["l411u28"]
        index_token, index_id, index_started = await publish_index_goods(index_seller)

    samples = defaultdict(list)
    errors = defaultdict(list)
    semantic_modes = defaultdict(int)
    measure_start_wall = time.time() + args.warmup
    stop_wall = measure_start_wall + args.duration
    measure_start_mono = time.monotonic() + args.warmup
    stop_mono = measure_start_mono + args.duration
    print(f"load start in {args.warmup}s, measure {args.duration}s", flush=True)

    workers = []
    for i in range(args.http_workers):
        account = f"l411u{(i % 20) + 3:02d}"
        workers.append(asyncio.create_task(worker(apis[account], i, data, data["post_ids"], stop_mono, measure_start_mono, samples, errors, semantic_modes)))

    convs = data["conversations"]
    pairs = []
    seen = set()
    for c in convs:
        key = (c["seller"], c["buyer"])
        if key not in seen:
            seen.add(key)
            pairs.append(c)
        if len(pairs) == 5:
            break

    async def reminder_watch():
        if not reminder_goods:
            return
        pending = {g["id"]: g for g in reminder_goods}
        buyer_by_brand = {}
        for i in range(5):
            buyer_by_brand[f"LOADMATCH-{i + 1:02d}"] = f"l411u{38 + i:02d}"
        started = {g["id"]: g["created"] for g in reminder_goods}
        while pending and time.monotonic() < stop_mono + 180:
            for gid, g in list(pending.items()):
                account = buyer_by_brand[g["brand"]]
                try:
                    notices = await apis[account].get("/api/v1/notifications?page_size=50")
                    if any(str(n.get("target_id")) == gid and n.get("kind") == "goods_match" for n in notices["items"]):
                        samples["reminder_delivery"].append(time.time() - started[gid])
                        del pending[gid]
                except Exception:
                    pass
            await asyncio.sleep(2)
        for gid in pending:
            errors["reminder_delivery"].append(f"no notification for {gid}")

    tasks = await asyncio.gather(
        *workers,
        *(ws_pair(i, apis[c["seller"]], apis[c["buyer"]], c, stop_mono, measure_start_mono, samples, errors) for i, c in enumerate(pairs)),
        reminder_watch(),
        return_exceptions=True,
    )
    for t in tasks:
        if isinstance(t, Exception):
            errors["runner"].append(f"{type(t).__name__}: {t}")

    index_latency = None if index_id is None else await wait_index_visible(apis["l411u29"], index_token, index_id, index_started)
    if index_id:
        # Prefer the persisted timestamps: polling after the load window would count the wait itself.
        try:
            actual = db(
                "SELECT TIMESTAMPDIFF(SECOND,g.created_at,d.indexed_at) "
                "FROM search_documents d JOIN goods g ON g.id=d.source_id "
                f"WHERE d.kind='goods' AND d.source_id={int(index_id)} AND d.state='ready';"
            )
            if actual and actual.upper() != "NULL":
                index_latency = float(actual)
        except Exception:
            pass
    chat_count = len(samples["chat_delivery"])
    summary = {}
    for category, values in samples.items():
        threshold = THRESHOLDS.get(category, 5.0)
        summary[category] = {
            "count": len(values),
            "errors": len(errors.get(category, [])),
            "p50": round(percentile(values, .50), 4) if values else None,
            "p95": round(percentile(values, .95), 4) if values else None,
            "p99": round(percentile(values, .99), 4) if values else None,
            "max": round(max(values), 4) if values else None,
            "threshold": threshold,
            "within_threshold_pct": round(100 * sum(v <= threshold for v in values) / len(values), 2) if values else None,
        }
    payload = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "environment": "youzhihui-411 isolated stack, 4 vCPU / 16 GiB host, API cgroup 1 CPU / 512 MiB, slice 1.5 CPU",
        "seed": data["counts"],
        "http_workers": args.http_workers,
        "ws_connections": 10,
        "warmup_seconds": args.warmup,
        "measure_seconds": args.duration,
        "categories": summary,
        "semantic_modes": dict(semantic_modes),
        "index_sync_seconds": round(index_latency, 2) if index_latency is not None else None,
        "errors": {k: v for k, v in errors.items() if v},
        "db": {
            "posts": db("SELECT COUNT(*) FROM posts;"),
            "comments": db("SELECT COUNT(*) FROM comments;"),
            "goods": db("SELECT COUNT(*) FROM goods;"),
            "messages": db("SELECT COUNT(*) FROM messages;"),
            "tasks": db("SELECT COUNT(*) FROM subscriptions;"),
            "duplicate_messages": db("SELECT COUNT(*) FROM (SELECT conversation_id,sender_id,client_message_id,COUNT(*) c FROM messages GROUP BY conversation_id,sender_id,client_message_id HAVING c>1) x;"),
        },
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    for api in apis.values():
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())

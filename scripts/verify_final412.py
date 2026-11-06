"""Final HTTPS smoke flow. Creates only labelled acceptance data; never uses SQL.

Passwords and fixture IDs stay under ignored .local/final412. A second invocation
with --readback verifies those fixtures after a deployment/restart/restore.
"""
import argparse
import json
import secrets
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
import urllib.request

from test_support import ROOT
from test_support.fixtures import png
from test_support.http import GoodsClient

DEFAULT_ORIGIN = 'https://youzhihui.85-121-122-124.sslip.io'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def wait(check, timeout=430):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(3)
    raise AssertionError('Timed out waiting for persisted reminder')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', default=DEFAULT_ORIGIN)
    parser.add_argument('--work', type=Path, default=ROOT / '.local/final412')
    parser.add_argument('--out', type=Path, default=ROOT / 'docs/final/production-verification.json')
    parser.add_argument('--admin-credentials', type=Path)
    parser.add_argument('--readback', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Resume a flow interrupted before chat; reuse its accounts and objects')
    parser.add_argument('--management-only', action='store_true')
    parser.add_argument('--observe-paused', action='store_true', help='With --readback, observe a paused task for one real interval')
    parser.add_argument('--exercise-restore', action='store_true', help='With --readback on Linux loopback only, resume a restored task and restart only the restore API')
    args = parser.parse_args()
    if args.management_only and not args.admin_credentials:
        parser.error('--management-only requires --admin-credentials')
    if sum((args.readback, args.resume, args.management_only)) > 1:
        parser.error('Choose only one of --readback, --resume, --management-only')
    # Loopback is for the independent restore only. No arbitrary remote target.
    assert args.origin in (DEFAULT_ORIGIN, 'http://localhost:18103'), 'Unsupported target'
    if args.exercise_restore:
        assert args.readback and args.origin == 'http://localhost:18103' and __import__('os').name == 'posix'
    if args.observe_paused:
        assert args.readback
    config = SimpleNamespace(api=args.origin, web=args.origin)
    def make_client():
        value = GoodsClient(config)
        # Reach the deployed entry directly, consistently with the WSS check.
        value.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(value.jar))
        return value
    visitor, buyer, seller = (make_client() for _ in range(3))
    result = {'stage': '4.12', 'origin': args.origin,
              'checked_at': datetime.now(timezone.utc).isoformat(), 'checks': [], 'status': 'running'}
    statefile = args.work / 'fixtures.json'
    fixtures = json.loads(statefile.read_text(encoding='utf-8')) if args.readback or args.resume or args.management_only else {}

    def record(name, **details):
        result['checks'].append({'check': name, 'passed': True, **details})
        write(args.out, result)
        print('PASS ' + name, flush=True)

    def notices():
        return buyer.call('/api/v1/notifications?page_size=50')['data']['items']

    def target_count(gid):
        return sum(n['kind'] == 'goods_match' and str(n.get('target_id')) == str(gid) for n in notices())

    try:
        visitor.call('/health/ready')
        record('HTTPS/API readiness' if args.origin.startswith('https:') else 'Restore/API readiness')
        if args.management_only:
            buyer.login(fixtures['buyer'], fixtures['password'])
        elif args.readback:
            buyer.login(fixtures['buyer'], fixtures['password'])
            seller.login(fixtures['seller'], fixtures['password'])
            post = buyer.call('/api/v1/posts/' + fixtures['post_id'])['data']
            assert post['title'] == fixtures['post_title']
            buyer.call('/api/v1/files/' + fixtures['image_id'] + '/content', json_response=False)
            goods = seller.call('/api/v1/goods/' + fixtures['goods_id'])['data']
            assert goods['state'] == 'sold'
            messages = buyer.call('/api/v1/conversations/' + fixtures['conversation_id'] + '/messages')['data']['items']
            assert sum(m['id'] == fixtures['message_id'] for m in messages) == 1
            assert target_count(fixtures['goods_id']) == 1
            task = buyer.call('/api/v1/subscriptions/' + fixtures['task_id'])['data']
            assert task['state'] == 'paused'
            record('Readback: login, post, image, sold goods, paused task, message and notification preserved')
            if args.observe_paused or args.exercise_restore:
                c = task['conditions']
                probe = seller.publish(c['category_id'], title='课程验收412 调度恢复探针',
                                       description='仅用于验证暂停或恢复后的真实调度，非真实交易。',
                                       brand=c['brand'], price_cents=180000, purpose='记笔记')
                try:
                    if args.observe_paused:
                        deadline = time.monotonic() + task['interval_minutes'] * 60 + 20
                        while time.monotonic() < deadline:
                            assert target_count(probe['id']) == 0
                            assert target_count(fixtures['goods_id']) == 1
                            time.sleep(5)
                        record('One full real interval: paused task produces no new notification and old notification stays unique', observed_seconds=task['interval_minutes']*60+20)
                    else:
                        buyer.call('/api/v1/subscriptions/' + task['id'] + '/state', 'PATCH', {'state': 'active', 'version': task['config_version']})
                        subprocess.run(['docker', 'restart', 'youzhihui-restore412-api-1'], check=True, timeout=90, capture_output=True)
                        def ready():
                            try:
                                return visitor.call('/health/ready')
                            except (AssertionError, RuntimeError):
                                return False
                        wait(ready, 90)
                        wait(lambda: target_count(probe['id']) == 1)
                        # Observe another scheduled scan: no repeat alert after restore/restart.
                        time.sleep(1)
                        deadline = time.monotonic() + task['interval_minutes']*60 + 20
                        while time.monotonic() < deadline:
                            assert target_count(probe['id']) == 1
                            assert target_count(fixtures['goods_id']) == 1
                            time.sleep(5)
                        messages = buyer.call('/api/v1/conversations/' + fixtures['conversation_id'] + '/messages')['data']['items']
                        assert sum(m['id'] == fixtures['message_id'] for m in messages) == 1
                        record('Restored task resumes across isolated API restart; subsequent real scan keeps messages/notifications unique')
                finally:
                    current = buyer.call('/api/v1/subscriptions/' + task['id'])['data']
                    if current['state'] == 'active':
                        buyer.call('/api/v1/subscriptions/' + task['id'] + '/state', 'PATCH', {'state': 'paused', 'version': current['config_version']})
                    current_goods = seller.call('/api/v1/goods/' + probe['id'])['data']
                    seller.call('/api/v1/goods/' + probe['id'] + '/state', 'PATCH', {'state': 'off_shelf', 'version': current_goods['version']})
            result['fixture_ids'] = {k: v for k, v in fixtures.items() if k.endswith('_id')}
        else:
            if statefile.exists() and not args.resume:
                raise RuntimeError('Fixture file exists; use --readback or choose a new --work directory')
            suffix = fixtures['buyer'][-10:] if args.resume else uuid.uuid4().hex[:10]
            if not args.resume:
                fixtures = {'buyer': 'demo412b' + suffix, 'seller': 'demo412s' + suffix,
                            'password': secrets.token_urlsafe(24), 'origin': args.origin}
                write(statefile, fixtures)
            for client, role, nickname in ((buyer, 'buyer', '课程演示买家'), (seller, 'seller', '课程演示卖家')):
                if not args.resume:
                    client.register(fixtures[role], fixtures['password'], nickname)
                client.login(fixtures[role], fixtures['password'])
            record('Two independent accounts register and log in')
            board = visitor.call('/api/v1/boards')['data']['items'][0]['id']
            category = visitor.call('/api/v1/goods-categories')['data'][0]['id']
            image = fixtures.get('image_id') or seller.upload(png(), 'post_image')['data']['id']
            post = seller.call('/api/v1/posts/' + fixtures['post_id'])['data'] if fixtures.get('post_id') else seller.post(board, '课程验收412 ' + suffix, '课程演示与最终验收专用，请勿当作真实交易。', images=[image])
            fixtures.update(post_id=post['id'], post_title=post['title'], image_id=image)
            write(statefile, fixtures)
            buyer.call(f'/api/v1/posts/{post["id"]}/comments', 'POST', {'body': '课程验收回复'}, 201)
            buyer.call(f'/api/v1/posts/{post["id"]}', 'PATCH', {'version': post['version'], 'title': '越权修改', 'body_markdown': '拒绝越权', 'image_file_ids': [], 'pdf_file_ids': []}, 403)
            q = urlencode({'q': suffix, 'mode': 'keyword', 'kind': 'post'})
            assert any(x['id'] == post['id'] for x in visitor.call('/api/v1/search?' + q)['data']['items'])
            buyer.call('/api/v1/files/' + image + '/content', json_response=False)
            record('Image post, reply, keyword search and unauthorized edit rejected')
            brand = 'DEMO412-' + suffix
            preview = seller.call('/api/v1/goods/' + fixtures['preview_goods_id'])['data'] if fixtures.get('preview_goods_id') else seller.publish(
                category, title='课程验收412 首件匹配商品 ' + suffix,
                description='课程验收用学习平板，沙河交易，非真实交易。',
                price_cents=180000, brand=brand, purpose='记笔记')
            fixtures['preview_goods_id'] = preview['id']
            write(statefile, fixtures)
            # Real text service, with the same 15-second server timeout as the UI.
            started = time.monotonic()
            intent = buyer.call('/api/v1/ai/goods-intent', 'POST', {'text': '想买2000元以内沙河校区交易的二手平板，用来记笔记'})['data']
            assert intent['requires_confirmation'] is True
            assert intent['intent']['max_price_cents'] == 200000 and intent['intent']['campus_code'] == 'shahe'
            record('Real AI understands a goods request', elapsed_seconds=round(time.monotonic() - started, 3), max_price_cents=200000, campus_code='shahe')
            query = {'q': '课堂记录笔记的电子设备', 'mode': 'semantic', 'kind': 'goods',
                     'brand': brand, 'max_price_cents': 200000, 'campus_code': 'shahe'}
            wait(lambda: (r if r['mode_used'] == 'semantic' and any(x['id'] == preview['id'] for x in r['items']) else None)
                 if (r := visitor.call('/api/v1/search?' + urlencode(query))['data']) else None, 90)
            for changed in ({'max_price_cents': 100000}, {'campus_code': 'xitucheng'}):
                matches = visitor.call('/api/v1/search?' + urlencode({**query, **changed}))['data']['items']
                assert all(x['id'] != preview['id'] for x in matches)
            record('Published goods matches before subscription; lowered budget and changed campus both exclude it')
            conditions = {'schema_version': 1, 'min_price_cents': None, 'max_price_cents': 200000,
                          'campus_code': 'shahe', 'category_id': category, 'brand': brand,
                          'model': None, 'min_condition': 'good', 'required_attributes': {}, 'purpose': '记笔记'}
            task = buyer.call('/api/v1/subscriptions/' + fixtures['task_id'])['data'] if fixtures.get('task_id') else buyer.call('/api/v1/subscriptions', 'POST', {
                'name': '课程验收412 ' + suffix, 'original_query': '沙河2000元内学习平板',
                'conditions': conditions, 'interval_minutes': 5, 'confirmed': True}, 201)['data']
            fixtures['task_id'] = task['id']
            write(statefile, fixtures)
            # Let the initial scan finish before publishing: tests the incremental path.
            wait(lambda: buyer.call('/api/v1/subscriptions/' + task['id'])['data']['last_checked_at'], 90)
            good = seller.call('/api/v1/goods/' + fixtures['goods_id'])['data'] if fixtures.get('goods_id') else seller.publish(category, title='课程验收412 学习平板 ' + suffix,
                                  description='仅用于课程验收，支持课堂记笔记，非真实交易。',
                                  price_cents=180000, brand=brand, purpose='记笔记')
            fixtures['goods_id'] = good['id']
            write(statefile, fixtures)
            q = urlencode({'q': '课堂记录笔记的电子设备', 'mode': 'semantic', 'kind': 'goods',
                           'brand': brand, 'max_price_cents': 200000, 'campus_code': 'shahe'})
            # Poll until the newly published document has actually been indexed.
            found = wait(lambda: (r if r['mode_used'] == 'semantic' and any(x['id'] == good['id'] for x in r['items']) else None)
                         if (r := visitor.call('/api/v1/search?' + q)['data']) else None, 90)
            record('Semantic goods matching with confirmed budget/campus conditions', mode_used=found['mode_used'])
            started = time.monotonic()
            wait(lambda: target_count(good['id']) == 1)
            record('New goods triggers one persisted reminder through the real scheduler', observed_wait_seconds=round(time.monotonic()-started, 3))
            task = buyer.call('/api/v1/subscriptions/' + task['id'])['data']
            buyer.call('/api/v1/subscriptions/' + task['id'] + '/state', 'PATCH', {'state': 'paused', 'version': task['config_version']})
            fixtures['paused_at'] = datetime.now(timezone.utc).isoformat()
            seller.call('/api/v1/goods/' + good['id'] + '/state', 'PATCH', {'state': 'sold', 'version': good['version']})
            seller.call('/api/v1/goods/' + preview['id'] + '/state', 'PATCH', {'state': 'off_shelf', 'version': preview['version']})
            assert not any(x['id'] == good['id'] for x in visitor.call('/api/v1/search?' + q)['data']['items'])
            record('Paused task and sold goods excluded from matching')
            conv = buyer.call('/api/v1/conversations', 'POST', {'goods_id': good['id']})['data']
            from websockets.sync.client import connect
            sockets = []
            try:
                for client in (buyer, seller):
                    ws = connect(args.origin.replace('https:', 'wss:').replace('http:', 'ws:') + '/api/v1/ws', origin=args.origin,
                                 additional_headers={'Cookie': '; '.join(c.name+'='+c.value for c in client.jar)}, proxy=None, open_timeout=15)
                    sockets.append(ws)
                    ticket = client.call('/api/v1/ws-tickets', 'POST')['data']['ticket']
                    ws.send(json.dumps({'type': 'authenticate', 'request_id': str(uuid.uuid4()), 'data': {'ticket': ticket}}))
                    while json.loads(ws.recv(timeout=10))['type'] != 'ready':
                        pass
                mid = str(uuid.uuid4())
                sockets[0].send(json.dumps({'type': 'message.send', 'request_id': str(uuid.uuid4()), 'data': {
                    'conversation_id': conv['id'], 'client_message_id': mid, 'body': '课程验收412：你好，可以联系交易吗？'}}))
                end = time.monotonic() + 15
                while time.monotonic() < end:
                    event = json.loads(sockets[1].recv(timeout=max(.1, end-time.monotonic())))
                    if event['type'] == 'message.created' and event['data']['client_message_id'] == mid:
                        fixtures['message_id'] = event['data']['id']
                        break
                assert 'message_id' in fixtures
            finally:
                for ws in sockets:
                    ws.close()
            fixtures['conversation_id'] = conv['id']
            write(statefile, fixtures)
            messages = buyer.call('/api/v1/conversations/' + conv['id'] + '/messages')['data']['items']
            assert sum(m['id'] == fixtures['message_id'] for m in messages) == 1
            visitor.call('/api/v1/conversations/' + conv['id'] + '/messages', expected=401)
            record('Two WSS sessions deliver a real private message; history saved and anonymous access denied')
            result['fixture_ids'] = {k: v for k, v in fixtures.items() if k.endswith('_id')}
        if args.admin_credentials and not args.readback:
            creds = json.loads(args.admin_credentials.read_text(encoding='utf-8-sig'))
            admin = make_client()
            admin.login(creds['admin'], creds['admin_password'])
            rid = buyer.call('/api/v1/reports', 'POST', {'target_type': 'post', 'target_id': fixtures['post_id'], 'reason': '课程验收测试，请保留帖子'}, 201)['data']['id']
            report = admin.call('/api/v1/reports/' + rid)['data']
            if report['state'] == 'pending':
                admin.call('/api/v1/reports/' + rid, 'PATCH', {'action': 'dismiss', 'reason': '课程验收，无违规', 'version': report['version'], 'target_version': report['current']['version']})
            assert buyer.call('/api/v1/reports/' + rid)['data']['state'] == 'dismissed'
            announcement = admin.call('/api/v1/admin/announcements', 'POST', {'title': '课程验收412临时公告', 'body_markdown': '临时验证公告，验证后立即撤回。'}, 201)['data']
            visitor.call('/api/v1/announcements/' + announcement['id'], expected=404)
            published = admin.call('/api/v1/admin/announcements/' + announcement['id'], 'PATCH', {'action': 'publish', 'version': announcement['version'], 'reason': '课程验收'})['data']
            try:
                visitor.call('/api/v1/announcements/' + announcement['id'])
            finally:
                admin.call('/api/v1/admin/announcements/' + announcement['id'], 'PATCH', {'action': 'retract', 'version': published['version'], 'reason': '验收完成撤回'})
            visitor.call('/api/v1/announcements/' + announcement['id'], expected=404)
            record('Admin report decision, reporter readback, announcement draft/publish/retract')
        result['status'] = 'passed'
    except Exception as exc:
        result['status'] = 'failed'
        result['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        write(args.out, result)


if __name__ == '__main__':
    main()

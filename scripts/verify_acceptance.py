"""Acceptance scenarios; shared setup lives in test_support."""
from test_support import ROOT
import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import hashlib
import re
from test_support.runtime import environment
from test_support.chat import ChatVerification
from test_support.http import GoodsClient as Client
from test_support.fixtures import png, pdf
from test_support.websocket import Live
LOG=ROOT/".local/logs/acceptance"
RESULT=ROOT/"docs/acceptance/verification.json"

class Acceptance(ChatVerification):
    def __init__(self):
        super().__init__(log_dir=LOG)
        self.env['UPLOAD_ROOT'] = str(ROOT / '.local/acceptance-tests' / self.database)
        self.baseline = None
        self.accounts_unchanged = None
        self.browser_cases = 0
        self.regressions = {}

    def original_accounts(self):
        name = self.env['MYSQL_DATABASE']
        assert re.fullmatch(r'[A-Za-z0-9_]+', name)
        exists = self.sql(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='{name}' AND table_name='users';")
        data = '' if exists == '0' else self.sql(f"SELECT * FROM `{name}`.users WHERE account_norm IN ('administrator001','testuser001','testuser002') ORDER BY id;")
        # Compare privately in memory, never log hashes or account row contents.
        return hashlib.sha256(data.encode()).digest()

    def reject_old_writes(self, client, pid, gid, cid, post_version, goods_version):
        client.call('/api/v1/posts/' + pid, 'PATCH', {'version': post_version, 'title': '失效登录不应写入'}, 401)
        client.call('/api/v1/goods/' + gid, 'PATCH', {'version': goods_version, 'price_cents': 100}, 401)
        client.call('/api/v1/conversations/' + cid + '/messages', 'POST', {'client_message_id': str(uuid.uuid4()), 'body': '失效登录不应发送'}, 401)

    def execute(self, regressions=False):
        for address in [self.api, self.web]:
            parsed = urllib.parse.urlparse(address)
            assert parsed.hostname in ['localhost', '127.0.0.1', '::1'] and parsed.scheme == 'http'
            with socket.socket() as connection:
                assert connection.connect_ex((parsed.hostname, parsed.port)) != 0, 'Stop development programs first.'
        self.owns_services = True
        self.run(self.compose + ['up', '-d', '--wait', '--wait-timeout', '240'], 'services-up')
        self.baseline = self.original_accounts()
        if regressions:
            for label, script, report in [
                ('engineering', 'verify_runtime.py', 'docs/engineering/runtime-verification.json'),
                ('accounts', 'verify_accounts.py', 'docs/accounts/verification.json'),
                ('forum', 'verify_forum.py', 'docs/forum/verification.json'),
                ('goods', 'verify_goods.py', 'docs/goods/verification.json'),
                ('chat', 'verify_chat.py', 'docs/chat/verification.json'),
            ]:
                self.run([sys.executable, ROOT / 'scripts' / script], 'regression-' + label)
                result = json.loads((ROOT / report).read_text(encoding='utf-8'))
                assert result['status'] == 'passed' and result['error'] is None
                self.regressions[label] = {'status': 'passed', 'groups': len(result['checks']), 'report': report}
                print('PASS regression: ' + label, flush=True)
        self.run(self.compose + ['up', '-d', '--wait', '--wait-timeout', '240'], 'isolated-services-up')
        assert re.fullmatch(r'[A-Za-z0-9_]+', self.env['MYSQL_USER'])
        self.sql(f"CREATE DATABASE `{self.database}` CHARACTER SET utf8mb4; GRANT ALL ON `{self.database}`.* TO '{self.env['MYSQL_USER']}'@'%';", 'create-database')
        self.created = True
        self.cli(['--migrate'], 'migrate')
        self.cli(['--migrate'], 'migrate-repeat')
        assert self.query('SELECT COUNT(*) FROM _sqlx_migrations WHERE success=1;') == '5'
        self.cli(['--init-admin'], 'init-admin', json.dumps({'account': self.root_account, 'nickname': '联通管理员', 'password': self.password}).encode())
        self.api = self.api.replace('localhost', '127.0.0.1')
        self.server = self.start([self.binary], 'api')
        self.wait('/health/ready')
        admin = Client(self);admin.login(self.root_account, self.password)
        alice = Client(self);alice.register(self.alice_account, self.password, '联通卖家');alice.login(self.alice_account, self.password)
        bob = Client(self);bob.register(self.bob_account, self.password, '联通买家');bob.login(self.bob_account, self.password)
        outsider = Client(self);third = 'third_' + self.suffix;outsider.register(third, self.password, '无关用户');outsider.login(third, self.password)
        visitor = Client(self)
        board = visitor.call('/api/v1/boards')['data']['items'][0]['id']
        category = visitor.call('/api/v1/goods-categories')['data'][0]['id']
        image = alice.upload(png(), 'post_image')['data']
        post = alice.post(board, title='管理联动' + self.suffix + '帖子', images=[image['id']])
        product = alice.publish(category, title='管理联动' + self.suffix + '商品')
        cid = bob.call('/api/v1/conversations', 'POST', {'goods_id': product['id']})['data']['id']
        for summary, target_type, target in [('联通测试通知', 'none', None), ('来源商品通知', 'goods', product['id']), ('来源帖子通知', 'post', post['id'])]:
            self.fixture(bob.me()['id'], summary, target_type, target)
        notices = bob.call('/api/v1/notifications')['data']['items']
        system_notice = next(n['id'] for n in notices if n['target_type'] == 'none')
        goods_notice = next(n['id'] for n in notices if n['target_type'] == 'goods')
        self.record('Fresh isolated database, five migrations, independent roles and private notification fixtures')

        fixture = self.log_dir / 'fixture.png';fixture.write_bytes(png())
        next_cli = ROOT / 'apps/web/node_modules/next/dist/bin/next'
        self.web_process = self.start(['node', next_cli, 'start', '--hostname', '127.0.0.1', '--port', self.env['WEB_PORT']], 'web', cwd=ROOT / 'apps/web')
        self.wait('/health/ready', base=self.web)
        extra = {'E2E_ACCEPTANCE': '1', 'ACC_SUFFIX': self.suffix, 'ACC_PASSWORD': self.password, 'ACC_ALICE': self.alice_account, 'ACC_BOB': self.bob_account, 'ACC_THIRD': third, 'ACC_ADMIN': self.root_account, 'ACC_PNG': str(fixture), 'ACC_POST': post['id'], 'ACC_GOODS': product['id'], 'ACC_MANAGED_CID': cid, 'ACC_MANAGED_POST': post['title'], 'ACC_MANAGED_GOODS': product['title'], 'ACC_POST_FILE': image['url'], 'ACC_GOODS_FILE': product['images'][0]['url'], 'ACC_SYSTEM_NOTICE': system_notice, 'ACC_GOODS_NOTICE': goods_notice}
        self.run(['node', ROOT / 'apps/web/node_modules/@playwright/test/cli.js', 'test', 'tests/acceptance.spec.mjs'], 'browser', cwd=ROOT / 'apps/web', extra=extra)
        report = json.loads((ROOT / '.local/logs/dev/browser-results.json').read_text(encoding='utf-8'))
        assert report['stats']['expected'] == 3 and report['stats']['unexpected'] == 0
        (self.log_dir / 'browser-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        self.browser_cases = 3
        self.record('One real browser flow publishes and replies to a post, publishes and searches goods, contacts seller, receives real WS chat and persists notification read state')
        self.record('Browser loading/empty/validation/permission/read-failure/save-failure states recover without false success; list filters and narrow layout work')
        self.record('The same moderation changes remove search hits, revoke old files, clear conversation product context and redact notification targets')
        flow = json.loads((self.log_dir / 'flow-ids.json').read_text(encoding='utf-8'))
        pid, gid, flow_cid = flow['postId'], flow['goodsId'], flow['cid']
        assert visitor.call('/api/v1/goods/' + gid)['data']['price_cents'] == 12345
        assert bob.call('/api/v1/posts/' + pid)['data']['liked_by_me']
        assert bob.call('/api/v1/conversations/' + flow_cid + '/messages')['data']['items']
        for client in [outsider, admin]:client.call('/api/v1/conversations/' + flow_cid, expected=404)
        hidden = bob.call('/api/v1/notifications')['data']['items']
        assert all(not n['target_available'] and n['summary'] == '相关内容当前不可访问' for n in hidden if n['target_type'] != 'none')
        assert next(n for n in hidden if n['id'] == system_notice)['read_at']
        self.record('Browser writes are independently read back by HTTP; administrators and outsiders cannot access the private conversation')

        authored = alice.call('/api/v1/posts/' + pid)['data']
        owned = alice.call('/api/v1/me/goods/' + gid)['data']
        second = alice.clone()
        live = Live(self, alice, proxy=True)
        new_password = self.password + 'n'
        start = time.monotonic()
        alice.call('/api/v1/me/password', 'POST', {'current_password': self.password, 'new_password': new_password})
        event = live.until('session.revoked');elapsed = time.monotonic() - start
        assert event['data']['reason_code'] == 'password_changed' and elapsed < 5
        self.revocations['password_changed_cross_module'] = round(elapsed, 3)
        live.close()
        for client in [alice, second]:self.reject_old_writes(client, pid, gid, flow_cid, authored['version'], owned['version'])
        alice = Client(self);alice.login(self.alice_account, new_password)
        alice.call('/api/v1/posts/' + pid, 'PATCH', {'version': authored['version'], 'title': authored['title'] + '已核对'})
        self.admin_action(admin, alice.me()['id'], 'status', {'version': self.target(admin, alice.me()['id'])['version'], 'status': 'banned', 'reason': '跨业务封禁检查'})
        self.reject_old_writes(alice, pid, gid, flow_cid, authored['version'], owned['version'])
        bob.call('/api/v1/conversations/' + flow_cid + '/messages', 'POST', {'client_message_id': str(uuid.uuid4()), 'body': '封禁后不应送达'}, 409)
        self.record('Password change and ban reject old writes across posts, goods and chat; another member cannot send to the banned peer')

        self.stop(self.web_process);self.stop(self.server)
        self.run(self.compose + ['restart'], 'database-restart')
        self.run(self.compose + ['up', '-d', '--wait', '--wait-timeout', '240'], 'database-ready')
        self.server = self.start([self.binary], 'api-restarted');self.wait('/health/ready')
        assert visitor.call('/api/v1/goods/' + gid)['data']['price_cents'] == 12345
        assert bob.call('/api/v1/posts/' + pid)['data']['title'].endswith('已核对')
        assert bob.call('/api/v1/posts/' + pid + '/comments')['data']['total'] >= 1
        assert bob.call('/api/v1/conversations/' + flow_cid + '/messages')['data']['items']
        assert next(n for n in bob.call('/api/v1/notifications')['data']['items'] if n['id'] == system_notice)['read_at']
        assert self.query('SELECT COUNT(*) FROM messages;') == self.query("SELECT COUNT(DISTINCT CONCAT(conversation_id,':',sender_id,':',client_message_id)) FROM messages;")
        self.record('Restart preserves the same browser-created post, replies, exact price, conversation, message identities and notification read state')

    def cleanup(self):
        super().cleanup()
        if self.baseline is not None:
            try:
                self.run(self.compose + ['up', '-d', '--wait', '--wait-timeout', '240'], 'account-protection-ready')
                self.accounts_unchanged = self.original_accounts() == self.baseline
                assert self.accounts_unchanged, 'Original development account rows changed'
                self.record('The three original development account rows are identical before and after acceptance')
            finally:
                self.run(self.compose + ['stop'], 'account-protection-stop')

def main():
    parser = argparse.ArgumentParser();parser.add_argument('--regressions', action='store_true');args = parser.parse_args()
    LOG.mkdir(parents=True, exist_ok=True);RESULT.parent.mkdir(parents=True, exist_ok=True)
    verification = Acceptance();status = 'failed';error = None
    try:verification.execute(args.regressions);status = 'passed'
    except Exception as exc:error = f'{type(exc).__name__}: {str(exc)}';print(error, file=sys.stderr)
    finally:
        try:verification.cleanup()
        except Exception:status = 'failed';error = 'Acceptance cleanup/account protection failed';print(error, file=sys.stderr)
        RESULT.write_text(json.dumps({'stage': '4.6.4', 'date': '2026-10-28', 'status': status, 'checks': verification.checks, 'browser_cases': verification.browser_cases, 'regressions_run': verification.regressions, 'revocation_seconds': verification.revocations, 'isolated_database_removed': not verification.created, 'original_development_accounts_unchanged': verification.accounts_unchanged, 'server_deployed': False, 'ai_or_performance_acceptance_completed': False, 'error': error}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if status == 'passed' else 1

if __name__ == "__main__":sys.exit(main())

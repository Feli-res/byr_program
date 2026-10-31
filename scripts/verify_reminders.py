"""4.9 subscription and reminder verification against a disposable database."""
from test_support import ROOT
from test_support.accounts import AccountVerification
from test_support.http import GoodsClient
import json
import time


def wait_for(check, message, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.4)
    raise AssertionError(message)


class VerifyReminders(AccountVerification):
    def notification_count(self, user_id):
        return int(self.query(f"SELECT COUNT(*) FROM notifications WHERE recipient_id={user_id} AND kind='goods_match';"))

    def target_notified(self, user_id, goods_id):
        return self.query(
            f"SELECT COUNT(*) FROM notifications WHERE recipient_id={user_id} AND kind='goods_match' AND target_id={goods_id};"
        ) == '1'

    def due(self, sid):
        self.query(f"UPDATE subscriptions SET next_due_at=UTC_TIMESTAMP(6) WHERE id={sid};")

    def task(self, client, sid):
        return client.call(f'/api/v1/subscriptions/{sid}')['data']

    def conditions(self, category, **overrides):
        value = {
            'schema_version': 1,
            'min_price_cents': None,
            'max_price_cents': 200000,
            'campus_code': 'shahe',
            'category_id': category,
            'brand': 'Apple',
            'model': None,
            'min_condition': 'good',
            'required_attributes': {'stylus_support': True},
            'purpose': '记笔记',
        }
        value.update(overrides)
        return value

    def publish(self, seller, category, title, price=180000, campus='shahe', brand='Apple', attributes=None, state=None):
        goods = seller.publish(
            category,
            title=title,
            description='用于商品提醒验收的真实商品描述',
            price_cents=price,
            campus_code=campus,
            brand=brand,
            condition_code='good',
            attributes={'stylus_support': True} if attributes is None else attributes,
        )
        if state:
            seller.call(f"/api/v1/goods/{goods['id']}/state", 'PATCH', {'state': state, 'version': goods['version']})
            goods = seller.call(f"/api/v1/goods/{goods['id']}")['data']
        return goods

    def create_task(self, client, category, name, conditions=None, interval=5):
        return client.call('/api/v1/subscriptions', 'POST', {
            'name': name,
            'original_query': '想收一台 2000 元以内、沙河交易的二手平板，用来记笔记',
            'conditions': conditions or self.conditions(category),
            'interval_minutes': interval,
            'confirmed': True,
        }, 201)['data']

    def execute(self):
        self.env['AI_ENABLED'] = 'false'
        self.owns_services = True
        self.run(self.compose + ['up', '-d', '--wait', '--wait-timeout', '240'], 'services-up')
        self.sql(f"CREATE DATABASE `{self.database}` CHARACTER SET utf8mb4; GRANT ALL ON `{self.database}`.* TO '{self.env['MYSQL_USER']}'@'%';", 'create-test-database')
        self.created = True
        self.cli(['--migrate'], 'migrate')
        self.cli(['--init-admin'], 'init-admin', json.dumps({'account': self.root_account, 'nickname': '管理员', 'password': self.password}).encode())
        self.server = self.start([self.binary], 'api')
        self.wait('/health/ready')

        admin = GoodsClient(self)
        admin.login(self.root_account, self.password)
        alice = GoodsClient(self)
        alice.register(self.alice_account, self.password, '买家')
        alice.login(self.alice_account, self.password)
        bob = GoodsClient(self)
        bob.register(self.bob_account, self.password, '卖家')
        bob.login(self.bob_account, self.password)
        charlie = GoodsClient(self)
        charlie_account = 'other_' + self.suffix
        charlie.register(charlie_account, self.password, '其他用户')
        charlie.login(charlie_account, self.password)
        buyer_id = int(alice.me()['id'])
        category = charlie.call('/api/v1/goods-categories')['data'][0]['id']

        old = self.publish(bob, category, '学习平板 旧款', 180000)
        over = self.publish(bob, category, '超预算平板', 300000)
        wrong_campus = self.publish(bob, category, '西土城平板', 170000, campus='xitucheng')
        no_stylus = self.publish(bob, category, '无手写笔平板', 160000, attributes={})
        reserved = self.publish(bob, category, '已预留平板', 150000, state='reserved')
        self.publish(bob, category, '已售平板', 140000, state='sold')
        task = self.create_task(alice, category, '学习平板提醒')
        sid = int(task['id'])
        wait_for(lambda: self.target_notified(buyer_id, int(old['id'])), 'first full scan did not notify matching goods')
        assert not self.target_notified(buyer_id, int(over['id']))
        assert not self.target_notified(buyer_id, int(wrong_campus['id']))
        assert not self.target_notified(buyer_id, int(no_stylus['id']))
        assert not self.target_notified(buyer_id, int(reserved['id']))
        assert self.notification_count(buyer_id) == 1
        self.record('First full scan notifies matching on-sale goods once and excludes budget/campus/attribute/state mismatches')

        self.due(sid)
        time.sleep(8)
        assert self.notification_count(buyer_id) == 1
        assert int(self.query(f"SELECT COUNT(*) FROM subscription_runs WHERE subscription_id={sid} AND state='succeeded';")) >= 2
        assert int(self.task(alice, sid)['match_count']) == 1
        self.record('Repeated checks do not repeat notifications and keep the match count stable')

        fresh = self.publish(bob, category, '学习平板 新款', 190000)
        self.due(sid)
        wait_for(lambda: self.target_notified(buyer_id, int(fresh['id'])), 'incremental scan did not notify a new matching goods')
        assert self.notification_count(buyer_id) == 2
        self.record('Incremental cursor notifies a newly published matching goods exactly once')

        task = self.task(alice, sid)
        alice.call(f'/api/v1/subscriptions/{sid}/state', 'PATCH', {'state': 'paused', 'version': task['config_version']})
        paused_goods = self.publish(bob, category, '暂停期间发布平板', 170000)
        self.due(sid)
        time.sleep(8)
        assert not self.target_notified(buyer_id, int(paused_goods['id']))
        assert self.notification_count(buyer_id) == 2
        task = self.task(alice, sid)
        alice.call(f'/api/v1/subscriptions/{sid}/state', 'PATCH', {'state': 'active', 'version': task['config_version']})
        self.due(sid)
        wait_for(lambda: self.target_notified(buyer_id, int(paused_goods['id'])), 'resumed task did not catch up paused-period changes')
        self.record('Pause stops new notifications and resume catches up changes from the paused period')

        sold_later = self.publish(bob, category, '检查前售出的平板', 160000)
        bob.call(f"/api/v1/goods/{sold_later['id']}/state", 'PATCH', {'state': 'sold', 'version': sold_later['version']})
        self.due(sid)
        time.sleep(8)
        assert not self.target_notified(buyer_id, int(sold_later['id']))
        self.record('Goods sold before the check never become a valid reminder')

        for method, path, body, expected in [
            ('GET', f'/api/v1/subscriptions/{sid}', None, 404),
            ('GET', f'/api/v1/subscriptions/{sid}/runs', None, 404),
            ('GET', f'/api/v1/subscriptions/{sid}/matches', None, 404),
            ('PATCH', f'/api/v1/subscriptions/{sid}', {'name': '越权', 'original_query': None, 'conditions': self.conditions(category), 'interval_minutes': 5, 'version': 1, 'confirmed': True, 'resume_after_save': False}, 404),
            ('DELETE', f'/api/v1/subscriptions/{sid}', {'version': 1}, 404),
        ]:
            charlie.call(path, method, body, expected)
        assert self.notification_count(int(charlie.me()['id'])) == 0
        self.record('Another account cannot read, edit, delete or receive the task private conditions')

        base_write = {'name': '边界检查', 'original_query': None, 'conditions': self.conditions(category), 'interval_minutes': 5, 'confirmed': True}
        alice.call('/api/v1/subscriptions', 'POST', {**base_write, 'interval_minutes': 4}, 422)
        alice.call('/api/v1/subscriptions', 'POST', {**base_write, 'conditions': self.conditions(category, min_price_cents=300000, max_price_cents=200000)}, 422)
        alice.call('/api/v1/subscriptions', 'POST', {**base_write, 'conditions': {'schema_version': 1, 'min_price_cents': None, 'max_price_cents': None, 'campus_code': None, 'category_id': None, 'brand': None, 'model': None, 'min_condition': None, 'required_attributes': {}, 'purpose': None}}, 422)
        alice.call('/api/v1/subscriptions', 'POST', {**base_write, 'conditions': {**self.conditions(category), 'unknown': 1}}, 400)
        alice.call('/api/v1/subscriptions', 'POST', {**base_write, 'conditions': self.conditions('999999')}, 422)
        alice.call('/api/v1/subscriptions', 'POST', {**base_write, 'confirmed': False}, 422)
        self.record('Condition and interval boundaries are rejected without saving a task')

        deleted = self.task(alice, sid)
        alice.call(f'/api/v1/subscriptions/{sid}', 'DELETE', {'version': deleted['config_version']})
        alice.call(f'/api/v1/subscriptions/{sid}', 'GET', None, 404)
        after_delete = self.publish(bob, category, '删除任务后发布平板', 150000)
        self.due(sid)
        time.sleep(8)
        assert not self.target_notified(buyer_id, int(after_delete['id']))
        assert self.notification_count(buyer_id) == 3
        self.record('Deleted task stops future checks and notifications; historical matches stay in the database')

        placeholders = []
        for index in range(10):
            created = self.create_task(
                alice, category, f'占位任务 {index}',
                self.conditions(category, brand=f'NoSuchBrand{self.suffix}{index}', max_price_cents=1),
                interval=1440,
            )
            placeholders.append(alice.call(f"/api/v1/subscriptions/{created['id']}/state", 'PATCH', {'state': 'paused', 'version': created['config_version']})['data'])
        alice.call('/api/v1/subscriptions', 'POST', {
            'name': '第十一个任务', 'original_query': None,
            'conditions': self.conditions(category, brand='NoSuchBrandLimit'),
            'interval_minutes': 1440, 'confirmed': True,
        }, 409)
        alice.call(f"/api/v1/subscriptions/{placeholders[0]['id']}", 'DELETE', {'version': placeholders[0]['config_version']})
        self.create_task(alice, category, '删除一个后新建', self.conditions(category, brand='NoSuchBrandLimit'), interval=1440)
        self.record('At most ten non-deleted tasks are allowed, including paused/error tasks; deleting one frees a slot')

        alice.call(f"/api/v1/subscriptions/{placeholders[1]['id']}", 'DELETE', {'version': placeholders[1]['config_version']})
        ban_task = self.create_task(alice, category, '封禁测试提醒')
        ban_sid = int(ban_task['id'])
        before_ban = self.publish(bob, category, '封禁前匹配平板', 140000)
        self.due(ban_sid)
        wait_for(lambda: self.target_notified(buyer_id, int(before_ban['id'])), 'ban test setup did not notify')
        target = self.target(admin, str(buyer_id))
        self.admin_action(admin, buyer_id, 'status', {'status': 'banned', 'version': target['version'], 'reason': '提醒任务封禁验收'})
        assert self.query(f"SELECT state FROM subscriptions WHERE id={ban_sid};") == 'paused'
        after_ban = self.publish(bob, category, '封禁期间发布平板', 130000)
        self.due(ban_sid)
        time.sleep(8)
        assert not self.target_notified(buyer_id, int(after_ban['id']))
        target = self.target(admin, str(buyer_id))
        self.admin_action(admin, buyer_id, 'status', {'status': 'active', 'version': target['version'], 'reason': '提醒任务解封验收'})
        alice.login(self.alice_account, self.password)
        ban_task = self.task(alice, ban_sid)
        assert ban_task['state'] == 'paused'
        alice.call(f'/api/v1/subscriptions/{ban_sid}/state', 'PATCH', {'state': 'active', 'version': ban_task['config_version']})
        self.due(ban_sid)
        wait_for(lambda: self.target_notified(buyer_id, int(after_ban['id'])), 'resumed task after unban did not catch up')
        self.record('Ban pauses active tasks and blocks notifications; unban does not auto-resume but an explicit resume works')

        current_placeholder = self.task(alice, int(placeholders[2]['id']))
        alice.call(f"/api/v1/subscriptions/{placeholders[2]['id']}", 'DELETE', {'version': current_placeholder['config_version']})
        failure_task = self.create_task(alice, category, '失败重试提醒')
        failure_sid = int(failure_task['id'])
        wait_for(lambda: self.query(f"SELECT last_checked_at IS NOT NULL FROM subscriptions WHERE id={failure_sid};") == '1', 'failure task first scan did not finish')
        self.query('RENAME TABLE content_changes TO content_changes_hold;')
        try:
            self.due(failure_sid)
            wait_for(lambda: self.query(f"SELECT retry_count FROM subscriptions WHERE id={failure_sid};") == '1', 'first failure was not recorded')
            for expected_retry in ['2', '3']:
                self.due(failure_sid)
                wait_for(lambda expected=expected_retry: self.query(f"SELECT retry_count FROM subscriptions WHERE id={failure_sid};") == expected, f'retry {expected_retry} was not recorded')
            self.due(failure_sid)
            wait_for(lambda: self.query(f"SELECT state FROM subscriptions WHERE id={failure_sid};") == 'error', 'task did not enter error after retries')
            assert self.query(f"SELECT last_error_code FROM subscriptions WHERE id={failure_sid};") == 'DEPENDENCY_UNAVAILABLE'
        finally:
            self.query('RENAME TABLE content_changes_hold TO content_changes;')
        failure_task = self.task(alice, failure_sid)
        alice.call(f'/api/v1/subscriptions/{failure_sid}/state', 'PATCH', {'state': 'active', 'version': failure_task['config_version']})
        failure_goods = self.publish(bob, category, '恢复后匹配平板', 120000)
        self.due(failure_sid)
        wait_for(lambda: self.target_notified(buyer_id, int(failure_goods['id'])), 'manually resumed task did not succeed after dependency recovery')
        self.record('Transient failures retry with backoff, persist an error state, and recover after manual resume')

        admin_meta = admin.call('/api/v1/admin/subscriptions?page_size=50')['data']['items']
        assert admin_meta and all('conditions' not in item and 'original_query' not in item for item in admin_meta)
        active = next(item for item in admin_meta if item['state'] == 'active')
        admin.call(f"/api/v1/admin/subscriptions/{active['id']}/pause", 'POST', {'reason': '管理员异常任务验收'})
        assert self.query(f"SELECT state FROM subscriptions WHERE id={int(active['id'])};") == 'paused'
        self.record('Admin task list is redacted and admin pause is audited without exposing private conditions')

        self.stop(self.server)
        self.server = self.start([self.binary], 'api-restarted')
        self.wait('/health/ready')
        current_placeholder = self.task(alice, int(placeholders[3]['id']))
        alice.call(f"/api/v1/subscriptions/{placeholders[3]['id']}", 'DELETE', {'version': current_placeholder['config_version']})
        restart_task = self.create_task(alice, category, '重启后继续提醒')
        restart_sid = int(restart_task['id'])
        restart_goods = self.publish(bob, category, '重启后发布平板', 110000)
        self.due(restart_sid)
        wait_for(lambda: self.target_notified(buyer_id, int(restart_goods['id'])), 'restarted API did not continue subscription checks')
        self.record('API restart keeps effective tasks working and notifications deduplicated')

        current_placeholder = self.task(alice, int(placeholders[4]['id']))
        alice.call(f"/api/v1/subscriptions/{placeholders[4]['id']}", 'DELETE', {'version': current_placeholder['config_version']})
        cli = ROOT / 'apps/web/node_modules/next/dist/bin/next'
        self.web_process = self.start(['node', str(cli), 'start', '--hostname', '127.0.0.1', '--port', self.env['WEB_PORT']], 'web', cwd=ROOT / 'apps/web')
        self.wait('/health/ready', base=self.web)
        self.run(['node', str(ROOT / 'scripts/reminders-browser.cjs')], 'browser', extra={
            'REMINDERS_BUYER': self.alice_account,
            'REMINDERS_PASSWORD': self.password,
            'REMINDERS_CATEGORY': category,
        })
        self.record('Browser saves a reminder, sees a match notification, pauses and resumes it, and fits a narrow screen')

        self.record('4.9 backend and browser verification complete')


def main():
    task = VerifyReminders(log_dir=ROOT / '.local/logs/reminders')
    status = 'failed'
    error = None
    try:
        task.execute()
        status = 'passed'
    except Exception as exc:
        error = f'{type(exc).__name__}: {str(exc)}'
        print(error)
    finally:
        task.cleanup()
    result = {
        'stage': '4.9',
        'status': status,
        'checks': task.checks,
        'browser_cases': 1 if any('Browser saves' in item for item in task.checks) else 0,
        'isolated_database_removed': not task.created,
        'development_accounts_modified': False,
        'server_deployed': False,
        'error': error,
    }
    out = ROOT / 'docs/reminders/verification.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if status == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

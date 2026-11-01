"""4.10 management and cross-feature checks on a disposable database."""
import json
import time
import urllib.parse
import uuid

from test_support import ROOT
from test_support.accounts import AccountVerification
from test_support.http import GoodsClient


class VerifyAdmin(AccountVerification):
    def execute(self):
        self.env['AI_ENABLED'] = 'false'
        self.run(self.compose + ['up', '-d', '--wait', '--wait-timeout', '240'], 'services-up')
        self.sql(
            f"CREATE DATABASE `{self.database}` CHARACTER SET utf8mb4; GRANT ALL ON `{self.database}`.* TO '{self.env['MYSQL_USER']}'@'%';",
            'create-test-database',
        )
        self.created = True
        self.cli(['--migrate'], 'migrate')
        self.cli(
            ['--init-admin'],
            'init-admin',
            json.dumps(
                {'account': self.root_account, 'nickname': '管理员', 'password': self.password}
            ).encode(),
        )
        self.server = self.start([self.binary], 'api')
        self.wait('/health/ready')

        admin = GoodsClient(self)
        admin.login(self.root_account, self.password)
        alice = GoodsClient(self)
        alice.register(self.alice_account, self.password)
        alice.login(self.alice_account, self.password)
        bob = GoodsClient(self)
        bob.register(self.bob_account, self.password)
        bob.login(self.bob_account, self.password)
        mod = GoodsClient(self)
        mod.register('mod_' + self.suffix, self.password)
        mod.login('mod_' + self.suffix, self.password)
        third = GoodsClient(self)
        third.register('third_' + self.suffix, self.password)
        third.login('third_' + self.suffix, self.password)

        visitor = GoodsClient(self)
        board = visitor.call('/api/v1/boards')['data']['items'][0]['id']
        category = visitor.call('/api/v1/goods-categories')['data'][0]['id']
        mod_id = mod.me()['id']
        member = self.target(admin, mod_id)
        self.admin_action(
            admin,
            mod_id,
            'role',
            {
                'role': 'moderator',
                'board_ids': [board],
                'version': member['version'],
                'reason': '4.10举报权限检查',
            },
        )
        self.record('Moderator granted one board for report scope checks')

        # --- comment report, moderator handling, public visibility ---
        post = alice.post(board, '管理联动验收帖', '用于检查举报、隐藏与搜索联动')
        comment = bob.call(
            f'/api/v1/posts/{post["id"]}/comments',
            'POST',
            {'body': '这条评论用于举报隐藏检查', 'parent_id': None},
            expected=201,
        )['data']
        rid = alice.call(
            '/api/v1/reports',
            'POST',
            {
                'target_type': 'comment',
                'target_id': comment['id'],
                'reason': '辱骂或人身攻击：验收用评论',
            },
            expected=201,
        )['data']['id']
        duplicate = alice.call(
            '/api/v1/reports',
            'POST',
            {
                'target_type': 'comment',
                'target_id': comment['id'],
                'reason': '重复提交',
            },
            expected=201,
        )['data']
        assert duplicate['already_exists'] and duplicate['id'] == rid
        detail = admin.call(f'/api/v1/reports/{rid}')['data']
        assert detail['snapshot']['comment_body'] == '这条评论用于举报隐藏检查'
        assert detail['target_type'] == 'comment' and detail['current']['visibility'] == 'public'
        mod_detail = mod.call(f'/api/v1/reports/{rid}')['data']
        mod.call(
            f'/api/v1/reports/{rid}',
            'PATCH',
            {
                'action': 'hide',
                'reason': '版主核实评论违规',
                'version': mod_detail['version'],
            },
        )
        comments = visitor.call(f'/api/v1/posts/{post["id"]}/comments')['data']['items']
        hidden = next(item for item in comments if item['id'] == comment['id'])
        assert hidden['state'] == 'hidden' and hidden['body'] is None
        assert any(
            n['kind'] == 'report_result'
            for n in alice.call('/api/v1/notifications')['data']['items']
        )
        assert any(
            '评论已被管理员隐藏' in n['summary']
            for n in bob.call('/api/v1/notifications')['data']['items']
        )
        self.record('Comment report, moderator board scope, hide effect and notifications')

        # --- cross-board scope and legacy post-report entry ---
        other_board = admin.call(
            '/api/v1/admin/boards',
            'POST',
            {'name': '他板块' + self.suffix[:4], 'description': '跨板块权限检查'},
            expected=201,
        )['data']
        other_post = alice.post(other_board['id'], '跨板块举报帖', '用于检查版主不能跨板块处理')
        rid_cross = bob.call(
            '/api/v1/reports',
            'POST',
            {
                'target_type': 'post',
                'target_id': other_post['id'],
                'reason': '广告或垃圾信息：跨板块',
            },
            expected=201,
        )['data']['id']
        mod.call(f'/api/v1/reports/{rid_cross}', expected=404)
        mod_items = mod.call('/api/v1/admin/reports?page_size=100')['data']['items']
        assert all(item['id'] != rid_cross for item in mod_items)
        assert all(item['target_type'] in ('post', 'comment') for item in mod_items)
        legacy = bob.call(
            '/api/v1/post-reports',
            'POST',
            {'post_id': post['id'], 'reason': '旧入口兼容检查'},
        )['data']
        assert legacy['id']
        legacy_detail = admin.call(f'/api/v1/reports/{legacy["id"]}')['data']
        admin.call(
            f'/api/v1/reports/{legacy["id"]}',
            'PATCH',
            {
                'action': 'dismiss',
                'reason': '旧入口举报不成立',
                'version': legacy_detail['version'],
                'target_version': legacy_detail['current']['version'],
            },
        )
        self.record('Cross-board moderator denial, report type scope and legacy post-report entry')

        # --- post report hides content and search result ---
        hide_post = alice.post(board, '举报隐藏验收帖', '隐藏后不应出现在搜索中')
        rid_hide = bob.call(
            '/api/v1/reports',
            'POST',
            {
                'target_type': 'post',
                'target_id': hide_post['id'],
                'reason': '广告或垃圾信息：隐藏检查',
            },
            expected=201,
        )['data']['id']
        hide_detail = admin.call(f'/api/v1/reports/{rid_hide}')['data']
        admin.call(
            f'/api/v1/reports/{rid_hide}',
            'PATCH',
            {
                'action': 'hide',
                'reason': '核实为垃圾信息',
                'version': hide_detail['version'],
                'target_version': hide_detail['current']['version'],
            },
        )
        visitor.call(f'/api/v1/posts/{hide_post["id"]}', expected=404)
        hidden_search = visitor.call(
            '/api/v1/search?' + urllib.parse.urlencode({'q': '举报隐藏验收帖'})
        )['data']
        assert all(item['id'] != hide_post['id'] for item in hidden_search['items'])
        assert any(
            '帖子已被管理员隐藏' in n['summary']
            for n in alice.call('/api/v1/notifications')['data']['items']
        )
        self.record('Post report hide removes detail and search result, author notified')

        # --- goods report and restriction linkage ---
        reported_goods = alice.publish(
            category,
            title='举报下架验收商品',
            description='用于检查商品举报与下架联动',
            price_cents=12345,
        )
        rid_goods = bob.call(
            '/api/v1/reports',
            'POST',
            {
                'target_type': 'goods',
                'target_id': reported_goods['id'],
                'reason': '疑似诈骗：验收用商品',
            },
            expected=201,
        )['data']['id']
        goods_detail = admin.call(f'/api/v1/reports/{rid_goods}')['data']
        assert goods_detail['snapshot']['title'] == '举报下架验收商品'
        admin.call(
            f'/api/v1/reports/{rid_goods}',
            'PATCH',
            {
                'action': 'restrict',
                'reason': '商品信息与描述不符',
                'version': goods_detail['version'],
                'target_version': goods_detail['current']['version'],
            },
        )
        visitor.call(f'/api/v1/goods/{reported_goods["id"]}', expected=404)
        search = visitor.call(
            '/api/v1/search?' + urllib.parse.urlencode({'q': '举报下架验收商品'})
        )['data']
        assert all(item['id'] != reported_goods['id'] for item in search['items'])
        seller_goods = alice.call(f'/api/v1/me/goods/{reported_goods["id"]}')['data']
        assert seller_goods['state'] == 'off_shelf' and seller_goods['moderation'] == 'restricted'
        assert any(
            '商品已被管理员下架' in n['summary']
            for n in alice.call('/api/v1/notifications')['data']['items']
        )
        self.record('Goods report, admin-only handling, search/visibility effect and seller notice')

        # --- private message report: recipient only and minimal context ---
        chat_goods = alice.publish(
            category,
            title='私信验收商品',
            description='用于检查私信举报',
            price_cents=23456,
        )
        conversation = bob.call(
            '/api/v1/conversations', 'POST', {'goods_id': chat_goods['id']}
        )['data']
        message = alice.call(
            f'/api/v1/conversations/{conversation["id"]}/messages',
            'POST',
            {'client_message_id': str(uuid.uuid4()), 'body': '这条私信用于举报验收'},
            expected=201,
        )['data']
        rid_message = bob.call(
            '/api/v1/reports',
            'POST',
            {
                'target_type': 'message',
                'target_id': message['id'],
                'reason': '骚扰或人身攻击：验收私信',
            },
            expected=201,
        )['data']['id']
        alice.call(
            '/api/v1/reports',
            'POST',
            {
                'target_type': 'message',
                'target_id': message['id'],
                'reason': '发送者不能举报自己',
            },
            expected=403,
        )
        third.call(
            '/api/v1/reports',
            'POST',
            {
                'target_type': 'message',
                'target_id': message['id'],
                'reason': '非会话成员',
            },
            expected=404,
        )
        message_detail = admin.call(f'/api/v1/reports/{rid_message}')['data']
        context = message_detail['snapshot']['messages']
        assert 1 <= len(context) <= 5 and 'conversation_id' not in message_detail['snapshot']
        assert all(item['body'] for item in context)
        mod.call(f'/api/v1/reports/{rid_message}', expected=404)
        admin.call(
            f'/api/v1/reports/{rid_message}',
            'PATCH',
            {
                'action': 'uphold',
                'reason': '已核实为骚扰消息',
                'version': message_detail['version'],
            },
        )
        assert any(
            n['kind'] == 'report_result'
            for n in bob.call('/api/v1/notifications')['data']['items']
        )
        self.record('Message report recipient-only, minimal context, moderator denial and decision')

        # --- announcements lifecycle ---
        announcement = admin.call(
            '/api/v1/admin/announcements',
            'POST',
            {'title': '验收公告', 'body_markdown': '公告正文，用于检查发布与撤回。'},
            expected=201,
        )['data']
        assert announcement['state'] == 'draft'
        visitor.call(f'/api/v1/announcements/{announcement["id"]}', expected=404)
        public_before = visitor.call('/api/v1/announcements')['data']['items']
        assert all(item['id'] != announcement['id'] for item in public_before)
        published = admin.call(
            f'/api/v1/admin/announcements/{announcement["id"]}',
            'PATCH',
            {
                'action': 'publish',
                'version': announcement['version'],
                'reason': '验收发布公告',
            },
        )['data']
        assert published['state'] == 'published' and published['published_at']
        visitor.call(f'/api/v1/announcements/{announcement["id"]}')
        public_after = visitor.call('/api/v1/announcements')['data']['items']
        assert any(item['id'] == announcement['id'] for item in public_after)
        admin.call(
            f'/api/v1/admin/announcements/{announcement["id"]}',
            'PATCH',
            {
                'action': 'save',
                'version': published['version'],
                'title': '已发布后直接修改',
            },
            expected=409,
        )
        retracted = admin.call(
            f'/api/v1/admin/announcements/{announcement["id"]}',
            'PATCH',
            {
                'action': 'retract',
                'version': published['version'],
                'reason': '验收撤回公告',
            },
        )['data']
        assert retracted['state'] == 'retracted'
        visitor.call(f'/api/v1/announcements/{announcement["id"]}', expected=404)
        self.record('Announcement draft/publish/retract lifecycle and public visibility')

        # --- board management ---
        new_board = admin.call(
            '/api/v1/admin/boards',
            'POST',
            {'name': '验收板块' + self.suffix[:4], 'description': '用于检查板块停用'},
            expected=201,
        )['data']
        public_boards = visitor.call('/api/v1/boards')['data']['items']
        assert any(item['id'] == new_board['id'] for item in public_boards)
        kept_post = alice.post(new_board['id'], '停用板块历史帖', '停用后仍应可读')
        disabled = admin.call(
            f'/api/v1/admin/boards/{new_board["id"]}',
            'PATCH',
            {
                'version': new_board['version'],
                'reason': '验收停用板块',
                'enabled': False,
            },
        )['data']
        assert disabled['enabled'] is False
        public_boards = visitor.call('/api/v1/boards')['data']['items']
        assert all(item['id'] != new_board['id'] for item in public_boards)
        visitor.call(f'/api/v1/posts/{kept_post["id"]}')
        alice.post(new_board['id'], '停用后新帖', '应被拒绝', expected=422)
        self.record('Board create/disable, public list, historical post readable, new post rejected')

        # --- masked task metadata and pause ---
        bob_id = bob.me()['id']
        self.query(
            f"INSERT INTO subscriptions(owner_id,name,conditions,interval_minutes,state,next_due_at) "
            f"VALUES ({bob_id},'管理任务验收',JSON_OBJECT('schema_version',1),5,'active',UTC_TIMESTAMP(6))"
        )
        task_id = self.query(
            f"SELECT id FROM subscriptions WHERE owner_id={bob_id} ORDER BY id DESC LIMIT 1"
        )
        tasks = admin.call('/api/v1/admin/subscriptions?page_size=100')['data']['items']
        task = next(item for item in tasks if item['id'] == task_id)
        assert 'conditions' not in task and 'original_query' not in task
        admin.call(
            f'/api/v1/admin/subscriptions/{task_id}/pause',
            'POST',
            {'reason': '验收暂停异常任务'},
        )
        assert self.query(f"SELECT state FROM subscriptions WHERE id={task_id}") == 'paused'
        self.record('Admin task list is masked and pause persists')

        # --- permissions and audit ---
        mod.call(
            '/api/v1/admin/announcements',
            'POST',
            {'title': '版主公告', 'body_markdown': '不应成功'},
            expected=403,
        )
        mod.call(
            '/api/v1/admin/boards',
            'POST',
            {'name': '版主板块'},
            expected=403,
        )
        mod.call('/api/v1/admin/audit-logs', expected=403)
        mod.call(f'/api/v1/reports/{rid_goods}', expected=404)
        third.call('/api/v1/admin/reports', expected=403)
        logs = admin.call('/api/v1/admin/audit-logs?page_size=100')['data']['items']
        actions = {item['action'] for item in logs}
        assert {
            'report.resolve',
            'announcement.publish',
            'announcement.retract',
            'board.create',
            'board.disable',
            'subscription.pause',
        } <= actions
        assert all(isinstance(item['changes'], dict) for item in logs)
        self.record('Role denials, cross-board denial and audit trail with safe changes')

        browser_post = alice.post(board, '浏览器举报验收帖', '用于浏览器检查举报入口')
        bob.call(
            f'/api/v1/posts/{browser_post["id"]}/comments',
            'POST',
            {'body': '浏览器举报的评论', 'parent_id': None},
            expected=201,
        )

        # --- restart persistence ---
        self.stop(self.server)
        self.server = self.start([self.binary], 'api')
        self.wait('/health/ready')
        visitor.call(f'/api/v1/announcements/{announcement["id"]}', expected=404)
        assert admin.call(f'/api/v1/reports/{rid}')['data']['state'] == 'resolved'
        public_boards = visitor.call('/api/v1/boards')['data']['items']
        assert all(item['id'] != new_board['id'] for item in public_boards)
        assert self.query(f"SELECT state FROM subscriptions WHERE id={task_id}") == 'paused'
        self.record('Report, announcement, board and task states survive an API restart')

        # --- browser: report entry, admin decision, announcement and mobile layout ---
        cli = ROOT / 'apps/web/node_modules/next/dist/bin/next'
        self.web_process = self.start(
            ['node', str(cli), 'start', '--hostname', '127.0.0.1', '--port', self.env['WEB_PORT']],
            'web',
            cwd=ROOT / 'apps/web',
        )
        self.wait('/health/ready', base=self.web)
        self.run(
            ['node', str(ROOT / 'scripts/admin-browser.cjs')],
            'browser',
            extra={
                'ADMIN_BROWSER_USER': self.alice_account,
                'ADMIN_BROWSER_PASSWORD': self.password,
                'ADMIN_BROWSER_ADMIN': self.root_account,
                'ADMIN_BROWSER_ADMIN_PASSWORD': self.password,
                'ADMIN_BROWSER_POST': browser_post['id'],
            },
        )
        self.record('Browser comment report, admin decision, announcement publish and mobile layout')


if __name__ == '__main__':
    task = VerifyAdmin(log_dir=ROOT / '.local/logs/admin410')
    try:
        task.execute()
    finally:
        task.cleanup()

"""Forum pagination check: fixed 20 posts per page, page numbers and jump form."""
import json

from test_support import ROOT
from test_support.accounts import AccountVerification
from test_support.http import GoodsClient


class VerifyPagination(AccountVerification):
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

        alice = GoodsClient(self)
        alice.register(self.alice_account, self.password)
        alice.login(self.alice_account, self.password)
        board = alice.call('/api/v1/boards')['data']['items'][0]['id']
        for index in range(45):
            alice.post(
                board,
                title=f'分页验收帖 {index:02d}',
                body=f'第 {index} 条帖子用于检查固定分页、页码和跳页。',
            )
        total = alice.call(f'/api/v1/posts?board_id={board}&page_size=20')['data']['total']
        assert total == 45, total
        first = alice.call(f'/api/v1/posts?board_id={board}&page_size=20')['data']
        second = alice.call(f'/api/v1/posts?board_id={board}&page_size=20&page=2')['data']
        third = alice.call(f'/api/v1/posts?board_id={board}&page_size=20&page=3')['data']
        assert (len(first['items']), len(second['items']), len(third['items'])) == (20, 20, 5)
        assert first['page_size'] == 20 and first['page'] == 1
        self.record('45 posts are returned as 20/20/5 with page and page_size in the response')

        self.run(['node', str(ROOT / 'scripts/test_pagination.mjs')], 'page-window')
        self.record('Pure page-window checks cover edges, ellipsis and clamping')

        cli = ROOT / 'apps/web/node_modules/next/dist/bin/next'
        self.web_process = self.start(
            ['node', str(cli), 'start', '--hostname', '127.0.0.1', '--port', self.env['WEB_PORT']],
            'web',
            cwd=ROOT / 'apps/web',
        )
        self.wait('/health/ready', base=self.web)
        self.run(
            ['node', str(ROOT / 'scripts/pagination-browser.cjs')],
            'browser',
            extra={
                'PAGINATION_USER': self.alice_account,
                'PAGINATION_PASSWORD': self.password,
                'PAGINATION_BOARD': board,
            },
        )
        self.record(
            'Browser: 20/20/5 pages, page-number navigation, jump validation, disabled edges and 390px layout'
        )


if __name__ == '__main__':
    task = VerifyPagination(log_dir=ROOT / '.local/logs/pagination')
    try:
        task.execute()
    finally:
        task.cleanup()

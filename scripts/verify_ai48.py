"""Run against a disposable database and a local embedding service; no real AI key required."""
from test_support import ROOT
from test_support.accounts import AccountVerification
from test_support.http import GoodsClient
import json,time,urllib.parse

class Verify48(AccountVerification):
    def execute(self):
        self.env['AI_ENABLED']='false'
        self.env['AI_EMBEDDING_URL']='http://127.0.0.1:18084'
        self.owns_services=True
        self.run(self.compose+['up','-d','--wait','--wait-timeout','240'],'services-up')
        self.sql(f"CREATE DATABASE `{self.database}` CHARACTER SET utf8mb4; GRANT ALL ON `{self.database}`.* TO '{self.env['MYSQL_USER']}'@'%';",'create-test-database');self.created=True
        self.cli(['--migrate'],'migrate')
        self.query('DROP TABLE report_ai_jobs; ALTER TABLE search_documents DROP COLUMN embedding; DELETE FROM _sqlx_migrations WHERE version IN (6,7);')
        self.cli(['--migrate'],'migrate-upgrade-from-five')
        assert self.query('SELECT COUNT(*) FROM _sqlx_migrations WHERE success=1;')=='7'
        self.record('Upgrade from schema version five in disposable database')
        self.cli(['--init-admin'],'init-admin',json.dumps({'account':self.root_account,'nickname':'管理员','password':self.password}).encode())
        self.server=self.start([self.binary],'api');self.wait('/health/ready')
        admin=GoodsClient(self);admin.login(self.root_account,self.password)
        alice=GoodsClient(self);alice.register(self.alice_account,self.password);alice.login(self.alice_account,self.password)
        bob=GoodsClient(self);bob.register(self.bob_account,self.password);bob.login(self.bob_account,self.password)
        visitor=GoodsClient(self);board=visitor.call('/api/v1/boards')['data']['items'][0]['id'];category=visitor.call('/api/v1/goods-categories')['data'][0]['id']
        mod=GoodsClient(self);mod_account='mod_'+self.suffix;mod.register(mod_account,self.password);mod.login(mod_account,self.password);member=self.target(admin,mod.me()['id']);self.admin_action(admin,mod.me()['id'],'role',{'role':'moderator','board_ids':[board],'version':member['version'],'reason':'举报权限测试'})
        post=alice.post(board,'校园学习平板讨论','用电子设备在课堂上记录笔记')
        good=alice.publish(category,title='学习用平板电脑',description='适合课堂手写笔记',price_cents=180000,brand='Apple',attributes={'stylus_support':True})
        other=alice.publish(category,title='价格较高的平板电脑',price_cents=300000,brand='Apple')
        unknown=alice.publish(category,title='手写笔支持未知的平板',price_cents=100000,brand='Apple')
        for attempt in range(60):
            n=int(self.query("SELECT COUNT(*) FROM search_documents WHERE state='ready'"))
            if n>=4:break
            time.sleep(2)
        assert n>=4,'index did not finish'
        q=urllib.parse.urlencode({'q':'上课记录笔记的设备','mode':'semantic','kind':'goods','max_price_cents':'200000','campus_code':'shahe','brand':'Apple','stylus_support':'true','min_condition':'good'})
        result=visitor.call('/api/v1/search?'+q)['data'];assert result['mode_used']=='semantic' and not result['degraded']
        ids=[v['id'] for v in result['items']];assert good['id'] in ids and other['id'] not in ids and unknown['id'] not in ids
        self.record('Real local vector search and precise product filters')
        result=bob.call('/api/v1/post-reports','POST',{'post_id':post['id'],'reason':'疑似垃圾信息'})['data'];rid=result['id']
        assert bob.call('/api/v1/post-reports','POST',{'post_id':post['id'],'reason':'重复举报'})['data']['already_exists']
        alice.call('/api/v1/reports/'+rid,expected=404)
        detail=admin.call('/api/v1/reports/'+rid)['data'];assert detail['state']=='pending' and detail['snapshot']['title']==post['title']
        assert detail['ai']['state']=='disabled' and 'attachments' in detail['snapshot'] and 'captured_at' in detail['snapshot']
        assert any(x['id']==rid for x in admin.call('/api/v1/admin/reports')['data']['items'])
        assert mod.call('/api/v1/reports/'+rid)['data']['id']==rid
        bob.call('/api/v1/reports/'+rid,'PATCH',{'action':'hide','reason':'无权限','version':detail['version'],'post_version':detail['current']['version']},403)
        admin.call('/api/v1/reports/'+rid,'PATCH',{'action':'hide','reason':'人工复核','version':detail['version'],'post_version':detail['current']['version']})
        visitor.call('/api/v1/posts/'+post['id'],expected=404)
        result=bob.call('/api/v1/me/reports')['data'];assert result['items'][0]['state']=='resolved'
        assert any(n['kind']=='report_result' for n in bob.call('/api/v1/notifications')['data']['items'])
        self.record('Report duplicate prevention, permissions, decision, post hiding and persisted notification')
        q=urllib.parse.urlencode({'q':'学习平板','mode':'semantic','kind':'post'})
        assert all(v['id']!=post['id'] for v in visitor.call('/api/v1/search?'+q)['data']['items'])
        self.record('Hidden post excluded immediately from semantic results')
        bob.call('/api/v1/ai/goods-intent','POST',{'text':'沙河平板'},503)
        self.record('Disabled text model fails safely without blocking manual handling')
        browser_post=alice.post(board,'浏览器举报验收帖','用于验证举报页面的测试内容')
        cli=ROOT/'apps/web/node_modules/next/dist/bin/next'
        self.web_process=self.start(['node',str(cli),'start','--hostname','127.0.0.1','--port',self.env['WEB_PORT']],'web',cwd=ROOT/'apps/web')
        self.wait('/health/ready',base=self.web)
        self.run(['node',str(ROOT/'scripts/ai48-browser.cjs')],'browser',extra={'AI48_BUYER':self.bob_account,'AI48_PASSWORD':self.password,'AI48_POST':browser_post['id']})
        self.record('Browser AI confirmation, hard filters, reporting and mobile layout')

if __name__=='__main__':
    task=Verify48(log_dir=ROOT/'.local/logs/ai48')
    try:task.execute()
    finally:task.cleanup()

"""4.6.2 real goods, search, image and browser checks in an owned temporary database."""
import concurrent.futures
import json
import re
import socket
import sys
import urllib.parse
from pathlib import Path
import verify_accounts as accounts
import verify_forum as forum
import verify_runtime as runtime

ROOT=runtime.ROOT;LOG=ROOT/'.local/logs/goods';RESULT=ROOT/'docs/goods/verification.json'
accounts.LOG=LOG;runtime.LOG=LOG

class Client(forum.Client):
    def publish(self,category,images=None,expected=201,**overrides):
        if images is None:images=[self.upload(accounts.png(),'goods_image')['data']['id']]
        data={'category_id':category,'campus_code':'shahe','title':'校园测试商品','description':'商品真实描述','condition_code':'good','price_cents':1250,'location_text':'教学楼门口','image_file_ids':images,'brand':None,'model':None,'purpose':None,'attributes':{}}
        data.update(overrides);reply=self.call('/api/v1/goods','POST',data,expected)
        return reply['data'] if expected==201 else reply

class Goods(accounts.Accounts):
    def execute(self):
        for address in [self.api,self.web]:
            parsed=urllib.parse.urlparse(address);assert parsed.hostname in ['localhost','127.0.0.1','::1'] and parsed.scheme=='http'
            with socket.socket() as connection:assert connection.connect_ex((parsed.hostname,parsed.port))!=0,'Stop development programs before verification.'
        self.api=self.api.replace('localhost','127.0.0.1');self.env['UPLOAD_ROOT']=str(ROOT/'.local/goods-tests'/self.database)
        self.owns_services=True;self.run(self.compose+['up','-d','--wait','--wait-timeout','240'],'services-up')
        assert re.fullmatch(r'[A-Za-z0-9_]+',self.env['MYSQL_USER'])
        self.sql(f"CREATE DATABASE `{self.database}` CHARACTER SET utf8mb4; GRANT ALL ON `{self.database}`.* TO '{self.env['MYSQL_USER']}'@'%';",'create-database');self.created=True
        self.cli(['--migrate'],'migrate');self.cli(['--migrate'],'migrate-repeat')
        self.cli(['--init-admin'],'init-admin',json.dumps({'account':self.root_account,'nickname':'商品测试管理员','password':self.password}).encode())
        self.server=self.start([self.binary],'api');self.wait('/health/ready')
        admin=Client(self);admin.login(self.root_account,self.password)
        alice=Client(self);alice.register(self.alice_account,self.password,'商品卖家');alice.login(self.alice_account,self.password);aid=alice.me()['id']
        bob=Client(self);bob.register(self.bob_account,self.password,'商品买家');bob.login(self.bob_account,self.password)
        mod=Client(self);mod_account='mod_'+self.suffix;mod.register(mod_account,self.password,'商品测试版主');mod.login(mod_account,self.password);mid=mod.me()['id']
        visitor=Client(self);board=visitor.call('/api/v1/boards')['data']['items'][0]['id']
        member=self.target(admin,mid);self.admin_action(admin,mid,'role',{'role':'moderator','board_ids':[board],'version':member['version'],'reason':'商品权限检查'})
        cats=visitor.call('/api/v1/goods-categories')['data'];campuses=visitor.call('/api/v1/campuses')['data'];category=cats[0]['id'];other_category=cats[1]['id']
        assert {v['code'] for v in campuses}=={'shahe','xitucheng','other'} and len(cats)>=2
        self.record('Independent database, migrations, enabled category/campus dictionaries and account roles')

        image=alice.upload(accounts.png(),'goods_image')['data'];visitor.call(image['url'],expected=404)
        item=alice.publish(category,[image['id']],title='校园检索平板',price_cents=29,attributes={'stylus_support':False,'storage_gb':64},brand='Apple',model='iPad',purpose='学习');gid=item['id'];url='/api/v1/goods/'+gid
        assert item['price_cents']==29 and item['attributes']['stylus_support'] is False and not item['can_contact']
        assert visitor.call(url)['data']['can_contact'] and visitor.call(url)['data']['seller']['id']==aid
        visitor.call(image['url'],json_response=False)
        assert any(v['id']==gid for v in visitor.call('/api/v1/goods')['data']['items'])
        self.record('Real product creation, exact integer cents, optional facts, image binding and public detail/list readback')

        for price,status in [(0,201),(9999999,201),(10000000,422),(-1,400),(1.25,400),('1.23',400),(True,400)]:
            alice.publish(category,price_cents=price,expected=status)
        for kwargs,status in [({'title':'短'},422),({'description':' '},422),({'description':'字'*5001},422),({'campus_code':'other','location_text':' '},422),({'condition_code':'unknown'},422),({'category_id':'999999'},422),({'attributes':{'storage_gb':0}},422),({'attributes':{'stylus_support':'yes'}},400),({'attributes':{'unknown':True}},400),({'seller_id':aid},400),({'state':'sold'},400)]:
            alice.publish(category,expected=status,**kwargs)
        alice.publish(category,campus_code='other',location_text='校外地铁站',description='邮'*5000)
        self.query(f'UPDATE goods_categories SET enabled=false WHERE id={other_category};');alice.publish(other_category,expected=422);self.query(f'UPDATE goods_categories SET enabled=true WHERE id={other_category};')
        self.record('Free/max prices and Unicode boundaries work; fractional, forged, missing-dictionary and invalid optional facts are rejected')

        for count in [0,7]:alice.publish(category,images=[image['id']]*count,expected=422)
        spare=alice.upload(accounts.png(),'goods_image')['data'];post_image=alice.upload(accounts.png(),'post_image')['data']
        alice.publish(category,images=[spare['id'],spare['id']],expected=422)
        alice.publish(category,images=[image['id']],expected=422)
        bob.publish(category,images=[spare['id']],expected=404)
        before=self.query('SELECT COUNT(*) FROM goods;')
        alice.publish(category,images=[spare['id'],post_image['id']],expected=422)
        assert self.query('SELECT COUNT(*) FROM goods;')==before and self.query(f"SELECT state FROM files WHERE id={spare['id']};")=='staged'
        expired=alice.upload(accounts.png(),'goods_image')['data'];self.query(f"UPDATE files SET expires_at=DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 1 HOUR) WHERE id={expired['id']};")
        alice.publish(category,images=[expired['id']],expected=422)
        self.record('One-to-six images, purpose, ownership, expiry, duplicate binding and publish rollback are enforced')

        visitor.call('/api/v1/goods','POST',{'title':'匿名发布'},401)
        for client in [bob,admin,mod]:client.call(url,'PATCH',{'version':item['version'],'price_cents':1},403)
        alice.call(url,'PATCH',{'version':item['version'],'price_cents':1},403,headers={'Origin':'https://invalid.example'})
        alice.call(url,'PATCH',{'version':item['version'],'price_cents':1},403,protect=False)
        alice.call(url,'PATCH',{'version':item['version'],'price_cents':None},400)
        alice.call(url,'PATCH',{'version':item['version']},422)
        alice.call(url,'PATCH',{'version':item['version'],'moderation':'clear'},400)
        self.record('Seller-only writes, JSON field rules, CSRF and exact Origin checks apply to all goods mutations')

        images=[alice.upload(accounts.png(),'goods_image')['data'] for _ in range(2)]
        current=alice.call(url,'PATCH',{'version':item['version'],'price_cents':3010,'image_file_ids':[i['id'] for i in images],'brand':None,'attributes':{'storage_gb':None,'stylus_support':True}})['data']
        assert current['price_cents']==3010 and current['brand'] is None and current['attributes']['storage_gb'] is None
        assert [v['id'] for v in current['images']]==[v['id'] for v in images]
        visitor.call(image['url'],expected=404)
        current=alice.call(url,'PATCH',{'version':current['version'],'image_file_ids':[v['id'] for v in reversed(images)]})['data']
        assert current['images'][0]['id']==images[1]['id']
        quota=int(alice.call('/api/v1/me/file-quota')['data']['used_bytes']);self.cli(['--cleanup-files'],'cleanup-removed-files')
        # Includes one expired spare upload as well as the replaced original image.
        assert int(alice.call('/api/v1/me/file-quota')['data']['used_bytes'])==quota-2*len(accounts.png())
        self.record('Editing preserves exact cents, clears optional values, reorders/replaces images and releases quota only after cleanup')

        def edit(client):
            try:client.call(url,'PATCH',{'version':current['version'],'price_cents':3030});return 200
            except AssertionError as error:assert 'received 409' in str(error);return 409
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(edit,[alice.clone(),alice.clone()]))
        assert sorted(outcomes)==[200,409];current=alice.call(url)['data']
        self.record('Concurrent seller edits accept one matching version and reject a stale update')

        for state in ['reserved','on_sale','off_shelf','on_sale']:
            current=alice.call(url+'/state','PATCH',{'version':current['version'],'state':state})['data']
            assert current['state']==state
            visible=visitor.call('/api/v1/goods')['data']['items'];assert any(v['id']==gid for v in visible)==(state=='on_sale')
            assert any(v['id']==gid for v in visitor.call('/api/v1/goods?state='+state)['data']['items'])
        alice.call(url+'/state','PATCH',{'version':current['version'],'state':'on_sale'},409)
        current=alice.call(url+'/state','PATCH',{'version':current['version'],'state':'sold'})['data']
        for state in ['on_sale','reserved','off_shelf']:alice.call(url+'/state','PATCH',{'version':current['version'],'state':state},409)
        alice.call(url,'PATCH',{'version':current['version'],'price_cents':3000},409)
        self.record('Reservation, cancellation, shelving and final sold state follow the required transition graph')

        protected=alice.publish(category,title='治理检索商品');restricted_url='/api/v1/goods/'+protected['id'];bound=protected['images'][0]['url']
        for client in [bob,mod]:client.call('/api/v1/admin/goods/'+protected['id']+'/moderation','PATCH',{'version':protected['version'],'action':'restrict','reason':'越权检查'},403)
        admin.call('/api/v1/admin/goods/'+protected['id']+'/moderation','PATCH',{'version':protected['version'],'action':'restrict','reason':'管理下架检查'})
        visitor.call(restricted_url,expected=404);bob.call(bound,expected=404);visitor.call(bound,expected=404)
        own=alice.call('/api/v1/me/goods/'+protected['id'])['data'];assert own['moderation']=='restricted' and own['state']=='off_shelf'
        alice.call(bound,json_response=False);admin.call(bound,json_response=False);bob.call('/api/v1/me/goods/'+protected['id'],expected=404)
        alice.call(restricted_url+'/state','PATCH',{'version':own['version'],'state':'on_sale'},409)
        alice.call(restricted_url,'PATCH',{'version':own['version'],'title':'绕过管理'},409)
        admin.call('/api/v1/admin/goods/'+protected['id']+'/moderation','PATCH',{'version':own['version'],'action':'release','reason':'解除限制检查'})
        released=alice.call(restricted_url)['data'];assert released['state']=='off_shelf'
        admin.call('/api/v1/admin/goods/'+gid+'/moderation','PATCH',{'version':current['version'],'action':'restrict','reason':'已售不能复活'})
        sold_private=admin.call('/api/v1/admin/goods/'+gid)['data'];assert sold_private['state']=='sold'
        admin.call('/api/v1/admin/goods/'+gid+'/moderation','PATCH',{'version':sold_private['version'],'action':'release','reason':'解除已售限制'})
        assert alice.call(url)['data']['state']=='sold'
        self.record('Admin restriction hides detail/files; only seller/admin can inspect, release never auto-lists or revives sold goods')

        post=alice.post(board,title='检索共同词帖子',body='公开帖子正文共同词');search_good=alice.publish(category,title='检索共同词商品',price_cents=1000,campus_code='shahe');description=alice.publish(other_category,title='普通物品',description='检索共同词在商品描述',price_cents=2000,campus_code='xitucheng')
        def search(q,extra=''):return visitor.call('/api/v1/search?q='+urllib.parse.quote(q)+extra)['data']
        hits=search('检索共同词');kinds={(v['kind'],v['id']) for v in hits['items']}
        assert ('post',post['id']) in kinds and ('goods',search_good['id']) in kinds and hits['mode_used']=='keyword' and not hits['degraded']
        assert hits['items'][-1]['rank_score']==1
        assert all(v['kind']=='post' for v in search('检索共同词','&kind=post')['items'])
        filtered=search('检索共同词',f'&category_id={category}&campus_code=shahe&max_price_cents=1000')
        assert [v['id'] for v in filtered['items']]==[search_good['id']]
        assert not search('检索共同词','&max_price_cents=999')['items']
        degraded=search('检索共同词','&mode=semantic');assert degraded['degraded'] and degraded['mode_used']=='keyword'
        self.record('Unified keyword search returns typed post/goods hits with truthful ranking, inclusive filters and explicit semantic fallback')

        literal=alice.publish(category,title='百分比20%_!商品')
        assert [v['id'] for v in search('20%_!')['items']]==[literal['id']]
        assert not search("' OR 1=1 --")['items']
        private_word='private_'+self.suffix
        self.query(f"INSERT INTO notifications(recipient_id,kind,target_type,safe_summary) VALUES ({aid},'system','none','{private_word}');")
        assert not search(private_word)['items']
        first=search('检索共同词','&page_size=1');second=search('检索共同词','&page_size=1&page=2')
        assert (first['items'][0]['kind'],first['items'][0]['id'])!=(second['items'][0]['kind'],second['items'][0]['id'])
        assert search('检索共同词','&page_size=1')['items']==first['items']
        for query in ['','?q=','?q='+urllib.parse.quote(' '),'?q=x&kind=bad','?q=x&max_price_cents=-1','?q=x&max_price_cents=1.1','?q=x&page=0','?q=x&page_size=101','?q=x&campus_code=bad']:visitor.call('/api/v1/search'+query,expected=422)
        self.record('Literal wildcard/SQL characters, private-source exclusion, stable mixed pagination and search validation')

        public_post=visitor.call('/api/v1/posts/'+post['id'])['data'];admin.call('/api/v1/admin/posts/'+post['id']+'/moderation','PATCH',{'version':public_post['version'],'action':'hide','reason':'搜索即时隐藏'})
        search_current=alice.call('/api/v1/goods/'+search_good['id'])['data']
        search_current=alice.call('/api/v1/goods/'+search_good['id']+'/state','PATCH',{'version':search_current['version'],'state':'reserved'})['data']
        hidden_hits={(v['kind'],v['id']) for v in search('检索共同词')['items']};assert ('post',post['id']) not in hidden_hits and ('goods',search_good['id']) not in hidden_hits
        admin.call('/api/v1/admin/goods/'+description['id']+'/moderation','PATCH',{'version':description['version'],'action':'restrict','reason':'搜索即时下架'})
        assert not search('检索共同词')['items']
        # Restore designated browser fixtures to a public, searchable state.
        hidden_post=admin.call('/api/v1/admin/posts/'+post['id'])['data'];admin.call('/api/v1/admin/posts/'+post['id']+'/moderation','PATCH',{'version':hidden_post['version'],'action':'restore','reason':'浏览器检查准备'})
        search_current=alice.call('/api/v1/goods/'+search_good['id']+'/state','PATCH',{'version':search_current['version'],'state':'on_sale'})['data']
        self.record('Search consults current source visibility and excludes hidden posts, reserved/sold/restricted goods immediately')

        shared=alice.upload(accounts.png(),'goods_image')['data'];
        def bind(client):
            try:client.call('/api/v1/goods','POST',{'category_id':category,'campus_code':'shahe','title':'并发图片绑定','description':'同一图片只能属于一件商品','condition_code':'good','price_cents':100,'location_text':'','image_file_ids':[shared['id']]},201);return 201
            except AssertionError as error:assert 'received 422' in str(error);return 422
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(bind,[alice.clone(),alice.clone()]))
        assert sorted(results)==[201,422]
        assert self.query(f"SELECT COUNT(*) FROM file_bindings WHERE file_id={shared['id']};")=='1'
        self.record('Concurrent publishing cannot bind the same uploaded image to two products')

        for bad in ['?max_price_cents=1.5','?max_price_cents=-1','?state=bad','?page=abc','?page_size=0']:visitor.call('/api/v1/goods'+bad,expected=422)
        assert all(v['seller']['id']==aid for v in alice.call('/api/v1/me/goods?page_size=100')['data']['items'])
        bob.call('/api/v1/admin/goods',expected=403);mod.call('/api/v1/admin/goods',expected=403)
        assert admin.call('/api/v1/admin/goods')['data']['total']>=1
        self.record('Goods/public/owner/admin JSON follows the existing OpenAPI with bounded inputs and private ownership')

        fixture=LOG/'fixture.png';fixture.write_bytes(accounts.png())
        next_cli=ROOT/'apps/web/node_modules/next/dist/bin/next'
        self.web_process=self.start(['node',next_cli,'start','--hostname','127.0.0.1','--port',self.env['WEB_PORT']],'web',cwd=ROOT/'apps/web');self.wait('/health/ready',base=self.web)
        extra={'E2E_GOODS':'1','GOODS_ALICE':self.alice_account,'GOODS_BOB':self.bob_account,'GOODS_ADMIN':self.root_account,'GOODS_PASSWORD':self.password,'GOODS_SUFFIX':self.suffix,'GOODS_PNG':str(fixture),'GOODS_CATEGORY':category,'GOODS_SEED':search_good['id'],'GOODS_POST':post['id']}
        cli=ROOT/'apps/web/node_modules/@playwright/test/cli.js';self.run(['node',cli,'test','tests/goods.spec.mjs'],'browser',cwd=ROOT/'apps/web',extra=extra)
        report=json.loads((ROOT/'.local/logs/dev/browser-results.json').read_text(encoding='utf-8'));assert report['stats']['expected']==4 and report['stats']['unexpected']==0
        (LOG/'browser-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        self.record('Four real browser cases: goods lifecycle/uploads, search-return/mobile, moderation privacy and database-failure recovery')

        restart=alice.publish(category,title='重启保留商品',price_cents=1234)
        self.stop(self.server);self.run(self.compose+['restart'],'database-restart');self.run(self.compose+['up','-d','--wait'],'database-ready');self.server=self.start([self.binary],'api-restarted');self.wait('/health/ready')
        assert alice.call('/api/v1/goods/'+restart['id'])['data']['price_cents']==1234 and alice.me()['id']==aid
        assert search('重启保留商品')['total']==1
        self.record('API/MySQL/Redis restart preserves goods, exact prices, searchable records and valid sessions')

        original=alice.call(url)['data'];alice.call(url,'DELETE',{'version':original['version']});visitor.call(url,expected=404)
        for image in original['images']:visitor.call(image['url'],expected=404);alice.call(image['url'],expected=404)
        assert not search('校园检索平板')['items']
        assert self.query('SELECT COUNT(*) FROM content_changes;')==self.query('SELECT COUNT(*) FROM search_index_jobs;')
        assert int(self.query("SELECT COUNT(*) FROM audit_logs WHERE target_type='goods';"))>=5
        assert self.query("SELECT counter_value FROM system_counters WHERE counter_key='content_changes';")==self.query('SELECT MAX(change_seq) FROM content_changes;')
        self.record('Deletion revokes old detail/image/search routes; shared change counter, search jobs and moderation audit remain consistent')

def main():
    LOG.mkdir(parents=True,exist_ok=True);RESULT.parent.mkdir(parents=True,exist_ok=True)
    verification=Goods();status='failed';error=None
    try:verification.execute();status='passed'
    except Exception as exc:error=str(exc);print(error,file=sys.stderr)
    finally:
        try:verification.cleanup()
        except Exception as exc:status='failed';error=str(exc);print('Goods verification cleanup failed',file=sys.stderr)
        RESULT.write_text(json.dumps({'stage':'4.6.2','status':status,'checks':verification.checks,'browser_cases':4 if any('Four real browser' in s for s in verification.checks) else 0,'isolated_database_removed':not verification.created,'development_accounts_modified':False,'server_deployed':False,'ai_search_implemented':False,'error':error},ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if status=='passed' else 1
if __name__=='__main__':sys.exit(main())

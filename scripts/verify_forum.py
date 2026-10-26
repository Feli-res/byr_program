"""4.6.1 real HTTP/browser verification in an owned disposable database."""
from pathlib import Path
import concurrent.futures
import json
import os
import re
import secrets
import socket
import sys
import urllib.parse
import uuid
import verify_accounts as accounts
import verify_runtime as runtime

ROOT=runtime.ROOT
LOG=ROOT/'.local/logs/forum'
RESULT=ROOT/'docs/forum/verification.json'
accounts.LOG=LOG
runtime.LOG=LOG

def pdf(active=False):
    objects=[b'<< /Type /Catalog /Pages 2 0 R '+(b'/Names << /JavaScript << /Names [(demo) << /S /JavaScript /JS (alert) >>] >> >> ' if active=='nested' else b'/OpenAction << /S /JavaScript /JS (alert) >> ' if active else b'')+b'>>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>']
    data=b'%PDF-1.4\n';offsets=[0]
    for index,obj in enumerate(objects,1):offsets.append(len(data));data+=f'{index} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(data);data+=f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()
    for offset in offsets[1:]:data+=f'{offset:010d} 00000 n \n'.encode()
    return data+f'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()

class Client(accounts.Client):
    def upload(self,content,purpose='post_image',name='image.png',mime='image/png',expected=201):
        boundary='forum'+uuid.uuid4().hex
        raw=(f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\n{purpose}\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n').encode()+content+f'\r\n--{boundary}--\r\n'.encode()
        return self.call('/api/v1/files','POST',expected=expected,raw=raw,headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
    def post(self,board,title='接口测试帖子',body='真实保存的正文',images=None,pdfs=None,expected=201):
        result=self.call('/api/v1/posts','POST',{'board_id':board,'title':title,'body_markdown':body,'image_file_ids':images or [],'pdf_file_ids':pdfs or []},expected)
        return result['data'] if expected==201 else result

class Forum(accounts.Accounts):
    def execute(self):
        for address in [self.api,self.web]:
            parsed=urllib.parse.urlparse(address)
            assert parsed.hostname in ['localhost','127.0.0.1','::1'] and parsed.scheme=='http'
            with socket.socket() as connection:assert connection.connect_ex((parsed.hostname,parsed.port))!=0,'Stop local development programs first.'
        self.api=self.api.replace('localhost','127.0.0.1')
        self.env['UPLOAD_ROOT']=str(ROOT/'.local/forum-tests'/self.database)
        self.owns_services=True;self.run(self.compose+['up','-d','--wait','--wait-timeout','240'],'services-up')
        assert re.fullmatch(r'[A-Za-z0-9_]+',self.env['MYSQL_USER'])
        self.sql(f"CREATE DATABASE `{self.database}` CHARACTER SET utf8mb4; GRANT ALL ON `{self.database}`.* TO '{self.env['MYSQL_USER']}'@'%';",'create-test-database');self.created=True
        self.cli(['--migrate'],'migrate');self.cli(['--migrate'],'repeat-migrate')
        self.cli(['--init-admin'],'init-admin',json.dumps({'account':self.root_account,'nickname':'论坛测试管理员','password':self.password}).encode())
        self.server=self.start([self.binary],'api');self.wait('/health/ready')
        admin=Client(self);admin.login(self.root_account,self.password)
        alice=Client(self);alice.register(self.alice_account,self.password,'论坛测试甲');alice.login(self.alice_account,self.password);alice_id=alice.me()['id']
        bob=Client(self);bob.register(self.bob_account,self.password,'论坛测试乙');bob.login(self.bob_account,self.password);bob_id=bob.me()['id']
        mod=Client(self);mod_account='mod_'+self.suffix;mod.register(mod_account,self.password,'授权版主');mod.login(mod_account,self.password);mod_id=mod.me()['id']
        visitor=Client(self)
        boards=visitor.call('/api/v1/boards')['data']['items'];b1,b2=[b['id'] for b in boards[:2]]
        target=self.target(admin,mod_id)
        self.admin_action(admin,mod_id,'role',{'role':'moderator','board_ids':[b1],'version':target['version'],'reason':'论坛权限检查'})
        self.record('Independent migrated database and ordinary/admin/board-moderator identities')

        image=alice.upload(accounts.png())['data'];attachment=alice.upload(pdf(),'post_pdf','notes.pdf','application/pdf')['data']
        goods_image=alice.upload(accounts.png(),'goods_image')['data']
        for file in [image,attachment,goods_image]:
            visitor.call(file['url'],expected=404);bob.call(file['url'],expected=404);alice.call(file['url'],json_response=False)
        visitor.call('/api/v1/files','POST',expected=401,raw=b'',headers={'Content-Type':'multipart/form-data; boundary=none'})
        self.record('All new upload purposes work; staged uploads are readable only by their owner')
        alice.upload(accounts.png(),mime='image/jpeg',expected=415)
        alice.upload(b'not an image',expected=415)
        alice.upload(accounts.png(),'post_image','unsafe.svg','image/svg+xml',415)
        alice.upload(b'%PDF-1.4\nnot a document\n%%EOF','post_pdf','fake.pdf','application/pdf',415)
        alice.upload(pdf(True),'post_pdf','active.pdf','application/pdf',415)
        alice.upload(pdf('nested'),'post_pdf','nested.pdf','application/pdf',415)
        alice.upload(accounts.png(),'post_image','../escape.png','image/png',422)
        alice.upload(b'x'*(5242880+1),expected=413)
        alice.upload(b'x'*(10485760+1),'post_pdf','large.pdf','application/pdf',413)
        self.record('Real image/PDF parsing, MIME-extension matching, active PDF rejection, path and size limits')

        first=alice.post(b1,images=[image['id']],pdfs=[attachment['id']]);pid=first['id'];url=f'/api/v1/posts/{pid}'
        second=bob.post(b2,title='第二板块帖子');p2=second['id']
        assert first['author']['id']==alice_id and 'account' not in first['author']
        detail=visitor.call(url)['data'];assert detail['title']==first['title'] and detail['image_files'][0]['id']==image['id']
        visitor.call(image['url'],json_response=False)
        visitor.call(attachment['url'],json_response=False)
        assert 'attachment' in visitor.last_headers['Content-Disposition'] and visitor.last_headers['X-Content-Type-Options']=='nosniff'
        assert len(visitor.call('/api/v1/posts')['data']['items'])==2
        self.record('Posts persist in two boards; attachments bind atomically and valid PDFs download with safe headers')

        for payload in [{'board_id':b1,'title':'短','body_markdown':'x'},{'board_id':b1,'title':'正常标题','body_markdown':' '},{'board_id':b1,'title':'正常标题','body_markdown':'字'*20001}]:alice.call('/api/v1/posts','POST',payload,422)
        alice.call('/api/v1/posts','POST',{'board_id':b1,'title':'伪造作者','body_markdown':'正文','author_id':bob_id},400)
        alice.call(url,'PATCH',{'version':first['version'],'title':None},400)
        alice.call(url,'PATCH',{'version':first['version']},422)
        boundary=alice.post(b1,title='Unicode边界',body='邮'*20000);assert len(boundary['body_markdown'])==20000
        self.query(f'UPDATE boards SET enabled=false WHERE id={b2};')
        alice.post(b2,expected=422)
        self.query(f'UPDATE boards SET enabled=true WHERE id={b2};')
        self.record('Unicode text boundaries, disabled boards, forged fields and null/no-op edits are rejected')

        alice.call(url,'PATCH',{'version':first['version'],'title':'非法来源'},403,headers={'Origin':'https://invalid.example'})
        alice.call(url,'PATCH',{'version':first['version'],'title':'缺少保护'},403,protect=False)
        bob.call(url,'PATCH',{'version':first['version'],'title':'越权修改'},403)
        admin.call(url,'PATCH',{'version':first['version'],'title':'管理员不代改'},403)
        mod.call(url,'DELETE',{'version':first['version']},403)
        self.record('CSRF, exact Origin and author restrictions protect forum writes for every role')

        for _ in range(2):bob.call(url+'/like','PUT');bob.call(url+'/favorite','PUT')
        detail=bob.call(url)['data'];assert detail['like_count']==1 and detail['liked_by_me'] and detail['saved_by_me']
        assert any(p['id']==pid for p in bob.call('/api/v1/me/favorites')['data']['items'])
        for _ in range(2):bob.call(url+'/like','DELETE');bob.call(url+'/favorite','DELETE')
        assert visitor.call(url)['data']['like_count']==0
        self.record('Likes and favorites are idempotent; personal collections return only current public posts')

        comment=bob.call(url+'/comments','POST',{'body':'真实评论'},201)['data'];cid=comment['id']
        reply=alice.call(url+'/comments','POST',{'body':'回复评论','parent_id':cid},201)['data']
        assert reply['parent_id']==cid
        alice.call(f'/api/v1/posts/{p2}/comments','POST',{'body':'跨帖回复','parent_id':cid},422)
        alice.call(f'/api/v1/comments/{cid}','DELETE',expected=403)
        assert visitor.call(url)['data']['comment_count']==2
        assert visitor.call(url)['data']['body_markdown']
        listing=visitor.call('/api/v1/posts?board_id='+b1)['data'];assert next(p for p in listing['items'] if p['id']==pid)['last_reply']['author']['id']==alice_id
        self.record('Comments preserve same-post parent relationships, counts and latest reply metadata')

        def edit(args):
            client,title=args
            try:client.call(url,'PATCH',{'version':first['version'],'title':title});return 200
            except AssertionError as e:
                assert 'received 409' in str(e);return 409
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(edit,[(alice.clone(),'并发修改甲'),(alice.clone(),'并发修改乙')]))
        assert sorted(outcomes)==[200,409]
        current=alice.call(url)['data'];assert current['version']==first['version']+1
        self.record('Concurrent edits with the same version preserve one successful update and reject the stale write')

        retained=alice.upload(accounts.png())['data']
        count=self.query('SELECT COUNT(*) FROM posts;')
        alice.post(b1,images=[retained['id'],goods_image['id']],expected=422)
        assert self.query('SELECT COUNT(*) FROM posts;')==count
        assert self.query(f"SELECT state FROM files WHERE id={retained['id']};")=='staged'
        bob.post(b1,images=[retained['id']],expected=404)
        alice.post(b1,images=[image['id']],expected=422)
        alice.post(b1,images=[retained['id'],retained['id']],expected=422)
        alice.post(b1,images=[retained['id']]*10,expected=422)
        alice.post(b1,pdfs=[attachment['id']]*3,expected=422)
        self.record('Failed publishing rolls back posts and bindings; ownership, purpose, duplication and attachment counts are enforced')

        updated=alice.call(url,'PATCH',{'version':current['version'],'image_file_ids':[retained['id']],'pdf_file_ids':[]})['data']
        visitor.call(image['url'],expected=404);alice.call(image['url'],expected=404)
        visitor.call(attachment['url'],expected=404);visitor.call(retained['url'],json_response=False)
        quota_before=int(alice.call('/api/v1/me/file-quota')['data']['used_bytes'])
        self.cli(['--cleanup-files'],'cleanup-replaced-attachments')
        assert int(alice.call('/api/v1/me/file-quota')['data']['used_bytes'])==quota_before-len(accounts.png())-len(pdf())
        assert self.query(f"SELECT state FROM files WHERE id={image['id']};")=='cleaned'
        self.record('Replacing/removing bound files revokes old URLs immediately and physical cleanup returns quota')

        mod.call(f'/api/v1/admin/posts/{p2}/moderation','PATCH',{'action':'pin','version':second['version'],'reason':'跨板块检查'},403)
        bob.call('/api/v1/admin/posts',expected=403)
        mod.call(f'/api/v1/admin/posts/{p2}',expected=403)
        mod.call(url.replace('/posts/','/admin/posts/')+'/moderation','PATCH',{'action':'pin','version':updated['version'],'reason':'有用讨论置顶'})
        pinned=visitor.call('/api/v1/posts?sort=popular')['data']['items'][0];assert pinned['id']==pid and pinned['pinned']
        assert {p['board_id'] for p in mod.call('/api/v1/admin/posts')['data']['items']}=={b1}
        self.record('Only authorized moderators can manage their board; pinned posts lead stable public ordering')

        current=admin.call('/api/v1/admin/posts/'+pid)['data']
        admin.call('/api/v1/admin/posts/'+pid+'/moderation','PATCH',{'action':'hide','version':current['version'],'reason':'隐藏与附件权限检查'})
        visitor.call(url,expected=404);visitor.call(retained['url'],expected=404);bob.call(retained['url'],expected=404)
        alice.call(retained['url'],json_response=False);mod.call(retained['url'],json_response=False)
        assert alice.call('/api/v1/me/posts/'+pid)['data']['visibility']=='hidden'
        hidden=admin.call('/api/v1/admin/posts/'+pid)['data']
        alice.call(url,'PATCH',{'version':hidden['version'],'title':'尝试绕过隐藏'},403)
        assert all(p['id']!=pid for p in visitor.call('/api/v1/posts')['data']['items'])
        admin.call('/api/v1/admin/posts/'+pid+'/moderation','PATCH',{'action':'restore','version':hidden['version'],'reason':'完成检查恢复'})
        visitor.call(retained['url'],json_response=False)
        self.record('Hidden posts leave public views; file reads enforce author/board governance scope and restore correctly')

        mod.call(f'/api/v1/admin/comments/{cid}/moderation','PATCH',{'action':'hide','reason':'评论隐藏检查'})
        hidden_comment=next(c for c in visitor.call(url+'/comments')['data']['items'] if c['id']==cid)
        assert hidden_comment['state']=='hidden' and hidden_comment['body'] is None and hidden_comment['author'] is None
        bob.call(url+'/comments','POST',{'body':'回复隐藏评论','parent_id':cid},422)
        mod.call(f'/api/v1/admin/comments/{cid}/moderation','PATCH',{'action':'restore','reason':'恢复评论检查'})
        bob.call(f'/api/v1/comments/{cid}','DELETE');bob.call(f'/api/v1/comments/{cid}','DELETE')
        placeholder=next(c for c in visitor.call(url+'/comments')['data']['items'] if c['id']==cid)
        assert placeholder['state']=='deleted' and placeholder['body'] is None
        mod.call(f'/api/v1/admin/comments/{cid}/moderation','PATCH',{'action':'restore','reason':'删除不可恢复'},404)
        assert any(c['id']==reply['id'] and c['parent_id']==cid for c in visitor.call(url+'/comments')['data']['items'])
        self.record('Hidden/deleted comments use safe placeholders, retain reply structure and cannot restore deleted text')

        for bad in ['page=0','page=garbage','page_size=101','sort=unsupported']:visitor.call('/api/v1/posts?'+bad,expected=422)
        pages=visitor.call('/api/v1/posts?page_size=1')['data'];assert len(pages['items'])==1
        assert visitor.call('/api/v1/posts?page=2&page_size=1')['data']['items'][0]['id']!=pages['items'][0]['id']
        self.record('Public/personal/admin responses conform to 4.3 OpenAPI with bounded stable pagination')

        self.query(f'UPDATE users SET used_file_bytes=209715200 WHERE id={bob_id};')
        bob.upload(accounts.png(),expected=422)
        self.query(f'UPDATE users SET used_file_bytes=0 WHERE id={bob_id};')
        expired=alice.upload(accounts.png(),'goods_image')['data']
        self.query(f"UPDATE files SET expires_at=DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 1 HOUR) WHERE id={expired['id']};")
        alice.call(expired['url'],expected=404);self.cli(['--cleanup-files'],'cleanup-expired-purpose')
        assert self.query(f"SELECT state FROM files WHERE id={expired['id']};")=='cleaned'
        self.record('Shared quota and staged expiry/cleanup apply to goods uploads as well as forum attachments')

        # Real browser tests operate in this same isolated database.
        image_path=LOG/'fixture.png';image_path.write_bytes(accounts.png())
        pdf_path=LOG/'fixture.pdf';prefix=pdf().rsplit(b'%%EOF',1)[0];large_pdf=prefix+b'%'+b' '*(10485760-len(prefix)-8)+b'\n%%EOF\n';assert len(large_pdf)==10485760;pdf_path.write_bytes(large_pdf)
        cli=ROOT/'apps/web/node_modules/next/dist/bin/next'
        self.web_process=self.start(['node',cli,'start','--hostname','127.0.0.1','--port',self.env['WEB_PORT']],'web',cwd=ROOT/'apps/web');self.wait('/health/ready',base=self.web)
        extra={'E2E_FORUM':'1','FORUM_ALICE':self.alice_account,'FORUM_BOB':self.bob_account,'FORUM_MOD':mod_account,'FORUM_PASSWORD':self.password,'FORUM_SUFFIX':self.suffix,'FORUM_PNG':str(image_path),'FORUM_PDF':str(pdf_path),'FORUM_POST':pid,'FORUM_OTHER_POST':p2,'FORUM_BOARD':b1}
        playwright=ROOT/'apps/web/node_modules/@playwright/test/cli.js'
        self.run(['node',playwright,'test','tests/forum.spec.mjs'],'browser',cwd=ROOT/'apps/web',extra=extra)
        report=json.loads((ROOT/'.local/logs/dev/browser-results.json').read_text(encoding='utf-8'));assert report['stats']['expected']==3 and report['stats']['unexpected']==0
        (LOG/'browser-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        self.record('Three real browser cases: forum/upload/edit flow, moderator scope and actual database-failure form recovery')

        self.run(self.compose+['stop','mysql'],'mysql-stop')
        alice.call('/api/v1/posts','POST',{'board_id':b1,'title':'故障不应成功','body_markdown':'保存失败检查'},503)
        self.run(self.compose+['up','-d','--wait'],'mysql-recover');self.wait('/health/ready')
        self.stop(self.server);self.run(self.compose+['restart'],'restart-databases');self.run(self.compose+['up','-d','--wait'],'wait-databases')
        self.server=self.start([self.binary],'api-restarted');self.wait('/health/ready')
        assert alice.call(url)['data']['id']==pid and alice.me()['id']==alice_id
        self.record('Actual database outage returns failure; restarted API/MySQL/Redis preserve forum records and sessions')

        current=alice.call(url)['data'];alice.call(url,'DELETE',{'version':current['version']})
        visitor.call(url,expected=404);visitor.call(retained['url'],expected=404);alice.call(retained['url'],expected=404)
        admin.call('/api/v1/admin/posts/'+pid+'/moderation','PATCH',{'action':'restore','version':current['version']+1,'reason':'不能恢复删除'},404)
        assert self.query('SELECT COUNT(*) FROM content_changes;')==self.query('SELECT COUNT(*) FROM search_index_jobs;')
        assert int(self.query("SELECT COUNT(*) FROM audit_logs WHERE target_type IN ('post','comment');"))>=5
        self.record('Soft deletion revokes content/files; durable content-change jobs and moderation audit are recorded together')

def main():
    LOG.mkdir(parents=True,exist_ok=True);RESULT.parent.mkdir(parents=True,exist_ok=True)
    verification=Forum();status='failed';error=None
    try:verification.execute();status='passed'
    except Exception as exc:error=str(exc);print(error,file=sys.stderr)
    finally:
        try:verification.cleanup()
        except Exception as exc:status='failed';error=str(exc);print('Forum cleanup failed',file=sys.stderr)
        RESULT.write_text(json.dumps({'stage':'4.6.1','status':status,'checks':verification.checks,'browser_cases':3 if any('Three real browser' in c for c in verification.checks) else 0,'isolated_database_removed':not verification.created,'development_accounts_modified':False,'server_deployed':False,'error':error},ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if status=='passed' else 1
if __name__=='__main__':sys.exit(main())

"""Real 4.5 verification in a uniquely created, disposable MySQL database."""
from pathlib import Path
import concurrent.futures
import copy
import hashlib
import http.cookiejar
import http.client
import json
import os
import re
import secrets
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib
import verify_runtime as runtime

ROOT=runtime.ROOT
for package_dir in [ROOT/'.local/design-qa/python',ROOT/'.local/accounts-qa/python']:
    if package_dir.exists():sys.path.insert(0,str(package_dir))
from jsonschema import Draft202012Validator,FormatChecker,ValidationError
CONTRACT=json.loads((ROOT/'docs/design/openapi.json').read_text(encoding='utf-8-sig'))
LOG=ROOT/'.local/logs/accounts'
RESULT=ROOT/'docs/accounts/verification.json'
runtime.LOG=LOG

def png(width=1,height=1):
    def chunk(name,data):return struct.pack('!I',len(data))+name+data+struct.pack('!I',zlib.crc32(name+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\0\0\xff'))+chunk(b'IEND',b'')

class Client:
    def __init__(self,verification):
        self.v=verification;self.jar=http.cookiejar.CookieJar();self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
    def clone(self):
        other=Client(self.v)
        for cookie in self.jar:other.jar.set_cookie(copy.copy(cookie))
        return other
    def cookie(self,name):return next((c.value for c in self.jar if c.name==name),None)
    def call(self,path,method='GET',body=None,expected=200,protect=True,headers=None,raw=None,json_response=True):
        head={'Connection':'close'};data=raw
        if body is not None:data=json.dumps(body,ensure_ascii=False).encode();head['Content-Type']='application/json'
        if method not in ['GET','HEAD']:
            head['Origin']=self.v.web
            if protect:head['X-CSRF-Token']=self.call('/api/v1/csrf')['data']['csrf_token']
        head.update(headers or {})
        request=urllib.request.Request(self.v.api+path,data=data,headers=head,method=method)
        for attempt in range(3):
            response=None
            try:
                try:response=self.opener.open(request,timeout=20);status=response.status
                except urllib.error.HTTPError as error:response=error;status=error.code
                self.last_headers=response.headers;result=response.read();break
            except (OSError,http.client.HTTPException) as error:
                if method not in ['GET','HEAD'] or attempt==2:raise RuntimeError(f'Transport failure for {method} {path}: {type(error).__name__}') from None
                time.sleep(.2)
            finally:
                if response is not None:response.close()
        assert status==expected,f'{method} {path}: expected {expected}, received {status}'
        if not json_response:return result
        payload=json.loads(result)
        assert uuid.UUID(payload['meta']['request_id'])
        for route,operations in CONTRACT['paths'].items():
            if method.lower() not in operations or not re.fullmatch(re.sub(r'\{[^}]+\}',r'[^/]+',route),urllib.parse.urlsplit(path).path):continue
            responses=operations[method.lower()]['responses'];spec=responses.get(str(status),responses.get('default'))
            schema=spec['content']['application/json']['schema']
            try:Draft202012Validator({**CONTRACT,**schema},format_checker=FormatChecker()).validate(payload)
            except ValidationError as error:raise AssertionError(f'OpenAPI response mismatch for {method} {path} at {error.json_path}') from None
            break
        if status>=400:
            assert 'error' in payload and 'data' not in payload
            assert all(word not in payload['error']['message'] for word in ['SELECT ','INSERT ','mysql://','D:\\'])
        return payload
    def login(self,account,password,expected=200):return self.call('/api/v1/auth/login','POST',{'account':account,'password':password},expected)
    def register(self,account,password,nickname='测试用户',expected=201):return self.call('/api/v1/auth/register','POST',{'account':account,'password':password,'nickname':nickname},expected)
    def upload(self,content,name='avatar.png',mime='image/png',expected=201):
        boundary='byr'+uuid.uuid4().hex
        raw=(f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\navatar\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n').encode()+content+f'\r\n--{boundary}--\r\n'.encode()
        return self.call('/api/v1/files','POST',expected=expected,raw=raw,headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
    def me(self):return self.call('/api/v1/me')['data']

class Accounts(runtime.Verification):
    def __init__(self):
        super().__init__();self.database='byr_accounts_'+uuid.uuid4().hex[:16];self.created=False
        self.env['DATABASE_URL']=self.env['DATABASE_URL'].rsplit('/',1)[0]+'/'+self.database
        self.env['UPLOAD_ROOT']=str(ROOT/'.local/account-tests'/self.database)
        self.env['RUST_LOG']='info,sqlx::query=error'
        self.suffix=uuid.uuid4().hex[:8]
        self.password=' '+secrets.token_urlsafe(18)+' '
        self.root_account='root_'+self.suffix;self.alice_account='alice_'+self.suffix;self.bob_account='bob_'+self.suffix
        self.server=None;self.web_process=None
    def sql(self,sql,name='sql'):
        command=self.compose+['exec','-T','mysql','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 --batch --skip-column-names']
        result=subprocess.run(command,input=sql.encode('utf-8'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.env,cwd=ROOT)
        if result.returncode:raise RuntimeError('Test SQL failed: '+name)
        return result.stdout.decode('utf-8').strip()
    def query(self,sql):return self.sql(f'USE `{self.database}`; '+sql)
    def cli(self,args,name,input=None,expected=0):
        with (LOG/(name+'.log')).open('wb') as log:
            result=subprocess.run([self.binary,*args],input=input,env=self.env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        assert (result.returncode==0)==(expected==0),name+' returned an unexpected exit status'
    def clear_limits(self):self.query('DELETE FROM auth_login_limits;')
    def admin_action(self,admin,target,kind,data,expected=200):
        return admin.call(f'/api/v1/admin/users/{target}/{kind}','POST' if kind=='password-reset' else 'PATCH',data,expected)
    def target(self,admin,uid):
        return next(item for item in admin.call('/api/v1/admin/users?page_size=100')['data']['items'] if item['id']==uid)
    def new_reset(self,admin,uid):
        version=self.target(admin,uid)['version']
        return self.admin_action(admin,uid,'password-reset',{'version':version,'reason':'账户集成检查'})['data']['credential']
    def execute(self):
        for address in [self.api,self.web]:
            parsed=urllib.parse.urlparse(address)
            assert parsed.hostname in ['localhost','127.0.0.1','::1'] and parsed.scheme=='http','Account verification is restricted to local HTTP development services.'
            with socket.socket() as connection:assert connection.connect_ex((parsed.hostname,parsed.port))!=0,'Stop development programs before running account verification.'
        self.owns_services=True;self.run(self.compose+['up','-d','--wait','--wait-timeout','240'],'services-up')
        assert re.fullmatch(r'[A-Za-z0-9_]+',self.env['MYSQL_USER'])
        self.sql(f"CREATE DATABASE `{self.database}` CHARACTER SET utf8mb4; GRANT ALL ON `{self.database}`.* TO '{self.env['MYSQL_USER']}'@'%';",'create-test-database');self.created=True
        self.cli(['--migrate'],'migrate-empty');self.cli(['--migrate'],'migrate-repeat')
        assert self.query('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE(); SELECT COUNT(*) FROM _sqlx_migrations WHERE success=1;').split()==['35','5']
        self.record('Fresh isolated database: five migrations and repeat execution')
        admin_input=json.dumps({'account':self.root_account,'nickname':'初始管理员','password':self.password}).encode()
        self.cli(['--init-admin'],'initialize-administrator',admin_input)
        self.cli(['--init-admin'],'refuse-second-bootstrap',admin_input,1)
        self.record('Interactive-admin command supports secure stdin verification and refuses repeated bootstrap')
        self.server=self.start([self.binary],'api');self.wait('/health/ready')
        admin=Client(self);admin.login(self.root_account,self.password)
        alice=Client(self);registered=alice.register(' '+self.alice_account.upper()+' ',self.password)
        assert set(registered['data'])=={'id','nickname','bio','avatar_url'}
        assert alice.cookie('byr_session') is None
        alice.call('/api/v1/me',expected=401)
        uid=registered['data']['id']
        duplicate=Client(self);duplicate.register(self.alice_account,self.password,expected=409)
        duplicate.call('/api/v1/auth/register','POST',{'account':'evil_'+self.suffix,'nickname':'角色注入','password':self.password,'role':'admin'},400)
        duplicate.register('1bad',self.password,expected=422)
        duplicate.register('valid_'+self.suffix,'short',expected=422)
        self.record('Registration normalization, duplicates, validation, no auto-login and role injection rejection')
        alice.login(self.alice_account,self.password);session=alice.cookie('byr_session')
        headers=';'.join(alice.last_headers.get_all('Set-Cookie'))
        assert 'HttpOnly' in headers and 'SameSite=Lax' in headers and 'Domain=' not in headers
        assert alice.me()['account']==self.alice_account and alice.me()['role']=='user'
        stored=self.query(f'SELECT password_hash FROM users WHERE id={uid};')
        assert stored.startswith('$argon2id$v=19$m=19456,t=2,p=1$') and self.password not in stored
        assert self.query('SELECT MIN(TIMESTAMPDIFF(SECOND,created_at,expires_at)) FROM sessions;')=='604800'
        self.record('Argon2id parameters, normalized login, host-only HttpOnly cookie and seven-day absolute session')
        alice.call('/api/v1/me','PATCH',{'version':alice.me()['version'],'bio':'拒绝没有请求保护'},403,protect=False)
        alice.call('/api/v1/me','PATCH',{'version':alice.me()['version'],'bio':'拒绝错误来源'},403,headers={'Origin':'https://unrelated.example'})
        alice.call('/api/v1/me','PATCH',{'version':alice.me()['version'],'bio':'拒绝空来源'},403,headers={'Origin':'null'})
        anon=Client(self);old_csrf=anon.call('/api/v1/csrf')['data']['csrf_token'];anon.login(self.alice_account,self.password)
        for c in anon.jar:
            if c.name=='byr_csrf':c.value=old_csrf
        anon.call('/api/v1/me','PATCH',{'version':anon.me()['version'],'bio':'旧的匿名保护'},403,protect=False,headers={'X-CSRF-Token':old_csrf})
        self.record('Signed CSRF cookie/header, strict Origin and anonymous-to-session binding')
        version=alice.me()['version']
        updated=alice.call('/api/v1/me','PATCH',{'version':version,'nickname':'资料已修改','bio':'校园生活与学习'})['data']
        assert updated['nickname']=='资料已修改' and updated['version']==version+1
        alice.call('/api/v1/me','PATCH',{'version':version,'bio':'过期版本'},409)
        alice.call('/api/v1/me','PATCH',{'version':updated['version'],'user_id':'999','role':'admin'},400)
        alice.call('/api/v1/me','PATCH',{'version':updated['version'],'nickname':None},400)
        clients=[alice.clone(),alice.clone()];version=alice.me()['version']
        def update(pair):
            client,index=pair
            try:client.call('/api/v1/me','PATCH',{'version':version,'nickname':f'并发修改{index}'},expected=200);return 200
            except AssertionError as error:
                assert 'received 409' in str(error);return 409
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(update,zip(clients,[1,2])))==[200,409]
        self.record('Personal data, stale versions, forged fields and concurrent profile updates')
        bob=Client(self);bob_id=bob.register(self.bob_account,self.password,'第二位用户')['data']['id'];bob.login(self.bob_account,self.password)
        photo=alice.upload(png())['data'];alice.call(photo['url'],json_response=False)
        Client(self).call(photo['url'],expected=404);bob.call(photo['url'],expected=404);admin.call(photo['url'],expected=404)
        bob.call('/api/v1/me','PATCH',{'version':bob.me()['version'],'avatar_file_id':photo['id']},404)
        saved=alice.call('/api/v1/me','PATCH',{'version':alice.me()['version'],'avatar_file_id':photo['id']})['data'];assert saved['avatar_url']==photo['url']
        assert Client(self).call(photo['url'],json_response=False)==png()
        alice.call('/api/v1/files/'+photo['id'],'DELETE',expected=422)
        alice.upload(b'<html>not a picture</html>',expected=415)
        alice.upload(png(),name='fake.jpg',mime='image/jpeg',expected=415)
        alice.upload(png(100000,100000),expected=415)
        alice.upload(b'x'*(2097152+1),expected=413)
        used=alice.call('/api/v1/me/file-quota')['data']['used_bytes'];assert used==len(png())
        self.query(f'UPDATE users SET used_file_bytes=209715199 WHERE id={uid};')
        alice.upload(png(),expected=422)
        self.query(f'UPDATE users SET used_file_bytes={used} WHERE id={uid};')
        alice.call('/api/v1/me','PATCH',{'version':alice.me()['version'],'avatar_file_id':None})
        Client(self).call(photo['url'],expected=404)
        self.cli(['--cleanup-files'],'cleanup-detached-avatar')
        assert alice.call('/api/v1/me/file-quota')['data']['used_bytes']==0
        unbound=alice.upload(png())['data'];alice.call('/api/v1/files/'+unbound['id'],'DELETE');alice.call('/api/v1/files/'+unbound['id'],'DELETE')
        expired=alice.upload(png())['data'];self.query(f"UPDATE files SET expires_at=DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 1 SECOND) WHERE id={expired['id']};")
        alice.call(expired['url'],expected=404);self.cli(['--cleanup-files'],'cleanup-expired-avatar')
        assert alice.call('/api/v1/me/file-quota')['data']['used_bytes']==0
        self.record('Real avatar decoding, size/dimension/quota limits, ownership, public binding, detach and cleanup')
        first=alice.clone();other=Client(self);other.login(self.alice_account,self.password)
        alice.call('/api/v1/auth/logout','POST');first.call('/api/v1/me',expected=401);other.me()
        self.record('Logout revokes current session while another browser session stays valid')
        changed=secrets.token_urlsafe(20)
        stale=other.clone();other.call('/api/v1/me/password','POST',{'current_password':self.password,'new_password':changed})
        stale.call('/api/v1/me',expected=401);anon.call('/api/v1/me',expected=401)
        alice=Client(self);alice.login(self.alice_account,changed)
        self.record('Password change revokes every old session and accepts the new password')
        token=alice.cookie('byr_session');digest=hashlib.sha256(token.encode()).hexdigest()
        self.query(f"UPDATE sessions SET expires_at=DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 1 SECOND) WHERE token_hash=UNHEX('{digest}');")
        alice.call('/api/v1/me',expected=401);alice.login(self.alice_account,changed)
        self.record('Expired sessions are rejected without silent renewal')
        alice.call('/api/v1/admin/users',expected=403)
        root_id=admin.me()['id'];root_version=admin.me()['version']
        self.admin_action(admin,root_id,'role',{'role':'user','board_ids':[],'version':root_version,'reason':'禁止移除最后管理员'},409)
        self.admin_action(admin,root_id,'status',{'status':'banned','version':root_version,'reason':'禁止封禁最后管理员'},409)
        self.admin_action(admin,root_id,'password-reset',{'version':root_version,'reason':'本人应使用改密入口'},422)
        role=self.admin_action(admin,bob_id,'role',{'role':'moderator','board_ids':['1'],'version':bob.me()['version'],'reason':'验证版主授权'})['data'];assert role['board_ids']==['1']
        assert bob.me()['role']=='moderator';bob.call('/api/v1/admin/users',expected=403)
        self.record('Ordinary/moderator/admin restrictions, board authorization and last-administrator protection')
        self.query(f"INSERT INTO subscriptions(owner_id,name,conditions,interval_minutes) VALUES ({uid},'封禁暂停检查',JSON_OBJECT(),5);")
        old=alice.clone()
        self.admin_action(admin,uid,'status',{'status':'banned','version':self.target(admin,uid)['version'],'reason':'验证封禁'})
        old.call('/api/v1/me',expected=401)
        banned=Client(self);banned.login(self.alice_account,changed,expected=403)
        assert self.query(f'SELECT state FROM subscriptions WHERE owner_id={uid};')=='paused'
        self.admin_action(admin,uid,'status',{'status':'active','version':self.target(admin,uid)['version'],'reason':'验证解封'})
        assert self.query(f'SELECT state FROM subscriptions WHERE owner_id={uid};')=='paused'
        alice=Client(self);alice.login(self.alice_account,changed)
        self.record('Ban revokes sessions and pauses tasks; unban does not resume tasks')
        old=alice.clone();credential=self.new_reset(admin,uid);old.call('/api/v1/me',expected=401)
        reset=Client(self);reset.login(self.alice_account,changed,expected=403)
        # A reset credential is never a normal login session.
        reset.call('/api/v1/me',expected=401,headers={'Cookie':'byr_session='+credential})
        reset_password=secrets.token_urlsafe(20)
        reset.call('/api/v1/auth/reset-password','POST',{'credential':credential,'new_password':reset_password})
        reset.call('/api/v1/auth/reset-password','POST',{'credential':credential,'new_password':reset_password},422)
        alice=Client(self);alice.login(self.alice_account,reset_password)
        expired_credential=self.new_reset(admin,uid)
        digest=hashlib.sha256(expired_credential.encode()).hexdigest()
        self.query(f"UPDATE password_resets SET expires_at=DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 1 SECOND) WHERE credential_hash=UNHEX('{digest}');")
        reset.call('/api/v1/auth/reset-password','POST',{'credential':expired_credential,'new_password':reset_password},422)
        current=self.new_reset(admin,uid)
        reset.call('/api/v1/auth/reset-password','POST',{'credential':expired_credential,'new_password':reset_password},422)
        reset.call('/api/v1/auth/reset-password','POST',{'credential':current,'new_password':reset_password})
        self.record('Admin reset: old sessions revoked, change-only token, single use, expiry and reissue')
        audit=self.query("SELECT CAST(safe_changes AS CHAR) FROM audit_logs;")
        assert all(secret not in audit for secret in [self.password,credential,current,reset_password])
        self.record('Management actions audited without passwords or credentials')
        self.record('Implemented JSON responses validate against the existing 4.3 OpenAPI schemas')
        self.clear_limits()
        next_cli=ROOT/'apps/web/node_modules/next/dist/bin/next'
        self.web_process=self.start(['node',next_cli,'start','--hostname','127.0.0.1','--port',self.env['WEB_PORT']],'web',cwd=ROOT/'apps/web')
        self.wait('/health/ready',base=self.web)
        self.browser_accounts(admin_account=self.root_account,admin_password=self.password)
        self.record('Browser registration/login/profile/avatar/change/logout and administrator reset flows')
        self.run(self.compose+['stop','mysql'],'mysql-stop')
        self.browser_accounts(failure=True)
        self.record('Browser database-failure registration retains non-secret fields and shows no success')
        self.run(self.compose+['up','-d','--wait'],'mysql-recover');self.wait('/health/ready')
        self.clear_limits()
        alice=Client(self);alice.login(self.alice_account,reset_password)
        self.stop(self.server);self.run(self.compose+['restart'],'database-restart');self.run(self.compose+['up','-d','--wait'],'restart-wait')
        self.server=self.start([self.binary],'api-after-restart');self.wait('/health/ready');assert alice.me()['id']==uid
        self.record('Accounts and still-valid sessions persist through API and database restart')
        # Concurrent changes must not remove both administrators.
        bob_data=self.target(admin,bob_id)
        self.admin_action(admin,bob_id,'role',{'role':'admin','board_ids':[],'version':bob_data['version'],'reason':'并发保护检查'})
        root_data=self.target(admin,root_id);bob_data=self.target(admin,bob_id)
        def demote(args):
            client,target,version=args
            try:self.admin_action(client,target,'role',{'role':'user','board_ids':[],'version':version,'reason':'并发移除管理员'});return 200
            except AssertionError as error:
                assert 'received 403' in str(error) or 'received 409' in str(error);return 409
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(demote,[(admin,bob_id,bob_data['version']),(bob,root_id,root_data['version'])]))
        assert sorted(outcomes)==[200,409]
        assert self.query("SELECT COUNT(*) FROM users WHERE role='admin' AND status='active' AND password_reset_required=false;")=='1'
        self.record('Concurrent administrator changes preserve one usable administrator')
        self.clear_limits();attacker=Client(self)
        for index in range(5):attacker.login(self.alice_account,'deliberately-wrong-password',expected=401)
        blocked=Client(self);blocked.login(self.alice_account,reset_password,expected=429)
        assert int(blocked.last_headers['Retry-After'])>0
        blocked.call('/api/v1/auth/login','POST',{'account':self.bob_account,'password':self.password},429,headers={'X-Forwarded-For':'203.0.113.123'})
        self.run(self.compose+['stop','redis'],'redis-off-during-limit')
        blocked.login(self.alice_account,reset_password,expected=429)
        self.query('UPDATE auth_login_limits SET locked_until=DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 1 SECOND),window_started_at=DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 31 MINUTE);')
        blocked.login(self.alice_account,reset_password)
        self.record('Five-failure account/IP throttling, Retry-After, spoofed forwarding rejection and Redis-loss persistence')
        logs='\n'.join(p.read_text(encoding='utf-8',errors='replace') for p in LOG.glob('api*.log'))
        assert all(secret not in logs for secret in [self.password,session,credential,current,reset_password])
        self.record('Access logs contain no tested passwords, session tokens or reset credentials')

    def browser_accounts(self,failure=False,admin_account='',admin_password=''):
        cli=ROOT/'apps/web/node_modules/@playwright/test/cli.js'
        fixture=LOG/'avatar.png';fixture.write_bytes(png())
        extra={'E2E_ACCOUNTS':'1','ACCOUNT_FAILURE_MODE':'1' if failure else '0','ACCOUNT_TEST_SUFFIX':self.suffix,'ACCOUNT_ADMIN':admin_account,'ACCOUNT_ADMIN_PASSWORD':admin_password,'ACCOUNT_TEST_PASSWORD':secrets.token_urlsafe(20),'ACCOUNT_PNG_FIXTURE':str(fixture)}
        self.run(['node',cli,'test','tests/accounts.spec.mjs'],'browser-failure' if failure else 'browser',cwd=ROOT/'apps/web',extra=extra)
        report=json.loads((ROOT/'.local/logs/dev/browser-results.json').read_text(encoding='utf-8'))
        assert report['stats']['expected']==(1 if failure else 2) and report['stats']['unexpected']==0
        (LOG/('browser-failure-results.json' if failure else 'browser-results.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def cleanup(self):
        for process in reversed(self.processes):self.stop(process)
        for log in self.logs:log.close()
        if self.created:
            assert re.fullmatch(r'byr_accounts_[a-f0-9]{16}',self.database)
            self.run(self.compose+['up','-d','--wait'],'cleanup-services-ready')
            self.sql(f"REVOKE ALL PRIVILEGES ON `{self.database}`.* FROM '{self.env['MYSQL_USER']}'@'%'; DROP DATABASE `{self.database}`;",'drop-own-test-database');self.created=False
        if self.owns_services:self.run(self.compose+['stop'],'services-stop')

def main():
    LOG.mkdir(parents=True,exist_ok=True);RESULT.parent.mkdir(parents=True,exist_ok=True)
    verification=Accounts();status='failed';error=None
    try:verification.execute();status='passed'
    except Exception as exc:error=str(exc);print(error,file=sys.stderr)
    finally:
        try:verification.cleanup()
        except Exception as exc:status='failed';error=str(exc);print('Verification cleanup failed',file=sys.stderr)
        RESULT.write_text(json.dumps({'stage':'4.5','status':status,'checks':verification.checks,'isolated_test_database_removed':not verification.created,'real_browser':'Microsoft Edge on Windows; bundled Chromium in CI','real_development_accounts_modified':False,'websocket_invalidation_tested':False,'server_deployed':False,'error':error},ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if status=='passed' else 1
if __name__=='__main__':sys.exit(main())

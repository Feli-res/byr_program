"""Chat scenarios; shared setup lives in test_support."""
from test_support import ROOT
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import concurrent.futures
import hashlib
from websockets.exceptions import ConnectionClosed, InvalidStatus
from test_support.runtime import environment
from test_support.chat import ChatVerification
from test_support.http import GoodsClient as Client
from test_support.fixtures import png, pdf
from test_support.websocket import Live
LOG=ROOT/".local/logs/chat"
RESULT=ROOT/"docs/chat/verification.json"

class Chat(ChatVerification):
    def __init__(self):
        super().__init__(log_dir=LOG)

    def revoke_check(self,admin,kind,index):
        client=Client(self);account='close_'+self.suffix+str(index);client.register(account,self.password,'连接撤销检查');client.login(account,self.password);uid=client.me()['id'];live=Live(self,client)
        if kind=='logout':
            other=Client(self);other.login(account,self.password);survivor=Live(self,other)
        start=time.monotonic()
        if kind=='logout':client.call('/api/v1/auth/logout','POST')
        elif kind=='password_changed':client.call('/api/v1/me/password','POST',{'current_password':self.password,'new_password':self.password+'n'})
        elif kind in ['banned','password_reset']:
            target=self.target(admin,uid)
            if kind=='banned':self.admin_action(admin,uid,'status',{'version':target['version'],'status':'banned','reason':'实时连接撤销检查'})
            else:self.admin_action(admin,uid,'password-reset',{'version':target['version'],'reason':'实时重置检查'})
        else:
            token=next(c.value for c in client.jar if c.name=='byr_session');digest=hashlib.sha256(token.encode()).hexdigest()
            self.query(f"UPDATE sessions SET expires_at=DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 1 SECOND) WHERE token_hash=UNHEX('{digest}');")
        event=live.until('session.revoked');elapsed=time.monotonic()-start;assert event['data']['reason_code']==kind and elapsed<5,(kind,elapsed)
        try:live.ws.recv(timeout=2);raise AssertionError('Revoked connection remained open')
        except ConnectionClosed as error:assert error.rcvd and error.rcvd.code==4001
        self.revocations[kind]=round(elapsed,3)
        if kind=='logout':rid=survivor.send('ping',{});assert survivor.until('pong')['request_id']==rid;survivor.close()

    def verify_push_failure(self,bob,cid,recipient):
        message=bob.call('/api/v1/conversations/'+cid+'/messages','POST',{'client_message_id':str(uuid.uuid4()),'body':'推送失败也保留的消息'},201)['data']
        source=message['id']
        self.query(f"UPDATE outbox_events SET state='pending',attempts=0,next_due_at=DATE_ADD(UTC_TIMESTAMP(6),INTERVAL 1 HOUR) WHERE event_type='message.created' AND source_id={source} AND recipient_id={recipient};")
        event_id=self.query(f"SELECT id FROM outbox_events WHERE event_type='message.created' AND source_id={source} AND recipient_id={recipient};")
        command=self.compose+['exec','-T','mysql','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 --batch --skip-column-names']
        holder=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=self.env,cwd=ROOT)
        try:
            holder.stdin.write(f'USE `{self.database}`; LOCK TABLES messages WRITE; SELECT SLEEP(9); UNLOCK TABLES;'.encode());holder.stdin.close()
            deadline=time.monotonic()+4
            while self.query("SELECT COUNT(*) FROM information_schema.processlist WHERE DB=DATABASE() AND INFO='SELECT SLEEP(9)';")=='0':
                assert time.monotonic()<deadline,'Temporary test lock was not acquired';time.sleep(.1)
            self.query(f"UPDATE outbox_events SET next_due_at=UTC_TIMESTAMP(6) WHERE id={event_id};")
            deadline=time.monotonic()+4
            while self.query(f'SELECT attempts FROM outbox_events WHERE id={event_id};')=='0':
                assert time.monotonic()<deadline,'Failed live hint was not retried';time.sleep(.1)
            assert self.query(f'SELECT state,attempts FROM outbox_events WHERE id={event_id};').split()==['pending','1']
            self.query(f"UPDATE outbox_events SET attempts=5,next_due_at=UTC_TIMESTAMP(6) WHERE id={event_id};")
            deadline=time.monotonic()+4
            while self.query(f'SELECT state FROM outbox_events WHERE id={event_id};')!='expired':
                assert time.monotonic()<deadline,'Live hint exceeded finite retry limit';time.sleep(.1)
            assert self.query(f'SELECT attempts FROM outbox_events WHERE id={event_id};')=='6'
        finally:
            try:holder.wait(timeout=12)
            except subprocess.TimeoutExpired:holder.terminate();holder.wait(timeout=3)
        assert any(m['id']==source for m in bob.call('/api/v1/conversations/'+cid+'/messages')['data']['items'])
        self.record('A real temporary read lock causes push retry and expiry after its final allowed attempt; committed HTTP history remains intact')

    def execute(self):
        for address in [self.api,self.web]:
            parsed=urllib.parse.urlparse(address);assert parsed.hostname in ['localhost','127.0.0.1','::1'] and parsed.scheme=='http'
            with socket.socket() as connection:assert connection.connect_ex((parsed.hostname,parsed.port))!=0,'Stop local development programs first.'
        self.api=self.api.replace('localhost','127.0.0.1');self.owns_services=True;self.run(self.compose+['up','-d','--wait','--wait-timeout','240'],'services-up')
        assert self.env['MYSQL_USER'].replace('_','').isalnum()
        self.sql(f"CREATE DATABASE `{self.database}` CHARACTER SET utf8mb4; GRANT ALL ON `{self.database}`.* TO '{self.env['MYSQL_USER']}'@'%';",'create-database');self.created=True
        self.cli(['--migrate'],'migrate');self.cli(['--migrate'],'migrate-repeat')
        assert self.query('SELECT COUNT(*) FROM _sqlx_migrations WHERE success=1;')=='5'
        self.cli(['--init-admin'],'init-admin',json.dumps({'account':self.root_account,'nickname':'聊天测试管理员','password':self.password}).encode())
        self.server=self.start([self.binary],'api');self.wait('/health/ready')
        admin=Client(self);admin.login(self.root_account,self.password)
        alice=Client(self);alice.register(self.alice_account,self.password,'聊天卖家');alice.login(self.alice_account,self.password);aid=alice.me()['id']
        bob=Client(self);bob.register(self.bob_account,self.password,'聊天买家');bob.login(self.bob_account,self.password);bid=bob.me()['id']
        outsider=Client(self);third='third_'+self.suffix;outsider.register(third,self.password,'无关用户');outsider.login(third,self.password)
        visitor=Client(self);category=visitor.call('/api/v1/goods-categories')['data'][0]['id'];product=alice.publish(category,title='联系卖家测试商品')
        self.record('Five migrations and independent seller/buyer/outsider/admin identities')

        opened=bob.call('/api/v1/conversations','POST',{'goods_id':product['id']})['data'];cid=opened['id'];base='/api/v1/conversations/'+cid
        assert opened['peer']['id']==aid and opened['context_goods']['id']==product['id']
        assert bob.call('/api/v1/conversations','POST',{'goods_id':product['id']})['data']['id']==cid
        second=alice.publish(category,title='同一卖家的其他商品');assert bob.call('/api/v1/conversations','POST',{'goods_id':second['id']})['data']['id']==cid
        alice.call('/api/v1/conversations','POST',{'goods_id':product['id']},422)
        bob.call('/api/v1/conversations','POST',{'goods_id':product['id'],'seller_id':aid},400)
        for client in [outsider,admin]:
            client.call(base,expected=404);client.call(base+'/messages',expected=404)
            client.call(base+'/read','PUT',{'through_sequence':'0'},404)
            client.call(base+'/messages','POST',{'client_message_id':str(uuid.uuid4()),'body':'越权消息'},404)
        self.record('Contact seller derives ownership, reuses one pair conversation and rejects outsiders including administrators')

        client_id=str(uuid.uuid4());first=bob.call(base+'/messages','POST',{'client_message_id':client_id,'body':'第一条真实文字消息'},201)['data']
        repeated=bob.call(base+'/messages','POST',{'client_message_id':client_id,'body':'第一条真实文字消息'})['data'];assert first==repeated
        bob.call(base+'/messages','POST',{'client_message_id':client_id,'body':'不同正文'},409)
        assert alice.call(base)['data']['unread_count']==1 and bob.call(base)['data']['unread_count']==0
        def simultaneous(client):return client.call(base+'/messages','POST',{'client_message_id':str(uuid.uuid4()),'body':'并发双向消息'},201)['data']
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(simultaneous,[alice.clone(),bob.clone()]))
        assert len({m['sequence'] for m in results})==2
        for _ in range(23):bob.call(base+'/messages','POST',{'client_message_id':str(uuid.uuid4()),'body':'分页历史消息'},201)
        history=alice.call(base+'/messages')['data'];assert len(history['items'])==20 and history['has_more']
        earlier=alice.call(base+'/messages?before_sequence='+history['next_before_sequence'])['data'];assert earlier['items'] and int(earlier['items'][-1]['sequence'])<int(history['items'][0]['sequence'])
        after=alice.call(base+'/messages?after_sequence=0&limit=5')['data'];assert len(after['items'])==5 and after['has_more']
        for query in ['?after_sequence=0&before_sequence=3','?after_sequence=-1','?limit=101']:alice.call(base+'/messages'+query,expected=422)
        last=alice.call(base)['data']['last_sequence'];alice.call(base+'/read','PUT',{'through_sequence':last});alice.call(base+'/read','PUT',{'through_sequence':'0'});assert alice.call(base)['data']['last_read_sequence']==last
        alice.call(base+'/read','PUT',{'through_sequence':str(int(last)+1)},422)
        self.record('HTTP persistence, retry deduplication, concurrent ordering, cursor history and monotonic peer-only unread counts')

        next_cli=ROOT/'apps/web/node_modules/next/dist/bin/next';self.web_process=self.start(['node',next_cli,'start','--hostname','127.0.0.1','--port',self.env['WEB_PORT']],'web',cwd=ROOT/'apps/web');self.wait('/health/ready',base=self.web)
        bob_live=Live(self,bob,proxy=True);alice_live=Live(self,alice);outsider_live=Live(self,outsider)
        token=bob.call('/api/v1/ws-tickets','POST')['data']['ticket'];redis_key='byr:ws:'+hashlib.sha256(token.encode()).hexdigest()
        assert 0<int(self.redis('TTL',redis_key))<=30 and token not in self.redis('GET',redis_key)
        once=Live(self,bob,ticket=token);once.close()
        replay=Live(self,bob,ticket=token,authenticate=False);replay.send('authenticate',{'ticket':token});assert replay.until('error')['data']['code']=='AUTH_REQUIRED';replay.close()
        expired=bob.call('/api/v1/ws-tickets','POST')['data']['ticket'];self.redis('PEXPIRE','byr:ws:'+hashlib.sha256(expired.encode()).hexdigest(),1);time.sleep(.02)
        expired_socket=Live(self,bob,authenticate=False);expired_socket.send('authenticate',{'ticket':expired});expired_socket.until('error');expired_socket.close()
        wrong=alice.call('/api/v1/ws-tickets','POST')['data']['ticket'];wrong_socket=Live(self,bob,authenticate=False);wrong_socket.send('authenticate',{'ticket':wrong});wrong_socket.until('error');wrong_socket.close()
        for origin,suffix in [('https://invalid.example',''),(False,''),(True,'?ticket=must-not-be-in-url')]:
            try:Live(self,bob,authenticate=False,origin=origin,url_suffix=suffix);raise AssertionError('Bad handshake accepted')
            except InvalidStatus as error:assert error.response.status_code==403
        try:Live(self,visitor,authenticate=False);raise AssertionError('Anonymous handshake accepted')
        except InvalidStatus as error:assert error.response.status_code==401
        self.record('Real WebSocket works through the web origin; hashed thirty-second single-use/session-bound tickets and exact Origin are enforced')

        mid=str(uuid.uuid4());rid=bob_live.send('message.send',{'conversation_id':cid,'client_message_id':mid,'body':'实时消息 <script>不执行</script>'});ack=bob_live.until('message.ack',lambda f:f['request_id']==rid)
        received=alice_live.until('message.created',lambda f:f['data']['client_message_id']==mid);assert received['data']==ack['data']
        retry=bob.call(base+'/messages','POST',{'client_message_id':mid,'body':'实时消息 <script>不执行</script>'})['data'];assert retry==ack['data']
        rid=bob_live.send('message.send',{'conversation_id':cid,'client_message_id':mid,'body':'实时消息 <script>不执行</script>'});assert bob_live.until('message.ack',lambda f:f['request_id']==rid)['data']==ack['data']
        bad=outsider_live.send('message.send',{'conversation_id':cid,'client_message_id':str(uuid.uuid4()),'body':'越权实时消息'});assert outsider_live.until('error',lambda f:f['request_id']==bad)['data']['code']=='NOT_FOUND'
        rid=bob_live.send('message.send',{'conversation_id':cid,'client_message_id':str(uuid.uuid4()),'body':'邮'*2001});assert bob_live.until('error',lambda f:f['request_id']==rid)['data']['code']=='VALIDATION_FAILED'
        rid=bob_live.send('ping',{});assert bob_live.until('pong',lambda f:f['request_id']==rid)['data']['server_time']
        upper=str(uuid.uuid4()).upper();bob_live.ws.send(json.dumps({'type':'ping','request_id':upper,'data':{}}));assert bob_live.until('pong',lambda f:f['request_id']==upper)
        bob_live.ws.send('{bad json');bob_live.until('error',lambda f:f['request_id'] is None)
        rid=alice_live.send('message.read',{'conversation_id':cid,'through_sequence':received['data']['sequence']});alice_live.until('conversation.read',lambda f:f['request_id']==rid)
        assert alice.call(base)['data']['unread_count']==0
        assert not any(f['type']=='message.created' for f in outsider_live.seen)
        self.record('WS acknowledgement follows persistence; WS/HTTP retries share one record, frames validate and outsiders cannot send or receive private messages')

        alice_live.close();offline=bob.call(base+'/messages','POST',{'client_message_id':str(uuid.uuid4()),'body':'离线后仍可补读'},201)['data'];alice_live=Live(self,alice)
        catchup=alice.call(base+'/messages?after_sequence='+received['data']['sequence'])['data'];assert any(m['id']==offline['id'] for m in catchup['items'])
        self.record('Offline/reconnected clients recover committed messages through sequence-based HTTP catch-up')

        self.fixture(bid,'独立测试通知'+self.suffix)
        notice=bob_live.until('notification.created',lambda f:f['data']['summary']=='独立测试通知'+self.suffix)['data'];nid=notice['id']
        for client in [alice,outsider,admin]:client.call('/api/v1/notifications/'+nid+'/read','PUT',expected=404)
        assert bob.call('/api/v1/notifications?unread_only=true')['data']['total']>=1
        bob.call('/api/v1/notifications/'+nid+'/read','PUT');bob.call('/api/v1/notifications/'+nid+'/read','PUT');assert next(n for n in bob.call('/api/v1/notifications')['data']['items'] if n['id']==nid)['read_at']
        self.fixture(bid,'全部已读之前');bob.call('/api/v1/notifications/read-all','PUT');self.fixture(bid,'全部已读之后')
        unread=bob.call('/api/v1/notifications?unread_only=true')['data'];assert unread['total']==1 and unread['items'][0]['summary']=='全部已读之后'
        self.record('Notification creation/outbox is atomic; private list, single/read-all idempotency and later-unread preservation work')

        board=visitor.call('/api/v1/boards')['data']['items'][0]['id'];post=alice.post(board,title='隐藏后不能泄漏的标题')
        self.fixture(bid,'旧摘要不能泄漏','post',post['id']);latest=bob.call('/api/v1/notifications')['data']['items'][0]
        admin.call('/api/v1/admin/posts/'+post['id']+'/moderation','PATCH',{'action':'hide','version':post['version'],'reason':'通知当前可见性检查'})
        hidden=next(n for n in bob.call('/api/v1/notifications')['data']['items'] if n['id']==latest['id']);assert not hidden['target_available'] and '标题' not in hidden['summary'] and '旧摘要' not in hidden['summary']
        self.fixture(bid,'新旧摘要都不能泄漏','post',post['id']);event=bob_live.until('notification.created',lambda f:not f['data']['target_available']);assert event['data']['summary']=='相关内容当前不可访问'
        admin.call('/api/v1/admin/goods/'+product['id']+'/moderation','PATCH',{'action':'restrict','version':product['version'],'reason':'会话来源权限检查'})
        assert bob.call(base)['data']['context_goods'] is None
        self.record('HTTP and queued notification delivery recheck current targets; hidden sources and conversation product context reveal no stale titles')

        for index,kind in enumerate(['logout','password_changed','password_reset','banned','expired']):self.revoke_check(admin,kind,index)
        self.record('Logout/password change/reset/ban/expiry close the correct old live sessions within five seconds; another login survives current-session logout')

        self.run(self.compose+['stop','redis'],'redis-stop')
        bob.call('/api/v1/ws-tickets','POST',expected=503)
        fallback=bob.call(base+'/messages','POST',{'client_message_id':str(uuid.uuid4()),'body':'Redis不可用仍可普通发送'},201)['data'];assert alice.call(base+'/messages')['data']['items'][-1]['id']==fallback['id']
        self.run(self.compose+['up','-d','--wait'],'redis-ready');self.wait('/health/ready')
        self.record('Redis failure rejects new tickets while HTTP message save/history remain available')

        # These raw clients are no longer used; close them before long browser/fault cases.
        for live in self.sockets:
            try:live.close()
            except Exception:pass

        fixture=self.log_dir/'fixture.png';fixture.write_bytes(png())
        extra={'E2E_CHAT':'1','CHAT_ALICE':self.alice_account,'CHAT_BOB':self.bob_account,'CHAT_THIRD':third,'CHAT_ADMIN':self.root_account,'CHAT_PASSWORD':self.password,'CHAT_SUFFIX':self.suffix,'CHAT_GOODS':second['id'],'CHAT_CONVERSATION':cid,'CHAT_NOTICE':nid,'CHAT_PNG':str(fixture)}
        self.run(['node',ROOT/'apps/web/node_modules/@playwright/test/cli.js','test','tests/chat.spec.mjs'],'browser',cwd=ROOT/'apps/web',extra=extra)
        report=json.loads((ROOT/'.local/logs/dev/browser-results.json').read_text(encoding='utf-8'));assert report['stats']['expected']==4 and report['stats']['unexpected']==0
        (self.log_dir/'browser-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        self.record('Four real browser cases cover contact/live chat, retry and reconnect, notifications/privacy, and database-failure recovery')

        self.verify_push_failure(bob,cid,aid)

        for live in self.sockets:
            try:live.close()
            except Exception:pass
        self.stop(self.server);self.run(self.compose+['restart'],'database-restart');self.run(self.compose+['up','-d','--wait'],'database-ready');self.server=self.start([self.binary],'api-restarted');self.wait('/health/ready')
        assert bob.call(base)['data']['id']==cid and any(m['id']==offline['id'] for m in alice.call(base+'/messages?after_sequence=0&limit=100')['data']['items'])
        assert any(n['id']==nid and n['read_at'] for n in bob.call('/api/v1/notifications')['data']['items'])
        assert self.query('SELECT COUNT(*) FROM messages;')==self.query("SELECT COUNT(DISTINCT CONCAT(conversation_id,':',sender_id,':',client_message_id)) FROM messages;")
        self.record('Service/database restart preserves sessions, message identities/history and notification read state')
        logs='\n'.join(p.read_text(encoding='utf-8',errors='replace') for p in self.log_dir.glob('api*.log'))
        assert self.password not in logs and token not in logs and '实时消息 <script>' not in logs
        self.record('Access logs exclude tested passwords, ticket values and private message content')

def main():
    LOG.mkdir(parents=True,exist_ok=True);RESULT.parent.mkdir(parents=True,exist_ok=True);verification=Chat();status='failed';error=None
    try:verification.execute();status='passed'
    except Exception as exc:error=f'{type(exc).__name__}: {str(exc)}';print(error,file=sys.stderr)
    finally:
        try:verification.cleanup()
        except Exception as exc:status='failed';error='Verification cleanup failed';print(error,file=sys.stderr)
        RESULT.write_text(json.dumps({'stage':'4.6.3','status':status,'checks':verification.checks,'browser_cases':4 if any('Four real browser' in s for s in verification.checks) else 0,'revocation_seconds':verification.revocations,'isolated_database_removed':not verification.created,'development_accounts_modified':False,'server_deployed':False,'error':error},ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if status=='passed' else 1

if __name__ == "__main__":sys.exit(main())

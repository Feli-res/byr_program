"""4.4 integration check. Uses only the dedicated local development services."""
from pathlib import Path
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / '.local/logs/dev'
RESULT = ROOT / 'docs/engineering/runtime-verification.json'

def environment():
    env = os.environ.copy()
    for line in (ROOT/'deploy/.env').read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, value = line.split('=',1);env[key] = value
    password = urllib.parse.quote(env['MYSQL_PASSWORD'], safe='')
    env['DATABASE_URL'] = f"mysql://{env['MYSQL_USER']}:{password}@127.0.0.1:{env['MYSQL_PORT']}/{env['MYSQL_DATABASE']}"
    env['REDIS_URL'] = f"redis://127.0.0.1:{env['REDIS_PORT']}/"
    env['NEXT_TELEMETRY_DISABLED'] = '1'
    if os.name == 'nt' and 'PLAYWRIGHT_CHANNEL' not in env:
        env['PLAYWRIGHT_CHANNEL'] = 'msedge'
    return env

class Verification:
    def __init__(self):
        self.env = environment()
        self.api = self.env['API_INTERNAL_URL']
        self.web = self.env['WEB_ORIGIN']
        self.processes=[];self.logs=[];self.checks=[];self.owns_services=False
        self.compose=['docker','compose','--env-file',str(ROOT/'deploy/.env'),'-f',str(ROOT/'deploy/compose.dev.yaml')]
        target = Path(self.env.get('CARGO_TARGET_DIR', ROOT/'target'))
        self.binary = target/'debug'/('youzhihui-api.exe' if os.name=='nt' else 'youzhihui-api')

    def run(self, args, name, cwd=ROOT, extra=None):
        env=self.env.copy();env.update(extra or {})
        with (LOG/(name+'.log')).open('wb') as log:
            result=subprocess.run([str(a) for a in args],cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise RuntimeError(f'{name} failed; see {(LOG/(name+chr(46)+"log")).relative_to(ROOT).as_posix()}')

    def start(self, args, name, cwd=ROOT, extra=None):
        env=self.env.copy();env.update(extra or {})
        log=(LOG/(name+'.log')).open('wb');self.logs.append(log)
        process=subprocess.Popen([str(a) for a in args],cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.processes.append(process);return process

    def stop(self, process):
        if process.poll() is not None:return
        if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        else:os.killpg(process.pid,signal.SIGTERM)
        process.wait(timeout=15)

    def request(self, path, body=None, expected=200, headers=None, base=None, raw=None):
        data=json.dumps(body,ensure_ascii=False).encode('utf-8') if body is not None else raw
        head={'Content-Type':'application/json'} if data is not None else {}
        head.update(headers or {})
        req=urllib.request.Request((base or self.api)+path,data=data,headers=head)
        try:
            with urllib.request.urlopen(req,timeout=12) as response:status=response.status;payload=json.load(response)
        except urllib.error.HTTPError as error:status=error.code;payload=json.load(error)
        assert status==expected,(path,status,expected)
        assert uuid.UUID(payload.get('meta',{}).get('request_id')),(path,'missing request id')
        return payload

    def wait(self, path, base=None):
        last=None
        for _ in range(60):
            try:return self.request(path,base=base)
            except (Exception,) as error:last=error;time.sleep(.5)
        raise RuntimeError('Service not ready: '+str(last))

    def record(self, text):
        self.checks.append(text);print('PASS '+text,flush=True)

    def browser(self, failure=False):
        cli=ROOT/'apps/web/node_modules/@playwright/test/cli.js'
        self.run(['node',cli,'test'],'browser-failure' if failure else 'browser-success',cwd=ROOT/'apps/web',extra={'E2E_FAILURE_MODE':'1' if failure else '0'})
        source=LOG/'browser-results.json'
        report=json.loads(source.read_text(encoding='utf-8'))
        assert report['stats']['expected']==1 and report['stats']['unexpected']==0
        (LOG/('browser-failure-results.json' if failure else 'browser-success-results.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

    def execute(self, skip_browser=False):
        for address in [self.api,self.web]:
            parsed=urllib.parse.urlparse(address)
            with socket.socket() as s:
                assert s.connect_ex((parsed.hostname,parsed.port))!=0,'A service is already using a development port. Stop it first.'
        self.owns_services=True
        self.run(self.compose+['up','-d','--wait','--wait-timeout','240'],'services-up')
        self.run([self.binary,'--migrate'],'migrate-first')
        self.run([self.binary,'--migrate'],'migrate-repeat')
        self.record('Versioned migrations and repeated migration execution')
        api=self.start([self.binary],'api-verification')
        self.wait('/health/ready');self.request('/health/live')
        self.record('Liveness and MySQL / Redis readiness')
        marker='4.4 persistence '+uuid.uuid4().hex
        saved=self.request('/api/dev/records',{'body':marker},expected=201)['data']
        assert isinstance(saved['id'],str)
        assert any(r['id']==saved['id'] and r['body']==marker for r in self.request('/api/dev/records')['data']['items'])
        self.record('Real HTTP write and read through MySQL')
        for body,status in [({'body':'   '},422),({'body':'邮'*501},422),({'body':'test','role':'admin'},400)]:self.request('/api/dev/records',body,expected=status)
        self.request('/api/dev/records',{'body':'test'},expected=403,headers={'Origin':'https://unrelated.example'})
        self.request('/api/dev/records',expected=415,raw=b'body=hello',headers={'Content-Type':'application/x-www-form-urlencoded'})
        self.request('/api/dev/records',expected=400,raw=b'{bad json')
        self.record('Validation boundaries, malformed JSON, unknown fields and origin rejection')
        self.run(self.compose+['exec','-T','mysql','sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" -D "$MYSQL_DATABASE" --batch --skip-column-names -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE(); SELECT COUNT(*) FROM _sqlx_migrations WHERE success=1;"'],'schema-count')
        counts=(LOG/'schema-count.log').read_text().split()
        assert counts==['35','5'],counts
        self.record('32 designed tables, development records, account throttling and migration history in MySQL')
        self.run(self.compose+['stop','redis'],'redis-stop')
        self.request('/health/live');self.request('/health/ready',expected=503)
        self.record('Redis failure changes readiness without killing liveness')
        self.run(self.compose+['up','-d','--wait'],'redis-recover');self.wait('/health/ready')
        cli=ROOT/'apps/web/node_modules/next/dist/bin/next'
        web=self.start(['node',cli,'start','--hostname','127.0.0.1','--port',self.env['WEB_PORT']],'web-verification',cwd=ROOT/'apps/web')
        self.wait('/health/ready',base=self.web)
        if not skip_browser:
            self.browser();self.record('Real browser save, refresh, escaped text, narrow screen and console checks')
        self.run(self.compose+['stop','mysql'],'mysql-stop')
        self.request('/health/live');self.request('/health/ready',expected=503)
        self.request('/api/dev/records',{'body':'must not report success'},expected=503)
        self.record('Database outage returns failure with liveness still available')
        if not skip_browser:
            self.browser(True);self.record('Browser retains input and shows no false success during real database outage')
        self.run(self.compose+['up','-d','--wait'],'database-recover');self.wait('/health/ready')
        self.stop(web);self.stop(api)
        self.run(self.compose+['restart'],'database-restart');self.run(self.compose+['up','-d','--wait'],'restart-wait')
        self.start([self.binary],'api-after-restart');self.wait('/health/ready')
        self.start(['node',cli,'start','--hostname','127.0.0.1','--port',self.env['WEB_PORT']],'web-after-restart',cwd=ROOT/'apps/web')
        self.wait('/health/ready',base=self.web)
        assert any(r['id']==saved['id'] and r['body']==marker for r in self.request('/api/dev/records',base=self.web)['data']['items'])
        self.record('Readback through restarted web and API after MySQL / Redis restart')
        self.stop(self.processes[-2]);self.stop(self.processes[-1])
        self.start([self.binary],'api-disabled-tools',extra={'DEV_TOOLS_ENABLED':'false'})
        self.wait('/health/ready');self.request('/api/dev/records',expected=404)
        self.record('Development write and read routes disappear when disabled')

    def cleanup(self):
        for process in reversed(self.processes):self.stop(process)
        for log in self.logs:log.close()
        if self.owns_services:self.run(self.compose+['stop'],'services-stop')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--skip-browser',action='store_true');args=parser.parse_args()
    LOG.mkdir(parents=True,exist_ok=True);RESULT.parent.mkdir(parents=True,exist_ok=True)
    verifier=Verification();status='failed';error=None
    try:verifier.execute(args.skip_browser);status='passed'
    except Exception as exc:error=str(exc);print(error,file=sys.stderr)
    finally:
        try:verifier.cleanup()
        except Exception as exc:status='failed';error=str(exc)
        report={'stage':'4.4','status':status,'checks':verifier.checks,'browser_tested':not args.skip_browser,'second_computer_tested':False,'application_acceptance_cases_run':False,'development_volumes_retained':True,'error':error}
        RESULT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if status=='passed' else 1

if __name__=='__main__':sys.exit(main())

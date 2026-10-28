"""Runtime scenarios; shared setup lives in test_support."""
from test_support import ROOT
import argparse
import json
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from test_support.runtime import environment
from test_support.runtime import RuntimeVerification
LOG=ROOT/".local/logs/dev"
RESULT=ROOT/"docs/engineering/runtime-verification.json"

class Verification(RuntimeVerification):
    def __init__(self):
        super().__init__(log_dir=LOG)

    def browser(self, failure=False):
        cli=ROOT/'apps/web/node_modules/@playwright/test/cli.js'
        self.run(['node',cli,'test'],'browser-failure' if failure else 'browser-success',cwd=ROOT/'apps/web',extra={'E2E_FAILURE_MODE':'1' if failure else '0'})
        source=self.log_dir/'browser-results.json'
        report=json.loads(source.read_text(encoding='utf-8'))
        assert report['stats']['expected']==1 and report['stats']['unexpected']==0
        (self.log_dir/('browser-failure-results.json' if failure else 'browser-success-results.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

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
        counts=(self.log_dir/'schema-count.log').read_text().split()
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

if __name__ == "__main__":sys.exit(main())

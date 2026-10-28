from pathlib import Path
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from . import ROOT

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

class RuntimeVerification:
    def __init__(self, log_dir=None):
        self.log_dir = Path(log_dir or ROOT / ".local/logs/dev")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.env = environment()
        self.api = self.env['API_INTERNAL_URL']
        self.web = self.env['WEB_ORIGIN']
        self.processes=[];self.logs=[];self.checks=[];self.owns_services=False
        self.compose=['docker','compose','--env-file',str(ROOT/'deploy/.env'),'-f',str(ROOT/'deploy/compose.dev.yaml')]
        target = Path(self.env.get('CARGO_TARGET_DIR', ROOT/'target'))
        self.binary = target/'debug'/('youzhihui-api.exe' if os.name=='nt' else 'youzhihui-api')

    def run(self, args, name, cwd=ROOT, extra=None):
        env=self.env.copy();env.update(extra or {})
        with (self.log_dir/(name+'.log')).open('wb') as log:
            result=subprocess.run([str(a) for a in args],cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise RuntimeError(f'{name} failed; see {(self.log_dir/(name+chr(46)+"log")).relative_to(ROOT).as_posix()}')

    def start(self, args, name, cwd=ROOT, extra=None):
        env=self.env.copy();env.update(extra or {})
        log=(self.log_dir/(name+'.log')).open('wb');self.logs.append(log)
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

    def cleanup(self):
        for process in reversed(self.processes):self.stop(process)
        for log in self.logs:log.close()
        if self.owns_services:self.run(self.compose+['stop'],'services-stop')

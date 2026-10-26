"""Portable preparation and foreground commands for Linux/macOS/WSL."""
from pathlib import Path
import os
import secrets
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
from verify_runtime import environment

def prepare_environment():
    path=ROOT/'deploy/.env'
    if not path.exists():
        template=(ROOT/'deploy/.env.example').read_text(encoding='utf-8')
        template=template.replace('CHANGE_ME_RANDOM_USER_PASSWORD',secrets.token_hex(32)).replace('CHANGE_ME_RANDOM_ROOT_PASSWORD',secrets.token_hex(32)).replace('CHANGE_ME_RANDOM_AUTH_SECRET',secrets.token_hex(32))
        with path.open('x',encoding='utf-8') as stream:stream.write(template)
        if os.name!='nt':path.chmod(0o600)

    existing=path.read_text(encoding='utf-8-sig')
    if 'AUTH_SECRET=' not in existing:
        with path.open('a',encoding='utf-8') as stream:stream.write('\nAUTH_SECRET='+secrets.token_hex(32)+'\nCOOKIE_SECURE=false\nUPLOAD_ROOT=.local/uploads\n')

def main():
    command=sys.argv[1] if len(sys.argv)>1 else 'help'
    if command=='init-env':prepare_environment();print('Created deploy/.env if missing.');return
    env=environment()
    compose=['docker','compose','--env-file',str(ROOT/'deploy/.env'),'-f',str(ROOT/'deploy/compose.dev.yaml')]
    npm='npm.cmd' if os.name=='nt' else 'npm'
    actions={
        'services':(compose+['up','-d','--wait','--wait-timeout','240'],ROOT),
        'init-admin':(['cargo','run','--locked','-p','youzhihui-api','--','--init-admin'],ROOT),
        'migrate':(['cargo','run','--locked','-p','youzhihui-api','--','--migrate'],ROOT),
        'api':(['cargo','run','--locked','-p','youzhihui-api'],ROOT),
        'web':(['node',str(ROOT/'apps/web/node_modules/next/dist/bin/next'),'dev','--hostname','127.0.0.1','--port',env['WEB_PORT']],ROOT/'apps/web'),
        'build-web':([npm,'run','build'],ROOT/'apps/web'),
        'stop-services':(compose+['stop'],ROOT),
    }
    if command not in actions:raise SystemExit('Commands: init-env, services, migrate, init-admin, api, web, build-web, stop-services')
    args,cwd=actions[command]
    raise SystemExit(subprocess.call(args,cwd=cwd,env=env))

if __name__=='__main__':main()

import subprocess
import uuid
import re
import secrets
from . import ROOT
from .runtime import RuntimeVerification

class AccountVerification(RuntimeVerification):
    def __init__(self, log_dir=None):
        super().__init__(log_dir=log_dir);self.database='byr_accounts_'+uuid.uuid4().hex[:16];self.created=False
        self.env['DATABASE_URL']=self.env['DATABASE_URL'].rsplit('/',1)[0]+'/'+self.database
        self.env['UPLOAD_ROOT']=str(ROOT/'.local/account-tests'/self.database)
        self.env['RUST_self.log_dir']='info,sqlx::query=error'
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
        with (self.log_dir/(name+'.log')).open('wb') as log:
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

    def cleanup(self):
        for process in reversed(self.processes):self.stop(process)
        for log in self.logs:log.close()
        if self.created:
            assert re.fullmatch(r'byr_accounts_[a-f0-9]{16}',self.database)
            self.run(self.compose+['up','-d','--wait'],'cleanup-services-ready')
            self.sql(f"REVOKE ALL PRIVILEGES ON `{self.database}`.* FROM '{self.env['MYSQL_USER']}'@'%'; DROP DATABASE `{self.database}`;",'drop-own-test-database');self.created=False
        if self.owns_services:self.run(self.compose+['stop'],'services-stop')

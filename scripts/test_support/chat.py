import json
import subprocess
from . import ROOT
from .accounts import AccountVerification

class ChatVerification(AccountVerification):
    def __init__(self, log_dir=None):
        super().__init__(log_dir=log_dir);self.sockets=[];self.env['CHAT_TEST_FIXTURES']='1';self.env['UPLOAD_ROOT']=str(ROOT/'.local/chat-tests'/self.database);self.revocations={}

    def fixture(self,recipient,summary,target_type='none',target=None):
        self.cli(['--seed-chat-notification'],'seed-notification',json.dumps({'recipient_id':recipient,'summary':summary,'target_type':target_type,'target_id':target}).encode())

    def redis(self,*args):
        r=subprocess.run(self.compose+['exec','-T','redis','redis-cli','--raw',*map(str,args)],cwd=ROOT,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
        assert r.returncode==0;return r.stdout.decode().strip()

    def cleanup(self):
        for live in self.sockets:
            try:live.close()
            except Exception:pass
        super().cleanup()

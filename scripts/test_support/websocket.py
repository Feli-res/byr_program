import json
import time
import uuid
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from websockets.sync.client import connect
from . import ROOT
from .http import CONTRACT

WS=json.loads((ROOT/"docs/design/ws-events.json").read_text(encoding="utf-8-sig").replace("openapi.json#/components/","#/components/"))
WS["components"]=CONTRACT["components"]

class Live:
    def __init__(self,v,client,ticket=None,authenticate=True,proxy=False,origin=True,url_suffix=''):
        self.v=v;self.seen=[]
        address=v.web if proxy else v.api;address=address.replace('localhost','127.0.0.1').replace('http:','ws:')+'/api/v1/ws'+url_suffix
        cookie='; '.join(c.name+'='+c.value for c in client.jar)
        self.ws=connect(address,origin=v.web if origin is True else origin or None,additional_headers={'Cookie':cookie},open_timeout=8,close_timeout=1,proxy=None)
        v.sockets.append(self)
        if authenticate:
            ticket=ticket or client.call('/api/v1/ws-tickets','POST')['data']['ticket'];self.send('authenticate',{'ticket':ticket});self.until('ready')
    def send(self,kind,data):
        rid=str(uuid.uuid4());self.ws.send(json.dumps({'type':kind,'request_id':rid,'data':data}));return rid
    def receive(self,timeout=5):
        value=json.loads(self.ws.recv(timeout=timeout));name='server.'+value['type']
        assert name in WS['$defs'],'Unknown server event'
        try:Draft202012Validator({**WS,'$ref':'#/$defs/'+name},format_checker=FormatChecker()).validate(value)
        except ValidationError as error:raise AssertionError('WebSocket schema mismatch at '+error.json_path) from None
        self.seen.append(value);return value
    def until(self,kind,predicate=lambda value:True,timeout=6):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            value=self.receive(end-time.monotonic())
            if value['type']==kind and predicate(value):return value
        raise AssertionError('Expected WebSocket event missing: '+kind)
    def close(self):self.ws.close()

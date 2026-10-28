import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import copy
import http.cookiejar
import http.client
import re
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from . import ROOT
from .fixtures import png

CONTRACT=json.loads((ROOT/"docs/design/openapi.json").read_text(encoding="utf-8-sig"))

class AccountClient:
    def __init__(self,verification):
        self.v=verification;self.jar=http.cookiejar.CookieJar();self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
    def clone(self):
        other=type(self)(self.v)
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

class ForumClient(AccountClient):
    def upload(self,content,purpose='post_image',name='image.png',mime='image/png',expected=201):
        boundary='forum'+uuid.uuid4().hex
        raw=(f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\n{purpose}\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n').encode()+content+f'\r\n--{boundary}--\r\n'.encode()
        return self.call('/api/v1/files','POST',expected=expected,raw=raw,headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
    def post(self,board,title='接口测试帖子',body='真实保存的正文',images=None,pdfs=None,expected=201):
        result=self.call('/api/v1/posts','POST',{'board_id':board,'title':title,'body_markdown':body,'image_file_ids':images or [],'pdf_file_ids':pdfs or []},expected)
        return result['data'] if expected==201 else result

class GoodsClient(ForumClient):
    def publish(self,category,images=None,expected=201,**overrides):
        if images is None:images=[self.upload(png(),'goods_image')['data']['id']]
        data={'category_id':category,'campus_code':'shahe','title':'校园测试商品','description':'商品真实描述','condition_code':'good','price_cents':1250,'location_text':'教学楼门口','image_file_ids':images,'brand':None,'model':None,'purpose':None,'attributes':{}}
        data.update(overrides);reply=self.call('/api/v1/goods','POST',data,expected)
        return reply['data'] if expected==201 else reply

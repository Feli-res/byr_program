"""Generate the HTTP design contract and its readable index. No external packages."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
S = {}
def ref(name): return {'$ref': '#/components/schemas/' + name}
def obj(fields, required=()): return {'type':'object','properties':fields,'required':list(required),'additionalProperties':False}
def string(maximum=None, minimum=None, **extra):
    result={'type':'string',**extra}
    if maximum is not None: result['maxLength']=maximum
    if minimum is not None: result['minLength']=minimum
    return result
def enum(*values): return {'type':'string','enum':list(values)}
def integer(low=0, high=None):
    return {'type':'integer','minimum':low,**({'maximum':high} if high is not None else {})}
def array(item,maximum=None): return {'type':'array','items':item,**({'maxItems':maximum} if maximum else {})}
def nullable(schema): return {'anyOf':[schema,{'type':'null'}]}
ID=string(20,1,pattern=r'^[1-9][0-9]{0,19}$')
SEQ=string(20,1,pattern=r'^[0-9]{1,20}$')
DATE=string(format='date-time')
BOOL={'type':'boolean'}
PRICE=integer(0,9999999)
VERSION=integer(1,4294967295)
STATE=enum('on_sale','reserved','sold','off_shelf')
CONDITION=enum('new','like_new','good','fair')
CAMPUS=enum('shahe','xitucheng','other')
PASSWORD=string(64,8,format='password',writeOnly=True)
TEXT=string(2000,1)

S['Error']=obj({'error':obj({'code':string(64),'message':string(300),'fields':array(obj({'path':string(100),'message':string(300)},['path','message'])),'retryable':BOOL},['code','message','fields','retryable']),'meta':obj({'request_id':string(format='uuid')},['request_id'])},['error','meta'])
S['Ok']=obj({'ok':{'const':True}},['ok'])
S['Dictionary']=obj({'id':ID,'code':string(30),'name':string(30),'enabled':BOOL},['id','code','name','enabled'])
S['Campus']=obj({'code':CAMPUS,'name':string(20),'enabled':BOOL},['code','name','enabled'])
S['Board']=obj({'id':ID,'name':string(30),'description':string(300),'enabled':BOOL,'version':VERSION},['id','name','description','enabled','version'])
S['File']=obj({'id':ID,'purpose':enum('avatar','post_image','post_pdf','goods_image'),'mime_type':string(80),'size_bytes':integer(1,10485760),'name':string(255),'url':string(),'state':enum('staged','attached'),'expires_at':nullable(DATE)},['id','purpose','mime_type','size_bytes','name','url','state','expires_at'])
S['PublicUser']=obj({'id':ID,'nickname':string(20,2),'bio':string(300),'avatar_url':nullable(string())},['id','nickname','bio','avatar_url'])
S['Me']=obj({**S['PublicUser']['properties'],'account':string(24,4),'role':enum('user','moderator','admin'),'board_ids':array(ID),'version':VERSION,'used_file_bytes':integer(0,209715200),'file_quota_bytes':{'const':209715200},'session_expires_at':DATE},['id','nickname','bio','avatar_url','account','role','board_ids','version','used_file_bytes','file_quota_bytes','session_expires_at'])
S['AdminUser']=obj({'id':ID,'account':string(24,4),'nickname':string(20),'role':enum('user','moderator','admin'),'status':enum('active','banned'),'password_reset_required':BOOL,'board_ids':array(ID),'version':VERSION},['id','account','nickname','role','status','password_reset_required','board_ids','version'])
S['Attributes']=obj({'stylus_support':nullable(BOOL),'storage_gb':nullable(integer(1,100000))})
S['Conditions']=obj({'schema_version':{'const':1},'min_price_cents':nullable(PRICE),'max_price_cents':nullable(PRICE),'campus_code':nullable(CAMPUS),'category_id':nullable(ID),'brand':nullable(string(100,1)),'model':nullable(string(100,1)),'min_condition':nullable(CONDITION),'required_attributes':ref('Attributes'),'purpose':nullable(string(100,1))},['schema_version','min_price_cents','max_price_cents','campus_code','category_id','brand','model','min_condition','required_attributes','purpose'])
goods_fields={'id':ID,'seller':ref('PublicUser'),'category_id':ID,'campus_code':CAMPUS,'title':string(100,2),'description':string(5000,1),'brand':nullable(string(100)),'model':nullable(string(100)),'purpose':nullable(string(100)),'condition_code':CONDITION,'price_cents':PRICE,'location_text':string(100),'attributes':ref('Attributes'),'state':STATE,'images':array(ref('File'),6),'version':VERSION,'created_at':DATE,'updated_at':DATE,'can_contact':BOOL}
S['Goods']=obj(goods_fields,goods_fields.keys())
S['GoodsWrite']=obj({k:v for k,v in goods_fields.items() if k in ['category_id','campus_code','title','description','brand','model','purpose','condition_code','price_cents','location_text','attributes']} | {'image_file_ids':{'type':'array','items':ID,'minItems':1,'maxItems':6,'uniqueItems':True}},['category_id','campus_code','title','description','condition_code','price_cents','location_text','image_file_ids'])
S['GoodsUpdate']=obj({**S['GoodsWrite']['properties'],'version':VERSION},['version']); S['GoodsUpdate']['minProperties']=2
post_fields={'id':ID,'board_id':ID,'title':string(100,2),'body_markdown':string(20000,1),'author':ref('PublicUser'),'pinned':BOOL,'version':VERSION,'image_files':array(ref('File'),9),'pdf_files':array(ref('File'),2),'like_count':integer(),'comment_count':integer(),'liked_by_me':BOOL,'saved_by_me':BOOL,'created_at':DATE,'updated_at':DATE}
S['Post']=obj(post_fields,post_fields.keys())
S['PostWrite']=obj({'board_id':ID,'title':string(100,2),'body_markdown':string(20000,1),'image_file_ids':{'type':'array','items':ID,'maxItems':9,'uniqueItems':True},'pdf_file_ids':{'type':'array','items':ID,'maxItems':2,'uniqueItems':True}},['board_id','title','body_markdown'])
S['PostUpdate']=obj({**S['PostWrite']['properties'],'version':VERSION},['version']); S['PostUpdate']['minProperties']=2
S['Comment']=obj({'id':ID,'post_id':ID,'parent_id':nullable(ID),'author':nullable(ref('PublicUser')),'body':nullable(TEXT),'state':enum('public','hidden','deleted'),'created_at':DATE},['id','post_id','parent_id','author','body','state','created_at'])
S['Message']=obj({'id':ID,'conversation_id':ID,'sequence':SEQ,'sender_id':ID,'client_message_id':string(format='uuid'),'body':TEXT,'created_at':DATE},['id','conversation_id','sequence','sender_id','client_message_id','body','created_at'])
S['MessageWrite']=obj({'client_message_id':string(format='uuid'),'body':TEXT},['client_message_id','body'])
S['Conversation']=obj({'id':ID,'peer':ref('PublicUser'),'last_message':nullable(ref('Message')),'last_sequence':SEQ,'last_read_sequence':SEQ,'unread_count':integer(),'context_goods':nullable(ref('Goods')),'updated_at':DATE},['id','peer','last_message','last_sequence','last_read_sequence','unread_count','context_goods','updated_at'])
S['MessagePage']=obj({'items':array(ref('Message'),100),'next_after_sequence':SEQ,'next_before_sequence':nullable(SEQ),'has_more':BOOL},['items','next_after_sequence','next_before_sequence','has_more'])
S['Notification']=obj({'id':ID,'kind':enum('goods_match','report_result','system'),'title':string(100),'summary':string(300),'target_type':enum('goods','post','report','announcement','none'),'target_id':nullable(ID),'target_available':BOOL,'target_state':nullable(string(30)),'read_at':nullable(DATE),'created_at':DATE},['id','kind','title','summary','target_type','target_id','target_available','target_state','read_at','created_at'])
S['Subscription']=obj({'id':ID,'name':string(100,1),'original_query':nullable(string(1000)),'conditions':ref('Conditions'),'interval_minutes':integer(5,1440),'state':enum('active','paused','error','deleted'),'config_version':VERSION,'last_checked_at':nullable(DATE),'next_due_at':nullable(DATE),'last_error_code':nullable(string(64)),'match_count':integer(),'created_at':DATE},['id','name','original_query','conditions','interval_minutes','state','config_version','last_checked_at','next_due_at','last_error_code','match_count','created_at'])
S['SubscriptionWrite']=obj({'name':string(100,1),'original_query':nullable(string(1000)),'conditions':ref('Conditions'),'interval_minutes':integer(5,1440),'confirmed':{'const':True}},['name','conditions','interval_minutes','confirmed'])
S['SubscriptionUpdate']=obj({'name':string(100,1),'original_query':nullable(string(1000)),'conditions':ref('Conditions'),'interval_minutes':integer(5,1440),'version':VERSION,'confirmed':{'const':True},'resume_after_save':BOOL},['version','conditions','interval_minutes','name','confirmed','resume_after_save'])
S['Run']=obj({'id':ID,'state':enum('running','succeeded','retry_wait','failed','cancelled'),'attempt_no':integer(0,3),'started_at':DATE,'finished_at':nullable(DATE),'error_code':nullable(string(64))},['id','state','attempt_no','started_at','finished_at','error_code'])
S['MatchResult']=obj({'goods':ref('Goods'),'matched_facts':array(string(200)),'rank_score':{'type':'number'},'reason':string(500)},['goods','matched_facts','rank_score','reason'])
S['MatchHistory']=obj({'id':ID,'goods_id':ID,'goods':nullable(ref('Goods')),'target_available':BOOL,'created_at':DATE},['id','goods_id','goods','target_available','created_at'])
S['Report']=obj({'id':ID,'target_type':enum('post','comment','goods','message'),'target_id':ID,'target_title':nullable(string(100)),'reporter_nickname':string(20,2),'reason':string(1000,1),'state':enum('pending','resolved','dismissed'),'resolution':nullable(string(1000)),'version':VERSION,'created_at':DATE,'resolved_at':nullable(DATE)},['id','target_type','target_id','reason','state','resolution','version','created_at','resolved_at'])
S['ReportCreated']=obj({'id':ID,'already_exists':BOOL},['id','already_exists'])
S['ReportDecision']=obj({'state':enum('resolved','dismissed'),'hidden':BOOL,'restricted':BOOL},['state','hidden','restricted'])
S['AdminReport']=obj({**S['Report']['properties'],'reporter':obj({'id':ID,'nickname':string(20,2)},['id','nickname']),'snapshot':{'type':'object'},'current':nullable({'type':'object'}),'ai':obj({'state':string(20),'result':nullable({'type':'object'}),'stale':BOOL},['state','result','stale'])},[*S['Report']['required'],'reporter','snapshot','current','ai'])
S['Announcement']=obj({'id':ID,'title':string(100,2),'body_markdown':string(20000,1),'published_at':nullable(DATE),'created_at':DATE,'updated_at':DATE},['id','title','body_markdown','published_at','created_at','updated_at'])
S['AnnouncementSummary']=obj({'id':ID,'title':string(100,2),'excerpt':string(300),'published_at':nullable(DATE),'created_at':DATE},['id','title','excerpt','published_at','created_at'])
S['AdminAnnouncement']=obj({'id':ID,'title':string(100,2),'excerpt':string(300),'state':enum('draft','published','retracted'),'version':VERSION,'created_by':string(20,2),'published_at':nullable(DATE),'created_at':DATE,'updated_at':DATE},['id','title','excerpt','state','version','created_by','published_at','created_at','updated_at'])
S['AdminAnnouncementDetail']=obj({'id':ID,'title':string(100,2),'body_markdown':string(20000,1),'state':enum('draft','published','retracted'),'version':VERSION,'created_by':string(20,2),'published_at':nullable(DATE),'created_at':DATE,'updated_at':DATE},['id','title','body_markdown','state','version','created_by','published_at','created_at','updated_at'])
S['AdminBoard']=obj({**S['Board']['properties'],'post_count':integer()},[*S['Board']['required'],'post_count'])
S['AdminTaskMeta']=obj({'id':ID,'owner_label':string(30),'state':enum('active','paused','error','deleted'),'interval_minutes':integer(5,1440),'last_checked_at':nullable(DATE),'next_due_at':nullable(DATE),'last_error_code':nullable(string(64))},['id','owner_label','state','interval_minutes','last_checked_at','next_due_at','last_error_code'])
S['Audit']=obj({'id':ID,'actor':obj({'id':ID,'nickname':string(20,2)},['id','nickname']),'action':string(64),'target_type':string(40),'target_id':nullable(ID),'reason':string(1000),'changes':{'type':'object'},'created_at':DATE},['id','actor','action','target_type','target_id','reason','changes','created_at'])
S['SearchHit']=obj({'kind':enum('post','goods'),'id':ID,'title':string(100),'excerpt':string(300),'price_cents':nullable(PRICE),'campus_code':nullable(CAMPUS),'reason':string(500),'rank_score':{'type':'number'},'updated_at':DATE},['kind','id','title','excerpt','price_cents','campus_code','reason','rank_score','updated_at'])
S['SearchPage']=obj({'items':array(ref('SearchHit'),100),'page':integer(1),'page_size':integer(1,100),'total':integer(),'mode_used':enum('keyword','semantic'),'degraded':BOOL},['items','page','page_size','total','mode_used','degraded'])
S['ParseResult']=obj({'proposed_conditions':ref('Conditions'),'missing_fields':array(string(100)),'warnings':array(string(300)),'model_id':string(100),'needs_confirmation':{'const':True}},['proposed_conditions','missing_fields','warnings','model_id','needs_confirmation'])
S['Quota']=obj({'used_bytes':integer(0,209715200),'quota_bytes':{'const':209715200}},['used_bytes','quota_bytes'])
S['Health']=obj({'status':enum('alive','ready','not_ready'),'database':enum('ok','unavailable','not_checked'),'redis':enum('ok','unavailable','not_checked')},['status','database','redis'])
S['SessionResult']=obj({'user':ref('Me'),'expires_at':DATE},['user','expires_at'])
S['Csrf']=obj({'csrf_token':string(200,32),'expires_at':DATE},['csrf_token','expires_at'])
S['WsTicket']=obj({'ticket':string(200,32),'expires_at':DATE},['ticket','expires_at'])
S['ResetCredential']=obj({'credential':string(200,32),'expires_at':DATE,'user_id':ID},['credential','expires_at','user_id'])
def paged(name):
    key=name+'Page'
    S[key]=obj({'items':array(ref(name),100),'page':integer(1),'page_size':integer(1,100),'total':integer()},['items','page','page_size','total'])
    return key
for name in ['Board','Goods','Post','Comment','Conversation','Notification','Subscription','Run','MatchResult','MatchHistory','Report','AdminReport','Announcement','AdminTaskMeta','AdminUser','Audit','File']: paged(name)
for name in ['AnnouncementSummary','AdminAnnouncement','AdminBoard']: paged(name)
def envelope(name): return obj({'data':ref(name),'meta':obj({'request_id':string(format='uuid')},['request_id'])},['data','meta'])

PATHS={}; rows=[]
PAGE_PARAMS=[{'name':'page','in':'query','schema':{'type':'integer','minimum':1,'default':1}},{'name':'page_size','in':'query','schema':{'type':'integer','minimum':1,'maximum':100,'default':20}}]
def param(name,schema,description=''):
    return {'name':name,'in':'query','schema':schema,'description':description}
def api(method,path,op,title,permission,request=None,response='Ok',checks='',status=200,params=(),paged_list=False,group=''):
    parameters=[{'name':name,'in':'path','required':True,'schema':ID} for name in re.findall(r'\{([^}]+)\}',path)]
    parameters+=list(params)+(PAGE_PARAMS if paged_list else [])
    if method in ['post','put','patch','delete']:
        parameters.append({'name':'X-CSRF-Token','in':'header','required':True,'schema':string(200,32),'description':'与有效 byr_csrf Cookie 一致，签名绑定当前会话或匿名随机量。'})
    responses={str(status):{'description':'成功；数据定义见对应 schema。','content':{'application/json':{'schema':envelope(response)}}},'default':{'description':'失败；HTTP 与业务错误码见 03 接口说明。','content':{'application/json':{'schema':ref('Error')}}}}
    spec={'operationId':op,'summary':title,'tags':[group or permission],'security':[] if permission in ['public','anonymous'] else [{'sessionCookie':[]}],'parameters':parameters,'responses':responses,'x-permission':permission,'x-server-checks':checks}
    if request: spec['requestBody']={'required':True,'content':{'application/json':{'schema':request if isinstance(request,dict) else ref(request)}}}
    PATHS.setdefault('/api/v1'+path,{})[method]=spec
    rows.append((op,method.upper(),'/api/v1'+path,title,permission,checks))

account=string(128,1,pattern=r'^\s*[A-Za-z][A-Za-z0-9_]{3,23}\s*$')
api('get','/csrf','getCsrf','获取请求保护凭据','public',response='Csrf',checks='设置签名 CSRF Cookie；禁止缓存；登录或会话变化后重新获取。',group='账户')
api('post','/auth/register','register','自主注册','anonymous',obj({'account':account,'nickname':string(20,2),'password':PASSWORD},['account','nickname','password']),response='PublicUser',status=201,checks='账号去首尾空白并小写后唯一；角色固定 user；密码不去空白，Argon2id；不自动登录。',group='账户')
api('post','/auth/login','login','登录','anonymous',obj({'account':account,'password':PASSWORD},['account','password']),response='SessionResult',checks='按账号或 IP 统计 15 分钟失败数，5 次后限制 15 分钟；封禁与强制重置不能获得会话；7 天绝对到期。',group='账户')
api('post','/auth/logout','logout','退出当前会话','member',checks='撤销数据库会话，清除 Cookie，并关闭该会话的实时连接。',group='账户')
api('get','/me','getMe','获取本人资料','member',response='Me',group='账户')
api('patch','/me','updateMe','修改本人资料','member',obj({'nickname':string(20,2),'bio':string(300),'avatar_file_id':nullable(ID),'version':VERSION},['version']),response='Me',checks='只能改本人资料；头像必须本人已验证 avatar 文件；配额、版本检查。',group='账户')
api('post','/me/password','changePassword','修改本人密码','member',obj({'current_password':PASSWORD,'new_password':PASSWORD},['current_password','new_password']),checks='核对旧密码；写新哈希并撤销全部会话，不返回或记录密码。',group='账户')
api('post','/auth/reset-password','completePasswordReset','使用一次性凭据改密','anonymous',obj({'credential':string(200,32),'new_password':PASSWORD},['credential','new_password']),checks='凭据未消费、未撤销、30 分钟内；只允许此操作，消费并改密在同一事务；完成后重新登录。',group='账户')
api('get','/boards','listBoards','查看板块','public',response='BoardPage',paged_list=True,group='论坛')
S['CategoryList']=array(ref('Dictionary'))
S['CampusList']=array(ref('Campus'))
api('get','/goods-categories','listCategories','获取商品类别','public',response='CategoryList',group='字典')
api('get','/campuses','listCampuses','获取校区选项','public',response='CampusList',group='字典')
api('get','/posts','listPosts','查看帖子列表','public',response='PostPage',params=[param('board_id',ID),param('sort',enum('latest','popular'))],paged_list=True,checks='仅公开且未删除；置顶优先，其后创建时间或点赞评论数，最终 id 倒序打破平局。',group='论坛')
api('post','/posts','createPost','发布帖子','member','PostWrite','Post',status=201,checks='板块启用，作者取会话；文件同属本人，图片≤9、PDF≤2；绑定与内容变更记录一起提交。',group='论坛')
api('get','/posts/{post_id}','getPost','查看帖子详情','public',response='Post',checks='隐藏或删除返回 404；管理员也通过受控管理接口处理隐藏内容。',group='论坛')
api('patch','/posts/{post_id}','updatePost','编辑自己的帖子','owner','PostUpdate','Post',checks='作者、version、公开状态均匹配；隐藏内容作者不能编辑；更新附件、索引变更记录。',group='论坛')
api('delete','/posts/{post_id}','deletePost','删除自己的帖子','owner',obj({'version':VERSION},['version']),checks='作者校验，软删除；评论及附件公开访问立即失效；记录索引移除。',group='论坛')
api('get','/posts/{post_id}/comments','listComments','查看回复','public',response='CommentPage',paged_list=True,checks='帖子可见；按创建时间和 id 正序，隐藏删除的评论仅返回占位，不返回正文。',group='论坛')
api('post','/posts/{post_id}/comments','createComment','评论或回复','member',obj({'body':TEXT,'parent_id':nullable(ID)},['body']),'Comment',status=201,checks='父评论必须同一帖子且可回复；作者从会话获得；正文不执行 HTML。',group='论坛')
api('delete','/comments/{comment_id}','deleteComment','删除自己的评论','owner',checks='归属检查，软删除保留父子结构。',group='论坛')
for suffix,concept in [('like','点赞'),('favorite','收藏')]:
    api('put',f'/posts/{{post_id}}/{suffix}',f'add{suffix.title()}',concept,'member',checks='帖子可见；数据库组合唯一键保证重复操作不重复插入。',group='论坛')
    api('delete',f'/posts/{{post_id}}/{suffix}',f'remove{suffix.title()}',f'取消{concept}','member',checks='幂等删除本人关联，不改他人记录。',group='论坛')
api('get','/me/posts','listMyPosts','查看本人帖子','member',response='PostPage',paged_list=True,checks='仅本人；隐藏记录不允许编辑；页面管理 DTO 不得把此接口用于公开查询。',group='个人中心')
api('get','/me/favorites','listMyFavorites','查看本人收藏','member',response='PostPage',paged_list=True,checks='已隐藏删除的目标不返回正文，列表剔除并调整 total。',group='个人中心')
api('get','/goods','listGoods','查看商品列表','public',response='GoodsPage',paged_list=True,params=[param('q',string(200,1)),param('campus_code',CAMPUS),param('category_id',ID),param('max_price_cents',PRICE),param('state',STATE)],checks='默认 on_sale；可主动指定其他公开状态；治理限制及删除目标不可公开返回。',group='商品')
api('post','/goods','createGoods','发布商品','member','GoodsWrite','Goods',status=201,checks='0～9999999 分；字典有效；其他校区必须地点；本人图片 1～6 张；原子绑定及内容变更。',group='商品')
api('get','/goods/{goods_id}','getGoods','查看商品详情','public',response='Goods',checks='状态为预留、已售等仍可公开查看；治理下架或删除返回 404。',group='商品')
api('patch','/goods/{goods_id}','updateGoods','修改自己的商品','owner','GoodsUpdate','Goods',checks='卖家与版本匹配；治理限制不可编辑；已售只允许查看，不重新发布。',group='商品')
api('delete','/goods/{goods_id}','deleteGoods','删除自己的商品','owner',obj({'version':VERSION},['version']),checks='软删除，附件与搜索立即不可见，不删除历史通知及去重记录。',group='商品')
api('patch','/goods/{goods_id}/state','setGoodsState','预留、已售、下架或上架','owner',obj({'state':STATE,'version':VERSION},['state','version']),'Goods',checks='只接受状态图中的流转；sold 终态；管理员解除限制不自动上架。',group='商品')
api('get','/me/goods','listMyGoods','查看本人商品','member',response='GoodsPage',paged_list=True,checks='仅本人，包括预留和下架；受限内容仅通过本人受限 DTO 返回，不暴露他人附件。',group='个人中心')
api('post','/files','uploadFile','上传头像、帖子或商品文件','member',response='File',status=201,checks='按 purpose 检验真实内容、解码、单文件大小与 200 MiB 配额；只接受 multipart/form-data；未绑定 24h 后清理。',group='文件')
PATHS['/api/v1/files']['post']['requestBody']={'required':True,'content':{'multipart/form-data':{'schema':obj({'purpose':enum('avatar','post_image','post_pdf','goods_image'),'file':{'type':'string','format':'binary'}},['purpose','file'])}}}
api('get','/files/{file_id}/content','readFile','读取有权访问的文件','public',checks='先检查绑定目标权限再读取磁盘或返回 304；未绑定仅上传者可读；私聊不接受文件。',group='文件')
PATHS['/api/v1/files/{file_id}/content']['get']['responses']['200']={'description':'已通过权限检查的文件字节流','content':{m:{'schema':{'type':'string','format':'binary'}} for m in ['image/jpeg','image/png','image/webp','application/pdf']}}
api('delete','/files/{file_id}','deleteUnboundFile','清理本人未绑定文件','owner',checks='仅未绑定文件；先标记清理，真正删除文件后再扣配额；重复删除幂等。',group='文件')
api('get','/me/file-quota','getFileQuota','查看本人文件配额','member',response='Quota',group='文件')
api('get','/search','searchPublic','关键词或语义全站搜索','public',response='SearchPage',params=[param('q',string(200,1)),param('mode',enum('keyword','semantic')),param('kind',enum('all','post','goods')),param('category_id',ID),param('campus_code',CAMPUS),param('max_price_cents',PRICE)],paged_list=True,checks='q 必填；语义失败回关键词并标记 degraded；返回前重查公开状态、版本和商品筛选；私聊/通知/任务不入索引。',group='搜索与匹配')
PATHS['/api/v1/search']['get']['parameters'][0]['required']=True
api('post','/ai/parse-product-need','parseProductNeed','解析自然语言商品要求','member',obj({'query':string(1000,1)},['query']),'ParseResult',checks='每人每分钟最多 5 次；业务总超时 15 秒且不自动重试；拒绝不符合字段 schema 的输出，未知硬条件留空，失败可手填。',group='搜索与匹配')
api('post','/goods/matches','previewGoodsMatches','确认条件后找商品','member',obj({'conditions':ref('Conditions'),'confirmed':{'const':True},'page':integer(1),'page_size':integer(1,100)},['conditions','confirmed']),'MatchResultPage',checks='共用 match_goods；先精确过滤预算、校区、类别、品牌、型号、成色与明确属性，再语义排序；只在售。',group='搜索与匹配')
api('get','/conversations','listConversations','查看本人会话','member',response='ConversationPage',paged_list=True,checks='仅双方成员；按 updated_at,id 倒序。',group='聊天')
api('post','/conversations','openConversation','从商品页联系卖家','member',obj({'goods_id':ID},['goods_id']),'Conversation',checks='商品公开且对方可联系；卖家由商品确定，不接受伪造 sender_id；双方排序唯一，拒绝自己联系自己；已有会话返回同一 id。',group='聊天')
api('get','/conversations/{conversation_id}','getConversation','获取会话及未读状态','participant',response='Conversation',checks='管理员身份不绕过成员校验。',group='聊天')
api('get','/conversations/{conversation_id}/messages','listMessages','读取历史或重连补消息','participant',response='MessagePage',params=[param('after_sequence',SEQ),param('before_sequence',SEQ),param('limit',integer(1,100))],checks='after/before 互斥；默认最新20条按 sequence 正序返回；历史用 before，补读用 after。',group='聊天')
api('post','/conversations/{conversation_id}/messages','sendMessage','发送文字消息（HTTP）','participant','MessageWrite','Message',status=201,checks='与 WS 共用同一保存命令；会话内递增 sequence；同 client_message_id 相同正文返回原消息，正文不同报冲突；提交后确认。',group='聊天')
PATHS['/api/v1/conversations/{conversation_id}/messages']['post']['responses']['200']=PATHS['/api/v1/conversations/{conversation_id}/messages']['post']['responses']['201']
api('put','/conversations/{conversation_id}/read','setConversationRead','更新本人已读位置','participant',obj({'through_sequence':SEQ},['through_sequence']),checks='只单调推进，不超过已存在的 last_sequence；未读只数对方消息。',group='聊天')
api('post','/ws-tickets','createWsTicket','获取一次性实时连接票据','member',response='WsTicket',checks='单次使用、30 秒过期，绑定当前会话；Redis 不可用返回 503，可使用 HTTP 读写；票据不得放 URL。',group='聊天')
api('get','/notifications','listNotifications','查看本人通知','member',response='NotificationPage',paged_list=True,params=[param('unread_only',BOOL)],checks='再次检查目标状态；隐藏删除目标只返回不可用占位，不泄漏旧标题、图片或条件。',group='通知')
api('put','/notifications/{notification_id}/read','readNotification','标记本人通知已读','owner',checks='仅接收者；重复操作幂等。',group='通知')
api('put','/notifications/read-all','readAllNotifications','全部标为已读','member',checks='只修改当前用户，事务中固定此次通知范围。',group='通知')
api('get','/subscriptions','listSubscriptions','查看本人的商品提醒任务','member',response='SubscriptionPage',paged_list=True,checks='默认排除 deleted；不得查询别人的私人条件。',group='商品提醒')
api('post','/subscriptions','createSubscription','确认并保存商品提醒','member','SubscriptionWrite','Subscription',status=201,checks='用户行锁下计数未删除任务，最多10；周期5～1440分钟；确认 schema 后保存，首轮全量匹配。',group='商品提醒')
api('get','/subscriptions/{subscription_id}','getSubscription','查看本人任务条件','owner',response='Subscription',checks='管理员无默认查看他人条件的权限。',group='商品提醒')
api('patch','/subscriptions/{subscription_id}','updateSubscription','编辑已暂停任务','owner','SubscriptionUpdate','Subscription',checks='编辑前先暂停；config_version 匹配；保存时显式选择是否恢复；改条件后全量检查但保留历史去重。',group='商品提醒')
api('patch','/subscriptions/{subscription_id}/state','setSubscriptionState','暂停或恢复任务','owner',obj({'state':enum('active','paused'),'version':VERSION},['state','version']),'Subscription',checks='可从 error 手动恢复；暂停立即撤销旧轮次提交资格；封禁账号不能恢复。',group='商品提醒')
api('delete','/subscriptions/{subscription_id}','deleteSubscription','删除任务','owner',obj({'version':VERSION},['version']),checks='标记 deleted、失效租约，保留去重和历史记录；不再提交通知。',group='商品提醒')
api('get','/subscriptions/{subscription_id}/runs','listSubscriptionRuns','查看本人任务执行记录','owner',response='RunPage',paged_list=True,checks='仅返回错误码，不返回模型密钥或内部堆栈。',group='商品提醒')
api('get','/subscriptions/{subscription_id}/matches','listSubscriptionMatches','查看本人任务历史提醒','owner',response='MatchHistoryPage',paged_list=True,checks='实时复核商品可见性；不可见目标 goods=null。',group='商品提醒')
api('post','/reports','createReport','举报帖子、评论、商品或骚扰消息','member',obj({'target_type':enum('post','comment','goods','message'),'target_id':ID,'reason':string(1000,1)},['target_type','target_id','reason']),'ReportCreated',status=201,checks='目标当时可见；消息举报者必须为接收者；服务端截取被举报消息和必要上下文最多5条，不能由客户端指定整段私聊。',group='举报')
api('get','/me/reports','listMyReports','查看本人举报结果','member',response='ReportPage',paged_list=True,group='举报')
api('get','/me/reports/{report_id}','getMyReport','查看本人单条举报','owner',response='Report',checks='不返回处理者私有信息或他人举报。',group='举报')
api('get','/announcements','listAnnouncements','查看已发布公告','public',response='AnnouncementSummaryPage',paged_list=True,checks='只 state=published。',group='公告')
api('get','/announcements/{announcement_id}','getAnnouncement','查看公开公告','public',response='Announcement',checks='草稿及撤回返回404。',group='公告')
api('get','/admin/users','adminListUsers','管理用户列表','admin',response='AdminUserPage',paged_list=True,group='管理')
api('patch','/admin/users/{user_id}/status','adminSetUserStatus','封禁或解封','admin',obj({'status':enum('active','banned'),'version':VERSION,'reason':string(1000,1)},['status','version','reason']),'AdminUser',checks='锁 administrators 后锁用户；不可封禁最后可用管理员；封禁撤销全部会话、暂停任务；解封不自动恢复任务；同事务审计。',group='管理')
api('patch','/admin/users/{user_id}/role','adminSetUserRole','分配角色和板块','admin',obj({'role':enum('user','moderator','admin'),'board_ids':{'type':'array','items':ID,'uniqueItems':True},'version':VERSION,'reason':string(1000,1)},['role','board_ids','version','reason']),'AdminUser',checks='统一锁防止并发移除最后可用管理员；只有 moderator 可绑定版面；撤销的版面权限立即生效；审计。',group='管理')
api('post','/admin/users/{user_id}/password-reset','adminIssuePasswordReset','管理员核实后发一次性凭据','admin',obj({'version':VERSION,'reason':string(1000,1)},['version','reason']),'ResetCredential',checks='不得对自己使用；不能使最后可用管理员失去可用性；撤销旧凭据和所有会话；有效30分钟，明文只在本次响应出现，不入日志；审计。',group='管理')
api('post','/admin/boards','adminCreateBoard','创建板块','admin',obj({'name':string(30,2),'description':string(300),'reason':string(1000,1)},['name']),'Board',status=201,checks='名称唯一；审计。',group='管理')
api('get','/admin/boards','adminListBoards','查看全部板块','admin',response='AdminBoardPage',paged_list=True,checks='包含已停用板块和帖子数量；停用不删除历史数据。',group='管理')
api('patch','/admin/boards/{board_id}','adminUpdateBoard','修改板块配置','admin',obj({'name':string(30,2),'description':string(300),'enabled':BOOL,'version':VERSION,'reason':string(1000,1)},['version','reason']),'Board',checks='禁用后不能新发帖，已有公开帖仍可读；不删除历史数据；审计。',group='管理')
api('get','/admin/posts','adminListPosts','查看权限范围内的帖子状态','moderator_or_admin',response='PostPage',paged_list=True,checks='版主仅授权板块；返回管理所需正文，所有结果不进入公共搜索缓存。',group='管理')
api('patch','/admin/posts/{post_id}/moderation','adminModeratePost','置顶、隐藏或恢复帖子','moderator_or_admin',obj({'action':enum('pin','unpin','hide','restore'),'version':VERSION,'reason':string(1000,1)},['action','version','reason']),checks='版主核对板块授权；删除不恢复；状态变更、内容变更日志、审计同事务。',group='管理')
api('patch','/admin/comments/{comment_id}/moderation','adminModerateComment','隐藏或恢复评论','moderator_or_admin',obj({'action':enum('hide','restore'),'reason':string(1000,1)},['action','reason']),checks='从所属帖子核对板块授权；删除不恢复；审计。',group='管理')
api('patch','/admin/goods/{goods_id}/moderation','adminModerateGoods','治理下架或解除限制','admin',obj({'action':enum('restrict','release'),'version':VERSION,'reason':string(1000,1)},['action','version','reason']),checks='restrict 设 off_shelf 与 restricted；release 仅解除限制，卖家自行恢复在售；审计和索引更新。',group='管理')
api('get','/admin/reports','adminListReports','查看职责范围内举报','moderator_or_admin',response='ReportPage',paged_list=True,checks='版主仅本人授权板块的帖子/评论举报；商品和私信举报仅管理员。',group='管理')
api('get','/admin/reports/{report_id}','adminGetReport','查看必要举报上下文','moderator_or_admin',response='AdminReport',checks='与列表同范围；私信只展示被举报内容和必要上下文，不提供会话历史入口。',group='管理')
api('patch','/admin/reports/{report_id}','adminResolveReport','处理举报并通知举报人','moderator_or_admin',obj({'action':enum('hide','restrict','keep','uphold','dismiss'),'reason':string(1000,1),'version':VERSION,'target_version':VERSION},['action','reason','version']),'ReportDecision',checks='检查范围、版本和待处理状态；隐藏/下架与处理通知、outbox和审计同事务。',group='管理')
api('get','/admin/announcements','adminListAnnouncements','查看公告草稿及状态','admin',response='AdminAnnouncementPage',paged_list=True,group='管理')
api('post','/admin/announcements','adminCreateAnnouncement','创建公告草稿','admin',obj({'title':string(100,2),'body_markdown':string(20000,1)},['title','body_markdown']),'AdminAnnouncementDetail',status=201,checks='初始 draft，不公开；审计。',group='管理')
api('patch','/admin/announcements/{announcement_id}','adminUpdateAnnouncement','编辑、发布或撤回公告','admin',obj({'action':enum('save','publish','retract'),'title':string(100,2),'body_markdown':string(20000,1),'version':VERSION,'reason':string(1000,1)},['action','version']),'AdminAnnouncementDetail',checks='遵守公告状态图；发布后修改需先撤回；审计。',group='管理')
api('get','/admin/subscriptions','adminListTaskMetadata','查看脱敏任务运行情况','admin',response='AdminTaskMetaPage',paged_list=True,checks='绝不返回 original_query、conditions、匹配历史和通知内容。',group='管理')
api('post','/admin/subscriptions/{subscription_id}/pause','adminPauseTask','暂停异常任务','admin',obj({'reason':string(1000,1)},['reason']),checks='只暂停不修改他人条件；记录审计并使旧租约失效。',group='管理')
api('get','/admin/audit-logs','adminListAuditLogs','查看治理记录','admin',response='AuditPage',paged_list=True,checks='只允许白名单变化字段；不记录密码、token、原始需求、私聊正文。',group='管理')
api('get','/health/live','healthLive','服务存活','public',response='Health',checks='只判断进程能否响应，不调用外部模型。',group='运行')
api('get','/health/ready','healthReady','依赖就绪','public',response='Health',checks='数据库与Redis必需；任一不可用返回503；模型故障不阻止基础论坛就绪。',group='运行')

# Lists do not carry entire article bodies. Hidden own/admin detail has explicit routes.
summary_fields={k:v for k,v in post_fields.items() if k not in ['body_markdown','image_files','pdf_files']}
summary_fields.update({'excerpt':string(300),'visibility':enum('public','hidden')})
summary_fields['last_reply']=nullable(obj({'author':ref('PublicUser'),'created_at':DATE},['author','created_at']))
S['PostSummary']=obj(summary_fields,summary_fields.keys())
paged('PostSummary')
S['OwnerPost']=obj({**post_fields,'visibility':enum('public','hidden')},[*post_fields.keys(),'visibility'])
S['AdminPost']=obj({**post_fields,'visibility':enum('public','hidden'),'deleted_at':nullable(DATE)},[*post_fields.keys(),'visibility','deleted_at'])
S['AdminGoods']=obj({**goods_fields,'moderation':enum('clear','restricted'),'deleted_at':nullable(DATE)},[*goods_fields.keys(),'moderation','deleted_at'])
paged('AdminGoods')
for path in ['/posts','/me/posts','/me/favorites','/admin/posts']:
    PATHS['/api/v1'+path]['get']['responses']['200']['content']['application/json']['schema']=envelope('PostSummaryPage')
api('get','/me/posts/{post_id}','getMyPost','读取本人隐藏帖用于查看状态','owner',response='OwnerPost',checks='仅作者；删除返回404；隐藏内容只读，不可借此恢复编辑或公开附件。',group='个人中心')
api('get','/me/goods/{goods_id}','getMyGoods','读取本人受限商品状态','owner',response='AdminGoods',checks='仅卖家；删除返回404；仅管理自己的内容，不解除治理限制。',group='个人中心')
api('get','/admin/posts/{post_id}','adminGetPost','读取职责内帖子用于治理','moderator_or_admin',response='AdminPost',checks='版主检查授权板块；允许查看治理所需隐藏内容；不改变公开可见性。',group='管理')
api('get','/admin/goods','adminListGoods','查看商品治理列表','admin',response='AdminGoodsPage',paged_list=True,checks='仅管理员；返回公开或受限商品，不包含私人需求。',group='管理')
api('get','/admin/goods/{goods_id}','adminGetGoods','读取商品治理详情','admin',response='AdminGoods',checks='仅管理员；不授权代卖家修改正文、价格。',group='管理')
api('get','/admin/announcements/{announcement_id}','adminGetAnnouncement','查看公告草稿详情','admin',response='AdminAnnouncementDetail',checks='仅管理员，草稿不可由公开接口获取。',group='管理')

document={'openapi':'3.1.0','info':{'title':'邮智汇第一版 HTTP 设计约定','version':'1.0.0','description':'计划书4.3设计交付。接口尚未实现；ID是字符串，金额是整数分，时间UTC；权限/事务约定见同目录文档。'},'servers':[{'url':'http://localhost:8080','description':'正式开发时的本机示例地址，当前尚无服务'}],'paths':PATHS,'components':{'securitySchemes':{'sessionCookie':{'type':'apiKey','in':'cookie','name':'byr_session'}},'schemas':S}}
(ROOT/'openapi.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# HTTP 操作目录','','日期：2026 年 10 月 31 日。以下为接口目录；账户、论坛/上传、商品/普通搜索、聊天/通知、4.8 AI 搜索与帖子举报、4.9 持续提醒、4.10 四类举报与管理已实现，实际结果见 [账户说明](../accounts/README.md) 、[论坛说明](../forum/README.md) 、[商品说明](../goods/README.md) 、[聊天说明](../chat/README.md) 、[4.8 说明](../ai48/README.md) 、[4.9 说明](../reminders/README.md) 与 [4.10 说明](../admin/README.md)。完整字段类型见 [openapi.json](openapi.json)，使用方式、错误及事务边界见 [03 接口与消息约定](03_接口与消息约定.md)。','','| 操作编号 | 请求 | 用途 | 允许身份 | 后端必须检查 |','| --- | --- | --- | --- | --- |']
for op,method,path,title,permission,checks in rows:
    lines.append(f'| `{op}` | `{method} {path}` | {title} | `{permission}` | {checks or "有效身份及本人的数据范围。"} |')
(ROOT/'HTTP操作目录.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def frame(kind,data,server=False):
    fields={'type':{'const':kind},'request_id':nullable(string(format='uuid')) if server else string(format='uuid'),'data':data}
    if server: fields.update({'event_id':string(180,1),'occurred_at':DATE})
    return obj(fields,fields.keys())
events={'$schema':'https://json-schema.org/draft/2020-12/schema','title':'邮智汇 WebSocket 帧设计','description':'只用于4.3契约，不代表服务已建立。外部引用复用同目录openapi.json。','$defs':{}}
E=events['$defs']
E['client.authenticate']=frame('authenticate',obj({'ticket':string(200,32)},['ticket']))
E['client.message.send']=frame('message.send',obj({'conversation_id':ID,'client_message_id':string(format='uuid'),'body':TEXT},['conversation_id','client_message_id','body']))
E['client.message.read']=frame('message.read',obj({'conversation_id':ID,'through_sequence':SEQ},['conversation_id','through_sequence']))
E['client.ping']=frame('ping',obj({}))
E['server.ready']=frame('ready',obj({'user_id':ID,'session_expires_at':DATE},['user_id','session_expires_at']),True)
for name,model in [('message.ack','Message'),('message.created','Message'),('notification.created','Notification')]:
    E['server.'+name]=frame(name,{'$ref':'openapi.json#/components/schemas/'+model},True)
E['server.conversation.read']=frame('conversation.read',obj({'conversation_id':ID,'reader_id':ID,'through_sequence':SEQ},['conversation_id','reader_id','through_sequence']),True)
E['server.unread.updated']=frame('unread.updated',obj({'conversation_id':nullable(ID),'message_unread_count':integer(),'notification_unread_count':integer()},['conversation_id','message_unread_count','notification_unread_count']),True)
E['server.pong']=frame('pong',obj({'server_time':DATE},['server_time']),True)
E['server.session.revoked']=frame('session.revoked',obj({'reason_code':enum('logout','expired','password_changed','password_reset','banned')},['reason_code']),True)
E['server.error']=frame('error',obj({'code':string(64),'message':string(300),'retryable':BOOL},['code','message','retryable']),True)
events['oneOf']=[{'$ref':'#/$defs/'+name} for name in E]
(ROOT/'ws-events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
page_specs=[
    ('index','F02','论坛首页',['listBoards','listPosts','listAnnouncements','getAnnouncement']),
    ('forum','F02','板块与帖子列表',['listBoards','listPosts']),
    ('post','F02','帖子详情与回复',['getPost','listComments','createComment','deleteComment','addLike','removeLike','addFavorite','removeFavorite','createReport']),
    ('compose','F02','发帖编辑',['createPost','updatePost','deletePost','uploadFile','deleteUnboundFile']),
    ('goods','F04','商品列表',['listGoods','listCategories','listCampuses']),
    ('goods-detail','F04','商品详情',['getGoods','openConversation','setGoodsState','createReport']),
    ('goods-edit','F04','商品编辑',['createGoods','updateGoods','deleteGoods','uploadFile','listCategories','listCampuses']),
    ('search','F03','搜索与匹配',['searchPublic','parseProductNeed','previewGoodsMatches','createSubscription']),
    ('subscriptions','F07','商品提醒',['listSubscriptions','getSubscription','updateSubscription','setSubscriptionState','deleteSubscription','listSubscriptionRuns','listSubscriptionMatches']),
    ('chat','F05','私信',['listConversations','getConversation','listMessages','sendMessage','setConversationRead','createWsTicket']),
    ('notifications','F05','通知',['listNotifications','readNotification','readAllNotifications']),
    ('login','F01','注册登录与辅助改密',['getCsrf','register','login','completePasswordReset']),
    ('profile','F01','个人中心',['getMe','updateMe','changePassword','logout','listMyPosts','getMyPost','listMyFavorites','listMyGoods','getMyGoods','getFileQuota','listMyReports','getMyReport','uploadFile','deleteUnboundFile','readFile']),
    ('admin','F08','社区管理',[r[0] for r in rows if r[0].startswith('admin')]),
    ('directory','F09','草图目录',[])
]
page_map={'date':'2026-10-23','status':'design_complete_not_implemented','pages':[{'page':key,'html':'../../archive/early-docs/page-drafts/'+key+'.html','feature':feature,'name':name,'planned_operations':ops} for key,feature,name,ops in page_specs],
    'global_operations':['getCsrf','healthLive','healthReady'],
    'feature_cross_links':{'F01':['login','profile'],'F02':['index','forum','post','compose'],'F03':['search'],'F04':['goods','goods-detail','goods-edit'],'F05':['chat','notifications'],'F06':['search'],'F07':['search','subscriptions','notifications'],'F08':['admin'],'F09':['directory']}}
(ROOT/'page-map.json').write_text(json.dumps(page_map,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Generated {len(rows)} operations, {len(S)} schemas and {len(E)} WebSocket frame types.')

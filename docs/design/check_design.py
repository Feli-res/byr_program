"""Check design artifacts. Does not test or start the future forum application."""
import copy
import hashlib
import json
import re
import sys
import warnings
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent.parent
optional=PROJECT/'.local/design-qa/python'
if optional.exists(): sys.path.insert(0,str(optional))
warnings.filterwarnings('ignore',category=DeprecationWarning)

def read_json(name): return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))
api=read_json('openapi.json')
events=read_json('ws-events.json')
mapping=read_json('page-map.json')
operations={}
for path,methods in api['paths'].items():
    for method,spec in methods.items():
        op=spec['operationId']
        assert op not in operations,op
        operations[op]=spec
        assert set(re.findall(r'\{([^}]+)\}',path))=={p['name'] for p in spec['parameters'] if p['in']=='path'},path
        assert all(p.get('required') for p in spec['parameters'] if p['in']=='path'),path
        if method in ['post','put','patch','delete']:
            assert any(p['name']=='X-CSRF-Token' and p.get('required') for p in spec['parameters']),op
        if spec['x-permission'] not in ['public','anonymous']: assert spec['security'],op

def pointer(value,fragment):
    for part in fragment.lstrip('/').split('/'):
        if part: value=value[part.replace('~1','/').replace('~0','~')]
    return value
refs=0
def check_refs(value,current):
    global refs
    if isinstance(value,dict):
        if '$ref' in value:
            name,fragment=value['$ref'].split('#',1)
            doc=read_json(name) if name else current
            pointer(doc,fragment)
            refs+=1
        for child in value.values(): check_refs(child,current)
    elif isinstance(value,list):
        for child in value: check_refs(child,current)
check_refs(api,api);check_refs(events,events)
covered=set(mapping['global_operations'])
for page in mapping['pages']:
    assert (ROOT/page['html']).is_file(),page
    assert set(page['planned_operations']).issubset(operations),page
    covered.update(page['planned_operations'])
assert covered==set(operations),(set(operations)-covered,covered-set(operations))
assert set(mapping['feature_cross_links'])=={'F'+str(i).zfill(2) for i in range(1,10)}
for names in mapping['feature_cross_links'].values():
    assert set(names).issubset({p['page'] for p in mapping['pages']})

links=0
for file in [*ROOT.glob('*.md'),ROOT.parent/'README.md',ROOT.parent.parent/'README.md']:
    for raw in re.findall(r'\]\(([^)]+)\)',file.read_text(encoding='utf-8-sig')):
        if raw.startswith(('https:','http:','#')): continue
        raw=re.sub(r':\d+$','',raw).split('#')[0].strip('<>')
        dest=Path(raw) if re.match(r'^[A-Za-z]:/',raw) else file.parent/raw
        if dest in [ROOT/'verification.json',ROOT/'数据字段字典.md'] and not dest.exists():
            links+=1
            continue
        assert dest.exists(),(file.name,raw)
        links+=1
completion=(ROOT/'05_完成核对.md').read_text(encoding='utf-8')
cases=re.findall(r'^\| (AC\d{2}) \|',completion,re.M)
assert cases==['AC'+str(i).zfill(2) for i in range(1,21)],cases

sql=(ROOT/'schema.sql').read_text(encoding='utf-8')
tables=re.findall(r'CREATE TABLE (\w+) \((.*?)\n\) ENGINE=InnoDB[^;]*;',sql,re.S)
assert len(tables)==len(set(name for name,_ in tables))
for key in ['uq_user_account','uq_message_retry','uq_message_sequence','uq_subscription_goods','uq_notification_match','uq_conversation_pair','uq_binding_file']:
    assert key in sql,key
dictionary=['# 数据字段字典','','字段取自 [schema.sql](schema.sql)，含义与关系见 [02_数据与关系.md](02_数据与关系.md)。本文件由 `check_design.py` 提取，类型与空值以SQL为准，业务校验还需遵守页面/接口/状态说明。','','共有 '+str(len(tables))+' 张表。`id` 为内部编号；`created_at/updated_at` 为UTC时间；`version/config_version` 用于防止旧页面覆盖新数据。','','| 表 | 字段数 |','| --- | --- |']
table_columns={}
for name,body in tables:
    cols=[]
    for line in body.splitlines():
        match=re.match(r'\s*(\w+)\s+((?:BIGINT|INT|TINYINT|SMALLINT|VARCHAR|CHAR|BINARY|BOOLEAN|DATETIME|MEDIUMTEXT|JSON|ENUM)\b.*)',line)
        if match: cols.append((match[1],match[2].rstrip(',')))
    table_columns[name]=cols
    dictionary.append('| `'+name+'` | '+str(len(cols))+' |')
for name,cols in table_columns.items():
    dictionary+=['','## '+name,'','| 字段 | 类型、空值、默认值与列约束 |','| --- | --- |']
    dictionary+=['| `'+name+'` | `'+spec.replace('|','\\|')+'` |' for name,spec in cols]
(ROOT/'数据字段字典.md').write_text('\n'.join(dictionary)+'\n',encoding='utf-8')

contract_checks=[]
try:
    from openapi_spec_validator import validate_spec
    validate_spec(api)
    contract_checks.append('OpenAPI 3.1 validator passed')
    openapi_status='passed'
except ImportError:
    openapi_status='not_run_dependency_missing'

schema_cases=0
try:
    from jsonschema import Draft202012Validator, RefResolver, FormatChecker
    resolver=RefResolver.from_schema(api)
    def sample(name,value,valid=True):
        global schema_cases
        schema={'$ref':'#/components/schemas/'+name}
        found=list(Draft202012Validator(schema,resolver=resolver,format_checker=FormatChecker()).iter_errors(value))
        assert bool(found)!=valid,(name,value,[e.message for e in found])
        schema_cases+=1
    good={'title':'二手平板','description':'示例商品描述','category_id':'1','campus_code':'shahe','condition_code':'good','price_cents':220000,'location_text':'图书馆门口','image_file_ids':['11']}
    sample('GoodsWrite',good)
    for key,value in [('price_cents',-1),('price_cents',10000000),('price_cents',1.5),('campus_code','unknown'),('image_file_ids',[]),('image_file_ids',['1','2','3','4','5','6','7']),('seller_id','9')]:
        case=copy.deepcopy(good);case[key]=value;sample('GoodsWrite',case,False)
    conditions={'schema_version':1,'min_price_cents':None,'max_price_cents':0,'campus_code':'shahe','category_id':None,'brand':None,'model':None,'min_condition':None,'required_attributes':{},'purpose':None}
    sample('Conditions',conditions)
    for key,value in [('schema_version',2),('max_price_cents',-1),('required_attributes',{'stylus_support':'yes'}),('sql','anything')]:
        case=copy.deepcopy(conditions);case[key]=value;sample('Conditions',case,False)
    task={'name':'测试提醒','conditions':conditions,'interval_minutes':5,'confirmed':True}
    sample('SubscriptionWrite',task)
    for key,value in [('interval_minutes',4),('interval_minutes',1441),('confirmed',False)]:
        case=copy.deepcopy(task);case[key]=value;sample('SubscriptionWrite',case,False)
    message={'client_message_id':'267efdf5-e641-4cef-b112-2d86b1751e1a','body':'示例文字'}
    sample('MessageWrite',message)
    for key,value in [('body','字'*2001),('sender_id','99'),('client_message_id','bad')]:
        case=copy.deepcopy(message);case[key]=value;sample('MessageWrite',case,False)
    sample('PublicUser',{'id':'1','nickname':'小邮','bio':'','avatar_url':None})
    sample('PublicUser',{'id':'1','nickname':'小邮','bio':'','avatar_url':None,'account':'private'},False)
    schema_status='passed'
except ImportError:
    schema_status='not_run_dependency_missing'

assert 'conditions' not in api['components']['schemas']['AdminTaskMeta']['properties']
assert 'original_query' not in api['components']['schemas']['AdminTaskMeta']['properties']
assert 'password_hash' not in api['components']['schemas']['PublicUser']['properties']
report={'date':'2026-10-23','status':'passed' if openapi_status==schema_status=='passed' else 'partial','http_operations':len(operations),'schemas':len(api['components']['schemas']),'ws_frame_types':len(events['$defs']),'sql_tables':len(tables),'sql_columns':sum(len(v) for v in table_columns.values()),'page_entries':len(mapping['pages']),'feature_groups':9,'mapped_acceptance_cases':len(cases),'resolved_refs':refs,'checked_local_links':links,'openapi_validation':openapi_status,'schema_sample_validation':schema_status,'schema_samples':schema_cases,'application_tests_run':False,'browser_visual_tested':False,'word_modified':False,'sql_sha256':hashlib.sha256(sql.encode()).hexdigest()}
database=ROOT/'database-verification.json'
report['database_draft_check']=json.loads(database.read_text(encoding='utf-8')) if database.exists() else {'status':'not_run'}
if report['database_draft_check'].get('status')=='passed':
    assert report['database_draft_check'].get('sql_sha256')==report['sql_sha256'],'Database result is stale; rerun check_database.py --run.'
(ROOT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
if report['status']!='passed': print('Install requirements-checks.txt to run the remaining contract checks.')

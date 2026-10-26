"""Validate schema.sql in a unique disposable database inside the checks container.
Requires explicit --run. Does not use or alter a production server/database.
"""
import json
import hashlib
import re
import subprocess
import sys
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent.parent
if sys.argv[1:]!=['--run']:
    raise SystemExit('Use --run to validate in a disposable database in youzhihui-checks-mysql-1.')
compose=['docker','compose','--env-file',str(PROJECT/'.local/checks.env'),'-f',str(PROJECT/'checks/compose.yaml')]
def command(args,input=None,check=True,timeout=120):
    result=subprocess.run(args,input=input,text=True,encoding='utf-8',capture_output=True,timeout=timeout)
    if check and result.returncode: raise RuntimeError(result.stderr or result.stdout)
    return result
prior=command(['docker','inspect','--format','{{.State.Running}}','youzhihui-checks-mysql-1'],check=False)
was_running=prior.returncode==0 and prior.stdout.strip()=='true'
database='byr_design_'+uuid.uuid4().hex[:12]
assert re.fullmatch(r'byr_design_[0-9a-f]{12}',database)
mysql=compose+['exec','-T','mysql','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 --batch --skip-column-names']
checks=[];owned=False
source_sql=(ROOT/'schema.sql').read_text(encoding='utf-8')
source_hash=hashlib.sha256(source_sql.encode()).hexdigest()
def sql(text,check=True): return command(mysql,'USE '+database+';\n'+text,check=check)
def reject(name,text,error):
    result=sql(text,check=False)
    assert result.returncode!=0 and ('ERROR '+str(error)) in result.stderr,(name,result.stdout,result.stderr)
    checks.append(name)
try:
    command(compose+['up','-d','--wait','--wait-timeout','180','mysql'],timeout=210)
    command(mysql,'CREATE DATABASE '+database+' CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;')
    owned=True
    sql(source_sql)
    count=int(sql('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE();').stdout.strip())
    checks.append('All '+str(count)+' tables created on MySQL 8.4')
    fixture="""
INSERT INTO users(id,account_norm,password_hash,nickname) VALUES
 (1,'alpha','design-only-hash','甲同学'),(2,'bravo','design-only-hash','乙同学');
INSERT INTO posts(id,author_id,board_id,title,body_markdown) VALUES
 (1,1,1,'测试帖子一','设计检查正文'),(2,2,2,'测试帖子二','设计检查正文');
INSERT INTO comments(id,post_id,author_id,body) VALUES(1,1,1,'第一条评论');
INSERT INTO goods(id,seller_id,category_id,campus_code,title,description,condition_code,price_cents)
 VALUES(1,1,1,'shahe','测试商品','设计检查商品','good',220000);
INSERT INTO files(id,owner_id,purpose,storage_key,original_name,mime_type,size_bytes,sha256)
 VALUES(1,1,'goods_image','design-test-image','test.png','image/png',1024,UNHEX(REPEAT('0',64)));
INSERT INTO file_bindings(file_id,kind,goods_id,position_no) VALUES(1,'goods_image',1,1);
INSERT INTO conversations(id,user_low_id,user_high_id) VALUES(1,1,2);
INSERT INTO messages(id,conversation_id,sequence_no,sender_id,client_message_id,body,body_hash)
 VALUES(1,1,1,1,'267efdf5-e641-4cef-b112-2d86b1751e1a','设计检查消息',UNHEX(REPEAT('0',64)));
INSERT INTO subscriptions(id,owner_id,name,conditions,interval_minutes)
 VALUES(1,1,'设计检查任务',JSON_OBJECT('schema_version',1),5);
INSERT INTO subscription_runs(id,subscription_id,cycle_key,config_version,lease_token,upper_change_seq,state,started_at)
 VALUES(1,1,'267efdf5-e641-4cef-b112-2d86b1751e1a',1,'267efdf5-e641-4cef-b112-2d86b1751e1a',0,'succeeded',UTC_TIMESTAMP(6));
INSERT INTO subscription_matches(id,subscription_id,goods_id,run_id) VALUES(1,1,1,1);
INSERT INTO notifications(recipient_id,kind,match_id,target_type,target_id,safe_summary)
 VALUES(1,'goods_match',1,'goods',1,'测试通知');
INSERT INTO post_likes(post_id,user_id) VALUES(1,1);
INSERT INTO post_favorites(post_id,user_id) VALUES(1,1);
"""
    sql(fixture);checks.append('Valid linked fixtures and seed dictionaries accepted')
    reject('Normalized account uniqueness',"INSERT INTO users(account_norm,password_hash,nickname) VALUES('alpha','test','重复用户');",1062)
    reject('Price upper bound',"UPDATE goods SET price_cents=10000000 WHERE id=1;",3819)
    reject('Cross-post parent rejected',"INSERT INTO comments(post_id,author_id,parent_id,body) VALUES(2,2,1,'跨帖回复');",1452)
    reject('Unknown campus foreign key',"UPDATE goods SET campus_code='missing' WHERE id=1;",1452)
    reject('Other campus requires location',"UPDATE goods SET campus_code='other',location_text='' WHERE id=1;",3819)
    reject('Empty message rejected',"UPDATE messages SET body='' WHERE id=1;",3819)
    reject('Same members only one conversation',"INSERT INTO conversations(user_low_id,user_high_id) VALUES(1,2);",1062)
    reject('Self conversation rejected',"INSERT INTO conversations(user_low_id,user_high_id) VALUES(1,1);",3819)
    reject('Message retry uniqueness',"INSERT INTO messages(conversation_id,sequence_no,sender_id,client_message_id,body,body_hash) VALUES(1,2,1,'267efdf5-e641-4cef-b112-2d86b1751e1a','重发',UNHEX(REPEAT('0',64)));",1062)
    reject('Message sequence uniqueness',"INSERT INTO messages(conversation_id,sequence_no,sender_id,client_message_id,body,body_hash) VALUES(1,1,2,'367efdf5-e641-4cef-b112-2d86b1751e1a','序号重复',UNHEX(REPEAT('0',64)));",1062)
    reject('Repeated like rejected',"INSERT INTO post_likes VALUES(1,1,UTC_TIMESTAMP(6));",1062)
    reject('Repeated favorite rejected',"INSERT INTO post_favorites VALUES(1,1,UTC_TIMESTAMP(6));",1062)
    reject('Task interval lower bound',"UPDATE subscriptions SET interval_minutes=4 WHERE id=1;",3819)
    reject('Task interval upper bound',"UPDATE subscriptions SET interval_minutes=1441 WHERE id=1;",3819)
    reject('Only two scheduler slots',"INSERT INTO scheduler_slots(slot_no) VALUES(3);",3819)
    reject('Repeated match rejected',"INSERT INTO subscription_matches(subscription_id,goods_id,run_id) VALUES(1,1,1);",1062)
    reject('Repeated match notification rejected',"INSERT INTO notifications(recipient_id,kind,match_id,target_type,target_id,safe_summary) VALUES(1,'goods_match',1,'goods',1,'重复');",1062)
    reject('Mixed file target rejected',"UPDATE file_bindings SET post_id=1 WHERE file_id=1;",3819)
    reject('Avatar per-file size bound',"INSERT INTO files(owner_id,purpose,storage_key,original_name,mime_type,size_bytes,sha256) VALUES(1,'avatar','bad-avatar','test.png','image/png',3145728,UNHEX(REPEAT('0',64)));",3819)
    reject('User quota upper bound',"UPDATE users SET used_file_bytes=209715201 WHERE id=1;",3819)
    sql("UPDATE goods SET price_cents=0 WHERE id=1;")
    assert sql('SELECT price_cents FROM goods WHERE id=1;').stdout.strip()=='0'
    checks.append('Free goods stored exactly as zero cents')
    version=sql('SELECT VERSION();').stdout.strip()
    report={'date':'2026-10-23','status':'passed','sql_sha256':source_hash,'mysql_version':version,'tables_created':count,'checks':checks,'application_permission_logic_tested':False,'concurrent_transaction_logic_tested':False,'database':database,'disposable_database_removed':False,'prior_container_running':was_running}
except Exception as error:
    report={'date':'2026-10-23','status':'failed','sql_sha256':source_hash,'checks':checks,'error':str(error)[:2000],'database':database,'disposable_database_removed':False,'prior_container_running':was_running}
    raise
finally:
    removed=False
    if owned:
        command(mysql,'DROP DATABASE '+database+';');removed=True
    if not was_running:
        command(compose+['stop','mysql'])
    if 'report' in locals():
        report['disposable_database_removed']=removed
        report['container_restored_to_prior_state']=True
        (ROOT/'database-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if 'report' in locals(): print(json.dumps(report,ensure_ascii=False,indent=2))

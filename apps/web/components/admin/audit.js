'use client';
import {useState} from 'react';
import {request} from '../../lib/api';
import {Failure,Time,Pager} from '../shared/content';
import {useData} from '../../lib/use-data';
import {AdminGuard} from './common';

const targetNames={post:'帖子',comment:'评论',goods:'商品',report:'举报',announcement:'公告',board:'板块',subscription:'提醒任务',user:'用户'};
const actionNames={'report.resolve':'处理举报','post.moderate':'管理帖子','comment.moderate':'管理评论','goods.moderate':'管理商品','announcement.create':'创建公告','announcement.update':'编辑公告','announcement.publish':'发布公告','announcement.retract':'撤回公告','board.create':'创建板块','board.update':'编辑板块','board.enable':'启用板块','board.disable':'停用板块','subscription.pause':'暂停任务'};

function Audit(){
  const [page,setPage]=useState(1),[target,setTarget]=useState(''),[action,setAction]=useState('');
  const query=new URLSearchParams({page:String(page)});if(target)query.set('target_type',target);if(action)query.set('action',action);
  const data=useData(`audit:${query}`,()=>request(`/api/v1/admin/audit-logs?${query}`));
  return <section className="panel"><div className="panel-heading"><h1>操作记录</h1></div>
    <p className="muted">记录谁在什么时间、因为什么、对哪个对象做了什么处理；不包含私聊正文和用户私人条件。</p>
    <div className="filter-fields"><div><label htmlFor="audit-target">对象类型</label><select id="audit-target" value={target} onChange={e=>{setTarget(e.target.value);setPage(1);}}><option value="">全部</option>{Object.entries(targetNames).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></div><div><label htmlFor="audit-action">操作</label><select id="audit-action" value={action} onChange={e=>{setAction(e.target.value);setPage(1);}}><option value="">全部</option>{Object.entries(actionNames).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></div></div>
    <Failure data={data}/>
    {data.value&&<><ul className="record-list">{data.value.items.map(a=><li key={a.id}><div className="topic-title"><span>{actionNames[a.action]||a.action} · {targetNames[a.target_type]||a.target_type}{a.target_id?` #${a.target_id}`:''}</span><span className="tag">{a.actor.nickname}</span></div><p>原因：{a.reason}</p><p className="muted"><Time value={a.created_at}/> · 变化：{JSON.stringify(a.changes)}</p></li>)}</ul>{data.value.items.length===0&&<p className="empty">暂无操作记录。</p>}<Pager page={page} total={data.value.total} onPage={setPage}/></>}
  </section>;
}

export function AuditPage(){return <AdminGuard adminOnly><Audit/></AdminGuard>;}

'use client';
import {useState} from 'react';
import {request,jsonRequest} from '../lib/api';
import {centsToYuan} from '../lib/money.mjs';
import {Feedback,Protected,useAuth} from './auth';
import {Failure,Time,Pager} from './shared/content';
import {useData} from '../lib/use-data';
import {AdminGuard} from './admin/common';

const kindNames={post:'帖子',comment:'评论',goods:'商品',message:'私信'};
const states={pending:'待处理',resolved:'已处理',dismissed:'举报不成立'};
const reasons=['广告或垃圾信息','辱骂或人身攻击','泄露个人信息','疑似诈骗','其他'];
const actions={
  post:[['hide','成立并隐藏帖子'],['keep','成立但不隐藏'],['dismiss','举报不成立']],
  comment:[['hide','成立并隐藏评论'],['keep','成立但不隐藏'],['dismiss','举报不成立']],
  goods:[['restrict','成立并下架商品'],['keep','成立但不处理'],['dismiss','举报不成立']],
  message:[['uphold','举报成立'],['dismiss','举报不成立']],
};

export function ReportButton({targetType='post',targetId,label='举报',compact=false}){
  const [open,setOpen]=useState(false),[kind,setKind]=useState(reasons[0]),[text,setText]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  async function submit(e){e.preventDefault();setBusy(true);setError('');setNotice('');try{const result=await jsonRequest('/api/v1/reports','POST',{target_type:targetType,target_id:String(targetId),reason:kind+(text.trim()?'：'+text.trim():'')});setNotice(result.already_exists?'你已经提交过待处理的举报。':'举报已提交，处理结果可在“我的举报”查看。');setOpen(false);setText('');}catch(e){setError(e.message);}finally{setBusy(false);}}
  return <div className={compact?'inline-report':''}><button className="text-button" type="button" onClick={()=>setOpen(v=>!v)}>{label}</button>{open&&<form onSubmit={submit}><label htmlFor={`report-kind-${targetType}-${targetId}`}>举报原因</label><select id={`report-kind-${targetType}-${targetId}`} value={kind} onChange={e=>setKind(e.target.value)}>{reasons.map(x=><option key={x}>{x}</option>)}</select><label htmlFor={`report-detail-${targetType}-${targetId}`}>补充说明（选填）</label><textarea id={`report-detail-${targetType}-${targetId}`} value={text} onChange={e=>setText(e.target.value)} maxLength={950} rows={3}/><div className="actions"><button disabled={busy}>{busy?'正在提交…':'提交举报'}</button><button type="button" className="secondary" onClick={()=>setOpen(false)}>取消</button></div></form>}<Feedback error={error} notice={notice}/></div>;
}

function Detail({chosen,admin,onDecided,onClose}){
  const [reason,setReason]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function decide(action){
    if(!reason.trim())return;
    setBusy(true);setError('');
    try{
      const body={action,reason,version:chosen.version};
      if(chosen.current?.version)body.target_version=chosen.current.version;
      await jsonRequest(`/api/v1/reports/${chosen.id}`,'PATCH',body);
      onDecided();
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  const snap=chosen.snapshot,current=chosen.current;
  return <section className="panel"><div className="panel-heading"><h2>举报详情</h2><button className="secondary" onClick={onClose}>关闭</button></div>
    <p>类型：{kindNames[chosen.target_type]||chosen.target_type} · 状态：{states[chosen.state]||chosen.state}</p>
    {chosen.reporter&&<p className="muted">举报人：{chosen.reporter.nickname}</p>}
    <p>举报原因：{chosen.reason}</p>
    {chosen.resolution&&<p>处理说明：{chosen.resolution}</p>}
    {snap&&chosen.target_type==='post'&&<><h2>举报时的帖子</h2><p>{snap.title}</p><p className="comment-body">{snap.body}</p>{snap.attachments?.length>0&&<p>当时的附件：{snap.attachments.map((f,i)=><span key={f.id}>{i>0&&'、'}<a href={`/api/v1/files/${f.id}/content`} target="_blank" rel="noreferrer">{f.kind==='post_pdf'?'PDF':'图片'} {i+1}</a></span>)}</p>}</>}
    {snap&&chosen.target_type==='comment'&&<><h2>举报时的评论</h2><p className="muted">所属帖子：{snap.post_title}</p><p className="comment-body">{snap.comment_body}</p>{snap.parent_body&&<p className="muted">回复的评论：{snap.parent_body}</p>}</>}
    {snap&&chosen.target_type==='goods'&&<><h2>举报时的商品</h2><p>{snap.title} · {snap.price_cents===0?'免费':`¥ ${centsToYuan(snap.price_cents)}`}</p><p className="comment-body">{snap.description}</p><p className="muted">校区 {snap.campus_code} · 成色 {snap.condition_code} · 状态 {snap.state} · 图片 {snap.images?.length||0} 张</p></>}
    {snap&&chosen.target_type==='message'&&<><h2>被举报消息及必要上下文</h2><p className="hint">只展示被举报消息和此前最多 4 条，不提供整段会话。</p><ol className="record-list">{snap.messages?.map(m=><li key={m.id}><p className={m.mine?'':'muted'}>{m.mine?'我：':'对方：'}{m.body}</p><p className="muted"><Time value={m.created_at}/></p></li>)}</ol></>}
    {current&&chosen.target_type==='post'&&<><h2>当前帖子</h2><p>{current.title} · {current.deleted?'已删除':current.visibility==='hidden'?'已隐藏':'公开'}</p><p className="comment-body">{current.body}</p></>}
    {current&&chosen.target_type==='comment'&&<><h2>当前评论</h2><p>{current.deleted?'已删除':current.visibility==='hidden'?'已隐藏':'公开'} · 所属帖子：{current.post_title}（{current.post_deleted?'已删除':current.post_visibility==='hidden'?'已隐藏':'公开'}）</p><p className="comment-body">{current.body}</p></>}
    {current&&chosen.target_type==='goods'&&<><h2>当前商品</h2><p>{current.title} · {current.deleted?'已删除':current.state} · 管理状态 {current.moderation}</p><p className="comment-body">{current.description}</p></>}
    {chosen.target_type==='post'&&<div className="moderation-box"><h2>AI 辅助分析</h2>{chosen.ai?.stale?<p>帖子已修改，原 AI 建议已过期，请人工核查。</p>:chosen.ai?.state==='completed'&&chosen.ai.result?<><p>{chosen.ai.result.assessment} · {chosen.ai.result.suggested_action}</p><p>{chosen.ai.result.explanation}</p>{chosen.ai.result.evidence&&<p>参考原文：{chosen.ai.result.evidence}</p>}</>:<p>AI 分析{chosen.ai?.state==='pending'||chosen.ai?.state==='running'?'进行中':'暂不可用'}，可以继续人工处理。</p>}<p className="hint">AI 只分析文字，未分析附件；结果仅供参考，最终由管理员决定。</p></div>}
    {!['post','comment','goods','message'].includes(chosen.target_type)&&<p>未知举报类型。</p>}
    {chosen.target_type==='message'&&<p className="hint">私信举报不调用外部 AI，只做人工核实；管理员不能浏览整段私聊。</p>}
    {admin&&chosen.state==='pending'&&<><label htmlFor="report-resolution">处理说明</label><textarea id="report-resolution" value={reason} onChange={e=>setReason(e.target.value)} maxLength={1000} rows={3}/><div className="actions">{(actions[chosen.target_type]||[]).map(([value,text])=><button key={value} className={value==='dismiss'?'secondary':''} disabled={busy||!reason.trim()} onClick={()=>decide(value)}>{text}</button>)}</div><p className="hint">处理会立即影响其他页面：隐藏帖子后不再被搜索到，评论隐藏后正文不再返回，商品下架后不再产生新提醒。</p></>}
    <Feedback error={error}/>
  </section>;
}

function MyReports({admin}){
  const {user}=useAuth();const [page,setPage]=useState(1),[type,setType]=useState(''),[state,setState]=useState(''),[board,setBoard]=useState(''),[chosen,setChosen]=useState(null),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const boards=useData(`admin-report-boards:${admin}:${user?.role}`,()=>admin&&user?.role==='admin'?request('/api/v1/admin/boards?page_size=100'):Promise.resolve(null));
  const query=new URLSearchParams({page:String(page)});if(type)query.set('target_type',type);if(state)query.set('state',state);if(board)query.set('board_id',board);
  const data=useData(`reports:${admin}:${user?.id}:${query}`,()=>request(`/api/v1/${admin?'admin':'me'}/reports?${query}`));
  async function choose(row){setError('');try{setChosen(await request(`/api/v1/reports/${row.id}`));}catch(e){setError(e.message)}}
  function refresh(){setChosen(null);data.reload();setNotice('处理结果已保存。');}
  return <><section className="panel"><div className="panel-heading"><h1>{admin?'举报处理':'我的举报'}</h1>{admin&&<span className="muted">帖子与评论按板块授权，商品与私信仅管理员处理</span>}</div>
    <div className="filter-fields"><div><label htmlFor="report-type">举报类型</label><select id="report-type" value={type} onChange={e=>{setType(e.target.value);setPage(1);}}><option value="">全部类型</option>{Object.entries(kindNames).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></div><div><label htmlFor="report-state">处理状态</label><select id="report-state" value={state} onChange={e=>{setState(e.target.value);setPage(1);}}><option value="">全部状态</option>{Object.entries(states).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></div>{admin&&user?.role==='admin'&&<div><label htmlFor="report-board">板块</label><select id="report-board" value={board} onChange={e=>{setBoard(e.target.value);setPage(1);}}><option value="">全部板块</option>{boards.value?.items?.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></div>}</div>
    <Failure data={data}/><Feedback error={error} notice={notice}/>
    {data.value&&<><ul className="record-list">{data.value.items.map(r=><li key={r.id}><button className="text-button" onClick={()=>choose(r)}>{kindNames[r.target_type]||r.target_type} · {r.target_title||`#${r.target_id}`}</button><p>{states[r.state]||r.state} · {r.reason}</p><p className="muted"><Time value={r.created_at}/>{admin&&` · 举报人 ${r.reporter_nickname}`}</p></li>)}</ul>{data.value.items.length===0&&<p className="empty">暂无举报记录。</p>}<Pager page={page} total={data.value.total} onPage={setPage}/></>}
  </section>{chosen&&<Detail chosen={chosen} admin={admin} onDecided={refresh} onClose={()=>setChosen(null)}/>}</>;
}

export function ReportsPage({admin=false}){
  return admin?<AdminGuard><MyReports admin/></AdminGuard>:<Protected><MyReports admin={false}/></Protected>;
}

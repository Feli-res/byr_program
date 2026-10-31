'use client';
import {useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {request,jsonRequest} from '../../lib/api';
import {centsToYuan} from '../../lib/money.mjs';
import {Feedback,Protected} from '../auth';
import {Failure,Time} from '../shared/content';
import {useData} from '../../lib/use-data';
import {useDictionaries,states as goodsStates} from '../goods/common';
import {blankConditions,buildConditions,conditionSummary,ConditionFields,conditionsToForm,runStates,taskErrors,taskStates} from './common';

function Detail({subscriptionId}){
  const router=useRouter(),dictionary=useDictionaries();
  const data=useData(`reminder:${subscriptionId}`,()=>request(`/api/v1/subscriptions/${subscriptionId}`));
  const runs=useData(`reminder-runs:${subscriptionId}`,()=>request(`/api/v1/subscriptions/${subscriptionId}/runs?page_size=20`));
  const matches=useData(`reminder-matches:${subscriptionId}`,()=>request(`/api/v1/subscriptions/${subscriptionId}/matches?page_size=20`));
  const [editing,setEditing]=useState(false),[name,setName]=useState(''),[interval,setInterval]=useState('60'),[form,setForm]=useState(blankConditions()),[resume,setResume]=useState(false);
  const [busy,setBusy]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const item=data.value;
  async function startEdit(){
    if(!item)return;setBusy('edit');setError('');setNotice('');
    try{
      let current=item;
      if(current.state!=='paused'){
        current=await jsonRequest(`/api/v1/subscriptions/${subscriptionId}/state`,'PATCH',{state:'paused',version:current.config_version});
        data.setValue(current);
      }
      setName(current.name);setInterval(String(current.interval_minutes));setForm(conditionsToForm(current.conditions));setResume(false);setEditing(true);
      setNotice('任务已暂停，修改条件后由你决定是否恢复。');
    }catch(e){setError(e.message);}finally{setBusy('');}
  }
  async function save(e){
    e.preventDefault();if(!item)return;setBusy('save');setError('');setNotice('');
    try{
      const updated=await jsonRequest(`/api/v1/subscriptions/${subscriptionId}`,'PATCH',{name:name.trim(),original_query:item.original_query??null,conditions:buildConditions(form),interval_minutes:Number(interval),version:item.config_version,confirmed:true,resume_after_save:resume});
      data.setValue(updated);setEditing(false);setNotice(resume?'条件已保存，任务已恢复。':'条件已保存，任务保持暂停。');runs.reload();matches.reload();
    }catch(e){setError(e.message);}finally{setBusy('');}
  }
  async function change(state){
    if(!item)return;if(state==='paused'&&!window.confirm('暂停后不再检查商品；已经保存的提醒记录会保留。确认暂停？'))return;
    setBusy(state);setError('');setNotice('');
    try{const updated=await jsonRequest(`/api/v1/subscriptions/${subscriptionId}/state`,'PATCH',{state,version:item.config_version});data.setValue(updated);setNotice(state==='paused'?'任务已暂停。':'任务已恢复，会尽快检查一次。');}catch(e){setError(e.message);}finally{setBusy('');}
  }
  async function remove(){
    if(!item||!window.confirm('删除后不再产生新提醒，历史提醒记录保留。确认删除？'))return;
    setBusy('delete');setError('');
    try{await jsonRequest(`/api/v1/subscriptions/${subscriptionId}`,'DELETE',{version:item.config_version});router.push('/me/subscriptions');}catch(e){setError(e.message);setBusy('');}
  }
  const facts=conditionSummary(item?.conditions,dictionary.value);
  return <><nav className="forum-menu" aria-label="提醒导航"><Link href="/me/subscriptions">我的提醒</Link><Link href="/notifications">站内通知</Link></nav>
    <section className="panel"><Failure data={dictionary}/><Failure data={data}/><Feedback error={error} notice={notice}/>
      {item&&<>
        <div className="panel-heading"><div><h1>{item.name}</h1><p className="muted">每 {item.interval_minutes} 分钟检查一次 · 已提醒 {item.match_count} 件商品</p></div><span className={`tag ${item.state==='error'?'warning':''}`}>{taskStates[item.state]||item.state}</span></div>
        {item.original_query&&<p className="muted">原始需求：{item.original_query}</p>}
        <dl className="reminder-facts"><div><dt>最近检查</dt><dd>{item.last_checked_at?<Time value={item.last_checked_at}/>:'尚未检查'}</dd></div><div><dt>下次检查</dt><dd>{item.next_due_at?<Time value={item.next_due_at}/>:'暂停中'}</dd></div></dl>
        {item.last_error_code&&<p className="message error" role="status">最近异常：{taskErrors[item.last_error_code]||'检查未成功'}</p>}
        <h2>保存的条件</h2><dl className="reminder-facts">{facts.length?facts.map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>):<div><dt>条件</dt><dd>无</dd></div>}</dl>
        {!editing&&<div className="actions"><button className="secondary" disabled={busy!==''} onClick={startEdit}>{item.state==='paused'?'编辑条件':'暂停并编辑'}</button>{item.state==='active'?<button className="secondary" disabled={busy!==''} onClick={()=>change('paused')}>暂停</button>:<button disabled={busy!==''} onClick={()=>change('active')}>恢复</button>}<button className="danger-button" disabled={busy!==''} onClick={remove}>删除</button></div>}
        {editing&&<form className="reminder-form" onSubmit={save}><h2>编辑条件</h2><p className="hint">任务已暂停；保存后如果勾选“保存后恢复”，才会重新开始检查。</p>
          <div className="goods-form-grid"><div><label htmlFor="edit-reminder-name">名称</label><input id="edit-reminder-name" value={name} maxLength={100} required onChange={e=>setName(e.target.value)}/></div><div><label htmlFor="edit-reminder-interval">检查周期（分钟）</label><input id="edit-reminder-interval" inputMode="numeric" value={interval} onChange={e=>setInterval(e.target.value)}/></div></div>
          <ConditionFields idPrefix="edit-reminder" value={form} onChange={setForm} dictionaries={dictionary.value} disabled={busy==='save'}/>
          <label className="check-label"><input type="checkbox" checked={resume} onChange={e=>setResume(e.target.checked)}/>保存后恢复检查</label>
          <div className="actions"><button disabled={busy==='save'}>{busy==='save'?'正在保存…':'保存条件'}</button><button type="button" className="secondary" disabled={busy==='save'} onClick={()=>{setEditing(false);setNotice('任务保持暂停，可稍后恢复。');}}>取消编辑</button></div>
        </form>}
        <h2>最近检查记录</h2><Failure data={runs}/>{runs.value?.items?.length?<ul className="reminder-runs">{runs.value.items.map(run=><li key={run.id}><span>{runStates[run.state]||run.state}</span><span>第 {run.attempt_no+1} 次尝试</span><span><Time value={run.started_at}/></span>{run.error_code&&<span className="muted">{taskErrors[run.error_code]||run.error_code}</span>}</li>)}</ul>:<p className="empty">暂无检查记录。</p>}
        <h2>已提醒的商品</h2><Failure data={matches}/>{matches.value?.items?.length?<ul className="reminder-matches">{matches.value.items.map(match=><li key={match.id}>{match.goods?<><Link href={`/goods/${match.goods.id}`}>{match.goods.title}</Link><span className="muted">{match.goods.price_cents===0?'免费':`¥ ${centsToYuan(match.goods.price_cents)}`} · {goodsStates[match.goods.state]||match.goods.state}</span><Time value={match.created_at}/></>:<><span>商品已不可访问</span><Time value={match.created_at}/></>}</li>)}</ul>:<p className="empty">还没有提醒过商品。新商品符合条件后会出现在这里，并收到站内通知。</p>}
      </>}
    </section></>;
}

export function ReminderDetail({subscriptionId}){return <Protected><Detail subscriptionId={subscriptionId}/></Protected>;}

'use client';
import {useState} from 'react';
import Link from 'next/link';
import {request,jsonRequest} from '../../lib/api';
import {Feedback,Protected} from '../auth';
import {Failure,Time} from '../shared/content';
import {useData} from '../../lib/use-data';
import {useDictionaries} from '../goods/common';
import {blankConditions,buildConditions,ConditionFields,taskErrors,taskStates} from './common';

const intervals=[[5,'5 分钟'],[15,'15 分钟'],[30,'30 分钟'],[60,'1 小时'],[180,'3 小时'],[360,'6 小时'],[720,'12 小时'],[1440,'1 天']];

function ReminderList(){
  const dictionary=useDictionaries();
  const data=useData('reminders:list',()=>request('/api/v1/subscriptions?page_size=50'));
  const [open,setOpen]=useState(false),[name,setName]=useState(''),[interval,setInterval]=useState('60'),[form,setForm]=useState(blankConditions());
  const [busy,setBusy]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const items=data.value?.items||[];
  const limitReached=items.length>=10;
  function reset(){setName('');setInterval('60');setForm(blankConditions());}
  async function create(e){
    e.preventDefault();setBusy('create');setError('');setNotice('');
    try{
      await jsonRequest('/api/v1/subscriptions','POST',{name:name.trim(),original_query:null,conditions:buildConditions(form),interval_minutes:Number(interval),confirmed:true});
      reset();setOpen(false);setNotice('提醒已保存，后台会按周期检查商品。');data.reload();
    }catch(e){setError(e.message);}finally{setBusy('');}
  }
  async function change(item,state){
    if(state==='paused'&&!window.confirm('暂停后不再检查商品；已经保存的提醒记录会保留。确认暂停？'))return;
    setBusy(item.id);setError('');setNotice('');
    try{await jsonRequest(`/api/v1/subscriptions/${item.id}/state`,'PATCH',{state,version:item.config_version});data.reload();setNotice(state==='paused'?'任务已暂停。':'任务已恢复，会尽快检查一次。');}catch(e){setError(e.message);}finally{setBusy('');}
  }
  async function remove(item){
    if(!window.confirm('删除后不再产生新提醒，历史提醒记录保留。确认删除？'))return;
    setBusy(item.id);setError('');setNotice('');
    try{await jsonRequest(`/api/v1/subscriptions/${item.id}`,'DELETE',{version:item.config_version});data.reload();setNotice('任务已删除。');}catch(e){setError(e.message);}finally{setBusy('');}
  }
  return <><nav className="forum-menu" aria-label="提醒导航"><Link href="/me/subscriptions" aria-current="page">我的提醒</Link><Link href="/goods">去逛商品</Link><Link href="/notifications">站内通知</Link></nav>
    <section className="panel"><div className="panel-heading"><div><h1>我的商品提醒</h1><p className="muted">保存需求后，网站每隔一段时间检查新发布或有更新的在售商品；同一商品只提醒一次。</p></div><span className="muted">已保存 {items.length} / 10 个</span></div>
      <Failure data={dictionary}/><Failure data={data}/><Feedback error={error} notice={notice}/>
      {limitReached?<p className="message">最多保存 10 个提醒，请先删除不再使用的任务。</p>:<div className="actions"><button onClick={()=>setOpen(!open)} disabled={busy==='create'}>{open?'收起新建表单':'新建提醒'}</button><Link className="button secondary" href="/goods">从商品页选择条件</Link></div>}
      {open&&!limitReached&&<form className="reminder-form" onSubmit={create}>
        <h2>新建提醒</h2>
        <div className="goods-form-grid"><div><label htmlFor="reminder-name">名称</label><input id="reminder-name" value={name} maxLength={100} required onChange={e=>setName(e.target.value)} placeholder="例如：2500 元以内的平板"/></div><div><label htmlFor="reminder-interval">检查周期</label><select id="reminder-interval" value={interval} onChange={e=>setInterval(e.target.value)}>{intervals.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></div></div>
        <ConditionFields idPrefix="new-reminder" value={form} onChange={setForm} dictionaries={dictionary.value} disabled={busy==='create'}/>
        <p className="hint">空项表示不限制。至少填写一个条件；价格单位为元，最多两位小数。条件保存后不会每次重新请 AI 理解。</p>
        <div className="actions"><button disabled={busy==='create'||!name.trim()}>{busy==='create'?'正在保存…':'保存提醒'}</button><button type="button" className="secondary" disabled={busy==='create'} onClick={reset}>清空条件</button></div>
      </form>}
      {data.value&&items.length===0&&<p className="empty">还没有提醒任务。可以在这里新建，也可以在“AI 帮你找商品”确认条件后保存。</p>}
      {items.length>0&&<ul className="reminder-list">{items.map(item=><li key={item.id} className="reminder-card">
        <div className="panel-heading"><h2><Link href={`/me/subscriptions/${item.id}`}>{item.name}</Link></h2><span className={`tag ${item.state==='error'?'warning':''}`}>{taskStates[item.state]||item.state}</span></div>
        <p className="muted">每 {item.interval_minutes} 分钟检查一次 · 已提醒 {item.match_count} 件商品</p>
        <p>最近检查：{item.last_checked_at?<Time value={item.last_checked_at}/>:'尚未检查'} · 下次检查：{item.next_due_at?<Time value={item.next_due_at}/>:'暂停中'}</p>
        {item.last_error_code&&<p className="message error" role="status">最近异常：{taskErrors[item.last_error_code]||'检查未成功'}</p>}
        <div className="actions"><Link className="button secondary" href={`/me/subscriptions/${item.id}`}>查看条件与记录</Link>{item.state==='active'?<button className="secondary" disabled={busy===item.id} onClick={()=>change(item,'paused')}>暂停</button>:<button disabled={busy===item.id} onClick={()=>change(item,'active')}>恢复</button>}<button className="danger-button" disabled={busy===item.id} onClick={()=>remove(item)}>删除</button></div>
      </li>)}</ul>}
    </section></>;
}

export function Reminders(){return <Protected><ReminderList/></Protected>;}

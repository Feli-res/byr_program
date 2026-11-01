'use client';
import {useState} from 'react';
import {jsonRequest,request} from '../../lib/api';
import {Feedback} from '../auth';
import {Failure,Time,Pager} from '../shared/content';
import {useData} from '../../lib/use-data';
import {AdminGuard} from './common';

const taskStates={active:'运行中',paused:'已暂停',error:'异常'};

function Tasks(){
  const [page,setPage]=useState(1),[filter,setFilter]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const data=useData(`admin-tasks:${page}:${filter}`,()=>request(`/api/v1/admin/subscriptions?page=${page}${filter?'&state='+filter:''}`));
  async function pause(task){
    const why=window.prompt(`暂停 ${task.owner_label} 的提醒任务，请填写原因（不会修改对方条件）：`);
    if(why===null)return;
    if(!why.trim()){setError('暂停任务必须填写原因');return;}
    setBusy(true);setError('');setNotice('');
    try{await jsonRequest(`/api/v1/admin/subscriptions/${task.id}/pause`,'POST',{reason:why});data.reload();setNotice('任务已暂停。');}catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <section className="panel"><div className="panel-heading"><h1>提醒任务</h1><span className="muted">只显示脱敏运行信息</span></div>
    <p className="muted">这里不显示用户的条件、原始需求或匹配历史；管理员只能暂停异常或运行中的任务，不能替用户修改条件。</p>
    <div className="filter-fields"><div><label htmlFor="task-state">状态</label><select id="task-state" value={filter} onChange={e=>{setFilter(e.target.value);setPage(1);}}><option value="">全部</option>{Object.entries(taskStates).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></div></div>
    <Failure data={data}/><Feedback error={error} notice={notice}/>
    {data.value&&<><ul className="record-list">{data.value.items.map(t=><li key={t.id}><div className="topic-title"><span>{t.owner_label} 的任务 #{t.id}</span><span className={`tag ${t.state==='error'?'warning':''}`}>{taskStates[t.state]||t.state}</span></div><p className="muted">周期 {t.interval_minutes} 分钟 · 上次检查 {t.last_checked_at?<Time value={t.last_checked_at}/>:'尚未检查'} · 下次 {t.next_due_at?<Time value={t.next_due_at}/>:'未安排'}{t.last_error_code&&` · 错误 ${t.last_error_code}`}</p>{['active','error'].includes(t.state)&&<div className="actions"><button className="secondary" disabled={busy} onClick={()=>pause(t)}>暂停任务</button></div>}</li>)}</ul>{data.value.items.length===0&&<p className="empty">暂无任务。</p>}<Pager page={page} total={data.value.total} onPage={setPage}/></>}
  </section>;
}

export function TasksPage(){return <AdminGuard adminOnly><Tasks/></AdminGuard>;}

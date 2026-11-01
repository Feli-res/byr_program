'use client';
import {useState} from 'react';
import {request,jsonRequest} from '../../lib/api';
import {Feedback} from '../auth';
import {Failure,Time,Pager} from '../shared/content';
import {useData} from '../../lib/use-data';
import {AdminGuard} from './common';

const stateNames={draft:'草稿',published:'已发布',retracted:'已撤回'};

export function AnnouncementsAdmin(){
  const [page,setPage]=useState(1),[filter,setFilter]=useState(''),[selected,setSelected]=useState(null),[creating,setCreating]=useState(false);
  const [title,setTitle]=useState(''),[body,setBody]=useState(''),[reason,setReason]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const data=useData(`admin-announcements:${page}:${filter}`,()=>request(`/api/v1/admin/announcements?page=${page}${filter?'&state='+filter:''}`));
  function reset(){setSelected(null);setCreating(false);setTitle('');setBody('');setReason('');setError('');}
  async function choose(row){setError('');setNotice('');try{const value=await request(`/api/v1/admin/announcements/${row.id}`);setSelected(value);setCreating(false);setTitle(value.title);setBody(value.body_markdown);setReason('');}catch(e){setError(e.message);}}
  async function save(){
    setBusy(true);setError('');setNotice('');
    try{
      if(creating){await jsonRequest('/api/v1/admin/announcements','POST',{title,body_markdown:body});}
      else if(selected){await jsonRequest(`/api/v1/admin/announcements/${selected.id}`,'PATCH',{action:'save',version:selected.version,title,body_markdown:body,reason});}
      else return;
      reset();data.reload();setNotice('公告已保存为草稿或已更新。');
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function change(action){
    if(!selected)return;
    if(!reason.trim()){setError('发布或撤回必须填写原因');return;}
    setBusy(true);setError('');setNotice('');
    try{await jsonRequest(`/api/v1/admin/announcements/${selected.id}`,'PATCH',{action,version:selected.version,reason});reset();data.reload();setNotice(action==='publish'?'公告已发布。':'公告已撤回。');}catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <section className="panel"><div className="panel-heading"><h1>公告管理</h1><button onClick={()=>{reset();setCreating(true);}}>新建公告</button></div>
    <p className="muted">草稿不公开；发布后出现在首页和公告页；已发布内容修改前需先撤回。</p>
    <div className="filter-fields"><div><label htmlFor="announcement-filter">状态</label><select id="announcement-filter" value={filter} onChange={e=>{setFilter(e.target.value);setPage(1);}}><option value="">全部</option>{Object.entries(stateNames).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></div></div>
    <Failure data={data}/><Feedback error={error} notice={notice}/>
    {data.value&&<><ul className="record-list">{data.value.items.map(a=><li key={a.id}><button className="text-button" onClick={()=>choose(a)}>{a.title}</button><p>{stateNames[a.state]||a.state} · 版本 {a.version} · 创建人 {a.created_by}</p><p className="muted"><Time value={a.published_at||a.created_at}/></p></li>)}</ul>{data.value.items.length===0&&<p className="empty">暂无公告。</p>}<Pager page={page} total={data.value.total} onPage={setPage}/></>}
    {(creating||selected)&&<div className="moderation-box"><h2>{creating?'新建公告草稿':`编辑公告 #${selected.id}`}</h2>
      <label htmlFor="announcement-title">标题</label><input id="announcement-title" value={title} onChange={e=>setTitle(e.target.value)} maxLength={100} disabled={busy||selected?.state==='published'}/>
      <label htmlFor="announcement-body">正文（Markdown）</label><textarea id="announcement-body" rows={10} value={body} onChange={e=>setBody(e.target.value)} maxLength={20000} disabled={busy||selected?.state==='published'}/>
      {selected?.state==='published'&&<p className="hint">已发布公告不能直接修改，请先撤回。</p>}
      <label htmlFor="announcement-reason">操作原因（发布或撤回必填）</label><input id="announcement-reason" value={reason} onChange={e=>setReason(e.target.value)} maxLength={1000} disabled={busy}/>
      <div className="actions"><button disabled={busy||!title.trim()||!body.trim()||selected?.state==='published'} onClick={save}>{creating?'保存草稿':'保存修改'}</button>{selected&&selected.state!=='published'&&<button disabled={busy||!reason.trim()} onClick={()=>change('publish')}>发布</button>}{selected?.state==='published'&&<button className="secondary" disabled={busy||!reason.trim()} onClick={()=>change('retract')}>撤回</button>}<button className="secondary" disabled={busy} onClick={reset}>取消</button></div>
    </div>}
  </section>;
}

export function AnnouncementsPage(){return <AdminGuard adminOnly><AnnouncementsAdmin/></AdminGuard>;}

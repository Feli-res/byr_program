'use client';
import {useState} from 'react';
import {jsonRequest,request} from '../../lib/api';
import {Feedback} from '../auth';
import {Failure} from '../shared/content';
import {useData} from '../../lib/use-data';
import {AdminGuard} from './common';

function BoardRow({board,onSaved}){
  const [name,setName]=useState(board.name),[description,setDescription]=useState(board.description),[enabled,setEnabled]=useState(board.enabled),[reason,setReason]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  async function save(){
    if(!reason.trim()){setError('请填写操作原因');return;}
    setBusy(true);setError('');setNotice('');
    try{await jsonRequest(`/api/v1/admin/boards/${board.id}`,'PATCH',{version:board.version,reason,name,description,enabled});setNotice('板块已保存');onSaved();}catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <article className="managed-user"><h2 className="managed-heading"><span className="managed-identity"><span className="managed-label">板块</span>{board.name}</span><span className="tag">{enabled?'启用':'已停用'}</span></h2>
    <p className="muted">编号 #{board.id} · 帖子 {board.post_count} · 版本 {board.version}</p>
    <div className="management-fields"><label htmlFor={`board-name-${board.id}`}>名称</label><input id={`board-name-${board.id}`} value={name} onChange={e=>setName(e.target.value)} maxLength={30} disabled={busy}/><label htmlFor={`board-desc-${board.id}`}>说明</label><input id={`board-desc-${board.id}`} value={description} onChange={e=>setDescription(e.target.value)} maxLength={300} disabled={busy}/><label className="check-label"><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)} disabled={busy}/>启用（停用后不能新发帖，历史帖仍可读）</label><label htmlFor={`board-reason-${board.id}`}>操作原因</label><input id={`board-reason-${board.id}`} value={reason} onChange={e=>setReason(e.target.value)} maxLength={1000} disabled={busy}/></div>
    <div className="actions"><button disabled={busy||!reason.trim()} onClick={save}>保存板块</button></div><Feedback error={error} notice={notice}/></article>;
}

function Boards(){
  const [name,setName]=useState(''),[description,setDescription]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const data=useData('admin-boards',()=>request('/api/v1/admin/boards?page_size=100'));
  async function create(e){e.preventDefault();setBusy(true);setError('');setNotice('');try{await jsonRequest('/api/v1/admin/boards','POST',{name,description});setName('');setDescription('');data.reload();setNotice('板块已创建。');}catch(e){setError(e.message);}finally{setBusy(false);}}
  return <section className="panel"><div className="panel-heading"><h1>板块管理</h1></div><p className="muted">停用板块不会删除历史帖子；重新启用后可继续发帖。</p>
    <form onSubmit={create}><div className="filter-fields"><div><label htmlFor="new-board-name">新板块名称</label><input id="new-board-name" value={name} onChange={e=>setName(e.target.value)} maxLength={30} required/></div><div><label htmlFor="new-board-desc">说明</label><input id="new-board-desc" value={description} onChange={e=>setDescription(e.target.value)} maxLength={300}/></div></div><div className="actions"><button disabled={busy||!name.trim()}>新建板块</button></div></form>
    <Feedback error={error} notice={notice}/><Failure data={data}/>
    {data.value?.items?.map(board=><BoardRow key={`${board.id}:${board.version}`} board={board} onSaved={data.reload}/>)}
    {data.value&&data.value.items.length===0&&<p className="empty">暂无板块。</p>}
  </section>;
}

export function BoardsPage(){return <AdminGuard adminOnly><Boards/></AdminGuard>;}

'use client';
import {useEffect,useState} from 'react';
import {jsonRequest,request} from '../../../lib/api';
import {Feedback,Protected,useAuth} from '../../../components/auth';
const roleNames={user:'普通用户',moderator:'版主',admin:'管理员'};
function UserRow({user,boards,onSaved,number,expanded,onToggle}){
  const [role,setRole]=useState(user.role),[selected,setSelected]=useState(user.board_ids),[reason,setReason]=useState('');
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[credential,setCredential]=useState(null),[busy,setBusy]=useState(false);
  useEffect(()=>{setRole(user.role);setSelected(user.board_ids);},[user.version,user.role,user.board_ids]);
  async function act(kind){
    setError('');setNotice('');if(!reason.trim()){setError('请填写操作原因');return;}
    if(kind==='password-reset'&&!window.confirm(`为“${user.nickname}”签发重置凭据并使其旧登录失效？`))return;
    setBusy(true);
    try{
      const data={version:user.version,reason};
      if(kind==='role'){data.role=role;data.board_ids=role==='moderator'?selected:[];}
      if(kind==='status')data.status=user.status==='active'?'banned':'active';
      const value=await jsonRequest(`/api/v1/admin/users/${user.id}/${kind}`,kind==='password-reset'?'POST':'PATCH',data);
      if(kind==='password-reset')setCredential(value);
      setNotice('操作已保存');await onSaved();
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <article className="managed-user" data-user-id={user.id}>
    <h2 className="managed-heading"><button type="button" className="managed-toggle" aria-expanded={expanded} aria-controls={`user-details-${user.id}`} onClick={onToggle}>
      <span className="managed-number">{number}</span><span className="managed-identity"><span className="managed-label">账号</span>{user.account}</span><span className="managed-identity"><span className="managed-label">昵称</span>{user.nickname}</span><span className="managed-chevron" aria-hidden="true">{expanded?'−':'+'}</span>
    </button></h2>
    <div id={`user-details-${user.id}`} className="managed-details" hidden={!expanded}>
    <p className="muted">{roleNames[user.role]} · {user.status==='active'?'正常':'已封禁'}{user.password_reset_required?' · 待重置密码':''} · 用户编号 #{user.id}</p>
    <div className="management-fields"><label htmlFor={`role-${user.id}`}>角色</label><select id={`role-${user.id}`} value={role} onChange={e=>setRole(e.target.value)} disabled={busy}><option value="user">普通用户</option><option value="moderator">版主</option><option value="admin">管理员</option></select></div>
    {role==='moderator'&&<fieldset disabled={busy}><legend>可管理的板块</legend>{boards.map(b=><label className="check-label" key={b.id}><input type="checkbox" checked={selected.includes(b.id)} onChange={e=>setSelected(e.target.checked?[...selected,b.id]:selected.filter(id=>id!==b.id))}/>{b.name}</label>)}</fieldset>}
    <label htmlFor={`reason-${user.id}`}>操作原因</label><input id={`reason-${user.id}`} value={reason} onChange={e=>setReason(e.target.value)} placeholder="填写本次授权、封禁或重置的原因" disabled={busy}/>
    <div className="actions"><button onClick={()=>act('role')} disabled={busy}>保存角色</button><button className="secondary" onClick={()=>act('status')} disabled={busy}>{user.status==='active'?'封禁账号':'解除封禁'}</button><button className="secondary" onClick={()=>act('password-reset')} disabled={busy}>签发重置凭据</button></div>
    {credential&&<section className="credential-box"><h3>一次性重置凭据</h3><p>仅在本页显示。请在核实身份后交给对应用户，不要发布到帖子或聊天群。</p><label htmlFor={`credential-${user.id}`}>重置凭据</label><input id={`credential-${user.id}`} value={credential.credential} readOnly autoComplete="off"/><p className="hint">有效至 {new Date(credential.expires_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}，用户在“使用凭据重置密码”页面设置新密码。</p><button className="secondary" onClick={()=>setCredential(null)}>关闭凭据显示</button></section>}
    <Feedback error={error} notice={notice}/>
    </div>
  </article>;
}
function Users(){
  const {refresh}=useAuth();const [data,setData]=useState(null),[boards,setBoards]=useState([]),[page,setPage]=useState(1),[error,setError]=useState('');
  const [mode,setMode]=useState('multiple'),[expanded,setExpanded]=useState([]);
  async function load(){setError('');try{const [users,list]=await Promise.all([request(`/api/v1/admin/users?page=${page}&page_size=20`),request('/api/v1/boards')]);setData(users);setBoards(list.items);}catch(e){setError(e.message);}}
  useEffect(()=>{load();},[page]);
  async function saved(){await load();await refresh();}
  function toggle(id){setExpanded(old=>old.includes(id)?old.filter(value=>value!==id):mode==='single'?[id]:[...old,id]);}
  function changeMode(value){setMode(value);if(value==='single')setExpanded(old=>old.slice(-1));}
  function changePage(value){setExpanded([]);setData(null);setPage(value);}
  return <section className="panel"><div className="panel-heading"><h1>账户管理</h1><button className="secondary" onClick={load}>重新读取</button></div><p className="muted">授权、封禁和密码重置都会记录操作原因。重置或封禁会使该用户原有登录失效。</p><Feedback error={error}/>
    <fieldset className="expand-mode"><legend>展开方式</legend><label className="check-label"><input type="radio" name="expand-mode" value="multiple" checked={mode==='multiple'} onChange={()=>changeMode('multiple')}/>多项展开</label><label className="check-label"><input type="radio" name="expand-mode" value="single" checked={mode==='single'} onChange={()=>changeMode('single')}/>单项展开</label></fieldset>
    <p className="hint">按注册先后排列。点击账号行查看或收起管理操作。</p>
    {!data?<p>正在读取用户…</p>:<>{data.items.map((user,index)=><UserRow key={user.id} user={user} boards={boards} onSaved={saved} number={(page-1)*20+index+1} expanded={expanded.includes(user.id)} onToggle={()=>toggle(user.id)}/>)}<div className="actions"><button className="secondary" disabled={page===1} onClick={()=>changePage(page-1)}>上一页</button><span>第 {page} 页，共 {data.total} 个用户</span><button className="secondary" disabled={page*20>=data.total} onClick={()=>changePage(page+1)}>下一页</button></div></>}
  </section>;
}
export default function Page(){return <Protected admin><Users/></Protected>;}

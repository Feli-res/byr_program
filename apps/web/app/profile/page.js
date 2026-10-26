'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {jsonRequest,request} from '../../lib/api';
import {Feedback,Protected,useAuth} from '../../components/auth';
const roles={user:'普通用户',moderator:'版主',admin:'管理员'};
function Profile(){
  const {user,refresh}=useAuth();const [nickname,setNickname]=useState(user.nickname),[bio,setBio]=useState(user.bio),[file,setFile]=useState(null),[staged,setStaged]=useState(null),[remove,setRemove]=useState(false);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  useEffect(()=>{setNickname(user.nickname);setBio(user.bio);},[user.id,user.version,user.nickname,user.bio]);
  async function submit(e){e.preventDefault();setBusy(true);setError('');setNotice('');
    try{
      let avatar=staged;
      if(file&&!avatar){const data=new FormData();data.append('purpose','avatar');data.append('file',file);avatar=(await request('/api/v1/files',{method:'POST',body:data})).id;setStaged(avatar);}
      const data={nickname,bio,version:user.version};if(remove)data.avatar_file_id=null;else if(avatar)data.avatar_file_id=avatar;
      await jsonRequest('/api/v1/me','PATCH',data);setFile(null);setStaged(null);setRemove(false);await refresh();setNotice('个人资料已保存');
    }catch(e){setError(e.message);}finally{setBusy(false);}}
  async function pick(e){const chosen=e.target.files?.[0]||null;if(staged){try{await request(`/api/v1/files/${staged}`,{method:'DELETE'});}catch(error){setError(error.message);return;}}setFile(chosen);setStaged(null);setRemove(false);}
  return <section className="panel"><div className="panel-heading"><h1>个人资料</h1><span className="tag">{roles[user.role]}</span></div>
    <dl className="account-summary"><div><dt>账号</dt><dd>{user.account}</dd></div><div><dt>用户编号</dt><dd>{user.id}</dd></div><div><dt>本次登录有效至</dt><dd>{new Date(user.session_expires_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}</dd></div></dl>
    <form onSubmit={submit} className="profile-form">
      <label htmlFor="nickname">昵称</label><input id="nickname" value={nickname} onChange={e=>setNickname(e.target.value)} disabled={busy} required/>
      <label htmlFor="bio">简介</label><textarea id="bio" rows={3} value={bio} onChange={e=>setBio(e.target.value)} disabled={busy}/><p className="hint">昵称 2～20 个字符，简介最多 300 个字符。</p>
      <label htmlFor="avatar">头像</label>{user.avatar_url&&<img className="avatar" src={user.avatar_url} alt="当前头像" width="80" height="80"/>}
      <input key={user.version} id="avatar" type="file" accept="image/png,image/jpeg,image/webp" onChange={pick} disabled={busy}/><p className="hint">JPEG、PNG 或 WebP，不超过 2 MiB，最长边不超过 4096 像素。新头像在点击保存后生效。</p>
      {user.avatar_url&&<label className="check-label"><input type="checkbox" checked={remove} onChange={e=>setRemove(e.target.checked)} disabled={busy||!!file}/>移除现有头像</label>}
      <div className="actions"><button disabled={busy}>{busy?'正在保存…':'保存资料'}</button><button type="button" className="secondary" disabled={busy} onClick={refresh}>重新读取资料</button><Link href="/change-password">修改密码</Link></div>
    </form><Feedback error={error} notice={notice}/>
  </section>;
}
export default function Page(){return <Protected><Profile/></Protected>;}

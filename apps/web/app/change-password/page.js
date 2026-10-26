'use client';
import {useState} from 'react';
import {useRouter} from 'next/navigation';
import {jsonRequest} from '../../lib/api';
import {Feedback,Protected,useAuth} from '../../components/auth';
function ChangePassword(){
  const router=useRouter(),{refresh}=useAuth();const [current,setCurrent]=useState(''),[password,setPassword]=useState(''),[confirm,setConfirm]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  async function submit(e){e.preventDefault();setError('');if(password!==confirm){setError('两次新密码不一致');setPassword('');setConfirm('');return;}setBusy(true);
    try{await jsonRequest('/api/v1/me/password','POST',{current_password:current,new_password:password});await refresh();router.replace('/login');}catch(e){setError(e.message);}finally{setCurrent('');setPassword('');setConfirm('');setBusy(false);}}
  return <section className="panel account-panel"><div className="panel-heading"><h1>修改密码</h1></div><p>修改后，当前账号在所有浏览器中的登录状态都会失效，请重新登录。</p><form onSubmit={submit}>
    <label htmlFor="current-password">原密码</label><input id="current-password" type="password" autoComplete="current-password" value={current} onChange={e=>setCurrent(e.target.value)} required disabled={busy}/>
    <label htmlFor="new-password">新密码</label><input id="new-password" type="password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} required disabled={busy}/>
    <label htmlFor="confirm-password">确认新密码</label><input id="confirm-password" type="password" autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} required disabled={busy}/>
    <div className="actions"><button disabled={busy}>{busy?'正在修改…':'修改并重新登录'}</button></div>
  </form><Feedback error={error}/></section>;
}
export default function Page(){return <Protected><ChangePassword/></Protected>;}

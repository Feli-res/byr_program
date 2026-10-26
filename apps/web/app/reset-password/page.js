'use client';
import {useState} from 'react';
import Link from 'next/link';
import {jsonRequest} from '../../lib/api';
import {Feedback,useAuth} from '../../components/auth';
export default function Reset(){
  const {user}=useAuth();const [credential,setCredential]=useState(''),[password,setPassword]=useState(''),[confirm,setConfirm]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  async function submit(e){e.preventDefault();setError('');setNotice('');if(password!==confirm){setError('两次新密码不一致');setPassword('');setConfirm('');return;}setBusy(true);
    try{await jsonRequest('/api/v1/auth/reset-password','POST',{credential,new_password:password});setCredential('');setNotice('密码已重置，请使用新密码登录');}catch(e){setError(e.message);}finally{setPassword('');setConfirm('');setBusy(false);}}
  return <section className="panel account-panel"><div className="panel-heading"><h1>使用凭据重置密码</h1></div><p>请先联系管理员核实身份，获取一次性凭据。凭据有效期最长 30 分钟，使用后立即失效。</p>{user?<p>当前已登录，请使用“修改密码”，或先退出当前账号。</p>:<form onSubmit={submit}>
    <label htmlFor="credential">一次性重置凭据</label><input id="credential" autoComplete="off" value={credential} onChange={e=>setCredential(e.target.value)} required disabled={busy||!!notice}/>
    <label htmlFor="new-password">新密码</label><input id="new-password" type="password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} required disabled={busy||!!notice}/>
    <label htmlFor="confirm-password">确认新密码</label><input id="confirm-password" type="password" autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} required disabled={busy||!!notice}/>
    <div className="actions"><button disabled={busy||!!notice}>{busy?'正在重置…':'重置密码'}</button><Link href="/login">返回登录</Link></div>
  </form>}<Feedback error={error} notice={notice}/></section>;
}

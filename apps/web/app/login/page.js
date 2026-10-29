'use client';
import {useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {jsonRequest} from '../../lib/api';
import {Feedback,useAuth} from '../../components/auth';
export default function Login(){
  const router=useRouter(),{user,refresh}=useAuth();const [account,setAccount]=useState(''),[password,setPassword]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  async function submit(e){e.preventDefault();setBusy(true);setError('');try{await jsonRequest('/api/v1/auth/login','POST',{account,password});const current=await refresh();if(current)router.replace('/profile');else setError('登录后的身份读取失败，请重新确认服务状态');}catch(e){setError(e.message);}finally{setPassword('');setBusy(false);}}
  return <section className="panel account-panel"><div className="panel-heading"><h1>登录邮智汇</h1></div>{user?<p>当前已登录。<Link href="/profile">查看个人资料</Link></p>:<form onSubmit={submit}>
    <label htmlFor="account">账号</label><input id="account" autoComplete="username" autoCapitalize="none" autoCorrect="off" spellCheck={false} aria-describedby="login-account-hint" value={account} onChange={e=>setAccount(e.target.value)} required disabled={busy}/><p id="login-account-hint" className="hint">账号区分大小写，请与注册时保持一致。</p>
    <label htmlFor="password">密码</label><input id="password" type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required disabled={busy}/>
    <div className="actions"><button disabled={busy}>{busy?'正在登录…':'登录'}</button><Link href="/register">注册新账号</Link><Link href="/reset-password">使用重置凭据改密</Link></div>
    <p className="hint">忘记密码时，请联系管理员核实后获取一次性重置凭据。</p>
  </form>}<Feedback error={error}/></section>;
}

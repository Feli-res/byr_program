'use client';
import {useState} from 'react';
import Link from 'next/link';
import {jsonRequest} from '../../lib/api';
import {Feedback,useAuth} from '../../components/auth';
export default function Register(){
  const {user}=useAuth();const [account,setAccount]=useState(''),[nickname,setNickname]=useState(''),[password,setPassword]=useState(''),[confirm,setConfirm]=useState('');
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  async function submit(e){e.preventDefault();setError('');setNotice('');if(password!==confirm){setError('两次密码不一致');setPassword('');setConfirm('');return;}setBusy(true);
    try{await jsonRequest('/api/v1/auth/register','POST',{account,nickname,password});setNotice('注册成功，请使用新账号登录');}catch(e){setError(e.message);}finally{setPassword('');setConfirm('');setBusy(false);}}
  return <section className="panel account-panel"><div className="panel-heading"><h1>注册邮智汇账号</h1></div><p className="muted">使用平台自主账号，无需校园门户密码。</p>{user?<p>请先退出当前账号，再注册其他账号。</p>:<form onSubmit={submit}>
    <label htmlFor="account">账号</label><input id="account" autoComplete="username" value={account} onChange={e=>setAccount(e.target.value)} required disabled={busy||!!notice}/><p className="hint">4～24 位字母、数字或下划线，首位为字母；不区分大小写。</p>
    <label htmlFor="nickname">昵称</label><input id="nickname" autoComplete="nickname" value={nickname} onChange={e=>setNickname(e.target.value)} required disabled={busy||!!notice}/><p className="hint">2～20 个字符，将显示给其他用户。</p>
    <label htmlFor="password">密码</label><input id="password" type="password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} required disabled={busy||!!notice}/><p className="hint">8～64 个字符，空格属于密码的一部分。</p>
    <label htmlFor="confirm">确认密码</label><input id="confirm" type="password" autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} required disabled={busy||!!notice}/>
    <div className="actions"><button disabled={busy||!!notice}>{busy?'正在注册…':'注册账号'}</button><Link href="/login">已有账号，前往登录</Link></div>
  </form>}<Feedback error={error} notice={notice}/></section>;
}

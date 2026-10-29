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
    <label htmlFor="account">账号</label><input id="account" autoComplete="username" autoCapitalize="none" autoCorrect="off" spellCheck={false} aria-describedby="account-hint" value={account} onChange={e=>setAccount(e.target.value)} required disabled={busy||!!notice}/><p id="account-hint" className="hint">4～24 位，首位为英文字母；区分大小写。</p>
    <details className="account-rules"><summary>查看账号规则</summary><ul>
      <li>长度为 4～24 位，首位必须是英文字母。</li>
      <li>只能使用英文字母 A～Z、a～z、数字 0～9 和下划线 _。</li>
      <li>不能使用中文、账号中间的空格、连字符或其他符号；首尾空白会自动去除。</li>
      <li>账号区分大小写，例如 TestUser001 与 testuser001 是两个不同的账号；登录时请保持注册时的大小写。</li>
      <li>完全相同的账号不能重复注册。</li>
      <li>昵称与登录账号分开设置，昵称可以使用中文。</li>
    </ul></details>
    <label htmlFor="nickname">昵称</label><input id="nickname" autoComplete="nickname" value={nickname} onChange={e=>setNickname(e.target.value)} required disabled={busy||!!notice}/><p className="hint">2～20 个字符，将显示给其他用户。</p>
    <label htmlFor="password">密码</label><input id="password" type="password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} required disabled={busy||!!notice}/><p className="hint">8～64 个字符，空格属于密码的一部分。</p>
    <label htmlFor="confirm">确认密码</label><input id="confirm" type="password" autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} required disabled={busy||!!notice}/>
    <div className="actions"><button disabled={busy||!!notice}>{busy?'正在注册…':'注册账号'}</button><Link href="/login">已有账号，前往登录</Link></div>
  </form>}<Feedback error={error} notice={notice}/></section>;
}

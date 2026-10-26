'use client';
import {createContext,useCallback,useContext,useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {request} from '../lib/api';

const AuthContext=createContext(null);
export function AuthProvider({children}) {
  const [user,setUser]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
  const generation=useRef(0);
  const refresh=useCallback(async () => {
    const current=++generation.current;setError('');
    try {const value=await request('/api/v1/me');if(current===generation.current)setUser(value);return value;}
    catch(e){if(current===generation.current){setUser(null);if(e.status!==401)setError(e.message);}return null;}
    finally{if(current===generation.current)setLoading(false);}
  },[]);
  useEffect(() => {
    const invalid=(event)=>{generation.current++;setUser(null);setLoading(false);setError(event.detail?.code==='AUTH_REQUIRED'?'':event.detail?.message||'登录状态已失效，请重新登录');};
    const check=()=>{if(document.visibilityState==='visible')refresh();};
    window.addEventListener('byr-auth-invalid',invalid);window.addEventListener('focus',check);
    refresh();const timer=setInterval(check,60000);
    return ()=>{clearInterval(timer);window.removeEventListener('byr-auth-invalid',invalid);window.removeEventListener('focus',check);};
  },[refresh]);
  return <AuthContext.Provider value={{user,loading,error,refresh}}>{children}</AuthContext.Provider>;
}
export function useAuth(){return useContext(AuthContext);}
export function UserNavigation() {
  const {user,loading,refresh}=useAuth();const [error,setError]=useState(''),[busy,setBusy]=useState(false);
  async function logout(){setBusy(true);setError('');try{await request('/api/v1/auth/logout',{method:'POST'});await refresh();}catch(e){setError(e.message);}finally{setBusy(false);}}
  return <><nav aria-label="账户导航">{loading?<span>正在确认身份…</span>:user?<><Link href="/profile">{user.nickname}</Link>{user.role==='admin'&&<Link href="/admin/users">账户管理</Link>}<button className="text-button" onClick={logout} disabled={busy}>{busy?'正在退出…':'退出'}</button></>:<><Link href="/login">登录</Link><Link href="/register">注册</Link></>}</nav>{error&&<span className="nav-error" role="alert">{error}</span>}</>;
}
export function Protected({children,admin=false}) {
  const {user,loading,error,refresh}=useAuth();
  if(loading)return <section className="panel"><p>正在确认登录状态…</p></section>;
  if(!user)return <section className="panel"><h1>{error?'暂时无法确认登录状态':'请先登录'}</h1><p>{error||'登录后可以查看个人资料和使用账户功能。'}</p><Link className="button" href="/login">前往登录</Link> <button className="secondary" onClick={refresh}>重新确认</button></section>;
  if(admin&&user.role!=='admin')return <section className="panel"><h1>没有访问权限</h1><p>当前账号不能管理其他用户。</p><Link href="/profile">返回个人资料</Link></section>;
  return children;
}
export function Feedback({error,notice}){return <>{error&&<p role="alert" className="message error">{error}</p>}{notice&&<p role="status" className="message success">{notice}</p>}</>;}

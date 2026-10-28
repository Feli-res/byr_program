'use client';
import {createContext,useCallback,useContext,useEffect,useRef,useState} from 'react';
import {request,ApiError} from '../lib/api';
import {useAuth} from './auth';
const Context=createContext(null);
export function RealtimeProvider({children}){
  const {user}=useAuth(),[status,setStatus]=useState('offline'),[generation,setGeneration]=useState(0),[restart,setRestart]=useState(0),[counts,setCounts]=useState(null);
  const lastPong=useRef(0),socket=useRef(null),ready=useRef(false),listeners=useRef(new Set()),pending=useRef(new Map());
  const subscribe=useCallback(fn=>{listeners.current.add(fn);return()=>listeners.current.delete(fn);},[]);
  const publish=useCallback(frame=>{for(const fn of listeners.current)fn(frame);},[]);
  const rejectPending=useCallback(()=>{for(const item of pending.current.values()){clearTimeout(item.timer);item.reject(new Error('实时发送尚未确认'));}pending.current.clear();},[]);
  useEffect(()=>{
    setCounts(null);if(!user){setStatus('offline');return;}
    let cancelled=false,timer=null,attempt=0,active=null;
    function retry(){if(cancelled)return;setStatus('http');timer=setTimeout(connect,Math.min(15000,1000*2**Math.min(attempt++,4)));}
    async function connect(){
      if(cancelled)return;setStatus('connecting');
      try{
        const token=await request('/api/v1/ws-tickets',{method:'POST'});if(cancelled)return;
        const url=new URL('/api/v1/ws',location.href);url.protocol=location.protocol==='https:'?'wss:':'ws:';
        active=new WebSocket(url);socket.current=active;ready.current=false;
        const authTimeout=setTimeout(()=>{if(!ready.current)active?.close();},8000);
        active.onopen=()=>active.send(JSON.stringify({type:'authenticate',request_id:crypto.randomUUID(),data:{ticket:token.ticket}}));
        active.onmessage=event=>{
          let frame;try{frame=JSON.parse(event.data);}catch{return;}
          if(frame.type==='pong')lastPong.current=Date.now();
          if(frame.type==='ready'){lastPong.current=Date.now();ready.current=true;attempt=0;clearTimeout(authTimeout);setStatus('online');setGeneration(v=>v+1);}
          if(frame.type==='unread.updated')setCounts(frame.data);
          if(frame.type==='session.revoked'){
            cancelled=true;setStatus('offline');ready.current=false;rejectPending();
            window.dispatchEvent(new CustomEvent('byr-auth-invalid',{detail:{code:'AUTH_REQUIRED',message:'登录状态已失效，请重新登录'}}));active.close();
          }
          const item=frame.request_id&&pending.current.get(frame.request_id);
          if(item&&(frame.type==='message.ack'||frame.type==='error')){clearTimeout(item.timer);pending.current.delete(frame.request_id);if(frame.type==='error')item.reject(new ApiError(frame.data.message,0,frame.data.code));else item.resolve(frame.data);}
          publish(frame);
        };
        active.onclose=()=>{clearTimeout(authTimeout);if(socket.current===active){ready.current=false;socket.current=null;rejectPending();}retry();};
        active.onerror=()=>{setStatus('http');};
      }catch(error){if(!cancelled){if(error.status===401||['ACCOUNT_BANNED','PASSWORD_RESET_REQUIRED'].includes(error.code)){setStatus('offline');return;}retry();}}
    }
    connect();
    const check=()=>{if(document.visibilityState==='visible')publish({type:'client.visible'});};
    window.addEventListener('focus',check);document.addEventListener('visibilitychange',check);
    return()=>{cancelled=true;clearTimeout(timer);if(active){active.onclose=null;active.onmessage=null;active.close();}if(socket.current===active){socket.current=null;ready.current=false;}rejectPending();window.removeEventListener('focus',check);document.removeEventListener('visibilitychange',check);};
  },[user?.id,user?.session_expires_at,restart,publish,rejectPending]);
  useEffect(()=>{if(!user)return;const timer=setInterval(()=>{if(!ready.current||socket.current?.readyState!==WebSocket.OPEN)return;if(Date.now()-lastPong.current>=60000){socket.current.close();return;}try{socket.current.send(JSON.stringify({type:'ping',request_id:crypto.randomUUID(),data:{}}));}catch{socket.current.close();}},30000);return()=>clearInterval(timer);},[user?.id]);
  const sendMessage=useCallback(data=>new Promise((resolve,reject)=>{
    if(!ready.current||socket.current?.readyState!==WebSocket.OPEN){reject(new Error('实时连接暂不可用'));return;}
    const id=crypto.randomUUID(),timer=setTimeout(()=>{pending.current.delete(id);reject(new Error('实时发送尚未确认'));},4000);pending.current.set(id,{resolve,reject,timer});
    try{socket.current.send(JSON.stringify({type:'message.send',request_id:id,data}));}catch(error){clearTimeout(timer);pending.current.delete(id);reject(error);}
  }),[]);
  return <Context.Provider value={{status,generation,counts,subscribe,sendMessage,reconnect:()=>setRestart(v=>v+1)}}>{children}</Context.Provider>;
}
export function useRealtime(){return useContext(Context);}
export function ConnectionState(){const live=useRealtime();return <p className="connection-state" role="status">{live.status==='online'?'实时连接正常':live.status==='connecting'?'正在连接，历史消息仍可读取':'实时连接暂不可用，消息通过普通请求发送和读取'}<button className="text-button" onClick={live.reconnect}>重新连接</button></p>;}
export function UnreadNavigation(){const live=useRealtime();return <><span className="unread-label">{live.counts?.message_unread_count>0?`私聊未读 ${live.counts.message_unread_count}`:''}</span><span className="unread-label">{live.counts?.notification_unread_count>0?`通知未读 ${live.counts.notification_unread_count}`:''}</span></>;}

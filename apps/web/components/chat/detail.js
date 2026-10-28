'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {request} from '../../lib/api';
import {Feedback,Protected,useAuth} from '../auth';
import {useRealtime,ConnectionState} from '../realtime';
import {Menu} from './navigation';
import {Messages} from './messages';

export function Detail({conversationId}){
  const {user}=useAuth(),live=useRealtime(),[info,setInfo]=useState(null),[error,setError]=useState('');const loadGeneration=useRef(0);
  const refresh=useCallback(()=>{const current=++loadGeneration.current;return request('/api/v1/conversations/'+conversationId).then(value=>{if(current===loadGeneration.current){setInfo(value);setError('');}}).catch(e=>{if(current===loadGeneration.current)setError(e.message);});},[conversationId,user.id]);
  useEffect(()=>{setInfo(null);refresh();const unsubscribe=live.subscribe(frame=>{if(['ready','client.visible'].includes(frame.type)||(frame.data?.conversation_id===conversationId&&['message.created','conversation.read'].includes(frame.type)))refresh();});const timer=setInterval(refresh,10000);return()=>{loadGeneration.current++;unsubscribe();clearInterval(timer);};},[conversationId,refresh,live.subscribe]);
  return <><Menu/><p className="breadcrumb"><Link href="/messages">← 返回私聊列表</Link></p><section className="panel chat-panel"><div className="panel-heading"><h1>{info?'与 '+info.peer.nickname+' 的私聊':'私聊'}</h1></div><ConnectionState/>{info?.context_goods?<p className="chat-context">来源商品：<Link href={'/goods/'+info.context_goods.id}>{info.context_goods.title}</Link></p>:info&&<p className="hint">来源商品当前不可用，已有聊天仍可读取。</p>}<Feedback error={error}/>{info&&<Messages key={`${conversationId}:${user.id}`} conversationId={conversationId} peer={info.peer}/>}</section></>;
}

export function ChatDetail({conversationId}){return <Protected><Detail conversationId={conversationId}/></Protected>;}

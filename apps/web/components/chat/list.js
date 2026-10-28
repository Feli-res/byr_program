'use client';
import {Suspense,useEffect} from 'react';
import Link from 'next/link';
import {useRouter,useSearchParams} from 'next/navigation';
import {request} from '../../lib/api';
import {Protected,useAuth} from '../auth';
import {useRealtime,ConnectionState} from '../realtime';
import {Failure,Time,Pager} from '../shared/content';
import {useBackgroundData as useData} from '../../lib/use-data';
import {Menu} from './navigation';

export function Conversations(){
  const {user}=useAuth(),live=useRealtime(),params=useSearchParams(),router=useRouter(),page=Number(params.get('page')||1);
  const data=useData(`conversations:${user.id}:${page}`,()=>request('/api/v1/conversations?page='+page));
  useEffect(()=>live.subscribe(frame=>{if(['message.created','conversation.read','client.visible','ready'].includes(frame.type))data.reload();}),[live.subscribe,data.reload]);
  useEffect(()=>{const timer=setInterval(data.reload,live.status==='online'?15000:3000);return()=>clearInterval(timer);},[data.reload,live.status]);
  return <><Menu/><section className="panel"><div className="panel-heading"><h1>私聊列表</h1><button className="text-button" onClick={data.reload}>刷新列表</button></div><ConnectionState/><Failure data={data}/>{data.value&&<><ul className="conversation-list">{data.value.items.map(c=><li key={c.id}><div><Link href={'/messages/'+c.id}>{c.peer.nickname}</Link>{c.unread_count>0&&<span className="unread-badge">{c.unread_count} 条未读</span>}</div><p>{c.last_message?.body||'还没有消息，可以开始交流。'}</p><p className="muted">{c.context_goods?`来源商品：${c.context_goods.title} · `:''}<Time value={c.updated_at}/></p></li>)}</ul>{data.value.total===0&&<p className="empty">暂无会话，可在商品详情中点击“联系卖家”。</p>}<Pager page={page} total={data.value.total} onPage={v=>router.push('/messages?page='+v)}/></>}</section></>;
}

export function ConversationList(){return <Protected><Suspense fallback={<p>正在读取…</p>}><Conversations/></Suspense></Protected>;}

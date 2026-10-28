'use client';
import {Suspense,useCallback,useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {useRouter,useSearchParams} from 'next/navigation';
import {request,jsonRequest} from '../lib/api';
import {Protected,Feedback,useAuth} from './auth';
import {Failure,Pager,Time} from './forum';
import {useRealtime,ConnectionState,UnreadNavigation} from './realtime';

// Keep the current view during background refresh; never carry it across accounts or filters.
function useData(key,loader){
  const load=useRef(loader);load.current=loader;
  const [revision,setRevision]=useState(0),[snapshot,setSnapshot]=useState({key,value:null,error:'',loading:true});
  useEffect(()=>{let alive=true;setSnapshot(old=>({key,value:old.key===key?old.value:null,error:'',loading:true}));load.current().then(value=>{if(alive)setSnapshot({key,value,error:'',loading:false});}).catch(error=>{if(alive)setSnapshot({key,value:null,error:error.message,loading:false});});return()=>{alive=false;};},[key,revision]);
  return {...(snapshot.key===key?snapshot:{value:null,error:'',loading:true}),reload:useCallback(()=>setRevision(v=>v+1),[])};
}
function Menu(){return <nav className="forum-menu" aria-label="消息导航"><Link href="/messages">私聊列表</Link><Link href="/notifications">站内通知</Link><UnreadNavigation/></nav>;}
function Conversations(){
  const {user}=useAuth(),live=useRealtime(),params=useSearchParams(),router=useRouter(),page=Number(params.get('page')||1);
  const data=useData(`conversations:${user.id}:${page}`,()=>request('/api/v1/conversations?page='+page));
  useEffect(()=>live.subscribe(frame=>{if(['message.created','conversation.read','client.visible','ready'].includes(frame.type))data.reload();}),[live.subscribe,data.reload]);
  useEffect(()=>{const timer=setInterval(data.reload,live.status==='online'?15000:3000);return()=>clearInterval(timer);},[data.reload,live.status]);
  return <><Menu/><section className="panel"><div className="panel-heading"><h1>私聊列表</h1><button className="text-button" onClick={data.reload}>刷新列表</button></div><ConnectionState/><Failure data={data}/>{data.value&&<><ul className="conversation-list">{data.value.items.map(c=><li key={c.id}><div><Link href={'/messages/'+c.id}>{c.peer.nickname}</Link>{c.unread_count>0&&<span className="unread-badge">{c.unread_count} 条未读</span>}</div><p>{c.last_message?.body||'还没有消息，可以开始交流。'}</p><p className="muted">{c.context_goods?`来源商品：${c.context_goods.title} · `:''}<Time value={c.updated_at}/></p></li>)}</ul>{data.value.total===0&&<p className="empty">暂无会话，可在商品详情中点击“联系卖家”。</p>}<Pager page={page} total={data.value.total} onPage={v=>router.push('/messages?page='+v)}/></>}</section></>;
}
export function ConversationList(){return <Protected><Suspense fallback={<p>正在读取…</p>}><Conversations/></Suspense></Protected>;}
function order(a,b){const x=BigInt(a.sequence),y=BigInt(b.sequence);return x<y?-1:x>y?1:0;}
function merged(old,incoming){const values=new Map(old.map(m=>[m.id,m]));for(const value of incoming)values.set(value.id,value);return [...values.values()].sort(order);}
function Messages({conversationId,peer}){
  const {user}=useAuth(),live=useRealtime(),[messages,setMessages]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[body,setBody]=useState(''),[attempt,setAttempt]=useState(null),[busy,setBusy]=useState(false),[older,setOlder]=useState(null),[loadingOlder,setLoadingOlder]=useState(false),[historyRetry,setHistoryRetry]=useState(0),[peerRead,setPeerRead]=useState('0');
  const scroll=useRef(null),atBottom=useRef(true),confirmed=useRef('0'),initialized=useRef(false),syncing=useRef(false),lastRead=useRef('0'),pending=useRef(null),alive=useRef(true);
  const base='/api/v1/conversations/'+conversationId;
  async function readBottom(){if(!initialized.current||document.visibilityState!=='visible'||!atBottom.current||BigInt(confirmed.current)<=BigInt(lastRead.current))return;const through=confirmed.current;try{await jsonRequest(base+'/read','PUT',{through_sequence:through});lastRead.current=through;}catch(e){if(alive.current)setError(e.message);}}
  const syncRef=useRef(null);
  async function sync(){if(!initialized.current||syncing.current)return;syncing.current=true;try{let more=true;while(more&&alive.current){const page=await request(base+'/messages?after_sequence='+confirmed.current+'&limit=100');if(!alive.current)return;setMessages(old=>merged(old,page.items));confirmed.current=page.next_after_sequence;more=page.has_more;}await readBottom();}catch(e){if(alive.current)setError(e.message);}finally{syncing.current=false;}}
  syncRef.current=sync;
  useEffect(()=>{
    alive.current=true;initialized.current=false;confirmed.current='0';lastRead.current='0';setMessages([]);setLoading(true);setError('');
    const unsubscribe=live.subscribe(frame=>{
      if(frame.type==='message.created'&&frame.data.conversation_id===conversationId){setMessages(old=>merged(old,[frame.data]));if(pending.current?.client_message_id===frame.data.client_message_id&&frame.data.sender_id===user.id){setAttempt(null);pending.current=null;setBody('');}syncRef.current?.();}
      if(frame.type==='conversation.read'&&frame.data.conversation_id===conversationId&&frame.data.reader_id!==user.id)setPeerRead(old=>BigInt(frame.data.through_sequence)>BigInt(old)?frame.data.through_sequence:old);
      if(['ready','client.visible'].includes(frame.type))syncRef.current?.();
    });
    request(base+'/messages').then(page=>{if(!alive.current)return;setMessages(old=>merged(old,page.items));confirmed.current=page.next_after_sequence;setOlder(page.next_before_sequence);initialized.current=true;setLoading(false);setTimeout(()=>{if(scroll.current)scroll.current.scrollTop=scroll.current.scrollHeight;atBottom.current=true;readBottom();syncRef.current?.();},0);}).catch(e=>{if(alive.current){setLoading(false);setError(e.message);}});
    const timer=setInterval(()=>syncRef.current?.(),3000);
    return()=>{alive.current=false;unsubscribe();clearInterval(timer);};
  },[conversationId,user.id,live.subscribe,historyRetry]);
  useEffect(()=>{if(atBottom.current&&scroll.current)scroll.current.scrollTop=scroll.current.scrollHeight;},[messages]);
  async function previous(){if(!older)return;setLoadingOlder(true);setError('');const oldHeight=scroll.current?.scrollHeight||0,oldTop=scroll.current?.scrollTop||0;atBottom.current=false;try{const page=await request(base+'/messages?before_sequence='+older);setMessages(old=>merged(old,page.items));setOlder(page.next_before_sequence);requestAnimationFrame(()=>{if(scroll.current)scroll.current.scrollTop=scroll.current.scrollHeight-oldHeight+oldTop;});}catch(e){setError(e.message);}finally{setLoadingOlder(false);}}
  async function submit(e){e?.preventDefault();setError('');let item=pending.current;if(!item){const value=body.trim();if(!value||Array.from(value).length>2000){setError('消息须为1～2000个字符');return;}item={client_message_id:crypto.randomUUID(),body:value};pending.current=item;setAttempt(item);}setBusy(true);
    try{let value;if(live.status==='online'){try{value=await live.sendMessage({conversation_id:conversationId,...item});}catch(e){if(['MESSAGE_CONFLICT','VALIDATION_FAILED','NOT_FOUND','FORBIDDEN','PEER_UNAVAILABLE'].includes(e.code))throw e;value=await jsonRequest(base+'/messages','POST',item);}}else value=await jsonRequest(base+'/messages','POST',item);
      if(!alive.current)return;setMessages(old=>merged(old,[value]));pending.current=null;setAttempt(null);setBody('');atBottom.current=true;syncRef.current?.();
    }catch(e){if(alive.current)setError(e.message);}finally{if(alive.current)setBusy(false);}
  }
  return <><div className="chat-tools">{error&&!loading&&!initialized.current&&<button className="text-button" onClick={()=>setHistoryRetry(v=>v+1)}>重试读取历史</button>}{older&&<button className="text-button" disabled={loadingOlder} onClick={previous}>{loadingOlder?'正在读取…':'加载更早消息'}</button>}<button className="text-button" onClick={()=>syncRef.current?.()}>补读最新消息</button><button className="text-button" onClick={()=>{atBottom.current=true;if(scroll.current)scroll.current.scrollTop=scroll.current.scrollHeight;readBottom();}}>查看最新并标为已读</button></div>
    <div className="chat-messages" ref={scroll} onScroll={e=>{atBottom.current=e.currentTarget.scrollHeight-e.currentTarget.scrollTop-e.currentTarget.clientHeight<40;if(atBottom.current)readBottom();}} aria-label="聊天记录" role="log" aria-live="polite">
      {loading&&<p className="muted">正在读取历史消息…</p>}{!loading&&messages.length===0&&<p className="empty">还没有消息。</p>}
      {messages.map(m=><article key={m.id} className={'chat-message '+(m.sender_id===user.id?'mine':'')} data-message-id={m.id}><div className="chat-message-meta"><span>{m.sender_id===user.id?'我':peer.nickname}</span><Time value={m.created_at}/></div><p>{m.body}</p><span className="message-state">{m.sender_id===user.id?(BigInt(m.sequence)<=BigInt(peerRead)?'对方已读':'已保存'):''}</span></article>)}
    </div><form className="chat-composer" onSubmit={submit}><label htmlFor="message-body">文字消息</label><textarea id="message-body" rows={3} value={body} onChange={e=>setBody(e.target.value)} disabled={busy||!!attempt} required/><p className="hint">最多 2000 个字符，只支持文字。</p>{attempt&&!busy&&<p className="hint">尚未确认发送结果，重试不会重复保存同一条消息。</p>}<div className="actions"><button disabled={busy}>{busy?'正在确认保存…':attempt?'重试发送':'发送消息'}</button>{attempt&&!busy&&<button type="button" className="secondary" onClick={()=>{if(window.confirm('清空只移除此处草稿，已经保存的消息不会撤回。')){pending.current=null;setAttempt(null);setBody('');setError('');}}}>清空待确认草稿</button>}</div></form><Feedback error={error}/>
  </>;
}
function Detail({conversationId}){
  const {user}=useAuth(),live=useRealtime(),[info,setInfo]=useState(null),[error,setError]=useState('');const loadGeneration=useRef(0);
  const refresh=useCallback(()=>{const current=++loadGeneration.current;return request('/api/v1/conversations/'+conversationId).then(value=>{if(current===loadGeneration.current){setInfo(value);setError('');}}).catch(e=>{if(current===loadGeneration.current)setError(e.message);});},[conversationId,user.id]);
  useEffect(()=>{setInfo(null);refresh();const unsubscribe=live.subscribe(frame=>{if(['ready','client.visible'].includes(frame.type)||(frame.data?.conversation_id===conversationId&&['message.created','conversation.read'].includes(frame.type)))refresh();});const timer=setInterval(refresh,10000);return()=>{loadGeneration.current++;unsubscribe();clearInterval(timer);};},[conversationId,refresh,live.subscribe]);
  return <><Menu/><p className="breadcrumb"><Link href="/messages">← 返回私聊列表</Link></p><section className="panel chat-panel"><div className="panel-heading"><h1>{info?'与 '+info.peer.nickname+' 的私聊':'私聊'}</h1></div><ConnectionState/>{info?.context_goods?<p className="chat-context">来源商品：<Link href={'/goods/'+info.context_goods.id}>{info.context_goods.title}</Link></p>:info&&<p className="hint">来源商品当前不可用，已有聊天仍可读取。</p>}<Feedback error={error}/>{info&&<Messages key={`${conversationId}:${user.id}`} conversationId={conversationId} peer={info.peer}/>}</section></>;
}
export function ChatDetail({conversationId}){return <Protected><Detail conversationId={conversationId}/></Protected>;}
const targetStates={on_sale:'在售',reserved:'已预留',sold:'已售',off_shelf:'已下架',public:'可查看',published:'已发布',pending:'待处理',resolved:'已处理',dismissed:'不予处理'};
function Notifications(){
  const {user}=useAuth(),live=useRealtime(),params=useSearchParams(),router=useRouter(),page=Number(params.get('page')||1),unread=params.get('unread_only')==='true';
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const data=useData(`notifications:${user.id}:${page}:${unread}`,()=>request(`/api/v1/notifications?page=${page}&unread_only=${unread}`));
  const count=useData(`notification-count:${user.id}:${page}:${unread}`,()=>request('/api/v1/notifications?unread_only=true&page_size=1'));
  const refresh=useCallback(()=>{data.reload();count.reload();},[data.reload,count.reload]);
  useEffect(()=>live.subscribe(frame=>{if(['notification.created','unread.updated','ready','client.visible'].includes(frame.type))refresh();}),[live.subscribe,refresh]);
  useEffect(()=>{const timer=setInterval(refresh,10000);return()=>clearInterval(timer);},[refresh]);
  async function mark(id){setBusy(true);setError('');try{await request(id?`/api/v1/notifications/${id}/read`:'/api/v1/notifications/read-all',{method:'PUT'});refresh();}catch(e){setError(e.message);}finally{setBusy(false);}}
  function onPage(value){router.push(`/notifications?page=${value}&unread_only=${unread}`);}
  return <><Menu/><section className="panel"><div className="panel-heading"><h1>站内通知</h1><span className="muted">{count.value?`未读 ${count.value.total} 条`:'正在读取未读数量…'}</span></div><ConnectionState/><div className="actions"><label className="check-label"><input type="checkbox" checked={unread} onChange={e=>router.push('/notifications?unread_only='+e.target.checked)}/>只看未读</label><button className="secondary" disabled={busy} onClick={()=>mark(null)}>全部标为已读</button><button className="text-button" onClick={refresh}>刷新通知</button></div><Failure data={data}/><Failure data={count}/><Feedback error={error}/>{data.value&&<><ul className="notification-list">{data.value.items.map(n=><li key={n.id} data-notification-id={n.id}><div className="topic-title"><span>{n.title}</span>{!n.read_at&&<span className="tag">未读</span>}</div><p>{n.summary}</p><p className="muted"><Time value={n.created_at}/>{n.target_state&&` · 当前状态：${targetStates[n.target_state]||'已更新'}`}</p><div className="actions">{n.target_available&&['post','goods'].includes(n.target_type)&&<Link href={`/${n.target_type==='post'?'posts':'goods'}/${n.target_id}`}>查看相关内容</Link>}{!n.read_at&&<button className="text-button" disabled={busy} onClick={()=>mark(n.id)}>标为已读</button>}</div></li>)}</ul>{data.value.items.length===0&&<p className="empty">暂无{unread?'未读':''}通知。</p>}<Pager page={page} total={data.value.total} onPage={onPage}/></>}</section></>;
}
export function NotificationPage(){return <Protected><Suspense fallback={<p>正在读取通知…</p>}><Notifications/></Suspense></Protected>;}

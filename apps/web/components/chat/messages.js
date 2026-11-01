'use client';
import {useEffect,useRef,useState} from 'react';
import {request,jsonRequest} from '../../lib/api';
import {Feedback,useAuth} from '../auth';
import {useRealtime} from '../realtime';
import {Time} from '../shared/content';
import {ReportButton} from '../reports';

export function order(a,b){const x=BigInt(a.sequence),y=BigInt(b.sequence);return x<y?-1:x>y?1:0;}

export function merged(old,incoming){const values=new Map(old.map(m=>[m.id,m]));for(const value of incoming)values.set(value.id,value);return [...values.values()].sort(order);}

export function Messages({conversationId,peer}){
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
      {messages.map(m=><article key={m.id} className={'chat-message '+(m.sender_id===user.id?'mine':'')} data-message-id={m.id}><div className="chat-message-meta"><span>{m.sender_id===user.id?'我':peer.nickname}</span><Time value={m.created_at}/></div><p>{m.body}</p><span className="message-state">{m.sender_id===user.id?(BigInt(m.sequence)<=BigInt(peerRead)?'对方已读':'已保存'):''}</span>{m.sender_id!==user.id&&<ReportButton targetType="message" targetId={m.id} label="举报这条消息" compact/>}</article>)}
    </div><form className="chat-composer" onSubmit={submit}><label htmlFor="message-body">文字消息</label><textarea id="message-body" rows={3} value={body} onChange={e=>setBody(e.target.value)} disabled={busy||!!attempt} required/><p className="hint">最多 2000 个字符，只支持文字。</p>{attempt&&!busy&&<p className="hint">尚未确认发送结果，重试不会重复保存同一条消息。</p>}<div className="actions"><button disabled={busy}>{busy?'正在确认保存…':attempt?'重试发送':'发送消息'}</button>{attempt&&!busy&&<button type="button" className="secondary" onClick={()=>{if(window.confirm('清空只移除此处草稿，已经保存的消息不会撤回。')){pending.current=null;setAttempt(null);setBody('');setError('');}}}>清空待确认草稿</button>}</div></form><Feedback error={error}/>
  </>;
}

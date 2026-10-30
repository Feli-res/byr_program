'use client';
import {Suspense,useCallback,useEffect,useState} from 'react';
import Link from 'next/link';
import {useRouter,useSearchParams} from 'next/navigation';
import {request} from '../../lib/api';
import {Feedback,Protected,useAuth} from '../auth';
import {useRealtime,ConnectionState} from '../realtime';
import {Failure,Time,Pager} from '../shared/content';
import {useBackgroundData as useData} from '../../lib/use-data';
import {Menu} from './navigation';

export const targetStates={on_sale:'在售',reserved:'已预留',sold:'已售',off_shelf:'已下架',public:'可查看',published:'已发布',pending:'待处理',resolved:'已处理',dismissed:'不予处理'};

export function Notifications(){
  const {user}=useAuth(),live=useRealtime(),params=useSearchParams(),router=useRouter(),page=Number(params.get('page')||1),unread=params.get('unread_only')==='true';
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const data=useData(`notifications:${user.id}:${page}:${unread}`,()=>request(`/api/v1/notifications?page=${page}&unread_only=${unread}`));
  const count=useData(`notification-count:${user.id}:${page}:${unread}`,()=>request('/api/v1/notifications?unread_only=true&page_size=1'));
  const refresh=useCallback(()=>{data.reload();count.reload();},[data.reload,count.reload]);
  useEffect(()=>live.subscribe(frame=>{if(['notification.created','unread.updated','ready','client.visible'].includes(frame.type))refresh();}),[live.subscribe,refresh]);
  useEffect(()=>{const timer=setInterval(refresh,10000);return()=>clearInterval(timer);},[refresh]);
  async function mark(id){setBusy(true);setError('');try{await request(id?`/api/v1/notifications/${id}/read`:'/api/v1/notifications/read-all',{method:'PUT'});refresh();}catch(e){setError(e.message);}finally{setBusy(false);}}
  function onPage(value){router.push(`/notifications?page=${value}&unread_only=${unread}`);}
  return <><Menu/><section className="panel"><div className="panel-heading"><h1>站内通知</h1><span className="muted">{count.value?`未读 ${count.value.total} 条`:'正在读取未读数量…'}</span></div><ConnectionState/><div className="actions"><label className="check-label"><input type="checkbox" checked={unread} onChange={e=>router.push('/notifications?unread_only='+e.target.checked)}/>只看未读</label><button className="secondary" disabled={busy} onClick={()=>mark(null)}>全部标为已读</button><button className="text-button" onClick={refresh}>刷新通知</button></div><Failure data={data}/><Failure data={count}/><Feedback error={error}/>{data.value&&<><ul className="notification-list">{data.value.items.map(n=><li key={n.id} data-notification-id={n.id}><div className="topic-title"><span>{n.title}</span>{!n.read_at&&<span className="tag">未读</span>}</div><p>{n.summary}</p><p className="muted"><Time value={n.created_at}/>{n.target_state&&` · 当前状态：${targetStates[n.target_state]||'已更新'}`}</p><div className="actions">{n.target_available&&['post','goods'].includes(n.target_type)&&<Link href={`/${n.target_type==='post'?'posts':'goods'}/${n.target_id}`}>查看相关内容</Link>}{n.target_available&&n.target_type==='report'&&<Link href="/me/reports">查看举报结果</Link>}{!n.read_at&&<button className="text-button" disabled={busy} onClick={()=>mark(n.id)}>标为已读</button>}</div></li>)}</ul>{data.value.items.length===0&&<p className="empty">暂无{unread?'未读':''}通知。</p>}<Pager page={page} total={data.value.total} onPage={onPage}/></>}</section></>;
}

export function NotificationPage(){return <Protected><Suspense fallback={<p>正在读取通知…</p>}><Notifications/></Suspense></Protected>;}

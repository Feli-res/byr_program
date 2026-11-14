'use client';
import {useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {request} from '../lib/api';
import {Failure,SafeMarkdown,Time,Pager} from './shared/content';
import {useData} from '../lib/use-data';

export function AnnouncementStrip(){
  const data=useData('announcement-strip',()=>request('/api/v1/announcements?page_size=3'));
  return <section className="panel announcement-strip" aria-label="公告"><div className="panel-heading"><h2>校园公告</h2><Link href="/announcements">全部公告</Link></div><Failure data={data}/>{data.value&&<><ul className="record-list">{data.value.items.map(a=><li key={a.id}><Link href={`/announcements/${a.id}`}>{a.title}</Link><p className="muted"><Time value={a.published_at}/></p></li>)}</ul>{data.value.items.length===0&&<p className="muted">暂无公告</p>}</>}</section>;
}

export function AnnouncementsList(){
  const [page,setPage]=useState(1);
  const data=useData(`announcements:${page}`,()=>request(`/api/v1/announcements?page=${page}`));
  return <section className="panel"><div className="panel-heading"><h1>公告</h1></div><Failure data={data}/>{data.value&&<><ul className="record-list">{data.value.items.map(a=><li key={a.id}><Link href={`/announcements/${a.id}`}>{a.title}</Link><p>{a.excerpt}</p><p className="muted"><Time value={a.published_at}/></p></li>)}</ul>{data.value.items.length===0&&<p className="empty">暂无公告。</p>}<Pager page={page} total={data.value.total} onPage={setPage}/></>}</section>;
}

export function AnnouncementDetail({announcementId}){
  const router=useRouter();
  const data=useData(`announcement:${announcementId}`,()=>request(`/api/v1/announcements/${announcementId}`));
  return <section className="panel"><Failure data={data}/>{data.value&&<><div className="panel-heading"><h1>{data.value.title}</h1></div><p className="muted">发布于 <Time value={data.value.published_at}/></p><SafeMarkdown>{data.value.body_markdown}</SafeMarkdown><div className="actions"><button className="secondary" onClick={()=>router.push('/announcements')}>返回公告列表</button><Link href="/">返回首页</Link></div></>}{data.error&&<p className="muted">公告可能已被撤回，不再公开。</p>}</section>;
}

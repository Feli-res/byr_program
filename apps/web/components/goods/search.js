'use client';
import {Suspense} from 'react';
import Link from 'next/link';
import {useRouter,useSearchParams} from 'next/navigation';
import {request} from '../../lib/api';
import {centsToYuan} from '../../lib/money.mjs';
import {Failure,Time,Pager} from '../shared/content';
import {useData} from '../../lib/use-data';
import {useDictionaries,Filters} from './common';

export function Search(){
  const params=useSearchParams(),router=useRouter(),dictionary=useDictionaries(),query=params.toString(),term=params.get('q')||'';
  const data=useData(`search:${query}`,()=>term.trim()?request('/api/v1/search?'+query):Promise.resolve(null));
  const back='/search'+(query?'?'+query:'');
  function onPage(page){const next=new URLSearchParams(query);next.set('page',page);router.push('/search?'+next);}
  return <><section className="panel"><div className="panel-heading"><h1>全站搜索</h1><span className="tag">{params.get('mode')==='semantic'?'按意思搜索':'关键词'}</span></div><Filters key={query} params={params} dictionaries={dictionary.value} search onSubmit={next=>router.push('/search?'+next)}/><Failure data={dictionary}/>{params.get('mode')==='semantic'&&<p className="hint">新发布或修改的内容需要短暂时间更新索引；结果请结合原文核实。</p>}{term.trim()?<Failure data={data}/>:<p className="empty">输入关键词，查找公开帖子和在售商品。</p>}
    {data.value&&<>{data.value.degraded&&<p className="message" role="status">语义搜索暂不可用，已改用关键词搜索。</p>}<p className="muted">找到 {data.value.total} 条结果</p><ul className="search-results">{data.value.items.map(hit=><li key={`${hit.kind}:${hit.id}`}><div className="topic-title"><span className="tag">{hit.kind==='post'?'帖子':'商品'}</span><Link href={`/${hit.kind==='post'?'posts':'goods'}/${hit.id}?return_to=${encodeURIComponent(back)}`}>{hit.title}</Link></div><p className="topic-excerpt">{hit.excerpt}</p><div className="topic-meta"><span>{hit.price_cents!=null&&`${hit.price_cents===0?'免费':'¥ '+centsToYuan(hit.price_cents)} · `}{hit.campus_code&&`${dictionary.value?.campuses.find(c=>c.code===hit.campus_code)?.name||hit.campus_code} · `}{hit.reason}</span><Time value={hit.updated_at}/></div></li>)}</ul>{data.value.items.length===0&&<p className="empty">没有符合条件的结果，可调整关键词或筛选条件。</p>}<Pager page={data.value.page} size={data.value.page_size} total={data.value.total} onPage={onPage}/></>}
  </section></>;
}

export function SearchPage(){return <Suspense fallback={<p>正在读取搜索条件…</p>}><Search/></Suspense>;}

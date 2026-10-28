'use client';
import {Suspense} from 'react';
import Link from 'next/link';
import {useRouter,useSearchParams,usePathname} from 'next/navigation';
import {request} from '../../lib/api';
import {centsToYuan} from '../../lib/money.mjs';
import {Protected,useAuth} from '../auth';
import {Failure,Time,Pager} from '../shared/content';
import {useData} from '../../lib/use-data';
import {states,conditions,useDictionaries,GoodsMenu,Filters} from './common';

export function List({mode}){
  const {user}=useAuth(),router=useRouter(),pathname=usePathname(),params=useSearchParams(),dictionaries=useDictionaries();
  const query=params.toString();const endpoint=mode==='owner'?'/api/v1/me/goods':mode==='admin'?'/api/v1/admin/goods':'/api/v1/goods';
  const data=useData(`goods:${mode}:${query}:${user?.id}`,()=>request(endpoint+(query?'?'+query:'')));
  const back=pathname+(query?'?'+query:'');
  function onPage(page){const next=new URLSearchParams(query);next.set('page',page);router.push(`${pathname}?${next}`);}
  return <><GoodsMenu/><section className="panel"><div className="panel-heading"><div><h1>{mode==='owner'?'我的商品':mode==='admin'?'商品管理':'校园二手'}</h1><p className="muted">校内闲置物品，查看真实价格与交易地点。</p></div>{user&&<Link className="button" href="/goods/new">发布商品</Link>}</div>
    <Filters key={query} params={params} dictionaries={dictionaries.value} mode={mode} onSubmit={next=>router.push(`${pathname}${next.size?'?'+next:''}`)}/><Failure data={dictionaries}/><Failure data={data}/>
    {data.value&&<><p className="muted">共 {data.value.total} 件商品</p><ul className="goods-list">{data.value.items.map(g=>{const target=mode==='owner'?`/me/goods/${g.id}`:mode==='admin'?`/admin/goods/${g.id}`:`/goods/${g.id}`;return <li key={g.id}>
      {g.images[0]&&<Link href={`${target}?return_to=${encodeURIComponent(back)}`} className="goods-thumbnail"><img src={g.images[0].url} alt={g.images[0].name} loading="lazy"/></Link>}
      <div className="goods-list-copy"><div className="topic-title"><Link href={`${target}?return_to=${encodeURIComponent(back)}`}>{g.title}</Link><span className={`tag ${g.state!=='on_sale'?'warning':''}`}>{states[g.state]}</span>{g.moderation==='restricted'&&<span className="tag warning">管理限制</span>}</div>
      <p className="goods-price">{g.price_cents===0?'免费':`¥ ${centsToYuan(g.price_cents)}`}</p><p className="muted">{dictionaries.value?.categories.find(c=>c.id===g.category_id)?.name||'商品'} · {dictionaries.value?.campuses.find(c=>c.code===g.campus_code)?.name||g.campus_code} · {conditions[g.condition_code]}{g.location_text&&` · ${g.location_text}`}</p><p className="topic-excerpt">{g.description}</p><p className="muted">{g.seller.nickname} · <Time value={g.created_at}/></p></div>
    </li>;})}</ul>{data.value.items.length===0&&<p className="empty">暂时没有符合条件的商品。</p>}<Pager page={data.value.page} size={data.value.page_size} total={data.value.total} onPage={onPage}/></>}
  </section></>;
}

export function GoodsList({mode='public'}){const content=<Suspense fallback={<p>正在读取商品…</p>}><List mode={mode}/></Suspense>;return mode==='public'?content:<Protected admin={mode==='admin'}>{content}</Protected>;}

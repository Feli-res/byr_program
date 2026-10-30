'use client';
import {useState} from 'react';
import Link from 'next/link';
import {request} from '../../lib/api';
import {centsToYuan,yuanToCents} from '../../lib/money.mjs';
import {Feedback,useAuth} from '../auth';
import {useData} from '../../lib/use-data';
import {SectionLink} from '../section-link';

export const states={on_sale:'在售',reserved:'已预留',sold:'已售',off_shelf:'已下架'};

export const conditions={new:'全新',like_new:'近新',good:'良好',fair:'一般'};

export function useDictionaries(){return useData('goods-dictionaries',()=>Promise.all([request('/api/v1/goods-categories'),request('/api/v1/campuses')]).then(([categories,campuses])=>({categories,campuses})));}

export function GoodsMenu(){const {user}=useAuth();return <nav className="forum-menu" aria-label="商品导航"><SectionLink href="/goods">二手商品</SectionLink>{user&&<><SectionLink href="/goods/new">发布商品</SectionLink><SectionLink href="/me/goods">我的商品</SectionLink>{user.role==='admin'&&<SectionLink href="/admin/goods">商品管理</SectionLink>}</>}</nav>;}

export function Filters({params,dictionaries,onSubmit,search=false,mode='public'}){
  const [q,setQ]=useState(params.get('q')||''),[category,setCategory]=useState(params.get('category_id')||''),[campus,setCampus]=useState(params.get('campus_code')||''),[price,setPrice]=useState(()=>{try{return params.has('max_price_cents')?centsToYuan(Number(params.get('max_price_cents'))):'';}catch{return params.get('max_price_cents')||'';}}),[state,setState]=useState(params.get('state')||(mode==='public'?'on_sale':'')),[kind,setKind]=useState(params.get('kind')||'all'),[error,setError]=useState('');
  function submit(e){e.preventDefault();setError('');try{const next=new URLSearchParams();if(q.trim())next.set('q',q.trim());if(search&&!q.trim())throw new Error('请输入关键词');if(search)next.set('kind',kind);if(!search&&state)next.set('state',state);if(!search||kind!=='post'){if(category)next.set('category_id',category);if(campus)next.set('campus_code',campus);if(price.trim()!=='')next.set('max_price_cents',String(yuanToCents(price)));}if(params.has('page_size'))next.set('page_size',params.get('page_size'));onSubmit(next);}catch(e){setError(e.message);}}
  return <form className="catalog-filters" onSubmit={submit}><div className="filter-fields">
    <div className="keyword-field"><label htmlFor="catalog-query">关键词</label><input id="catalog-query" value={q} onChange={e=>setQ(e.target.value)} placeholder={search?'搜索公开帖子和在售商品':'商品标题、品牌或描述'} required={search}/></div>
    {search?<div><label htmlFor="catalog-kind">内容类型</label><select id="catalog-kind" value={kind} onChange={e=>setKind(e.target.value)}><option value="all">帖子和商品</option><option value="post">帖子</option><option value="goods">商品</option></select></div>:<div><label htmlFor="catalog-state">商品状态</label><select id="catalog-state" value={state} onChange={e=>setState(e.target.value)}>{mode!=='public'&&<option value="">全部状态</option>}{Object.entries(states).map(([key,value])=><option key={key} value={key}>{value}</option>)}</select></div>}
    <div><label htmlFor="catalog-category">类别</label><select id="catalog-category" value={category} onChange={e=>setCategory(e.target.value)} disabled={search&&kind==='post'}><option value="">不限类别</option>{dictionaries?.categories.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
    <div><label htmlFor="catalog-campus">交易校区</label><select id="catalog-campus" value={campus} onChange={e=>setCampus(e.target.value)} disabled={search&&kind==='post'}><option value="">不限校区</option>{dictionaries?.campuses.map(c=><option key={c.code} value={c.code}>{c.name}</option>)}</select></div>
    <div><label htmlFor="catalog-price">最高价格（元）</label><input id="catalog-price" inputMode="decimal" value={price} onChange={e=>setPrice(e.target.value)} placeholder="不限" disabled={search&&kind==='post'}/></div>
    <button>{search?'搜索':'筛选商品'}</button><Link href={search?'/search':mode==='owner'?'/me/goods':mode==='admin'?'/admin/goods':'/goods'}>清空筛选</Link>
  </div>{search&&<p className="hint">当前使用关键词搜索。选择类别、校区或价格时，只返回符合条件的在售商品。</p>}<Feedback error={error}/></form>;
}

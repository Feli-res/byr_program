'use client';
import {Suspense,useState} from 'react';
import Link from 'next/link';
import {useRouter,useSearchParams} from 'next/navigation';
import {request,jsonRequest} from '../../lib/api';
import {centsToYuan} from '../../lib/money.mjs';
import {Feedback,Protected,useAuth} from '../auth';
import {Attachments} from '../files';
import ReturnLink,{safeReturn} from '../return-link';
import ContactSeller from '../chat-contact';
import {Failure,Time} from '../shared/content';
import {useData} from '../../lib/use-data';
import {states,conditions,useDictionaries,GoodsMenu} from './common';

export function Detail({goodsId,mode}){
  const {user}=useAuth(),router=useRouter(),params=useSearchParams(),dictionary=useDictionaries();
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[reason,setReason]=useState('');
  const endpoint=mode==='owner'?'/api/v1/me/goods':mode==='admin'?'/api/v1/admin/goods':'/api/v1/goods';
  const data=useData(`goods-detail:${goodsId}:${mode}:${user?.id}`,()=>request(`${endpoint}/${goodsId}`));const g=data.value;
  const owned=g&&user?.id===g.seller.id,restricted=g?.moderation==='restricted';
  async function state(value){if(!window.confirm(`确认将商品改为“${states[value]}”？${value==='sold'?'已售后不能重新上架。':''}`))return;setBusy(true);setError('');setNotice('');try{const result=await jsonRequest(`/api/v1/goods/${goodsId}/state`,'PATCH',{state:value,version:g.version});data.setValue({...g,...result});setNotice('商品状态已保存');}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function remove(){if(!window.confirm('确认删除自己的商品？删除后不能恢复。'))return;setBusy(true);setError('');try{await jsonRequest(`/api/v1/goods/${goodsId}`,'DELETE',{version:g.version});router.push('/me/goods');}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function moderation(){setBusy(true);setError('');setNotice('');try{await jsonRequest(`/api/v1/admin/goods/${goodsId}/moderation`,'PATCH',{action:restricted?'release':'restrict',version:g.version,reason});data.reload();setNotice('管理操作已保存');}catch(e){setError(e.message);}finally{setBusy(false);}}
  const back=safeReturn(params.get('return_to'),mode==='owner'?'/me/goods':mode==='admin'?'/admin/goods':'/goods');
  return <><GoodsMenu/><ReturnLink defaultTo={mode==='owner'?'/me/goods':mode==='admin'?'/admin/goods':'/goods'}/><section className="panel"><Failure data={dictionary}/><Failure data={data}/>{g&&<>
    <div className="panel-heading"><h1>{g.title}</h1><span className={`tag ${g.state!=='on_sale'?'warning':''}`}>{states[g.state]}</span></div>{restricted&&<p className="message error" role="alert">商品受管理限制，普通访问者无法查看；解除限制后仍需卖家自行上架。</p>}
    <p className="goods-price goods-detail-price">{g.price_cents===0?'免费':`¥ ${centsToYuan(g.price_cents)}`}</p>
    <dl className="goods-facts"><div><dt>卖家</dt><dd>{g.seller.nickname}</dd></div><div><dt>类别</dt><dd>{dictionary.value?.categories.find(c=>c.id===g.category_id)?.name||'原类别'}</dd></div><div><dt>交易校区</dt><dd>{dictionary.value?.campuses.find(c=>c.code===g.campus_code)?.name||g.campus_code}</dd></div><div><dt>交易地点</dt><dd>{g.location_text||'未提供'}</dd></div><div><dt>成色</dt><dd>{conditions[g.condition_code]}</dd></div>{g.brand&&<div><dt>品牌</dt><dd>{g.brand}</dd></div>}{g.model&&<div><dt>型号</dt><dd>{g.model}</dd></div>}{g.purpose&&<div><dt>用途</dt><dd>{g.purpose}</dd></div>}{g.attributes.storage_gb!=null&&<div><dt>容量</dt><dd>{g.attributes.storage_gb} GB</dd></div>}{g.attributes.stylus_support!=null&&<div><dt>手写笔</dt><dd>{g.attributes.stylus_support?'支持':'不支持'}</dd></div>}</dl>
    <p className="goods-description">{g.description}</p><Attachments images={g.images}/><p className="muted">发布于 <Time value={g.created_at}/> · 更新于 <Time value={g.updated_at}/></p>
    {owned&&!g.deleted_at&&<div className="actions">{g.state!=='sold'&&!restricted&&<Link className="button" href={`/goods/${g.id}/edit?return_to=${encodeURIComponent(back)}`}>编辑商品</Link>}{!restricted&&g.state==='on_sale'&&<button className="secondary" disabled={busy} onClick={()=>state('reserved')}>标记预留</button>}{!restricted&&g.state==='reserved'&&<button className="secondary" disabled={busy} onClick={()=>state('on_sale')}>取消预留</button>}{!restricted&&['on_sale','reserved'].includes(g.state)&&<><button className="secondary" disabled={busy} onClick={()=>state('sold')}>标记已售</button><button className="secondary" disabled={busy} onClick={()=>state('off_shelf')}>下架商品</button></>}{!restricted&&g.state==='off_shelf'&&<button className="secondary" disabled={busy} onClick={()=>state('on_sale')}>重新上架</button>}<button className="danger-button" disabled={busy} onClick={remove}>删除商品</button></div>}
    {!owned&&<ContactSeller goods={g}/>}
    {mode==='admin'&&!g.deleted_at&&<div className="moderation-box"><h2>管理商品</h2><label htmlFor="goods-reason">操作原因</label><input id="goods-reason" value={reason} onChange={e=>setReason(e.target.value)} disabled={busy}/><div className="actions"><button className="secondary" disabled={busy||!reason.trim()} onClick={moderation}>{restricted?'解除限制':'管理下架'}</button></div><p className="hint">解除限制不会自动重新上架，也不会恢复已售商品。</p></div>}
  </>}<Feedback error={error} notice={notice}/></section></>;
}

export function GoodsDetail({goodsId,mode='public'}){const content=<Suspense fallback={<p>正在读取商品…</p>}><Detail goodsId={goodsId} mode={mode}/></Suspense>;return mode==='public'?content:<Protected admin={mode==='admin'}>{content}</Protected>;}

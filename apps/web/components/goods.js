'use client';
import {Suspense,useState} from 'react';
import Link from 'next/link';
import {usePathname,useRouter,useSearchParams} from 'next/navigation';
import {jsonRequest,request} from '../lib/api';
import {centsToYuan,yuanToCents} from '../lib/money.mjs';
import {Feedback,Protected,useAuth} from './auth';
import {Attachments,FilePicker} from './files';
import {useData,Failure,Pager,Time} from './forum';
import ReturnLink,{safeReturn} from './return-link';
import ContactSeller from './chat-contact';

export const states={on_sale:'在售',reserved:'已预留',sold:'已售',off_shelf:'已下架'};
const conditions={new:'全新',like_new:'近新',good:'良好',fair:'一般'};
function useDictionaries(){return useData('goods-dictionaries',()=>Promise.all([request('/api/v1/goods-categories'),request('/api/v1/campuses')]).then(([categories,campuses])=>({categories,campuses})));}
export function GoodsMenu(){const {user}=useAuth();return <nav className="forum-menu" aria-label="商品导航"><Link href="/goods">二手商品</Link><Link href="/search">全站搜索</Link>{user&&<><Link href="/goods/new">发布商品</Link><Link href="/me/goods">我的商品</Link>{user.role==='admin'&&<Link href="/admin/goods">商品管理</Link>}</>}</nav>;}

function Filters({params,dictionaries,onSubmit,search=false,mode='public'}){
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

function List({mode}){
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

function Editor({goodsId}){
  const {user}=useAuth(),router=useRouter(),params=useSearchParams(),back=safeReturn(params.get('return_to'),'/me/goods');
  const initial=useData(`goods-editor:${goodsId||'new'}:${user.id}`,()=>Promise.all([request('/api/v1/goods-categories'),request('/api/v1/campuses'),goodsId?request(`/api/v1/me/goods/${goodsId}`):Promise.resolve(null)]));
  if(!initial.value)return <section className="panel"><h1>{goodsId?'编辑商品':'发布商品'}</h1><Failure data={initial}/></section>;
  return <GoodsForm key={`${goodsId||'new'}:${initial.value[2]?.version||0}`} categories={initial.value[0]} campuses={initial.value[1]} goods={initial.value[2]} onReload={initial.reload} onSaved={id=>router.push(`/goods/${id}?return_to=${encodeURIComponent(back)}`)}/>;
}
function GoodsForm({categories,campuses,goods:g,onReload,onSaved}){
  const [title,setTitle]=useState(g?.title||''),[description,setDescription]=useState(g?.description||''),[category,setCategory]=useState(g?.category_id||categories[0]?.id||''),[campus,setCampus]=useState(g?.campus_code||'shahe'),[condition,setCondition]=useState(g?.condition_code||'good'),[price,setPrice]=useState(g?centsToYuan(g.price_cents):''),[location,setLocation]=useState(g?.location_text||''),[brand,setBrand]=useState(g?.brand||''),[model,setModel]=useState(g?.model||''),[purpose,setPurpose]=useState(g?.purpose||''),[stylus,setStylus]=useState(g?.attributes?.stylus_support==null?'':String(g.attributes.stylus_support)),[storage,setStorage]=useState(g?.attributes?.storage_gb==null?'':String(g.attributes.storage_gb)),[images,setImages]=useState(g?.images||[]);
  const [busy,setBusy]=useState(false),[uploading,setUploading]=useState(false),[error,setError]=useState('');const readonly=g&&(g.state==='sold'||g.moderation==='restricted'),disabled=busy||uploading||readonly;
  async function submit(e){e.preventDefault();setBusy(true);setError('');try{
    if(images.length<1||images.length>6)throw new Error('请选择 1～6 张商品图片');
    if(storage!==''&&(!/^[0-9]+$/.test(storage)||Number(storage)<1||Number(storage)>100000))throw new Error('容量须为 1～100000 的整数');
    const data={category_id:category,campus_code:campus,title,description,condition_code:condition,price_cents:yuanToCents(price),location_text:location,brand:brand||null,model:model||null,purpose:purpose||null,attributes:{stylus_support:stylus===''?null:stylus==='true',storage_gb:storage===''?null:Number(storage)},image_file_ids:images.map(f=>f.id)};if(g)data.version=g.version;
    const value=await jsonRequest(g?`/api/v1/goods/${g.id}`:'/api/v1/goods',g?'PATCH':'POST',data);onSaved(value.id);
  }catch(e){setError(e.message);}finally{setBusy(false);}}
  return <><GoodsMenu/><section className="panel"><div className="panel-heading"><h1>{g?'编辑商品':'发布商品'}</h1><Link href="/me/goods">我的商品</Link></div>{readonly&&<p className="message error" role="alert">{g.moderation==='restricted'?'商品受管理限制，解除前不能编辑或上架。':'商品已售，只能查看或删除，不能修改后重新出售。'}</p>}
  <form onSubmit={submit}><fieldset className="editor-fields" disabled={disabled}>
    <label htmlFor="goods-title">商品标题</label><input id="goods-title" value={title} onChange={e=>setTitle(e.target.value)} required/><p className="hint">2～100 个字符</p>
    <div className="goods-form-grid"><div><label htmlFor="goods-category">商品类别</label><select id="goods-category" value={category} onChange={e=>setCategory(e.target.value)} required>{g&&!categories.some(c=>c.id===g.category_id)&&<option value={g.category_id}>原类别（已停用）</option>}{categories.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
    <div><label htmlFor="goods-price">价格（元）</label><input id="goods-price" inputMode="decimal" value={price} onChange={e=>setPrice(e.target.value)} placeholder="例如 25.50；免费填 0" required/></div>
    <div><label htmlFor="goods-campus">交易校区</label><select id="goods-campus" value={campus} onChange={e=>setCampus(e.target.value)}>{campuses.map(c=><option key={c.code} value={c.code}>{c.name}</option>)}</select></div>
    <div><label htmlFor="goods-condition">成色</label><select id="goods-condition" value={condition} onChange={e=>setCondition(e.target.value)}>{Object.entries(conditions).map(([key,value])=><option key={key} value={key}>{value}</option>)}</select></div></div>
    <label htmlFor="goods-location">交易地点</label><input id="goods-location" value={location} onChange={e=>setLocation(e.target.value)} required={campus==='other'}/><p className="hint">选择“其他”校区时必填，最多 100 个字符。</p>
    <label htmlFor="goods-description">商品描述</label><textarea id="goods-description" rows={6} value={description} onChange={e=>setDescription(e.target.value)} required/><p className="hint">1～5,000 个字符，请说明物品情况。</p>
    <div className="goods-form-grid"><div><label htmlFor="goods-brand">品牌（可选）</label><input id="goods-brand" value={brand} onChange={e=>setBrand(e.target.value)}/></div><div><label htmlFor="goods-model">型号（可选）</label><input id="goods-model" value={model} onChange={e=>setModel(e.target.value)}/></div><div><label htmlFor="goods-storage">容量 GB（可选）</label><input id="goods-storage" inputMode="numeric" value={storage} onChange={e=>setStorage(e.target.value)}/></div><div><label htmlFor="goods-stylus">支持手写笔（可选）</label><select id="goods-stylus" value={stylus} onChange={e=>setStylus(e.target.value)}><option value="">未提供</option><option value="true">支持</option><option value="false">不支持</option></select></div></div>
    <label htmlFor="goods-purpose">用途（可选）</label><input id="goods-purpose" value={purpose} onChange={e=>setPurpose(e.target.value)}/><p className="hint">可选信息不清楚时留空，系统不会推测为事实。</p></fieldset>
    <FilePicker purpose="goods_image" files={images} onChange={setImages} disabled={disabled} onBusy={setUploading}/><p className="hint">必须有 1～6 张图片，顺序即展示顺序。</p>
    <div className="actions"><button disabled={disabled}>{busy?'正在保存…':g?'保存修改':'发布商品'}</button>{g&&<button type="button" className="secondary" disabled={busy||uploading} onClick={onReload}>重新读取商品</button>}</div>
  </form><Feedback error={error}/></section></>;
}
export function GoodsEditor({goodsId}){return <Protected><Suspense fallback={<p>正在读取…</p>}><Editor goodsId={goodsId}/></Suspense></Protected>;}

function Detail({goodsId,mode}){
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

function Search(){
  const params=useSearchParams(),router=useRouter(),dictionary=useDictionaries(),query=params.toString(),term=params.get('q')||'';
  const data=useData(`search:${query}`,()=>term.trim()?request('/api/v1/search?'+query):Promise.resolve(null));
  const back='/search'+(query?'?'+query:'');
  function onPage(page){const next=new URLSearchParams(query);next.set('page',page);router.push('/search?'+next);}
  return <><GoodsMenu/><section className="panel"><div className="panel-heading"><h1>全站搜索</h1><span className="tag">关键词</span></div><Filters key={query} params={params} dictionaries={dictionary.value} search onSubmit={next=>router.push('/search?'+next)}/><Failure data={dictionary}/>{term.trim()?<Failure data={data}/>:<p className="empty">输入关键词，查找公开帖子和在售商品。</p>}
    {data.value&&<>{data.value.degraded&&<p className="message" role="status">语义搜索暂未开放，已使用关键词搜索。</p>}<p className="muted">找到 {data.value.total} 条结果</p><ul className="search-results">{data.value.items.map(hit=><li key={`${hit.kind}:${hit.id}`}><div className="topic-title"><span className="tag">{hit.kind==='post'?'帖子':'商品'}</span><Link href={`/${hit.kind==='post'?'posts':'goods'}/${hit.id}?return_to=${encodeURIComponent(back)}`}>{hit.title}</Link></div><p className="topic-excerpt">{hit.excerpt}</p><div className="topic-meta"><span>{hit.price_cents!=null&&`${hit.price_cents===0?'免费':'¥ '+centsToYuan(hit.price_cents)} · `}{hit.campus_code&&`${dictionary.value?.campuses.find(c=>c.code===hit.campus_code)?.name||hit.campus_code} · `}{hit.reason}</span><Time value={hit.updated_at}/></div></li>)}</ul>{data.value.items.length===0&&<p className="empty">没有符合条件的结果，可调整关键词或筛选条件。</p>}<Pager page={data.value.page} size={data.value.page_size} total={data.value.total} onPage={onPage}/></>}
  </section></>;
}
export function SearchPage(){return <Suspense fallback={<p>正在读取搜索条件…</p>}><Search/></Suspense>;}

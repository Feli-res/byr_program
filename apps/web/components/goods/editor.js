'use client';
import {Suspense,useState} from 'react';
import Link from 'next/link';
import {useRouter,useSearchParams} from 'next/navigation';
import {request,jsonRequest} from '../../lib/api';
import {centsToYuan,yuanToCents} from '../../lib/money.mjs';
import {Feedback,Protected,useAuth} from '../auth';
import {FilePicker} from '../files';
import {safeReturn} from '../return-link';
import {Failure} from '../shared/content';
import {useData} from '../../lib/use-data';
import {conditions,GoodsMenu} from './common';

export function Editor({goodsId}){
  const {user}=useAuth(),router=useRouter(),params=useSearchParams(),back=safeReturn(params.get('return_to'),'/me/goods');
  const initial=useData(`goods-editor:${goodsId||'new'}:${user.id}`,()=>Promise.all([request('/api/v1/goods-categories'),request('/api/v1/campuses'),goodsId?request(`/api/v1/me/goods/${goodsId}`):Promise.resolve(null)]));
  if(!initial.value)return <section className="panel"><h1>{goodsId?'编辑商品':'发布商品'}</h1><Failure data={initial}/></section>;
  return <GoodsForm key={`${goodsId||'new'}:${initial.value[2]?.version||0}`} categories={initial.value[0]} campuses={initial.value[1]} goods={initial.value[2]} onReload={initial.reload} onSaved={id=>router.push(`/goods/${id}?return_to=${encodeURIComponent(back)}`)}/>;
}

export function GoodsForm({categories,campuses,goods:g,onReload,onSaved}){
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

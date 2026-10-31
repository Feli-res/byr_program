'use client';
import {useState} from 'react';
import {useRouter} from 'next/navigation';
import Link from 'next/link';
import {jsonRequest} from '../../lib/api';
import {centsToYuan,yuanToCents} from '../../lib/money.mjs';
import {Feedback,useAuth} from '../auth';

export function GoodsAiPanel({dictionaries}){
  const {user}=useAuth(),router=useRouter();
  const [text,setText]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [intent,setIntent]=useState(null),[category,setCategory]=useState(''),[campus,setCampus]=useState(''),[price,setPrice]=useState(''),[brand,setBrand]=useState(''),[stylus,setStylus]=useState(''),[condition,setCondition]=useState('');
  const [saveOpen,setSaveOpen]=useState(false),[saveName,setSaveName]=useState(''),[saveInterval,setSaveInterval]=useState('60'),[saveBusy,setSaveBusy]=useState(false),[saveError,setSaveError]=useState(''),[saveNotice,setSaveNotice]=useState('');
  async function parse(e){e.preventDefault();setBusy(true);setError('');setIntent(null);setSaveOpen(false);setSaveNotice('');try{
    const {intent:result}=await jsonRequest('/api/v1/ai/goods-intent','POST',{text},{timeoutMs:16500});
    setIntent(result);setPrice(result.max_price_cents==null?'':centsToYuan(result.max_price_cents));setCampus(result.campus_code||'');setBrand(result.brand||'');setStylus(result.stylus_support==null?'':String(result.stylus_support));setCondition(result.min_condition||'');
    setCategory(dictionaries?.categories.find(c=>c.name===result.category)?.id||'');
  }catch(e){setError(e.message);}finally{setBusy(false);}}
  function search(e){e.preventDefault();setError('');try{
    const query=new URLSearchParams({q:[...text.trim()].slice(0,200).join(''),kind:'goods',mode:'semantic'});
    if(category)query.set('category_id',category);if(campus)query.set('campus_code',campus);if(price.trim())query.set('max_price_cents',String(yuanToCents(price)));if(brand.trim())query.set('brand',brand.trim());if(stylus)query.set('stylus_support',stylus);if(condition)query.set('min_condition',condition);
    router.push('/search?'+query);
  }catch(e){setError(e.message);}}
  function openSave(){setSaveError('');setSaveNotice('');setSaveName(`${intent?.category||'商品'}提醒`.slice(0,100));setSaveInterval('60');setSaveOpen(true);}
  async function save(e){e.preventDefault();setSaveBusy(true);setSaveError('');setSaveNotice('');
    try{
      const attributes={};if(stylus)attributes.stylus_support=stylus==='true';
      const conditions={schema_version:1,min_price_cents:null,max_price_cents:price.trim()?yuanToCents(price):null,campus_code:campus||null,category_id:category||null,brand:brand.trim()||null,model:null,min_condition:condition||null,required_attributes:attributes,purpose:(intent.preferences?.join('、')||'').slice(0,100)||null};
      if(!conditions.category_id&&!conditions.brand&&conditions.max_price_cents==null&&!conditions.campus_code&&!conditions.min_condition&&!conditions.purpose&&Object.keys(attributes).length===0)throw new Error('请至少填写一个商品条件');
      await jsonRequest('/api/v1/subscriptions','POST',{name:saveName.trim(),original_query:text.trim().slice(0,1000),conditions,interval_minutes:Number(saveInterval),confirmed:true});
      setSaveOpen(false);setSaveNotice(true);
    }catch(e){setSaveError(e.message);}finally{setSaveBusy(false);}}
  return <section className="panel"><div className="panel-heading"><div><h2>AI 帮你找商品</h2><p className="muted">描述需求，确认条件后搜索。价格、校区、品牌和类别按确认条件过滤。需求会发送给模型服务处理，请勿输入密码等敏感信息。</p></div></div>
    {user?<form onSubmit={parse}><label htmlFor="goods-ai-request">你的需求</label><textarea id="goods-ai-request" value={text} onChange={e=>{setText(e.target.value);setIntent(null)}} maxLength={1000} rows={3} placeholder="例如：想收 2000 元以内、沙河交易的平板，用来记笔记" required/><div className="actions"><button disabled={busy}>{busy?'正在理解需求…':'理解需求'}</button><button type="button" className="secondary" disabled={busy||!text.trim()} onClick={()=>{setError('');setCategory('');setCampus('');setPrice('');setBrand('');setStylus('');setCondition('');setIntent({category:null,preferences:[]});}}>手动填写条件</button></div></form>:<p><Link href="/login">登录</Link>后可以使用 AI 理解商品需求；也可以直接使用下方普通筛选。</p>}
    {intent&&<form onSubmit={search}><p>请检查并修改条件，空项表示不限制。AI 识别的商品类型：{intent.category||'未明确'}。</p><div className="filter-fields">
      <div><label htmlFor="ai-category">类别</label><select id="ai-category" value={category} onChange={e=>setCategory(e.target.value)}><option value="">不限类别</option>{dictionaries?.categories.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
      <div><label htmlFor="ai-campus">交易校区</label><select id="ai-campus" value={campus} onChange={e=>setCampus(e.target.value)}><option value="">不限校区</option>{dictionaries?.campuses.map(c=><option key={c.code} value={c.code}>{c.name}</option>)}</select></div>
      <div><label htmlFor="ai-price">最高价格（元）</label><input id="ai-price" inputMode="decimal" value={price} onChange={e=>setPrice(e.target.value)}/></div>
      <div><label htmlFor="ai-brand">品牌（精确筛选）</label><input id="ai-brand" value={brand} maxLength={100} onChange={e=>setBrand(e.target.value)}/></div>
      <div><label htmlFor="ai-stylus">手写笔支持</label><select id="ai-stylus" value={stylus} onChange={e=>setStylus(e.target.value)}><option value="">不限</option><option value="true">需要支持</option><option value="false">不支持</option></select></div>
      <div><label htmlFor="ai-condition">最低成色</label><select id="ai-condition" value={condition} onChange={e=>setCondition(e.target.value)}><option value="">不限</option><option value="new">全新</option><option value="like_new">近新及以上</option><option value="good">良好及以上</option><option value="fair">一般及以上</option></select></div>
      </div>{intent.preferences?.length>0&&<p className="hint">其他需求：{intent.preferences.join('、')}。请结合商品详情核实。</p>}<div className="actions"><button>确认条件并搜索</button></div></form>}
    {intent&&!saveOpen&&!saveNotice&&<div className="actions"><button type="button" className="secondary" onClick={openSave}>保存为提醒</button><span className="hint">保存后会定期检查新商品，并在站内通知你。</span></div>}
    {saveNotice&&<p className="message success" role="status">提醒已保存。<Link href="/me/subscriptions">打开我的提醒</Link></p>}
    {saveOpen&&<form className="reminder-form" onSubmit={save}><h2>保存为提醒</h2><p className="hint">保存当前确认的条件；后台按周期检查，同一商品只提醒一次。</p><div className="goods-form-grid"><div><label htmlFor="ai-reminder-name">提醒名称</label><input id="ai-reminder-name" value={saveName} maxLength={100} required onChange={e=>setSaveName(e.target.value)}/></div><div><label htmlFor="ai-reminder-interval">检查周期</label><select id="ai-reminder-interval" value={saveInterval} onChange={e=>setSaveInterval(e.target.value)}><option value="5">5 分钟</option><option value="15">15 分钟</option><option value="30">30 分钟</option><option value="60">1 小时</option><option value="180">3 小时</option><option value="360">6 小时</option><option value="1440">1 天</option></select></div></div><Feedback error={saveError}/><div className="actions"><button disabled={saveBusy||!saveName.trim()}>{saveBusy?'正在保存…':'保存提醒'}</button><button type="button" className="secondary" disabled={saveBusy} onClick={()=>setSaveOpen(false)}>取消</button></div></form>}
    <Feedback error={error}/>
  </section>;
}

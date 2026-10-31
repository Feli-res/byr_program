'use client';
import {centsToYuan,yuanToCents} from '../../lib/money.mjs';
import {conditions as conditionLabels} from '../goods/common';

export const taskStates={active:'启用中',paused:'已暂停',error:'异常'};
export const runStates={running:'检查中',succeeded:'成功',retry_wait:'等待重试',failed:'失败',cancelled:'已取消'};
export const taskErrors={
  DEPENDENCY_UNAVAILABLE:'服务暂时不可用，稍后会自动重试',
  MATCH_TIMEOUT:'检查超时，稍后会自动重试',
  INVALID_CONDITIONS:'保存的条件无法使用，请编辑后恢复',
  LEASE_EXPIRED:'上次检查中断，已重新排队',
  ACCOUNT_INACTIVE:'账号状态异常，任务已暂停',
  TASK_DELETED:'任务已删除',
  LEASE_LOST:'任务状态已变化',
  SLOT_LOST:'执行名额已变化',
  PAUSED:'任务已暂停',
  DELETED:'任务已删除',
  BANNED:'账号已被封禁',
};

export function blankConditions(){
  return {category:'',campus:'',minPrice:'',maxPrice:'',brand:'',model:'',condition:'',stylus:'',storage:'',purpose:''};
}

export function buildConditions(form){
  const text=value=>String(value??'').trim();
  const price=value=>text(value)===''?null:yuanToCents(text(value));
  const min=price(form.minPrice),max=price(form.maxPrice);
  if(min!=null&&max!=null&&min>max)throw new Error('最低价格不能高于最高价格');
  const attributes={};
  if(text(form.stylus)==='true'||text(form.stylus)==='false')attributes.stylus_support=text(form.stylus)==='true';
  if(text(form.storage)){
    const storage=Number(text(form.storage));
    if(!Number.isInteger(storage)||storage<1||storage>100000)throw new Error('容量须为 1～100000 的整数');
    attributes.storage_gb=storage;
  }
  const conditions={
    schema_version:1,
    min_price_cents:min,
    max_price_cents:max,
    campus_code:text(form.campus)||null,
    category_id:text(form.category)||null,
    brand:text(form.brand)||null,
    model:text(form.model)||null,
    min_condition:text(form.condition)||null,
    required_attributes:attributes,
    purpose:text(form.purpose).slice(0,100)||null,
  };
  if(!conditions.category_id&&!conditions.brand&&!conditions.model&&conditions.min_price_cents==null&&conditions.max_price_cents==null&&!conditions.campus_code&&!conditions.min_condition&&!conditions.purpose&&Object.keys(attributes).length===0)throw new Error('请至少填写一个商品条件');
  return conditions;
}

export function conditionsToForm(conditions){
  const attributes=conditions?.required_attributes||{};
  return {
    category:conditions?.category_id||'',
    campus:conditions?.campus_code||'',
    minPrice:conditions?.min_price_cents==null?'':centsToYuan(conditions.min_price_cents),
    maxPrice:conditions?.max_price_cents==null?'':centsToYuan(conditions.max_price_cents),
    brand:conditions?.brand||'',
    model:conditions?.model||'',
    condition:conditions?.min_condition||'',
    stylus:attributes.stylus_support==null?'':String(attributes.stylus_support),
    storage:attributes.storage_gb==null?'':String(attributes.storage_gb),
    purpose:conditions?.purpose||'',
  };
}

export function ConditionFields({idPrefix,value,onChange,dictionaries,disabled=false}){
  const set=(key,next)=>onChange({...value,[key]:next});
  return <div className="filter-fields reminder-condition-fields">
    <div><label htmlFor={`${idPrefix}-category`}>类别</label><select id={`${idPrefix}-category`} value={value.category} disabled={disabled} onChange={e=>set('category',e.target.value)}><option value="">不限类别</option>{dictionaries?.categories?.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
    <div><label htmlFor={`${idPrefix}-campus`}>交易校区</label><select id={`${idPrefix}-campus`} value={value.campus} disabled={disabled} onChange={e=>set('campus',e.target.value)}><option value="">不限校区</option>{dictionaries?.campuses?.map(c=><option key={c.code} value={c.code}>{c.name}</option>)}</select></div>
    <div><label htmlFor={`${idPrefix}-min-price`}>最低价格（元）</label><input id={`${idPrefix}-min-price`} inputMode="decimal" value={value.minPrice} disabled={disabled} onChange={e=>set('minPrice',e.target.value)} placeholder="不限"/></div>
    <div><label htmlFor={`${idPrefix}-max-price`}>最高价格（元）</label><input id={`${idPrefix}-max-price`} inputMode="decimal" value={value.maxPrice} disabled={disabled} onChange={e=>set('maxPrice',e.target.value)} placeholder="不限"/></div>
    <div><label htmlFor={`${idPrefix}-brand`}>品牌（精确）</label><input id={`${idPrefix}-brand`} value={value.brand} maxLength={100} disabled={disabled} onChange={e=>set('brand',e.target.value)} placeholder="不限"/></div>
    <div><label htmlFor={`${idPrefix}-model`}>型号（精确）</label><input id={`${idPrefix}-model`} value={value.model} maxLength={100} disabled={disabled} onChange={e=>set('model',e.target.value)} placeholder="不限"/></div>
    <div><label htmlFor={`${idPrefix}-condition`}>最低成色</label><select id={`${idPrefix}-condition`} value={value.condition} disabled={disabled} onChange={e=>set('condition',e.target.value)}><option value="">不限</option>{Object.entries(conditionLabels).map(([key,label])=><option key={key} value={key}>{label}及以上</option>)}</select></div>
    <div><label htmlFor={`${idPrefix}-stylus`}>手写笔</label><select id={`${idPrefix}-stylus`} value={value.stylus} disabled={disabled} onChange={e=>set('stylus',e.target.value)}><option value="">不限</option><option value="true">需要支持</option><option value="false">不支持</option></select></div>
    <div><label htmlFor={`${idPrefix}-storage`}>容量（GB）</label><input id={`${idPrefix}-storage`} inputMode="numeric" value={value.storage} disabled={disabled} onChange={e=>set('storage',e.target.value)} placeholder="不限"/></div>
    <div className="reminder-purpose-field"><label htmlFor={`${idPrefix}-purpose`}>用途或其他要求</label><input id={`${idPrefix}-purpose`} value={value.purpose} maxLength={100} disabled={disabled} onChange={e=>set('purpose',e.target.value)} placeholder="例如：记笔记、轻便"/></div>
  </div>;
}

export function conditionSummary(conditions,dictionaries){
  if(!conditions)return [];
  const rows=[];
  if(conditions.category_id)rows.push(['类别',dictionaries?.categories?.find(c=>c.id===conditions.category_id)?.name||`编号 ${conditions.category_id}`]);
  if(conditions.campus_code)rows.push(['校区',dictionaries?.campuses?.find(c=>c.code===conditions.campus_code)?.name||conditions.campus_code]);
  if(conditions.min_price_cents!=null)rows.push(['最低价格',`¥ ${centsToYuan(conditions.min_price_cents)}`]);
  if(conditions.max_price_cents!=null)rows.push(['最高价格',`¥ ${centsToYuan(conditions.max_price_cents)}`]);
  if(conditions.brand)rows.push(['品牌',conditions.brand]);
  if(conditions.model)rows.push(['型号',conditions.model]);
  if(conditions.min_condition)rows.push(['最低成色',conditionLabels[conditions.min_condition]||conditions.min_condition]);
  if(conditions.required_attributes?.stylus_support!=null)rows.push(['手写笔',conditions.required_attributes.stylus_support?'需要支持':'不支持']);
  if(conditions.required_attributes?.storage_gb!=null)rows.push(['容量',`${conditions.required_attributes.storage_gb} GB`]);
  if(conditions.purpose)rows.push(['用途',conditions.purpose]);
  return rows;
}

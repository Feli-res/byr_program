'use client';
import {useState} from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {pageWindow} from '../../lib/pagination.mjs';

export function Failure({data}){return data.error?<p role="alert" className="message error">{data.error} <button className="text-button" onClick={data.reload}>重试读取</button></p>:data.loading?<p className="muted">正在读取…</p>:null;}

export function Time({value}){return <time dateTime={value}>{new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}</time>;}

export function SafeMarkdown({children}){
  return <div className="markdown"><Markdown remarkPlugins={[remarkGfm]} skipHtml components={{
    a:({href,children})=><a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    img:({src,alt})=>/^\/api\/v1\/files\/[1-9][0-9]*\/content$/.test(src||'')?<img src={src} alt={alt||'帖子图片'} loading="lazy"/>:<span className="muted">[外部图片未加载：{alt||'图片'}]</span>,
  }}>{children}</Markdown></div>;
}

export function Pager({page,total,onPage,size=20}){
  const [jump,setJump]=useState(''),[error,setError]=useState('');
  const count=Math.max(0,Math.floor(Number(total)||0));
  const perPage=Math.max(1,Math.floor(Number(size)||20));
  if(count<=perPage)return null;
  const pages=Math.max(1,Math.ceil(count/perPage));
  const current=Math.min(Math.max(1,Math.floor(Number(page)||1)),pages);
  const items=pageWindow(current,pages);
  function go(value){setError('');onPage(value);}
  function submitJump(event){
    event.preventDefault();
    const raw=jump.trim();
    const value=Number(raw);
    if(!/^[0-9]+$/.test(raw)||value<1||value>pages){setError(`请输入 1～${pages} 的页码`);return;}
    setError('');setJump('');
    if(value!==current)onPage(value);
  }
  return <nav className="pagination" aria-label="分页">
    <button type="button" className="secondary" disabled={current<=1} onClick={()=>go(current-1)}>上一页</button>
    <div className="pagination-pages">{items.map((item,index)=>item==='ellipsis'?<span className="page-ellipsis" aria-hidden="true" key={`ellipsis-${index}`}>…</span>:<button type="button" className={item===current?'page-number current':'page-number'} aria-current={item===current?'page':undefined} aria-label={`第 ${item} 页`} key={item} onClick={()=>go(item)}>{item}</button>)}</div>
    <button type="button" className="secondary" disabled={current>=pages} onClick={()=>go(current+1)}>下一页</button>
    <span className="pagination-meta">第 {current} / {pages} 页 · 共 {count} 条</span>
    <form className="pagination-jump" onSubmit={submitJump} noValidate><label>跳至 <input type="text" inputMode="numeric" pattern="[0-9]*" maxLength={7} value={jump} onChange={event=>{setJump(event.target.value);setError('');}} aria-label="跳转到页码" placeholder="页码"/> 页</label><button type="submit" className="secondary">跳转</button></form>
    {error&&<span className="pagination-error" role="alert">{error}</span>}
  </nav>;
}

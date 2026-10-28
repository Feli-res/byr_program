'use client';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function Failure({data}){return data.error?<p role="alert" className="message error">{data.error} <button className="text-button" onClick={data.reload}>重试读取</button></p>:data.loading?<p className="muted">正在读取…</p>:null;}

export function Time({value}){return <time dateTime={value}>{new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}</time>;}

export function SafeMarkdown({children}){
  return <div className="markdown"><Markdown remarkPlugins={[remarkGfm]} skipHtml components={{
    a:({href,children})=><a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    img:({src,alt})=>/^\/api\/v1\/files\/[1-9][0-9]*\/content$/.test(src||'')?<img src={src} alt={alt||'帖子图片'} loading="lazy"/>:<span className="muted">[外部图片未加载：{alt||'图片'}]</span>,
  }}>{children}</Markdown></div>;
}

export function Pager({page,total,onPage,size=20}){
  if(total<=size&&page===1)return null;
  return <nav className="pagination" aria-label="分页"><button className="secondary" disabled={page<=1} onClick={()=>onPage(page-1)}>上一页</button><span>第 {page} 页 · 共 {total} 条</span><button className="secondary" disabled={page*size>=total} onClick={()=>onPage(page+1)}>下一页</button></nav>;
}

'use client';
import {Suspense,useCallback,useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {useRouter,useSearchParams} from 'next/navigation';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {jsonRequest,request} from '../lib/api';
import {Feedback,Protected,useAuth} from './auth';
import {Attachments,FilePicker} from './files';

function useData(key,loader){
  const [value,setValue]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[revision,setRevision]=useState(0);
  const load=useRef(loader);load.current=loader;
  useEffect(()=>{let alive=true;setLoading(true);setError('');setValue(null);load.current().then(v=>{if(alive)setValue(v);}).catch(e=>{if(alive)setError(e.message);}).finally(()=>{if(alive)setLoading(false);});return()=>{alive=false;};},[key,revision]);
  return {value,error,loading,setValue,reload:useCallback(()=>setRevision(v=>v+1),[])};
}
function Failure({data}){return data.error?<p role="alert" className="message error">{data.error} <button className="text-button" onClick={data.reload}>重试读取</button></p>:data.loading?<p className="muted">正在读取…</p>:null;}
export function Time({value}){return <time dateTime={value}>{new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}</time>;}
export function SafeMarkdown({children}){
  return <div className="markdown"><Markdown remarkPlugins={[remarkGfm]} skipHtml components={{
    a:({href,children})=><a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    img:({src,alt})=>/^\/api\/v1\/files\/[1-9][0-9]*\/content$/.test(src||'')?<img src={src} alt={alt||'帖子图片'} loading="lazy"/>:<span className="muted">[外部图片未加载：{alt||'图片'}]</span>,
  }}>{children}</Markdown></div>;
}
function Pager({page,total,onPage,size=20}){
  if(total<=size&&page===1)return null;
  return <nav className="pagination" aria-label="分页"><button className="secondary" disabled={page<=1} onClick={()=>onPage(page-1)}>上一页</button><span>第 {page} 页 · 共 {total} 条</span><button className="secondary" disabled={page*size>=total} onClick={()=>onPage(page+1)}>下一页</button></nav>;
}
export function ForumMenu(){
  const {user}=useAuth();return <nav className="forum-menu" aria-label="论坛导航"><Link href="/posts">全部帖子</Link>{user&&<><Link href="/posts/new">发布帖子</Link><Link href="/me/posts">我的帖子</Link><Link href="/me/favorites">我的收藏</Link>{['admin','moderator'].includes(user.role)&&<Link href="/admin/posts">帖子管理</Link>}</>}</nav>;
}
function List({mode}){
  const {user}=useAuth(),router=useRouter(),params=useSearchParams();
  const board=params.get('board_id')||'',sort=params.get('sort')||'latest',page=Number(params.get('page')||1);
  const query=new URLSearchParams({page:String(page),sort});if(board)query.set('board_id',board);
  const endpoints={public:'/api/v1/posts',mine:'/api/v1/me/posts',favorites:'/api/v1/me/favorites',admin:'/api/v1/admin/posts'};
  const data=useData(`${mode}:${query}:${user?.id}:${user?.role}`,()=>request(`${endpoints[mode]}?${query}`));
  const boards=useData('boards',()=>request('/api/v1/boards?page_size=100'));
  const title={public:'校园讨论',mine:'我的帖子',favorites:'我的收藏',admin:'帖子管理'}[mode];
  function update(change){const next=new URLSearchParams(params.toString());for(const [key,value] of Object.entries(change)){if(value)next.set(key,String(value));else next.delete(key);}router.push(`?${next}`);}
  return <><ForumMenu/><section className="panel forum-panel"><div className="panel-heading"><div><h1>{title}</h1><p className="muted">学习交流、校园生活，把有用的信息留在这里。</p></div>{user&&<Link className="button" href="/posts/new">发布帖子</Link>}</div>
    <div className="forum-filters"><label>板块<select value={board} onChange={e=>update({board_id:e.target.value,page:1})}><option value="">全部板块</option>{boards.value?.items.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label><label>排序<select value={sort} onChange={e=>update({sort:e.target.value,page:1})}><option value="latest">最新发布</option><option value="popular">点赞与讨论</option></select></label><button className="text-button" onClick={data.reload}>刷新列表</button></div>
    <Failure data={boards}/><Failure data={data}/>{data.value&&<><p className="muted">共 {data.value.total} 条帖子</p><ul className="topic-list">{data.value.items.map(post=><li key={post.id}>
      <div className="topic-title">{post.pinned&&<span className="tag">置顶</span>}{post.visibility==='hidden'&&<span className="tag warning">已隐藏</span>}<Link href={mode==='admin'?`/admin/posts/${post.id}`:post.visibility==='hidden'?`/posts/${post.id}/edit`:`/posts/${post.id}`}>{post.title}</Link></div>
      <p className="topic-excerpt">{post.excerpt}</p><div className="topic-meta"><span>{boards.value?.items.find(b=>b.id===post.board_id)?.name||'板块'} · {post.author.nickname} · <Time value={post.created_at}/></span><span>{post.like_count} 赞 · {post.comment_count} 回复{post.saved_by_me?' · 已收藏':''}</span></div>
      {post.last_reply&&<p className="last-reply">最近回复：{post.last_reply.author.nickname} · <Time value={post.last_reply.created_at}/></p>}
    </li>)}</ul>{data.value.items.length===0&&<p className="empty">这里还没有帖子。</p>}<Pager page={page} total={data.value.total} onPage={v=>update({page:v})}/></>}
  </section></>;
}
function ManagementGuard({children}){const {user}=useAuth();return <Protected>{user&&['admin','moderator'].includes(user.role)?children:<section className="panel"><h1>没有访问权限</h1><p>帖子管理仅供管理员和授权版主使用。</p></section>}</Protected>;}
export function ForumList({mode='public'}){const content=<Suspense fallback={<p>正在读取列表…</p>}><List mode={mode}/></Suspense>;return mode==='admin'?<ManagementGuard>{content}</ManagementGuard>:mode==='public'?content:<Protected>{content}</Protected>;}

function Editor({postId}){
  const router=useRouter();const {user}=useAuth();
  const initial=useData(`edit:${postId||'new'}:${user.id}`,()=>Promise.all([request('/api/v1/boards?page_size=100'),postId?request(`/api/v1/me/posts/${postId}`):Promise.resolve(null)]));
  if(!initial.value)return <section className="panel"><h1>{postId?'编辑帖子':'发布帖子'}</h1><Failure data={initial}/></section>;
  return <PostForm key={`${postId||'new'}:${initial.value[1]?.version||0}`} boards={initial.value[0].items} post={initial.value[1]} onReload={initial.reload} onSaved={id=>router.push(`/posts/${id}`)}/>;
}
function PostForm({boards,post,onReload,onSaved}){
  const [title,setTitle]=useState(post?.title||''),[body,setBody]=useState(post?.body_markdown||''),[board,setBoard]=useState(post?.board_id||boards[0]?.id||''),[images,setImages]=useState(post?.image_files||[]),[pdfs,setPdfs]=useState(post?.pdf_files||[]);
  const [preview,setPreview]=useState(false),[busy,setBusy]=useState(false),[imageBusy,setImageBusy]=useState(false),[pdfBusy,setPdfBusy]=useState(false),[error,setError]=useState('');
  const hidden=post?.visibility==='hidden',disabled=busy||imageBusy||pdfBusy||hidden;
  async function submit(e){e.preventDefault();setBusy(true);setError('');try{const data={board_id:board,title,body_markdown:body,image_file_ids:images.map(f=>f.id),pdf_file_ids:pdfs.map(f=>f.id)};if(post)data.version=post.version;const result=await jsonRequest(post?`/api/v1/posts/${post.id}`:'/api/v1/posts',post?'PATCH':'POST',data);onSaved(result.id);}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function remove(){if(!window.confirm('确认删除自己的这篇帖子？删除后不能恢复。'))return;setBusy(true);setError('');try{await jsonRequest(`/api/v1/posts/${post.id}`,'DELETE',{version:post.version});window.location.assign('/me/posts');}catch(e){setError(e.message);setBusy(false);}}
  return <><ForumMenu/><section className="panel"><div className="panel-heading"><h1>{post?'编辑帖子':'发布帖子'}</h1><Link href="/posts">返回论坛</Link></div>
    {hidden&&<p className="message error" role="alert">帖子已被隐藏，当前只能查看或删除，不能编辑。请等待管理人员处理。</p>}
    <form onSubmit={submit}>
      <fieldset className="editor-fields" disabled={disabled}><label htmlFor="post-board">板块</label><select id="post-board" value={board} onChange={e=>setBoard(e.target.value)} required>{post&&!boards.some(b=>b.id===post.board_id)&&<option value={post.board_id}>原板块（已停用）</option>}{boards.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select>
      <label htmlFor="post-title">标题</label><input id="post-title" value={title} onChange={e=>setTitle(e.target.value)} required/><p className="hint">2～100 个字符</p>
      <label htmlFor="post-body">正文</label><textarea id="post-body" rows={12} value={body} onChange={e=>setBody(e.target.value)} required/><p className="hint">1～20,000 个字符，支持 Markdown；不执行 HTML 或脚本。</p></fieldset>
      <button type="button" className="text-button" onClick={()=>setPreview(v=>!v)}>{preview?'收起预览':'预览正文'}</button>{preview&&<div className="markdown-preview"><SafeMarkdown>{body}</SafeMarkdown></div>}
      <FilePicker purpose="post_image" files={images} onChange={setImages} disabled={disabled} onBusy={setImageBusy}/><FilePicker purpose="post_pdf" files={pdfs} onChange={setPdfs} disabled={disabled} onBusy={setPdfBusy}/>
      <div className="actions"><button disabled={disabled||!board}>{busy?'正在保存…':post?'保存修改':'发布帖子'}</button>{post&&<><button type="button" className="secondary" disabled={busy||imageBusy||pdfBusy} onClick={onReload}>重新读取帖子</button><button type="button" className="danger-button" disabled={busy||imageBusy||pdfBusy} onClick={remove}>删除帖子</button></>}</div>
    </form><Feedback error={error}/>
  </section></>;
}
export function PostEditor({postId}){return <Protected><Editor postId={postId}/></Protected>;}

function CommentList({postId,onChanged,manage=false}){
  const {user}=useAuth();const [page,setPage]=useState(1),[body,setBody]=useState(''),[parent,setParent]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const data=useData(`comments:${postId}:${page}`,()=>request(`/api/v1/posts/${postId}/comments?page=${page}`));
  async function submit(e){e.preventDefault();setBusy(true);setError('');setNotice('');try{await jsonRequest(`/api/v1/posts/${postId}/comments`,'POST',{body,parent_id:parent?.id||null});setBody('');setParent(null);setPage(Math.max(1,Math.ceil(((data.value?.total||0)+1)/20)));data.reload();onChanged();setNotice('回复已保存');}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function remove(comment){if(!window.confirm('确认删除自己的这条回复？'))return;setBusy(true);setError('');try{await request(`/api/v1/comments/${comment.id}`,{method:'DELETE'});data.reload();onChanged();}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function moderate(comment){const reason=window.prompt('请填写隐藏或恢复评论的原因');if(reason===null)return;setBusy(true);setError('');try{await jsonRequest(`/api/v1/admin/comments/${comment.id}/moderation`,'PATCH',{action:comment.state==='hidden'?'restore':'hide',reason});data.reload();onChanged();}catch(e){setError(e.message);}finally{setBusy(false);}}
  return <section className="panel"><h2>评论与回复</h2><Failure data={data}/>{data.value&&<><ol className="comments">{data.value.items.map(c=><li key={c.id}>
    <div className="comment-meta"><span>{c.author?.nickname||'内容不可用'} · <Time value={c.created_at}/>{c.parent_id&&` · 回复 #${c.parent_id}`}</span><span>#{c.id}</span></div>
    <p className="comment-body">{c.state==='deleted'?'这条评论已删除':c.state==='hidden'?'这条评论已隐藏':c.body}</p>
    <div className="actions">{user&&c.state==='public'&&<button className="text-button" disabled={busy} onClick={()=>{setParent(c);document.getElementById('comment-body')?.focus();}}>回复</button>}{user&&c.author?.id===user.id&&<button className="text-button" disabled={busy} onClick={()=>remove(c)}>删除回复</button>}{manage&&c.state!=='deleted'&&<button className="text-button" disabled={busy} onClick={()=>moderate(c)}>{c.state==='hidden'?'恢复评论':'隐藏评论'}</button>}</div>
  </li>)}</ol>{data.value.total===0&&<p className="muted">还没有回复。</p>}<Pager page={page} total={data.value.total} onPage={setPage}/></>}
  {user?<form onSubmit={submit}>{parent&&<p className="muted">正在回复 #{parent.id} · {parent.author.nickname} <button type="button" className="text-button" onClick={()=>setParent(null)}>取消回复</button></p>}<label htmlFor="comment-body">写回复</label><textarea id="comment-body" rows={3} value={body} onChange={e=>setBody(e.target.value)} disabled={busy} required/><p className="hint">1～2,000 个字符</p><div className="actions"><button disabled={busy}>{busy?'正在保存…':'提交回复'}</button></div></form>:<p><Link href="/login">登录</Link>后参与讨论。</p>}
  <Feedback error={error} notice={notice}/></section>;
}
function Detail({postId,manage=false}){
  const {user}=useAuth();const [revision,setRevision]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[reason,setReason]=useState('');
  const data=useData(`post:${postId}:${manage}:${user?.id}:${revision}`,()=>request(`${manage?'/api/v1/admin/posts':'/api/v1/posts'}/${postId}`));
  function changed(){setRevision(v=>v+1);}
  async function react(kind,active){setBusy(true);setError('');try{await request(`/api/v1/posts/${postId}/${kind}`,{method:active?'DELETE':'PUT'});changed();}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function moderation(action){setBusy(true);setError('');setNotice('');try{await jsonRequest(`/api/v1/admin/posts/${postId}/moderation`,'PATCH',{action,version:data.value.version,reason});setNotice('管理操作已保存');changed();}catch(e){setError(e.message);}finally{setBusy(false);}}
  const post=data.value;
  return <><ForumMenu/><section className="panel"><Failure data={data}/>{post&&<><div className="post-heading">{post.pinned&&<span className="tag">置顶</span>}{post.visibility==='hidden'&&<span className="tag warning">已隐藏</span>}<h1>{post.title}</h1><p className="muted">{post.author.nickname} · <Time value={post.created_at}/>{post.created_at!==post.updated_at&&<> · 更新于 <Time value={post.updated_at}/></>}</p></div>
    <SafeMarkdown>{post.body_markdown}</SafeMarkdown><Attachments images={post.image_files} pdfs={post.pdf_files}/>
    <div className="post-stats">{post.like_count} 人点赞 · {post.comment_count} 条回复</div>
    {(!manage||post.visibility==='public')&&!post.deleted_at&&<div className="actions"><button className="secondary" disabled={!user||busy} onClick={()=>react('like',post.liked_by_me)}>{post.liked_by_me?'取消点赞':'点赞'}</button><button className="secondary" disabled={!user||busy} onClick={()=>react('favorite',post.saved_by_me)}>{post.saved_by_me?'取消收藏':'收藏'}</button>{user?.id===post.author.id&&<Link href={`/posts/${post.id}/edit`}>编辑帖子</Link>}</div>}
    {!user&&<p className="muted">登录后可点赞、收藏和回复。</p>}
    {manage&&!post.deleted_at&&<div className="moderation-box"><h2>管理帖子</h2><label htmlFor="moderation-reason">操作原因</label><input id="moderation-reason" value={reason} onChange={e=>setReason(e.target.value)} disabled={busy}/><div className="actions"><button className="secondary" disabled={busy||!reason.trim()} onClick={()=>moderation(post.pinned?'unpin':'pin')}>{post.pinned?'取消置顶':'置顶帖子'}</button><button className="secondary" disabled={busy||!reason.trim()} onClick={()=>moderation(post.visibility==='hidden'?'restore':'hide')}>{post.visibility==='hidden'?'恢复帖子':'隐藏帖子'}</button></div><p className="hint">权限由后端检查，操作会记录原因；不能代作者修改正文。</p></div>}
  </>}<Feedback error={error} notice={notice}/></section>{post&&!post.deleted_at&&post.visibility!=='hidden'&&<CommentList postId={postId} manage={manage} onChanged={()=>{request(`${manage?'/api/v1/admin/posts':'/api/v1/posts'}/${postId}`).then(data.setValue).catch(e=>setError(e.message));}}/>}</>;
}
export function PostDetail({postId,manage=false}){return manage?<ManagementGuard><Detail postId={postId} manage/></ManagementGuard>:<Detail postId={postId}/>;}

'use client';
import {Suspense,useState} from 'react';
import Link from 'next/link';
import {request,jsonRequest} from '../../lib/api';
import {Feedback,useAuth} from '../auth';
import {Attachments} from '../files';
import ReturnLink from '../return-link';
import {Failure,Time,SafeMarkdown,Pager} from '../shared/content';
import {useData} from '../../lib/use-data';
import {ForumMenu,ManagementGuard} from './navigation';

export function CommentList({postId,onChanged,manage=false}){
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

export function Detail({postId,manage=false}){
  const {user}=useAuth();const [revision,setRevision]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[reason,setReason]=useState('');
  const data=useData(`post:${postId}:${manage}:${user?.id}:${revision}`,()=>request(`${manage?'/api/v1/admin/posts':'/api/v1/posts'}/${postId}`));
  function changed(){setRevision(v=>v+1);}
  async function react(kind,active){setBusy(true);setError('');try{await request(`/api/v1/posts/${postId}/${kind}`,{method:active?'DELETE':'PUT'});changed();}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function moderation(action){setBusy(true);setError('');setNotice('');try{await jsonRequest(`/api/v1/admin/posts/${postId}/moderation`,'PATCH',{action,version:data.value.version,reason});setNotice('管理操作已保存');changed();}catch(e){setError(e.message);}finally{setBusy(false);}}
  const post=data.value;
  return <><ForumMenu/><Suspense fallback={null}><ReturnLink defaultTo="/posts"/></Suspense><section className="panel"><Failure data={data}/>{post&&<><div className="post-heading">{post.pinned&&<span className="tag">置顶</span>}{post.visibility==='hidden'&&<span className="tag warning">已隐藏</span>}<h1>{post.title}</h1><p className="muted">{post.author.nickname} · <Time value={post.created_at}/>{post.created_at!==post.updated_at&&<> · 更新于 <Time value={post.updated_at}/></>}</p></div>
    <SafeMarkdown>{post.body_markdown}</SafeMarkdown><Attachments images={post.image_files} pdfs={post.pdf_files}/>
    <div className="post-stats">{post.like_count} 人点赞 · {post.comment_count} 条回复</div>
    {(!manage||post.visibility==='public')&&!post.deleted_at&&<div className="actions"><button className="secondary" disabled={!user||busy} onClick={()=>react('like',post.liked_by_me)}>{post.liked_by_me?'取消点赞':'点赞'}</button><button className="secondary" disabled={!user||busy} onClick={()=>react('favorite',post.saved_by_me)}>{post.saved_by_me?'取消收藏':'收藏'}</button>{user?.id===post.author.id&&<Link href={`/posts/${post.id}/edit`}>编辑帖子</Link>}</div>}
    {!user&&<p className="muted">登录后可点赞、收藏和回复。</p>}
    {manage&&!post.deleted_at&&<div className="moderation-box"><h2>管理帖子</h2><label htmlFor="moderation-reason">操作原因</label><input id="moderation-reason" value={reason} onChange={e=>setReason(e.target.value)} disabled={busy}/><div className="actions"><button className="secondary" disabled={busy||!reason.trim()} onClick={()=>moderation(post.pinned?'unpin':'pin')}>{post.pinned?'取消置顶':'置顶帖子'}</button><button className="secondary" disabled={busy||!reason.trim()} onClick={()=>moderation(post.visibility==='hidden'?'restore':'hide')}>{post.visibility==='hidden'?'恢复帖子':'隐藏帖子'}</button></div><p className="hint">权限由后端检查，操作会记录原因；不能代作者修改正文。</p></div>}
  </>}<Feedback error={error} notice={notice}/></section>{post&&!post.deleted_at&&post.visibility!=='hidden'&&<CommentList postId={postId} manage={manage} onChanged={()=>{request(`${manage?'/api/v1/admin/posts':'/api/v1/posts'}/${postId}`).then(data.setValue).catch(e=>setError(e.message));}}/>}</>;
}

export function PostDetail({postId,manage=false}){return manage?<ManagementGuard><Detail postId={postId} manage/></ManagementGuard>:<Detail postId={postId}/>;}

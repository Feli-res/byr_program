'use client';
import {useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {request,jsonRequest} from '../../lib/api';
import {Feedback,Protected,useAuth} from '../auth';
import {FilePicker} from '../files';
import {Failure,SafeMarkdown} from '../shared/content';
import {useData} from '../../lib/use-data';
import {ForumMenu} from './navigation';

export function Editor({postId}){
  const router=useRouter();const {user}=useAuth();
  const initial=useData(`edit:${postId||'new'}:${user.id}`,()=>Promise.all([request('/api/v1/boards?page_size=100'),postId?request(`/api/v1/me/posts/${postId}`):Promise.resolve(null)]));
  if(!initial.value)return <section className="panel"><h1>{postId?'编辑帖子':'发布帖子'}</h1><Failure data={initial}/></section>;
  return <PostForm key={`${postId||'new'}:${initial.value[1]?.version||0}`} boards={initial.value[0].items} post={initial.value[1]} onReload={initial.reload} onSaved={id=>router.push(`/posts/${id}`)}/>;
}

export function PostForm({boards,post,onReload,onSaved}){
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

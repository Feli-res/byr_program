'use client';
import {Suspense} from 'react';
import Link from 'next/link';
import {useRouter,useSearchParams} from 'next/navigation';
import {request} from '../../lib/api';
import {Protected,useAuth} from '../auth';
import {Failure,Time,Pager} from '../shared/content';
import {useData} from '../../lib/use-data';
import {ForumMenu,ManagementGuard} from './navigation';

export function List({mode}){
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

export function ForumList({mode='public'}){const content=<Suspense fallback={<p>正在读取列表…</p>}><List mode={mode}/></Suspense>;return mode==='admin'?<ManagementGuard>{content}</ManagementGuard>:mode==='public'?content:<Protected>{content}</Protected>;}

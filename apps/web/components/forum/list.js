'use client';
import {Suspense} from 'react';
import Link from 'next/link';
import {useRouter,useSearchParams} from 'next/navigation';
import {request} from '../../lib/api';
import {Protected,useAuth} from '../auth';
import {Failure,Time,Pager} from '../shared/content';
import {useData} from '../../lib/use-data';
import {ForumMenu,ManagementGuard,ZoneNav} from './navigation';
import {AnnouncementStrip} from '../announcements';

export function List({mode}){
  const {user}=useAuth(),router=useRouter(),params=useSearchParams();
  const board=params.get('board_id')||'',sort=params.get('sort')||'latest',page=Number(params.get('page')||1);
  const pageSize=20;
  const query=new URLSearchParams({page:String(page),page_size:String(pageSize),sort});if(board)query.set('board_id',board);
  const endpoints={public:'/api/v1/posts',mine:'/api/v1/me/posts',favorites:'/api/v1/me/favorites',admin:'/api/v1/admin/posts'};
  const data=useData(`${mode}:${query}:${user?.id}:${user?.role}`,()=>request(`${endpoints[mode]}?${query}`));
  const boards=useData('boards',()=>request('/api/v1/boards?page_size=100'));
  const title={public:'校园讨论',mine:'我的帖子',favorites:'我的收藏',admin:'帖子管理'}[mode];
  function update(change){const next=new URLSearchParams(params.toString());for(const [key,value] of Object.entries(change)){if(value)next.set(key,String(value));else next.delete(key);}router.push(`?${next}`);}
  return <>{mode!=='public'&&<ForumMenu/>}<ZoneNav boards={boards.value?.items||[]} board={board} sort={sort}/><div className="forum-workspace"><section className="panel forum-panel"><div className="panel-heading"><div><h1>{title}</h1><p className="muted">学习交流、校园生活，把有用的信息留在这里。</p></div>{user&&<Link className="button" href="/posts/new">发布帖子</Link>}</div>
    {mode==='public'&&user&&<nav className="forum-personal-actions" aria-label="我的论坛"><Link href="/me/posts">我的帖子</Link><Link href="/me/favorites">我的收藏</Link><Link href="/me/reports">我的举报</Link>{['admin','moderator'].includes(user.role)&&<><Link href="/admin">管理概览</Link><Link href="/admin/posts">帖子管理</Link><Link href="/admin/reports">举报处理</Link></>}</nav>}
    <div className="forum-filters"><label>排序<select value={sort} onChange={e=>update({sort:e.target.value,page:1})}><option value="latest">最新发布</option><option value="popular">点赞与讨论</option></select></label><button className="text-button" onClick={data.reload}>刷新列表</button></div>
    <Failure data={boards}/><Failure data={data}/>{data.value&&<><p className="muted">共 {data.value.total} 条帖子</p><ul className="topic-list">{data.value.items.map(post=><li key={post.id}>
      <div className="topic-content"><div className="topic-title">{post.pinned&&<span className="tag">置顶</span>}{post.visibility==='hidden'&&<span className="tag warning">已隐藏</span>}<Link href={mode==='admin'?`/admin/posts/${post.id}`:post.visibility==='hidden'?`/posts/${post.id}/edit`:`/posts/${post.id}`}>{post.title}</Link></div>
      <p className="topic-excerpt">{post.excerpt}</p><div className="topic-meta"><span>{post.author.nickname} · <Time value={post.created_at}/>{post.saved_by_me?' · 已收藏':''}</span></div></div>
      <span className="topic-board">{boards.value?.items.find(b=>b.id===post.board_id)?.name||'板块'}</span><div className="topic-activity"><span>{post.comment_count} 回复 · {post.like_count} 赞</span><span>{post.last_reply?<>最近回复 <Time value={post.last_reply.created_at}/></>:<Time value={post.created_at}/>}</span></div>
    </li>)}</ul>{data.value.items.length===0&&<p className="empty">这里还没有帖子。</p>}<Pager page={data.value.page} size={data.value.page_size} total={data.value.total} onPage={v=>update({page:v})}/></>}
  </section>{mode==='public'&&<ForumAside/>}</div></>;
}

function ForumAside(){
  return <aside className="forum-aside" aria-label="论坛信息">
    <AnnouncementStrip/>
    <section className="panel forum-aside-card"><h2>搜索与匹配</h2><p>搜索公开帖子和商品，也可以按意思查找相关内容。</p><form action="/search" className="forum-search"><label className="sr-only" htmlFor="forum-search-query">搜索帖子或商品</label><input id="forum-search-query" name="q" type="search" placeholder="搜索帖子、商品或问题" required/><button type="submit">搜索</button></form><Link className="forum-aside-link" href="/search?mode=semantic">按意思搜索 →</Link></section>
    <section className="panel forum-aside-card"><h2>商品提醒</h2><p>保存找货条件，有符合条件的商品时接收站内通知。</p><Link className="forum-reminder-link" href="/me/subscriptions">查看我的商品提醒 <span aria-hidden="true">→</span></Link></section>
  </aside>;
}

export function ForumList({mode='public'}){const content=<Suspense fallback={<p>正在读取列表…</p>}><List mode={mode}/></Suspense>;return mode==='admin'?<ManagementGuard>{content}</ManagementGuard>:mode==='public'?content:<Protected>{content}</Protected>;}

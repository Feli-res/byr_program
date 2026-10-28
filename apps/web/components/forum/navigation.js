'use client';
import Link from 'next/link';
import {Protected,useAuth} from '../auth';

export function ForumMenu(){
  const {user}=useAuth();return <nav className="forum-menu" aria-label="论坛导航"><Link href="/posts">全部帖子</Link>{user&&<><Link href="/posts/new">发布帖子</Link><Link href="/me/posts">我的帖子</Link><Link href="/me/favorites">我的收藏</Link>{['admin','moderator'].includes(user.role)&&<Link href="/admin/posts">帖子管理</Link>}</>}</nav>;
}

export function ManagementGuard({children}){const {user}=useAuth();return <Protected>{user&&['admin','moderator'].includes(user.role)?children:<section className="panel"><h1>没有访问权限</h1><p>帖子管理仅供管理员和授权版主使用。</p></section>}</Protected>;}

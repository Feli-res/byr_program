'use client';
import {SectionLink} from '../section-link';
import {Protected,useAuth} from '../auth';

export function ForumMenu(){
  const {user}=useAuth();return <nav className="forum-menu" aria-label="论坛导航"><SectionLink href="/posts">全部帖子</SectionLink>{user&&<><SectionLink href="/posts/new">发布帖子</SectionLink><SectionLink href="/me/posts">我的帖子</SectionLink><SectionLink href="/me/favorites">我的收藏</SectionLink><SectionLink href="/me/reports">我的举报</SectionLink>{['admin','moderator'].includes(user.role)&&<><SectionLink href="/admin/posts">帖子管理</SectionLink><SectionLink href="/admin/reports">举报处理</SectionLink></>}</>}</nav>;
}

export function ManagementGuard({children}){const {user}=useAuth();return <Protected>{user&&['admin','moderator'].includes(user.role)?children:<section className="panel"><h1>没有访问权限</h1><p>帖子管理仅供管理员和授权版主使用。</p></section>}</Protected>;}

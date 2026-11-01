'use client';
import Link from 'next/link';
import {Protected,useAuth} from '../auth';
import {SectionLink} from '../section-link';

const links=[
  {href:'/admin',label:'管理概览',admin:false},
  {href:'/admin/users',label:'账户管理',admin:true},
  {href:'/admin/boards',label:'板块管理',admin:true},
  {href:'/admin/posts',label:'帖子管理',admin:false},
  {href:'/admin/goods',label:'商品管理',admin:true},
  {href:'/admin/reports',label:'举报处理',admin:false},
  {href:'/admin/announcements',label:'公告管理',admin:true},
  {href:'/admin/subscriptions',label:'提醒任务',admin:true},
  {href:'/admin/audit-logs',label:'操作记录',admin:true},
];

export function AdminGuard({children,adminOnly=false}){
  return <Protected admin={adminOnly}><AdminGate adminOnly={adminOnly}>{children}</AdminGate></Protected>;
}
function AdminGate({children,adminOnly}){
  const {user}=useAuth();
  const allowed=user&&(user.role==='admin'||(!adminOnly&&user.role==='moderator'));
  if(!allowed)return <section className="panel"><h1>没有访问权限</h1><p>这项管理功能只对管理员{adminOnly?'':'或授权版主'}开放。</p><Link href="/">返回首页</Link></section>;
  return <><AdminMenu/>{children}</>;
}

export function AdminMenu(){
  const {user}=useAuth();
  if(!user||!['admin','moderator'].includes(user.role))return null;
  return <nav className="forum-menu" aria-label="管理导航">{links.filter(item=>user.role==='admin'||!item.admin).map(item=><SectionLink key={item.href} href={item.href}>{item.label}</SectionLink>)}<span className="muted">当前身份：{user.role==='admin'?'管理员':'版主'}</span></nav>;
}

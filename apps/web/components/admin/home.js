'use client';
import Link from 'next/link';
import {request} from '../../lib/api';
import {useAuth} from '../auth';
import {useData} from '../../lib/use-data';
import {AdminGuard} from './common';

const cards=[
  {href:'/admin/reports',title:'举报处理',text:'查看帖子、评论、商品和私信举报，人工裁定并通知举报人。',admin:false},
  {href:'/admin/posts',title:'帖子管理',text:'置顶、隐藏或恢复帖子，处理评论。',admin:false},
  {href:'/admin/users',title:'账户管理',text:'角色、板块授权、封禁和密码重置。',admin:true},
  {href:'/admin/boards',title:'板块管理',text:'新建、编辑、启用或停用板块。',admin:true},
  {href:'/admin/goods',title:'商品管理',text:'下架违规商品或解除限制。',admin:true},
  {href:'/admin/announcements',title:'公告管理',text:'草稿、发布和撤回公告。',admin:true},
  {href:'/admin/subscriptions',title:'提醒任务',text:'查看脱敏运行情况，暂停异常任务。',admin:true},
  {href:'/admin/audit-logs',title:'操作记录',text:'查看管理操作的操作者、原因、对象和结果。',admin:true},
];

function Home(){
  const {user}=useAuth();
  const pending=useData(`admin-pending:${user?.id}`,()=>request('/api/v1/admin/reports?state=pending&page_size=1'));
  return <section className="panel"><div className="panel-heading"><h1>管理概览</h1><span className="muted">{user.role==='admin'?'管理员':'版主'}</span></div>
    <p className="muted">管理动作会立即影响论坛、搜索、聊天和提醒；每项操作都要填写原因并留下记录。</p>
    {pending.value&&<p>待处理举报：<strong>{pending.value.total}</strong> 条。<Link href="/admin/reports?state=pending">去处理</Link></p>}
    <ul className="record-list">{cards.filter(card=>user.role==='admin'||!card.admin).map(card=><li key={card.href}><Link href={card.href}>{card.title}</Link><p>{card.text}</p></li>)}</ul>
  </section>;
}

export function AdminHome(){return <AdminGuard><Home/></AdminGuard>;}

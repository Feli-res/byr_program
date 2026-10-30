'use client';
import Link from 'next/link';
import {usePathname} from 'next/navigation';

const items=[
  {href:'/posts',label:'论坛',matches:path=>path==='/' || ['/posts','/me/posts','/me/favorites','/admin/posts'].some(base=>path===base || path.startsWith(base+'/'))},
  {href:'/goods',label:'商品',matches:path=>['/goods','/me/goods','/admin/goods'].some(base=>path===base || path.startsWith(base+'/'))},
  {href:'/search',label:'搜索',matches:path=>path==='/search' || path.startsWith('/search/')},
  {href:'/messages',label:'消息',matches:path=>['/messages','/notifications'].some(base=>path===base || path.startsWith(base+'/'))},
  {href:'/profile',label:'个人资料',matches:path=>['/profile','/change-password','/admin/users'].some(base=>path===base || path.startsWith(base+'/'))},
];

export function MainNavigation(){
  const path=usePathname()||'';
  return <nav aria-label="主导航">{items.map(({href,label,matches})=><Link key={href} href={href} aria-current={matches(path)?(path===href?'page':'location'):undefined}>{label}</Link>)}</nav>;
}

'use client';
import Link from 'next/link';
import {usePathname} from 'next/navigation';

function isCurrent(href,path){
  if(path===href)return true;
  if(href==='/posts')return path==='/' || /^\/posts\/[^/]+$/.test(path)&&path!=='/posts/new';
  if(href==='/me/posts')return /^\/posts\/[^/]+\/edit$/.test(path) || path.startsWith('/me/posts/');
  if(href==='/admin/posts')return path.startsWith('/admin/posts/');
  if(href==='/goods')return /^\/goods\/[^/]+$/.test(path)&&path!=='/goods/new';
  if(href==='/me/goods')return /^\/goods\/[^/]+\/edit$/.test(path) || path.startsWith('/me/goods/');
  if(href==='/admin/goods')return path.startsWith('/admin/goods/');
  if(href==='/messages')return path.startsWith('/messages/');
  return false;
}
export function SectionLink({href,children}){
  const path=usePathname()||'';
  return <Link href={href} aria-current={isCurrent(href,path)?'page':undefined}>{children}</Link>;
}

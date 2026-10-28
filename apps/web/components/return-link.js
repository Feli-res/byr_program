'use client';
import Link from 'next/link';
import {useSearchParams} from 'next/navigation';
export function safeReturn(value,fallback='/goods'){
  return value&&value.length<=8192&&/^\/(?:goods|posts|search|me\/goods|admin\/goods)(?:\?|$)/.test(value)?value:fallback;
}
export default function ReturnLink({defaultTo='/goods'}){const params=useSearchParams();return <p className="breadcrumb"><Link href={safeReturn(params.get('return_to'),defaultTo)}>← 返回列表</Link></p>;}

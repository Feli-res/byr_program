'use client';
import Link from 'next/link';
import {UnreadNavigation} from '../realtime';

export function Menu(){return <nav className="forum-menu" aria-label="消息导航"><Link href="/messages">私聊列表</Link><Link href="/notifications">站内通知</Link><UnreadNavigation/></nav>;}

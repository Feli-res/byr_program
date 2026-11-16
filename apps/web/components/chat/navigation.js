'use client';
import {SectionLink} from '../section-link';
import {UnreadNavigation} from '../realtime';

export function Menu(){return <nav className="forum-menu" aria-label="消息导航"><SectionLink href="/messages">私聊列表</SectionLink><SectionLink href="/notifications">站内通知</SectionLink><SectionLink href="/me/subscriptions">商品提醒</SectionLink><UnreadNavigation/></nav>;}

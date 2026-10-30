import './globals.css';
import Link from 'next/link';
import {AuthProvider,UserNavigation} from '../components/auth';
import {RealtimeProvider} from '../components/realtime';
import {MainNavigation} from '../components/main-navigation';
export const metadata={title:'邮智汇',description:'校园综合交互论坛'};
export default function Layout({children}) {
  return <html lang="zh-CN"><body><AuthProvider><RealtimeProvider>
    <header className="site-header"><div className="header-inner">
      <Link href="/" className="brand">邮智汇<span>校园综合论坛</span></Link>
      <MainNavigation/>
      <div className="account-nav"><UserNavigation/></div>
    </div></header>
    <main>{children}</main><footer>邮智汇 · 程序设计实验 {process.env.DISABLE_DEV_PAGE !== 'true' && <Link href="/dev-check">联通检查</Link>}</footer>
  </RealtimeProvider></AuthProvider></body></html>;
}

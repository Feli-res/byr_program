import './globals.css';
import Link from 'next/link';
import {AuthProvider,UserNavigation} from '../components/auth';
export const metadata={title:'邮智汇',description:'校园综合交互论坛'};
export default function Layout({children}) {
  return <html lang="zh-CN"><body><AuthProvider>
    <header className="site-header"><div className="header-inner">
      <Link href="/" className="brand">邮智汇<span>校园综合论坛</span></Link>
      <nav aria-label="主导航"><Link href="/">首页</Link><Link href="/profile">个人资料</Link></nav>
      <div className="account-nav"><UserNavigation/></div>
    </div></header>
    <main>{children}</main><footer>邮智汇 · 程序设计实验 <Link href="/dev-check">联通检查</Link></footer>
  </AuthProvider></body></html>;
}

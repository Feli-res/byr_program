import Link from 'next/link';
export default function Home(){return <section className="panel">
  <div className="panel-heading"><h1>邮智汇校园论坛</h1><span className="tag">账户功能已接入</span></div>
  <p>目前可以注册和登录自己的账号，修改个人资料与头像。论坛讨论、二手商品、私聊和 AI 服务按后续计划逐步开放。</p>
  <table><thead><tr><th>内容</th><th>当前状态</th></tr></thead><tbody>
    <tr><td>自主注册、登录、退出</td><td>已接入真实后端</td></tr><tr><td>个人资料、头像、修改密码</td><td>已接入真实后端</td></tr>
    <tr><td>管理员账户管理及辅助重置</td><td>管理员登录后使用</td></tr><tr><td>论坛、商品、聊天和 AI</td><td>后续开放</td></tr>
  </tbody></table><div className="actions"><Link className="button" href="/register">注册账号</Link><Link href="/login">已有账号，前往登录</Link></div>
</section>;}

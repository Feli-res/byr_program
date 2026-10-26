'use client';
import {useEffect, useState} from 'react';
import {request} from '../../lib/api';

export default function DevelopmentCheck() {
  const [body, setBody] = useState('');
  const [items, setItems] = useState([]);
  const [ready, setReady] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function reload() {
    setLoading(true);setError('');
    try {
      const result = await request('/api/dev/records');
      setItems(result.items);
    } catch (e) {setError(e.message);}
    finally {setLoading(false);}
    try {await request('/health/ready');setReady(true);} catch {setReady(false);}
  }
  useEffect(() => {reload();}, []);

  async function save(event) {
    event.preventDefault();
    if (saving) return;
    setError('');setNotice('');
    if (!body.trim() || [...body.trim()].length > 500) {setError('请填写 1～500 字的内容');return;}
    setSaving(true);
    try {
      const result = await request('/api/dev/records', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({body})});
      setBody('');setNotice(`已保存，记录编号 ${result.id}`);
      await reload();
    } catch (e) {setError(e.message);}
    finally {setSaving(false);}
  }

  return <>
    <div className="breadcrumb">首页 / 联通检查</div>
    <section className="panel">
      <div className="panel-heading"><h1>网页与数据库联通检查</h1><span className={`tag ${ready === false ? 'warning' : ''}`}>{ready === null ? '正在检查服务' : ready ? '服务已就绪' : '依赖尚未就绪'}</span></div>
      <p>填写一条测试内容，保存后从 MySQL 重新读取。刷新页面或重启程序，记录应当仍然存在。</p>
      <p className="muted">仅供本机开发验证，显示最近 20 条测试记录，不是真实论坛帖子。</p>
      <form onSubmit={save}>
        <label htmlFor="record-body">测试内容<span className="hint">1～500 字</span></label>
        <textarea id="record-body" name="body" rows={4} value={body} onChange={e => setBody(e.target.value)} placeholder="例如：今天已接通前端与数据库。" disabled={saving}/>
        <div className="actions"><button type="submit" disabled={saving}>{saving ? '正在保存…' : '保存记录'}</button><button type="button" className="secondary" onClick={reload} disabled={loading || saving}>{loading ? '正在读取…' : '重新读取'}</button></div>
      </form>
      {error && <p className="message error" role="alert">{error}</p>}
      {notice && <p className="message success" role="status">{notice}</p>}
    </section>
    <section className="panel" aria-busy={loading}>
      <div className="panel-heading"><h2>已保存的记录</h2><span className="muted">最近 {items.length} 条</span></div>
      {loading ? <p className="muted">正在读取记录…</p> : items.length ? <ul className="record-list">{items.map(item => <li key={item.id}><div className="record-meta"><span>#{item.id}</span><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString('zh-CN', {timeZone: 'Asia/Shanghai', hour12: false})}</time></div><p>{item.body}</p></li>)}</ul> : <p className="empty">还没有测试记录，保存第一条内容试试。</p>}
    </section>
  </>;
}

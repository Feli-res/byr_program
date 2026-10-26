export class ApiError extends Error {
  constructor(message, status, code, fields = [], retryAfter = null) {
    super(message);this.status=status;this.code=code;this.fields=fields;this.retryAfter=retryAfter;
  }
}
let csrfRequest = null;
async function csrf() {
  if (!csrfRequest) csrfRequest = send('/api/v1/csrf', {}).finally(() => {csrfRequest=null;});
  return (await csrfRequest).csrf_token;
}
async function send(path, options) {
  const controller=new AbortController();
  const timeout=setTimeout(() => controller.abort(), 12000);
  try {
    const response=await fetch(path, {...options, credentials:'include', cache:'no-store', signal:controller.signal});
    const payload=await response.json().catch(() => null);
    if (!response.ok) {
      const code=payload?.error?.code;
      if (typeof window!=='undefined' && ['AUTH_REQUIRED','SESSION_EXPIRED','ACCOUNT_BANNED','PASSWORD_RESET_REQUIRED'].includes(code)) window.dispatchEvent(new CustomEvent('byr-auth-invalid',{detail:{code,message:payload?.error?.message}}));
      const seconds=response.headers.get('Retry-After');
      const message=payload?.error?.message || '服务暂时无法连接，请稍后重试';
      throw new ApiError(seconds ? `${message}（约 ${seconds} 秒后可重试）` : message,response.status,code,payload?.error?.fields||[],seconds);
    }
    if (!payload || !('data' in payload)) throw new Error('服务返回内容不完整');
    return payload.data;
  } catch (error) {
    if (error.name==='AbortError') throw new Error('请求超时，暂未确认结果，请先重新读取再决定是否重试');
    if (error instanceof TypeError) throw new Error('无法连接服务，请检查后端是否已启动');
    throw error;
  } finally {clearTimeout(timeout);}
}
export async function request(path, options={}) {
  const write=['POST','PUT','PATCH','DELETE'].includes((options.method||'GET').toUpperCase()) && path.startsWith('/api/v1/');
  if (!write) return send(path,options);
  const headers={...options.headers,'X-CSRF-Token':await csrf()};
  try {return await send(path,{...options,headers});}
  catch (error) {
    // A CSRF rejection happens before any write; refreshing this protection can be retried once.
    if (error.code!=='CSRF_INVALID') throw error;
    return send(path,{...options,headers:{...options.headers,'X-CSRF-Token':await csrf()}});
  }
}
export function jsonRequest(path,method,data) {
  return request(path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
}

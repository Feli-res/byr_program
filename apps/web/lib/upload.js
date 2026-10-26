import {ApiError,request} from './api';

// One shared upload path for avatars, forum attachments and future goods pages.
export async function uploadFile(file,purpose,onProgress=()=>{}) {
  const {csrf_token}=await request('/api/v1/csrf');
  return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();xhr.open('POST','/api/v1/files');xhr.withCredentials=true;xhr.timeout=60000;
    xhr.setRequestHeader('X-CSRF-Token',csrf_token);
    xhr.upload.onprogress=e=>{if(e.lengthComputable)onProgress(Math.round(e.loaded/e.total*100));};
    xhr.onerror=()=>reject(new Error('文件上传连接中断，请检查已上传列表后重试'));
    xhr.ontimeout=()=>reject(new Error('文件上传超时，尚未确认结果，请稍后重试'));
    xhr.onload=()=>{
      let payload;try{payload=JSON.parse(xhr.responseText);}catch{reject(new Error('上传服务返回内容不完整'));return;}
      if(xhr.status>=200&&xhr.status<300&&payload?.data){resolve(payload.data);return;}
      const code=payload?.error?.code;
      if(['AUTH_REQUIRED','ACCOUNT_BANNED','PASSWORD_RESET_REQUIRED'].includes(code))window.dispatchEvent(new CustomEvent('byr-auth-invalid',{detail:{code,message:payload?.error?.message}}));
      reject(new ApiError(payload?.error?.message||'文件上传失败',xhr.status,code,payload?.error?.fields||[]));
    };
    const data=new FormData();data.append('purpose',purpose);data.append('file',file);xhr.send(data);
  });
}

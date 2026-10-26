'use client';
import {useId,useState} from 'react';
import {request} from '../lib/api';
import {uploadFile} from '../lib/upload';

export function FilePicker({purpose,files,onChange,disabled=false,onBusy=()=>{}}) {
  const inputId=useId(),[busy,setBusy]=useState(false),[progress,setProgress]=useState(0),[error,setError]=useState('');
  const pdf=purpose==='post_pdf',avatar=purpose==='avatar';
  const max=pdf?2:avatar?1:purpose==='goods_image'?6:9,limit=(pdf?10:avatar?2:5)*1048576;
  const title=pdf?'PDF 附件':avatar?'头像':'图片';
  async function pick(event){
    const chosen=Array.from(event.target.files||[]);event.target.value='';setError('');
    if(files.length+chosen.length>max){setError(`${title}最多 ${max} 个`);return;}
    if(chosen.some(f=>f.size===0||f.size>limit)){setError(`每个文件必须为 1 字节～${limit/1048576} MiB`);return;}
    setBusy(true);onBusy(true);let updated=[...files];
    try{for(const file of chosen){setProgress(0);const saved=await uploadFile(file,purpose,setProgress);updated=[...updated,saved];onChange(updated);}}
    catch(e){setError(e.message);}finally{setBusy(false);onBusy(false);}
  }
  async function remove(file){
    setError('');setBusy(true);onBusy(true);
    try{if(file.state==='staged')await request(`/api/v1/files/${file.id}`,{method:'DELETE'});onChange(files.filter(f=>f.id!==file.id));}
    catch(e){setError(e.message);}finally{setBusy(false);onBusy(false);}
  }
  return <fieldset className="file-picker" disabled={disabled||busy}>
    <legend>{title}</legend><label className="sr-only" htmlFor={inputId}>{pdf?'上传 PDF':avatar?'上传头像':'上传图片'}</label>
    <input id={inputId} type="file" multiple={!avatar} accept={pdf?'application/pdf':'.jpg,.jpeg,.png,.webp'} onChange={pick}/>
    <p className="hint">{pdf?'PDF，每个不超过 10 MiB，最多 2 个。':avatar?'JPEG、PNG、WebP，不超过 2 MiB。':`JPEG、PNG、WebP，每张不超过 5 MiB，最多 ${max} 张。`} 保存内容后附件才正式生效。</p>
    {busy&&<p role="status">正在处理文件… {progress}%</p>}{error&&<p className="message error" role="alert">{error}</p>}
    <ul className="upload-list">{files.map((file,index)=><li key={file.id}>
      {!pdf&&<img src={file.url} width="64" height="64" alt={file.name}/>}
      <span>{file.name}<small>{Math.ceil(file.size_bytes/1024)} KiB · {file.state==='staged'?'待保存':'已绑定'}</small></span>
      {files.length>1&&<button type="button" className="text-button" disabled={index===0} onClick={()=>{const updated=[...files];[updated[index-1],updated[index]]=[updated[index],updated[index-1]];onChange(updated);}}>上移</button>}
      <button type="button" className="text-button" onClick={()=>remove(file)}>移除</button>
    </li>)}</ul>
  </fieldset>;
}

export function Attachments({images=[],pdfs=[]}) {
  return <>{images.length>0&&<div className="post-images">{images.map(file=><a key={file.id} href={file.url} target="_blank" rel="noreferrer"><img src={file.url} alt={file.name} loading="lazy"/></a>)}</div>}
    {pdfs.length>0&&<ul className="pdf-list">{pdfs.map(file=><li key={file.id}><a href={file.url} download={file.name}>{file.name}</a><span className="muted"> · {Math.ceil(file.size_bytes/1024)} KiB</span></li>)}</ul>}</>;
}

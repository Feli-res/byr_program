'use client';
import {useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {jsonRequest} from '../lib/api';
import {useAuth,Feedback} from './auth';
export default function ContactSeller({goods}){
  const {user}=useAuth(),router=useRouter(),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function contact(){setBusy(true);setError('');try{const conversation=await jsonRequest('/api/v1/conversations','POST',{goods_id:goods.id});router.push('/messages/'+conversation.id);}catch(e){setError(e.message);}finally{setBusy(false);}}
  if(!goods.can_contact)return <p className="hint">对方暂时不可联系。</p>;
  if(!user)return <p><Link href="/login">登录后联系卖家</Link></p>;
  return <><div className="actions"><button disabled={busy} onClick={contact}>{busy?'正在打开会话…':'联系卖家'}</button></div><Feedback error={error}/></>;
}

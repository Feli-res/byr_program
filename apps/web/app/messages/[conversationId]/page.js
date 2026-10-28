'use client';
import {useParams} from 'next/navigation';
import {ChatDetail} from '../../../components/chat';
export default function Page(){const {conversationId}=useParams();return <ChatDetail conversationId={conversationId}/>;}

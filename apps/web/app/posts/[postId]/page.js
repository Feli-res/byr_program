'use client';
import {useParams} from 'next/navigation';
import {PostDetail} from '../../../components/forum';
export default function Page(){const {postId}=useParams();return <PostDetail postId={postId}/>;}

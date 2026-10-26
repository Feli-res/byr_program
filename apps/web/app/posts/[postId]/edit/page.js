'use client';
import {useParams} from 'next/navigation';
import {PostEditor} from '../../../../components/forum';
export default function Page(){const {postId}=useParams();return <PostEditor postId={postId}/>;}

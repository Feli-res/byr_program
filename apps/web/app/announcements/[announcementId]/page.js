'use client';
import {useParams} from 'next/navigation';
import {AnnouncementDetail} from '../../../components/announcements';
export default function Page(){const {announcementId}=useParams();return <AnnouncementDetail announcementId={announcementId}/>;}

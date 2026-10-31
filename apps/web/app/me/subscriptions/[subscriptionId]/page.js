'use client';
import {useParams} from 'next/navigation';
import {ReminderDetail} from '../../../../components/reminders';
export default function Page(){const {subscriptionId}=useParams();return <ReminderDetail subscriptionId={subscriptionId}/>;}

'use client';
import {useParams} from 'next/navigation';
import {GoodsDetail} from '../../../../components/goods';
export default function Page(){const {goodsId}=useParams();return <GoodsDetail goodsId={goodsId} mode="owner"/>;}

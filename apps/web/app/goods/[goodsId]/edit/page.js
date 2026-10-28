'use client';
import {useParams} from 'next/navigation';
import {GoodsEditor} from '../../../../components/goods';
export default function Page(){const {goodsId}=useParams();return <GoodsEditor goodsId={goodsId}/>;}

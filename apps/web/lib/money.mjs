export function yuanToCents(input){
  const value=String(input).trim();
  if(!/^(?:0|[1-9][0-9]{0,4})(?:\.[0-9]{1,2})?$/.test(value))throw new Error('价格须为 0～99999.99 元，最多两位小数');
  const [whole,decimal='']=value.split('.');return Number(whole)*100+Number(decimal.padEnd(2,'0'));
}
export function centsToYuan(cents){
  if(!Number.isInteger(cents)||cents<0||cents>9999999)throw new Error('金额数据不正确');
  return `${Math.floor(cents/100)}.${String(cents%100).padStart(2,'0')}`;
}

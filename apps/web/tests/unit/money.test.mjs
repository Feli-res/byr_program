import {test} from 'node:test';
import assert from 'node:assert/strict';
import {yuanToCents,centsToYuan} from '../../lib/money.mjs';
test('free, decimal precision and the maximum amount convert exactly',()=>{assert.equal(yuanToCents('0'),0);assert.equal(yuanToCents('0.01'),1);assert.equal(yuanToCents('0.10'),10);assert.equal(yuanToCents('0.29'),29);assert.equal(yuanToCents('12.3'),1230);assert.equal(yuanToCents('99999.99'),9999999);});
test('invalid prices cannot be silently rounded or interpreted as exponents',()=>{for(const input of ['','-1','1.001','1e2','100000','NaN','1,000','1.','0x10','免费'])assert.throws(()=>yuanToCents(input));});
test('integer cents format and round-trip without float arithmetic',()=>{for(const cents of [0,1,10,29,100,1230,250001,9999999])assert.equal(yuanToCents(centsToYuan(cents)),cents);assert.equal(centsToYuan(29),'0.29');});

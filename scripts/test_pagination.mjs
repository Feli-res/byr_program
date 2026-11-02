import assert from 'node:assert/strict';
import {pageWindow} from '../apps/web/lib/pagination.mjs';

assert.deepEqual(pageWindow(1, 1), [1]);
assert.deepEqual(pageWindow(2, 7), [1, 2, 3, 4, 5, 6, 7]);
assert.deepEqual(pageWindow(1, 20), [1, 2, 3, 'ellipsis', 20]);
assert.deepEqual(pageWindow(4, 20), [1, 2, 3, 4, 5, 6, 'ellipsis', 20]);
assert.deepEqual(pageWindow(10, 20), [1, 'ellipsis', 8, 9, 10, 11, 12, 'ellipsis', 20]);
assert.deepEqual(pageWindow(20, 20), [1, 'ellipsis', 18, 19, 20]);
assert.deepEqual(pageWindow(3, 50), [1, 2, 3, 4, 5, 'ellipsis', 50]);
assert.deepEqual(pageWindow(0, 20), pageWindow(1, 20));
assert.deepEqual(pageWindow(99, 20), pageWindow(20, 20));
console.log('PASS page window: edges, ellipsis, clamping and small totals');

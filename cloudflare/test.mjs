import {test} from 'node:test';import assert from 'node:assert/strict';import {appleStores} from './worker.js';
test('reject missing results',()=>assert.throws(()=>appleStores({})));
test('filter states and preserve unknown',()=>assert.deepEqual(appleStores({body:{stores:[{storeNumber:'a',state:'NY',storeName:'Test',partsAvailability:{}},{storeNumber:'b',state:'PA'}]}}),[{id:'a',name:'Test',status:'unknown'}]));

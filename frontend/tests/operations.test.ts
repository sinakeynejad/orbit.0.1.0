import {test} from 'node:test';
import assert from 'node:assert/strict';
import {LatestOperation} from '../src/operations.ts';
test('Stop aborts pending voice work and invalidates late results',()=>{
 const work=new LatestOperation(); const request=work.begin();
 work.cancel(); assert.equal(request.signal.aborted,true); assert.equal(request.isCurrent(),false);
});
test('Only the latest conversation response may update history',async()=>{
 const work=new LatestOperation(); const first=work.begin();const second=work.begin();
 let history='';await Promise.resolve();if(second.isCurrent())history='second';
 await Promise.resolve();if(first.isCurrent())history='first';
 assert.equal(history,'second');assert.equal(first.signal.aborted,true);assert.equal(second.signal.aborted,false);
});
test('Repeated cancellation is safe and a new request can start',()=>{
 const work=new LatestOperation();work.cancel();work.cancel();assert.equal(work.begin().isCurrent(),true);
});

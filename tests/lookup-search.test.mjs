import test from 'node:test';
import assert from 'node:assert/strict';
import {lookupSearch} from '../frontend/src/lookup-search.js';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
test('lookup waits for minimum characters and typing pause',async()=>{const calls=[],results=[];const q=lookupSearch(async t=>{calls.push(t);return t},(v)=>results.push(v));q.set('al');await sleep(60);assert.equal(calls.length,0);q.set('ali');await sleep(20);q.set('alic');await sleep(20);assert.equal(calls.length,0);await sleep(45);assert.deepEqual(calls,['alic']);assert.equal(results.at(-1),'alic');q.dispose();});
test('lookup serializes in-flight requests and discards stale replies',async()=>{const calls=[],results=[],finish=[];const q=lookupSearch(t=>{calls.push(t);return new Promise(r=>finish.push(r))},v=>{if(v)results.push(v)});q.set('ali');await sleep(65);q.set('alice');await sleep(65);assert.deepEqual(calls,['ali']);finish[0]('old');await sleep(0);assert.deepEqual(calls,['ali','alice']);assert.deepEqual(results,[]);finish[1]('new');await sleep(0);assert.deepEqual(results,['new']);q.dispose();});
test('clearing and disposal suppress pending lookup work',async()=>{let calls=0;const q=lookupSearch(async()=>{calls++;return []},()=>{});q.set('ali');q.set('');await sleep(65);assert.equal(calls,0);q.set('alice');q.dispose();await sleep(65);assert.equal(calls,0);});
test('recent suggestions reuse a field-local cache and expired suggestions refresh',async()=>{
  let calls=0, now=1000; const original=Date.now; Date.now=()=>now;
  const results=[]; const q=lookupSearch(async t=>{calls++;return t},v=>{if(v)results.push(v)},3,0);
  try {
    q.set('alice'); await sleep(10); q.set(''); q.set('alice');
    assert.equal(calls,1); assert.deepEqual(results,['alice','alice']);
    now+=30001; q.set('alice'); await sleep(10); assert.equal(calls,2);
    const other=lookupSearch(async t=>{calls++;return t},()=>{},3,0);
    other.set('alice'); await sleep(10); assert.equal(calls,3); other.dispose();
  } finally { q.dispose(); Date.now=original; }
});
test('cache hits invalidate older in-flight responses',async()=>{
  const results=[]; let finish;
  const q=lookupSearch(t=>t==='alice'?Promise.resolve(t):new Promise(r=>finish=r),v=>{if(v)results.push(v)},3,0);
  q.set('alice'); await sleep(10); q.set('bob'); await sleep(10); q.set('alice'); finish('bob'); await sleep(0);
  assert.deepEqual(results,['alice','alice']); q.dispose();
});

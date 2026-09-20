import test from 'node:test';
import assert from 'node:assert/strict';
import {lookupSearch} from '../frontend/src/lookup-search.js';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
test('lookup waits for minimum characters and typing pause',async()=>{const calls=[],results=[];const q=lookupSearch(async t=>{calls.push(t);return t},(v)=>results.push(v));q.set('al');await sleep(60);assert.equal(calls.length,0);q.set('ali');await sleep(20);q.set('alic');await sleep(20);assert.equal(calls.length,0);await sleep(45);assert.deepEqual(calls,['alic']);assert.equal(results.at(-1),'alic');q.dispose();});
test('lookup serializes in-flight requests and discards stale replies',async()=>{const calls=[],results=[],finish=[];const q=lookupSearch(t=>{calls.push(t);return new Promise(r=>finish.push(r))},v=>{if(v)results.push(v)});q.set('ali');await sleep(65);q.set('alice');await sleep(65);assert.deepEqual(calls,['ali']);finish[0]('old');await sleep(0);assert.deepEqual(calls,['ali','alice']);assert.deepEqual(results,[]);finish[1]('new');await sleep(0);assert.deepEqual(results,['new']);q.dispose();});
test('clearing and disposal suppress pending lookup work',async()=>{let calls=0;const q=lookupSearch(async()=>{calls++;return []},()=>{});q.set('ali');q.set('');await sleep(65);assert.equal(calls,0);q.set('alice');q.dispose();await sleep(65);assert.equal(calls,0);});

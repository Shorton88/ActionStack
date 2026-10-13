import test from 'node:test';
import assert from 'node:assert/strict';
import { keyedActionResults } from '../frontend/src/action-results.js';

const first={app_run_id:9,status:'success',summary:{task_id:'A'},data:[{task_id:'A'}]};
const second={app_run_id:9,status:'failed',summary:{task_id:'B'},data:[]};

test('reordered action results keep their own summary, data, and disclosure identity',()=>{
  const original=keyedActionResults([first,second]);
  const reordered=keyedActionResults([second,first]);
  assert.deepEqual(reordered,[original[1],original[0]]);
  assert.equal(reordered[0].result,second);
  assert.equal(reordered[1].result,first);
});

test('new asynchronous results do not shift existing result identities',()=>{
  const original=keyedActionResults([first,second]);
  const updated=keyedActionResults([{app_run_id:10,status:'failed',data:[]},first,second]);
  assert.deepEqual(updated.slice(1),original);
});

test('identical results remain separate and app runs are never merged',()=>{
  const rows=keyedActionResults([first,{...first},{...first,app_run_id:10}]);
  assert.equal(rows.length,3);
  assert.equal(new Set(rows.map(row=>row.key)).size,3);
});

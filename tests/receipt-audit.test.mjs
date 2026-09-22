import test from 'node:test';
import assert from 'node:assert/strict';
import { csvCell, receiptExport, receiptTimeline, submissionsCsv } from '../frontend/src/receipt-audit.js';

const submission = {
  id:'receipt-1', form_id:'scan', form_title:'Scan endpoints', form_version:2,
  form:{id:'scan', title:'Scan endpoints', version:2, revision:3, workspace_id:'security', fields:[{key:'targets',type:'text_multi',label:'Targets'}],mapping:{label:'actionstack_security',run_automation:true}},
  inputs:{targets:['HOST-A','HOST-B'],reason:'Requested, by audit\nwith "quotes"'},
  submitted_by:'alice',submitted_at:'2026-09-21T10:00:00Z',updated_at:'2026-09-21T10:00:02Z',
  status:'submitted',attempts:1,error:null,container_id:21,artifact_id:22,event_url:'https://soar.example/mission/21',demo:false,
  approval:{approval_required:false,approval_policy:'none'},
};
const group = items => ({items,total:items.length,truncated:false,error:null});
const activity = {
  checked_at:'2026-09-21T10:10:00Z', automation_enabled:true,demo:false,
  playbooks:group([{id:1,name:'Scan playbook',status:'running',updated_at:'2026-09-21T10:02:00Z'}]),
  actions:group([{id:2,name:'Scan target endpoints',status:'success',playbook_run_id:1,updated_at:'2026-09-21T12:01:00+02:00',summaries:[{app_run_id:3,status:'success',data:[{value:'x'}],data_truncated:true}]}]),
  blocks:group([{id:'block:1',name:'Format report',block_type:'Format',status:'unknown',updated_at:null}]),
};
const meta={exported_at:'2026-09-21T11:00:00Z',exported_by:'auditor',app_version:'0.5.5',workspace_id:'security',mine:false};

test('timeline orders actual update times, normalizes zones, and leaves undated blocks last',()=>{
  const result=receiptTimeline(submission,activity);
  assert.deepEqual(result.map(r=>r.id),['submitted','delivery','actions:2','playbooks:1','blocks:block:1']);
  assert.equal(result[2].at,'2026-09-21T10:01:00.000Z');
  assert.equal(result[4].at,null);
  assert.equal(result[4].status,'unknown');
});
test('invalid and absent dates do not become fabricated event times',()=>{
  const result=receiptTimeline({...submission,updated_at:'not a timestamp'},null);
  assert.equal(result.length,2);assert.equal(result[1].at,null);
  assert.equal(result[1].name,'Latest delivery update');
});
test('receipt export preserves submitted values, result limits and stale-read failures, but excludes connection internals',()=>{
  const source={...submission,connection:{token:'secret'},actor:{session:'secret'},container_payload:{private:'secret'},fingerprint:'secret'};
  const result=receiptExport(source,{data:activity,error:'Refresh failed',loading:false},meta);
  assert.equal(result.schema_version,1);assert.equal(result.exported_by,'auditor');
  assert.deepEqual(result.receipt.inputs,submission.inputs);
  assert.equal(result.activity.actions.items[0].summaries[0].data_truncated,true);
  assert.equal(result.activity.checked_at,activity.checked_at);assert.equal(result.activity_error,'Refresh failed');
  assert.equal(result.receipt.form_snapshot.version,2);
  assert.ok(!JSON.stringify(result).includes('secret'));
});
test('unavailable activity is explicit and does not prevent a delivery receipt export',()=>{
  const result=receiptExport(submission,{data:null,error:'Access unavailable',loading:false},meta);
  assert.equal(result.activity,null);assert.equal(result.activity_error,'Access unavailable');assert.equal(result.timeline.length,2);
});
test('CSV neutralizes formulas, including control and whitespace prefixes',()=>{
  for(const input of ['=HYPERLINK("x")','+cmd','-1+2','@SUM(A1)','  =1+2','\ttext','\r=1+2','\n=1+2']) {
    assert.ok(csvCell(input).startsWith('"\''),input);
  }
  assert.equal(csvCell('safe "value",\nnext'),'"safe ""value"",\nnext"');
  assert.equal(csvCell(null),'""');assert.equal(csvCell(false),'"false"');
});
test('CSV contains all filtered rows across pages, export scope, canonical inputs and identifiers',()=>{
  const csv=submissionsCsv(Array.from({length:12},(_,i)=>({...submission,id:`receipt-${i+1}`})),meta);
  assert.ok(csv.startsWith('\uFEFF"exported_at"'));assert.ok(csv.endsWith('\r\n'));
  assert.ok(csv.includes('"receipt-12"'));assert.ok(csv.includes('up to 200'));
  assert.ok(csv.includes('"auditor"'));assert.ok(csv.includes('"actionstack_security"'));
  assert.ok(csv.includes('HOST-A'));assert.ok(csv.includes('""targets""'));assert.ok(csv.includes('"21","22"'));
});

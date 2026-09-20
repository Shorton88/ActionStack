import test from 'node:test';
import assert from 'node:assert/strict';
import { approvalRequired, approvalRule } from '../frontend/src/approval.js';
const form = { mapping: { policy: 'block_object' }, fields: [{ key:'duration',type:'select' }] };
test('legacy preview preserves Forever approval', () => {
  assert.equal(approvalRequired(form, {duration:'forever'}), true);
  assert.equal(approvalRequired(form, {duration:'4h'}), false);
  assert.equal(approvalRule(form).policy, 'soar_playbook');
});
test('custom conditions replace the template default and use any matching row', () => {
  const f = structuredClone(form);
  f.mapping.approval = { mode:'conditional', policy:'soar_playbook', conditions:[{field:'duration',equals:'90d'}] };
  assert.equal(approvalRequired(f, {duration:'90d'}), true);
  assert.equal(approvalRequired(f, {duration:'forever'}), false);
});
test('hidden and missing values cannot satisfy the preview', () => {
  const f = structuredClone(form);
  f.fields[0].show_when = {field:'type',equals:'block'};
  assert.equal(approvalRequired(f,{duration:'forever'}), false);
  assert.equal(approvalRequired(f,{duration:'forever',type:'block'}), true);
});
test('checkbox matching preserves types and always/never need no conditions', () => {
  const f = {fields:[{key:'ok',type:'checkbox'}],mapping:{approval:{mode:'conditional',policy:'soar_playbook',conditions:[{field:'ok',equals:false}]}}};
  assert.equal(approvalRequired(f,{ok:false}), true);
  assert.equal(approvalRequired(f,{}), true);
  assert.equal(approvalRequired(f,{ok:'false'}), false);
  f.mapping.approval.mode='always'; assert.equal(approvalRequired(f,{}), true);
  f.mapping.approval.mode='never'; assert.equal(approvalRequired(f,{ok:false}), false);
});

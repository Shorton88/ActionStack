import test from 'node:test';
import assert from 'node:assert/strict';
import { formExport, parseFormFile, MAX_FORM_FILE_BYTES } from '../frontend/src/form-transfer.js';

test('portable exports preserve configuration without source identity, access, or history', () => {
  const source = { id:'source', workspace_id:'hr', title:'Access request', category:'People', description:'Help', intro:'Start here', icon:'user', accent:'cyan', fields:[{ key:'enabled', type:'checkbox', label:'Enabled', default:true }], mapping:{ label:'actionstack_hr', run_automation:true }, access:{edit_roles:['source_admin']}, revision:8, version:4, state:'published', updated_by:'alice', validation_policy_id:'local-policy', connection:{token:'secret'} };
  const result=formExport(source,'0.5.9');
  assert.deepEqual(Object.keys(result.form).sort(),['title','description','category','icon','accent','intro','fields','mapping'].sort());
  assert.deepEqual(parseFormFile(JSON.stringify(result)),result);
  assert.equal(result.form.fields[0].default,true);
  assert.equal(result.form.mapping.run_automation,true);
  assert.ok(!JSON.stringify(result).includes('secret'));
  result.form.fields[0].default=false;
  assert.equal(source.fields[0].default,true);
});

test('import file parser rejects bad JSON, unsupported formats, and oversized UTF-8 files', () => {
  for (const input of ['{', 'null', '[]', '{}', JSON.stringify({format:'actionstack-form',format_version:2}), JSON.stringify({format:'actionstack-form',format_version:true})]) assert.throws(()=>parseFormFile(input));
  assert.throws(()=>parseFormFile('é'.repeat(MAX_FORM_FILE_BYTES/2+1)),/200 KB/);
});

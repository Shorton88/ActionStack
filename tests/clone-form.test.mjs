import test from 'node:test';
import assert from 'node:assert/strict';
import {cloneForm} from '../frontend/src/clone-form.js';
test('cloning creates an independent draft without publication or audit identity',()=>{
 const source={id:'old',title:'Employee request',workspace_id:'hr',description:'Request',category:'People',icon:'file',accent:'violet',intro:'Hello',fields:[{key:'user',type:'lookup',lookup:{search:'| inputlookup users | table id name',value_field:'id',label_field:'name'}}],mapping:{label:'actionstack_hr',approval:{mode:'always',policy:'soar_playbook',conditions:[]}},access:{edit_roles:['as_hr_admin']},revision:9,version:4,state:'published',updated_by:'alice',updated_at:'yesterday',_key:'old:9'};
 const copy=cloneForm(source,'abcd');
 assert.equal(copy.id,'employee-request-copy-abcd');assert.equal(copy.state,'draft');assert.equal(copy.revision,0);assert.equal(copy.version,0);
 assert.equal(copy.workspace_id,'hr');assert.deepEqual(copy.access,source.access);
 assert.ok(!('updated_by' in copy));assert.ok(!('_key' in copy));
 copy.fields[0].lookup.label_field='changed';copy.access.edit_roles.push('test');
 assert.equal(source.fields[0].lookup.label_field,'name');assert.equal(source.access.edit_roles.length,1);
});

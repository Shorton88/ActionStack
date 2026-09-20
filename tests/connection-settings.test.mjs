import test from 'node:test';
import assert from 'node:assert/strict';
import {connectionSettingsPayload} from '../frontend/src/connection-settings.js';

test('connection edits send only writable settings, excluding KV and response metadata',()=>{
  const editable={soar_url:'https://soar.example.test',instance_name:'Edited',asset_id:17,ca_pem:'saved-ca',ignore_certificate_errors:true,request_timeout:20,label_prefix:'automation_',revision:4};
  const response={...editable,_key:'4',_user:'nobody',secret_ref:'internal',token_configured:true,demo:false,unexpected:'storage metadata'};
  assert.deepEqual(connectionSettingsPayload(response),editable);
  assert.deepEqual(connectionSettingsPayload(response,'replacement-token'),{...editable,token:'replacement-token'});
  assert.equal(response._user,'nobody');
});

test('older connection responses default certificate validation on without replacing the saved token',()=>{
  const payload=connectionSettingsPayload({soar_url:'https://soar.example.test',instance_name:'Old',asset_id:null,ca_pem:'saved-ca',request_timeout:15,revision:1});
  assert.equal(payload.ignore_certificate_errors,false);
  assert.equal(payload.label_prefix,'');
  assert.equal(payload.ca_pem,'saved-ca');
  assert.ok(!Object.hasOwn(payload,'token'));
});

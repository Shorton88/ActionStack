import test from 'node:test';
import assert from 'node:assert/strict';
import { webcrypto, createHash } from 'node:crypto';
import { randomId, cloneDefinition, submissionFingerprint } from '../frontend/src/browser-compat.js';

const httpCrypto = { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) };

test('creation IDs work when randomUUID is unavailable on an HTTP origin', () => {
  assert.throws(() => httpCrypto.randomUUID(), TypeError);
  const ids = Array.from({length: 100}, () => randomId(httpCrypto));
  assert.equal(new Set(ids).size, ids.length);
  for (const id of ids) assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

test('ID generation fails explicitly rather than using weak randomness', () => {
  assert.throws(() => randomId({}), /cannot generate request IDs/);
});

test('JSON form cloning does not need structuredClone and remains independent', () => {
  const form = { fields: [{key:'object_type',options:[{value:'ip',label:'IP'}],help:undefined}], mapping: {tags:['demo']} };
  const copy = cloneDefinition(form);
  copy.fields[0].options[0].label = 'Changed';
  copy.mapping.tags.push('new');
  assert.equal(form.fields[0].options[0].label,'IP');
  assert.deepEqual(form.mapping.tags,['demo']);
  assert.equal('help' in copy.fields[0],false);
});

test('HTTP fallback preserves the secure-context pending-submission fingerprint', async () => {
  const value=JSON.stringify({user:'alice',form:'block-object',version:1,values:{reason:'Unicode café 🔒',duration:'4h'}});
  const expected=createHash('sha256').update(value,'utf8').digest('hex');
  let calls=0;
  const fallback=async (received) => { calls++; assert.equal(received,value); return expected; };
  assert.equal(await submissionFingerprint(value,fallback,httpCrypto),expected);
  assert.equal(calls,1);
  assert.equal(await submissionFingerprint(value,fallback,webcrypto),expected);
  assert.equal(calls,1);
});

test('fingerprint fallback surfaces API errors without inventing a new key', async () => {
  await assert.rejects(submissionFingerprint('{}',async()=>{throw new Error('Session expired');},httpCrypto),/Session expired/);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { mergeValues } from '../frontend/src/multi-values.js';

test('lists accept commas, newlines and semicolons, trim and deduplicate', () => {
  assert.deepEqual(mergeValues(['alice'], ' alice, bob\r\ncarol; bob,, '), ['alice', 'bob', 'carol']);
  assert.deepEqual(mergeValues([], 'Alice Example'), ['Alice Example']);
});
test('lists enforce the total and per-item limits without changing existing values', () => {
  const existing = Array.from({length: 24}, (_, i) => String(i));
  assert.equal(mergeValues(existing, '0,new,new').length, 25);
  assert.throws(() => mergeValues(existing, 'new,extra'), /25 items/);
  assert.throws(() => mergeValues(existing, 'x'.repeat(201)), /200 characters/);
  assert.equal(existing.length, 24);
});

test('lookup lists deduplicate ignoring case while retaining stored casing', () => {
  assert.deepEqual(mergeValues(['Alice'], 'ALICE,alice,Bob,BOB', true), ['Alice', 'Bob']);
  assert.deepEqual(mergeValues([], 'Alice,alice'), ['Alice', 'alice']);
});

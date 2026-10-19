import test from 'node:test';
import assert from 'node:assert/strict';
import { classifyField, proposeValue } from './field-map.mjs';

test('standard autocomplete and explicit job-form labels', () => {
  assert.deepEqual(classifyField({ autocomplete: 'given-name' }), {kind:'suggest',field:'firstName',reason:'Standard autocomplete attribute'});
  assert.equal(classifyField({ label: 'Phone number' }).field, 'phone');
  assert.equal(classifyField({ label: 'Postal Code' }).field, 'postalCode');
});
test('blocks passwords, hidden fields and leaves uploads to candidate', () => {
  assert.equal(classifyField({ type: 'password', label:'Password' }).kind, 'blocked');
  assert.equal(classifyField({ type: 'hidden', label:'First name' }).kind, 'blocked');
  assert.equal(classifyField({ type: 'file', label:'Resume' }).kind, 'manual');
});
test('sensitive and application-specific questions need manual answer', () => {
  for(const label of ['Gender','Visa sponsorship','Are you authorized to work?', 'EEO veteran status','Expected salary','Date of birth']) {
    assert.equal(classifyField({ label }).kind, 'manual', label);
  }
  assert.equal(classifyField({ type:'checkbox', label:'I agree' }).kind, 'manual');
});
test('ambiguous or unrecognized fields remain manual', () => {
  assert.equal(classifyField({ label:'Contact phone or email' }).kind, 'manual');
  assert.equal(classifyField({ id:'r9f3m' }).kind, 'manual');
});
test('suggestions use explicit profile strings and still require review', () => {
  assert.deepEqual(proposeValue({ label:'Email' }, {email:'candidate@example.org'}), {
    status:'candidate_review_required',field:'email',value:'candidate@example.org',reason:'Explicit form label or attribute'
  });
  assert.equal(proposeValue({ label:'Email' }, {}).status,'manual');
  assert.equal(proposeValue({ label:'Gender' }, { gender: 'X'}).status,'manual');
});

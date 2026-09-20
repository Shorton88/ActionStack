import test from 'node:test';
import assert from 'node:assert/strict';
import { createTransport, csrfToken, ApiError } from '../frontend/src/transport.js';

const token = '12345678901234567890';
const environment = (overrides={}) => ({
  pathname:'/en-US/app/splunk_actionstack/actionstack',port:'8000',protocol:'http:',
  cookie:()=>`splunkweb_csrf_token_8000=${token}`,
  fetch:async()=>new Response(JSON.stringify({data:{ok:true}})),
  ...overrides,
});

test('settings POST includes the AJAX header, matching form key, cookies and original JSON', async()=>{
  let count=0;
  const request=createTransport(environment({fetch:async(url,init)=>{
    count++;
    assert.equal(url,'/en-US/splunkd/__raw/services/actionstack/settings');
    assert.equal(init.method,'POST');
    assert.equal(init.credentials,'same-origin');
    assert.equal(init.headers['X-Requested-With'],'XMLHttpRequest');
    assert.equal(init.headers['X-Splunk-Form-Key'],token);
    assert.equal(init.headers['Content-Type'],'application/json');
    assert.deepEqual(JSON.parse(init.body),{soar_url:'https://soar.example.test',token:'TEST_ONLY'});
    return new Response(JSON.stringify({data:{token_configured:true}}));
  }}));
  assert.deepEqual(await request('/settings',{soar_url:'https://soar.example.test',token:'TEST_ONLY'}),{token_configured:true});
  assert.equal(count,1);
});

test('current-port token wins over another Splunk instance cookie',()=>{
  assert.equal(csrfToken(`splunkweb_csrf_token_9000=other; splunkweb_csrf_token_8000=${token}`,'8000','http:'),token);
});

test('reverse proxy supports a single internal-port token',()=>{
  assert.equal(csrfToken(`splunkweb_csrf_token_8000=${token}`,'','https:'),token);
});

test('ambiguous or malformed cookies never select an arbitrary token',()=>{
  for(const cookies of ['splunkweb_csrf_token_8000=a; splunkweb_csrf_token_9000=b','splunkweb_csrf_token_8000=','splunkweb_csrf_token_8000=%GG','splunkweb_csrf_token_8000=bad%0Avalue','splunkweb_csrf_token_8000fake=a']) {
    assert.equal(csrfToken(cookies,'443','https:'),undefined);
  }
  assert.equal(csrfToken('splunkweb_csrf_token_8000=a; splunkweb_csrf_token_8000=b','8000','http:'),undefined);
});

test('quoted/encoded tokens preserve full string precision',()=>{
  assert.equal(csrfToken(`splunkweb_csrf_token_8000=%22${token}%22`,'8000','http:'),token);
});

test('missing token blocks mutation before credentials leave the browser',async()=>{
  let calls=0;
  const request=createTransport(environment({cookie:()=>'',fetch:async()=>{calls++;return new Response('{}');}}));
  await assert.rejects(request('/settings',{token:'TEST_SECRET'}),error=>error instanceof ApiError && error.status===401 && /No request was sent/.test(error.message) && !error.message.includes('TEST_SECRET'));
  assert.equal(calls,0);
});

test('renewed CSRF cookie is read on each request',async()=>{
  let current='first'; const sent=[];
  const request=createTransport(environment({cookie:()=>`splunkweb_csrf_token_8000=${current}`,fetch:async(url,init)=>{sent.push(init.headers['X-Splunk-Form-Key']);return new Response('{"data":{}}');}}));
  await request('/settings/test',{}); current='second'; await request('/settings/test',{});
  assert.deepEqual(sent,['first','second']);
});

test('non-JSON Splunk CSRF rejection is actionable and never automatically retried',async()=>{
  let calls=0;
  const request=createTransport(environment({fetch:async()=>{calls++;return new Response('<html>Splunk cannot authenticate the request. CSRF validation failed. SECRET_DIAGNOSTIC</html>',{status:401});}}));
  await assert.rejects(request('/settings',{token:'TEST_SECRET'}),error=>error.status===401 && /CSRF validation failed/.test(error.message) && /did not reach SOAR/.test(error.message) && !/SECRET/.test(error.message));
  assert.equal(calls,1);
});

test('401 without CSRF is distinguished from SOAR connectivity',async()=>{
  const request=createTransport(environment({fetch:async()=>new Response('<html>Login required</html>',{status:401})}));
  await assert.rejects(request('/settings/test',{}),/Splunk session was rejected or has expired/);
});

test('structured backend permission and SOAR errors remain intact',async()=>{
  const request=createTransport(environment({fetch:async()=>new Response(JSON.stringify({error:'SOAR rejected the integration credentials or permissions.',fields:{token:'invalid'}}),{status:403})}));
  await assert.rejects(request('/settings/test',{}),error=>error.status===403 && error.message.startsWith('SOAR rejected') && error.fields.token==='invalid');
});

test('demo does not require or forward Splunk cookies',async()=>{
  const request=createTransport(environment({pathname:'/',cookie:()=>`splunkweb_csrf_token_8000=${token}`,fetch:async(url,init)=>{
    assert.equal(url,'/api/settings/test'); assert.equal(init.headers['X-Splunk-Form-Key'],undefined);
    return new Response('{"data":{"demo":true}}');
  }}));
  assert.deepEqual(await request('/settings/test',{}),{demo:true});
});

test('root proxy prefixes and locales remain in the request URL',async()=>{
  const request=createTransport(environment({pathname:'/splunk/de-DE/app/splunk_actionstack/actionstack',fetch:async(url)=>{
    assert.equal(url,'/splunk/de-DE/splunkd/__raw/services/actionstack/context');
    return new Response('{"data":{}}');
  }}));
  await request('/context');
});

test('invalid JSON envelopes produce controlled errors',async()=>{
  for(const body of ['null','[]','{}','<html>Unknown</html>']) {
    const request=createTransport(environment({fetch:async()=>new Response(body)}));
    await assert.rejects(request('/context'),error=>error instanceof ApiError && /unexpected response/.test(error.message));
  }
});

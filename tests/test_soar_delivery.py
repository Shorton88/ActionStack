"""Exercise the actual SOAR adapter against HTTP-shaped fixtures, without a server."""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib import error, parse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'splunk_actionstack'/'bin'))
from actionstack.core import Error, event_payload, seed_form
from actionstack.soar import Soar

TOKEN='do-not-display-this-token'

class Response(io.BytesIO):
    def getcode(self): return 200

def response(body): return Response(json.dumps(body).encode())
def rejected(status,body):
    return error.HTTPError('https://soar.example.test/rest/container',status,'Rejected',{},io.BytesIO(json.dumps(body).encode()))

def payloads(label='events'):
    f=seed_form(); f.update(version=1,revision=1); f['mapping']['label']=label
    actor={'username':'alice','roles':['user']}
    return event_payload(f,actor,{'object_type':'ip','object_value':'192.0.2.42','duration':'4h','reason':'fixture'},'submission-id','2026-09-16T00:00:00Z',{})

class SoarDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.remote=Soar({'soar_url':'https://soar.example.test'},TOKEN)
        self.remote.opener=Mock()
    def test_missing_label_prevents_post_and_explains_retry_snapshot(self):
        self.remote.opener.open.side_effect=[response({'count':0,'data':[]}),response({'label':['events']})]
        with self.assertRaises(Error) as err: self.remote.ensure('container',payloads('automation_requests')[0])
        self.assertEqual(err.exception.status,400)
        self.assertIn("'automation_requests'",err.exception.message)
        self.assertIn('No new event was created',err.exception.message)
        self.assertIn('original label',err.exception.message)
        self.assertTrue(all(c.args[0].method=='GET' for c in self.remote.opener.open.call_args_list))
    def test_http_400_shows_method_endpoint_status_and_soar_reason(self):
        self.remote.opener.open.side_effect=rejected(400,{'message':'Invalid source_data_identifier filter'})
        with self.assertRaises(Error) as err: self.remote.lookup('container',payloads()[0])
        self.assertEqual(err.exception.status,400)
        self.assertIn('GET /rest/container (HTTP 400)',err.exception.message)
        self.assertIn('Invalid source_data_identifier filter',err.exception.message)
    def test_post_payload_error_is_distinguished_from_lookup_error(self):
        self.remote.opener.open.side_effect=[response({'count':0,'data':[]}),response({'label':['events']}),rejected(400,{'message':'Invalid asset_id'})]
        with self.assertRaises(Error) as err: self.remote.ensure('container',payloads()[0])
        self.assertIn('POST /rest/container (HTTP 400)',err.exception.message)
        self.assertIn('Invalid asset_id',err.exception.message)
    def test_actual_adapter_creates_event_then_artifact_with_automation_disabled(self):
        self.remote.opener.open.side_effect=[response({'count':0,'data':[]}),response({'label':['events']}),response({'success':True,'id':501}),response({'count':0,'data':[]}),response({'success':True,'id':502})]
        container,artifact=payloads(); container_id=self.remote.ensure('container',container)
        artifact['container_id']=container_id
        self.assertEqual(self.remote.ensure('artifact',artifact),502)
        calls=[c.args[0] for c in self.remote.opener.open.call_args_list]
        self.assertEqual([r.method for r in calls],['GET','GET','POST','GET','POST'])
        self.assertEqual(json.loads(calls[2].data)['label'],'events')
        self.assertEqual(json.loads(calls[4].data)['label'],'events')
        self.assertFalse(json.loads(calls[2].data)['run_automation'])
        self.assertFalse(json.loads(calls[4].data)['run_automation'])
        self.assertEqual(json.loads(calls[4].data)['container_id'],501)
        query=parse.parse_qs(parse.urlsplit(calls[0].full_url).query)
        self.assertEqual(json.loads(query['_filter_source_data_identifier'][0]),container['source_data_identifier'])
    def test_duplicate_http_reply_is_reconciled_not_blindly_adopted(self):
        container=payloads()[0]
        self.remote.opener.open.side_effect=[response({'count':0,'data':[]}),response({'label':['events']}),rejected(400,{'failed':True,'existing_container_id':501}),response({'count':1,'data':[dict(container,id=501)]})]
        self.assertEqual(self.remote.ensure('container',container),501)
        self.assertEqual(self.remote.opener.open.call_count,4)
    def test_existing_matching_event_needs_no_label_preflight_or_write(self):
        container=payloads()[0]
        self.remote.opener.open.return_value=response({'count':1,'data':[dict(container,id=501)]})
        self.assertEqual(self.remote.ensure('container',container),501)
        self.assertEqual(self.remote.opener.open.call_count,1)
    def test_http_200_failure_keeps_message(self):
        self.remote.opener.open.return_value=response({'failed':True,'message':'Invalid label'})
        with self.assertRaises(Error) as err: self.remote.call('POST','container',payloads()[0])
        self.assertIn('HTTP 200',err.exception.message)
        self.assertIn('Invalid label',err.exception.message)
    def test_diagnostic_redacts_credentials_and_ignores_unrelated_response_fields(self):
        self.remote.opener.open.side_effect=rejected(400,{'message':f'Bad input. {TOKEN}; ph-auth-token: "another-token"; password=private; Authorization: Bearer third-token', 'request':{'token':'not-for-display'},'stack':'private-stack'})
        with self.assertRaises(Error) as err: self.remote.call('POST','container',{})
        for secret in [TOKEN,'another-token','private','third-token','not-for-display','private-stack']:
            self.assertNotIn(secret,err.exception.message)
        self.assertIn('[redacted]',err.exception.message)
    def test_html_and_large_error_details_are_not_echoed(self):
        for message in ['<html>secret proxy body</html>','x'*2000]:
            self.remote.opener.open.side_effect=rejected(400,{'message':message})
            with self.assertRaises(Error) as err: self.remote.call('POST','container',{})
            self.assertNotIn('<html>',err.exception.message)
            self.assertNotIn('secret proxy body',err.exception.message)
            self.assertLess(len(err.exception.message),750)
    def test_auth_failure_keeps_distinct_status(self):
        self.remote.opener.open.side_effect=rejected(403,{'message':'Access denied'})
        with self.assertRaises(Error) as err: self.remote.call('POST','container',{})
        self.assertEqual(err.exception.status,403)
        self.assertIn('HTTP 403',err.exception.message)

if __name__=='__main__': unittest.main()

"""Behavioral tests use isolated stores and a simulated remote; no live systems."""
import sys
import tempfile
import threading
import unittest
import ssl
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'splunk_actionstack'/'bin'))
sys.path.insert(0,str(ROOT/'scripts'))
from actionstack.core import Error, Conflict, PREFIX, seed_form, clone, validate_definition, validate_inputs, event_payload
from actionstack.service import Service
from actionstack.soar import Soar, validate_url, validate_ca, NoRedirect
from actionstack.splunk_store import identity
from dev_server import SQLiteStore, DemoSoar

ROLES=['admin','user','analyst','author','team_a','team_b']
def actor(name='alice',roles=None,caps=None):
    return {'username':name,'roles':roles or ['user'],'capabilities':[PREFIX+c for c in (caps or ['use','submit'])],'email':name+'@example.test','display_name':name.title()}
ADMIN=actor('admin',['admin'],['admin'])
def editable(f):
    return {k:clone(v) for k,v in f.items() if k not in ['_key','revision','version','state','updated_at','updated_by']}
def inputs(**kw): return dict(object_type='ip',object_value='192.0.2.42',duration='4h',reason='Test intake',**kw)

class ValidationTests(unittest.TestCase):
    def test_seed_is_valid(self): self.assertEqual(validate_definition(seed_form(),ROLES)['id'],'block-object')
    def test_ip_canonicalization(self):
        data=inputs(); data['object_value']='2001:0db8:0000:0000::1'
        self.assertEqual(validate_inputs(seed_form(),data)['object_value'],'2001:db8::1')
    def test_domain_canonicalization(self):
        data=inputs(); data.update(object_type='domain',object_value='EXAMPLE.TEST.')
        self.assertEqual(validate_inputs(seed_form(),data)['object_value'],'example.test')
        for bad in ['https://example.test','*.example.test','192.0.2.1','-bad.example','localhost',{'bad':'type'}]:
            data['object_value']=bad
            with self.subTest(value=bad),self.assertRaises(Error): validate_inputs(seed_form(),data)
    def test_hashes(self):
        for algorithm,size in [('sha1',40),('sha256',64)]:
            data=inputs(); data.update(object_type='hash',hash_type=algorithm,object_value='A'*size)
            self.assertEqual(validate_inputs(seed_form(),data)['object_value'],'a'*size)
            data['object_value']='a'*(size-1)
            with self.assertRaises(Error): validate_inputs(seed_form(),data)
    def test_hidden_unknown_and_invalid_duration_rejected(self):
        for key,value in [('hash_type','sha1'),('submitted_by','mallory'),('duration','2h')]:
            data=inputs(); data[key]=value
            with self.subTest(key=key),self.assertRaises(Error): validate_inputs(seed_form(),data)
    def test_every_duration_and_policy_is_typed(self):
        from actionstack.core import DURATIONS
        f=seed_form(); f.update(version=1,revision=1)
        for duration,seconds in DURATIONS.items():
            data=inputs(); data['duration']=duration
            c,a=event_payload(f,actor(),validate_inputs(f,data),'id','2026-09-15T00:00:00Z',{})
            envelope=c['data']['actionstack']
            self.assertEqual(envelope['derived']['requested_duration_seconds'],seconds)
            self.assertEqual(envelope['policy']['approval_required'],duration=='forever')
            self.assertFalse(c['run_automation']); self.assertFalse(a['run_automation'])
            self.assertEqual(envelope['submitted_by']['username'],'alice')
            self.assertNotIn('capabilities',envelope['submitted_by'])
    def test_reserved_projection_and_duplicate_cef_rejected(self):
        f=seed_form(); f['fields'].append({'key':'submitted_by','type':'text','label':'Impersonate'})
        with self.assertRaises(Error): validate_definition(f,ROLES)
        f=seed_form(); f['fields'][2]['cef_key']='actionstack_submitted_by'
        with self.assertRaises(Error): validate_definition(f,ROLES)
        f=seed_form(); f['fields'][2]['cef_key']='custom'; f['fields'][4]['cef_key']='custom'
        with self.assertRaises(Error): validate_definition(f,ROLES)
    def test_invalid_default_and_forward_condition_rejected(self):
        f=seed_form(); f['fields'][0]['default']='unavailable'
        with self.assertRaises(Error): validate_definition(f,ROLES)
        f=seed_form(); f['fields'][0]['show_when']={'field':'duration','equals':'4h'}
        with self.assertRaises(Error): validate_definition(f,ROLES)
    def test_generic_types_and_conditions(self):
        f={'fields':[{'key':'approved','label':'Approved','type':'checkbox'},{'key':'count','label':'Count','type':'number','min':1,'max':10,'show_when':{'field':'approved','equals':True}},{'key':'targets','type':'multiselect','label':'Targets','options':[{'value':'a','label':'A'}]}]}
        self.assertEqual(validate_inputs(f,{'approved':True,'count':2,'targets':['a']})['count'],2)
        for data in [{'count':2},{'approved':True,'count':True},{'targets':['a','a']},{'targets':['x']}]:
            with self.subTest(data=data),self.assertRaises(Error): validate_inputs(f,data)

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.db=Path(self.temp.name)/'test.sqlite'
        self.store=SQLiteStore(self.db); self.remote=DemoSoar(self.store)
        self.secret_values={}
        self.secrets=Mock(); self.secrets.get.side_effect=lambda k:self.secret_values.get(k,''); self.secrets.put.side_effect=lambda k,v:self.secret_values.update({k:v})
        self.factory=Mock(side_effect=lambda s,t:self.remote)
        self.svc=Service(self.store,self.secrets,self.factory,lambda:ROLES,demo=True)
        self.svc.bootstrap(); self.user=actor()
    def tearDown(self): self.temp.cleanup()
    def body(self,key='stable-key-1'):
        return {'form_id':'block-object','form_version':1,'inputs':inputs(),'idempotency_key':key}
    def submit(self,key='stable-key-1'): return self.svc.submit(self.user,self.body(key))
    def test_connection_can_be_edited_after_kv_metadata_is_added(self):
        from actionstack.service import DEFAULT_SETTINGS
        self.svc.save_settings(ADMIN,{'soar_url':'https://soar.example.test','revision':0,'token':'SECRET'})
        stored=self.svc.settings()
        secret_ref=stored['secret_ref']
        stored.update(_user='nobody',internal_metadata={'owner':'storage'})
        self.store.put('settings',stored)
        public=self.svc.public_settings()
        self.assertEqual(set(public),set(DEFAULT_SETTINGS)|{'token_configured','demo'})
        body={k:v for k,v in public.items() if k not in ['token_configured','demo']}
        body['instance_name']='Edited instance'
        saved=self.svc.save_settings(ADMIN,body)
        self.assertEqual(saved['instance_name'],'Edited instance')
        self.assertEqual(saved['revision'],2)
        self.assertEqual(self.svc.settings()['secret_ref'],secret_ref)
        self.secrets.put.assert_called_once()
    def test_connection_still_rejects_unknown_writable_keys(self):
        for key in ['_user','secret_ref','unexpected']:
            with self.subTest(key=key),self.assertRaises(Error):
                self.svc.save_settings(ADMIN,{'soar_url':'https://soar.example.test','revision':0,key:'unexpected'})
        self.assertEqual(self.store.list('settings'),[])
    def test_certificate_option_defaults_off_for_existing_settings(self):
        saved=self.svc.save_settings(ADMIN,{'soar_url':'https://soar.example.test','revision':0})
        self.assertFalse(saved['ignore_certificate_errors'])
        record=self.svc.settings(); record.pop('ignore_certificate_errors')
        self.store.put('settings',record)
        self.assertFalse(self.svc.public_settings()['ignore_certificate_errors'])
    def test_certificate_option_persists_and_reaches_test_and_delivery(self):
        saved=self.svc.save_settings(ADMIN,{'soar_url':'https://soar.example.test','revision':0,'ignore_certificate_errors':True})
        self.assertTrue(saved['ignore_certificate_errors'])
        self.svc.connection_test(ADMIN)
        self.assertTrue(self.factory.call_args.args[0]['ignore_certificate_errors'])
        self.submit()
        self.assertTrue(self.factory.call_args.args[0]['ignore_certificate_errors'])
        self.svc.save_settings(ADMIN,{'soar_url':'https://soar.example.test','revision':1,'ignore_certificate_errors':False})
        self.svc.connection_test(ADMIN)
        self.assertFalse(self.factory.call_args.args[0]['ignore_certificate_errors'])
    def test_certificate_option_rejects_non_booleans_without_saving(self):
        for value in ['false','true',0,1,None,[]]:
            with self.subTest(value=value),self.assertRaises(Error):
                self.svc.save_settings(ADMIN,{'soar_url':'https://soar.example.test','revision':0,'ignore_certificate_errors':value})
        self.assertEqual(self.store.list('settings'),[])
    def test_certificate_option_requires_app_admin(self):
        with self.assertRaises(Error) as err:
            self.svc.save_settings(self.user,{'soar_url':'https://soar.example.test','revision':0,'ignore_certificate_errors':True})
        self.assertEqual(err.exception.status,403)
        self.assertEqual(self.store.list('settings'),[])
    def test_browser_fingerprint_matches_sha256_without_creating_submission(self):
        import hashlib,json
        value=json.dumps({'user':'alice','form':'block-object','version':1,'values':{'reason':'Unicode café 🔒'}},ensure_ascii=False,separators=(',',':'))
        result=self.svc.dispatch(self.user,'POST','/submission-fingerprint',{'value':value})
        self.assertEqual(result['fingerprint'],hashlib.sha256(value.encode()).hexdigest())
        self.assertEqual(self.store.list('submissions'),[])
        self.factory.assert_not_called()
    def test_browser_fingerprint_requires_identity_capability_and_form_acl(self):
        import json
        value=json.dumps({'user':'alice','form':'block-object','version':1,'values':{}})
        for user in [actor('bob'),actor(caps=['use'])]:
            with self.assertRaises(Error): self.svc.dispatch(user,'POST','/submission-fingerprint',{'value':value})
        f=seed_form(); f['access']['submit_roles']=['analyst']
        self.svc.save_form(ADMIN,{'form':f,'expected_revision':1},True)
        with self.assertRaises(Error): self.svc.dispatch(self.user,'POST','/submission-fingerprint',{'value':value})
    def test_browser_fingerprint_rejects_malformed_requests(self):
        for body in [{},{'value':'invalid'},{'value':'[]'},{'value':'{}'},{'value':4},{'value':'a'*262145}]:
            with self.subTest(body=str(body)[:80]),self.assertRaises(Error): self.svc.dispatch(self.user,'POST','/submission-fingerprint',body)
    def test_connection_result_calls_out_unavailable_published_label(self):
        self.remote.labels=lambda:['events']
        result=self.svc.connection_test(ADMIN)
        self.assertEqual(result['labels'],['events'])
        self.assertIn('Block an object → automation_requests',result['message'])
        self.assertNotIn('intake test',result['message'])
    def test_rejected_submission_retains_error_and_old_routing_after_republish(self):
        self.factory.side_effect=lambda s,t:Mock(ensure=Mock(side_effect=Error(400,'SOAR rejected POST /rest/container (HTTP 400). Invalid label')))
        first=self.submit()
        self.assertEqual(first['status'],'failed')
        self.assertIn('HTTP 400',first['error'])
        f=seed_form(); f['mapping']['label']='events'
        self.svc.save_form(ADMIN,{'form':f,'expected_revision':1},True)
        captured=[]
        def ensure(kind,payload):
            captured.append((kind,clone(payload)))
            return self.remote.ensure(kind,payload)
        self.factory.side_effect=lambda s,t:Mock(ensure=ensure)
        self.svc.deliver(self.user,first['id'])
        self.assertEqual(captured[0][1]['label'],'automation_requests')
        self.assertEqual(captured[1][1]['label'],'automation_requests')
        newer=self.body('new-routing-key'); newer['form_version']=2
        self.svc.submit(self.user,newer)
        self.assertEqual(captured[2][1]['label'],'events')
        self.assertEqual(captured[3][1]['label'],'events')
    def test_legacy_retry_preserves_saved_artifact_label(self):
        self.factory.side_effect=lambda s,t:Mock(ensure=Mock(side_effect=Error(504,'Delivery uncertain')))
        first=self.submit()
        record=self.store.get('submissions',first['id'])
        # Simulate a request persisted by 0.1.3 before the artifact-label change.
        record['artifact_payload']['label']='event'
        self.store.put('submissions',record)
        self.factory.side_effect=lambda s,t:self.remote
        retried=self.svc.deliver(self.user,first['id'])
        self.assertEqual(retried['status'],'submitted')
        self.assertEqual(self.store.list('remote_artifact')[0]['label'],'event')
        self.assertEqual(len(self.store.list('remote_artifact')),1)
    def test_complete_event_and_receipt_redaction(self):
        r=self.submit(); self.assertEqual(r['status'],'submitted'); self.assertIsNotNone(r['artifact_id'])
        self.assertEqual(r['submitted_by'],'alice')
        for secret in ['connection','actor','fingerprint','container_payload','artifact_payload']: self.assertNotIn(secret,r)
        remote=self.store.list('remote_container')[0]
        self.assertEqual(remote['data']['actionstack']['inputs']['object_value'],'192.0.2.42')
    def test_idempotency_and_binding(self):
        first=self.submit(); second=self.submit()
        self.assertEqual(first['id'],second['id']); self.assertEqual(len(self.store.list('remote_container')),1)
        body=self.body(); body['inputs']['reason']='different'
        with self.assertRaises(Conflict): self.svc.submit(self.user,body)
    def test_concurrent_duplicate_across_two_services(self):
        peer=Service(SQLiteStore(self.db),self.secrets,self.factory,lambda:ROLES,demo=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda svc:svc.submit(self.user,self.body()),[self.svc,peer]))
        self.assertEqual(results[0]['id'],results[1]['id']); self.assertEqual(len(self.store.list('remote_container')),1)
        self.assertEqual(len(self.store.list('remote_artifact')),1)
    def test_partial_artifact_failure_resumes(self):
        remote=self.remote; failures=[True]
        def ensure(kind,payload):
            if kind=='artifact' and failures and failures.pop(): raise Error(504,'Delivery uncertain')
            return remote.ensure(kind,payload)
        self.factory.side_effect=lambda s,t:Mock(ensure=ensure)
        first=self.submit(); self.assertEqual(first['status'],'needs_attention'); self.assertIsNotNone(first['container_id']); self.assertIsNone(first['artifact_id'])
        self.factory.side_effect=lambda s,t:remote
        second=self.svc.deliver(self.user,first['id'])
        self.assertEqual(second['status'],'submitted'); self.assertEqual(second['attempts'],2); self.assertEqual(len(self.store.list('remote_container')),1)
    def test_lost_create_ack_is_reconciled(self):
        remote=self.remote
        def uncertain(kind,payload):
            remote.ensure(kind,payload); raise Error(504,'Unknown delivery')
        self.factory.side_effect=lambda s,t:Mock(ensure=uncertain)
        first=self.submit(); self.assertIsNone(first['container_id']); self.assertEqual(len(self.store.list('remote_container')),1)
        self.factory.side_effect=lambda s,t:remote
        second=self.svc.deliver(self.user,first['id']); self.assertEqual(second['status'],'submitted'); self.assertEqual(len(self.store.list('remote_container')),1)
    def test_permission_checks_and_identity_tampering(self):
        with self.assertRaises(Error): self.svc.submit(actor(caps=['use']),self.body())
        body=self.body(); body['actor']=ADMIN
        with self.assertRaises(Error): self.svc.submit(self.user,body)
        r=self.submit()
        with self.assertRaises(Error): self.svc.dispatch(actor('bob'),'GET','/submissions/'+r['id'])
        with self.assertRaises(Error): self.svc.dispatch(self.user,'GET','/settings')
        with self.assertRaises(Error): self.svc.dispatch(self.user,'GET','/audit')
    def test_form_acl_and_team_receipts(self):
        f=seed_form(); f['access'].update(view_roles=['analyst'],submit_roles=['analyst'],team_roles=['team_a'])
        self.svc.save_form(ADMIN,{'form':f,'expected_revision':1},True)
        self.assertEqual(self.svc.list_forms(self.user),[])
        with self.assertRaises(Error): self.submit()
        self.user=actor(roles=['analyst']); body=self.body(); body['form_version']=2
        r=self.svc.submit(self.user,body)
        self.assertEqual(self.svc.dispatch(actor('reader',['team_a'],['use','read_team']),'GET','/submissions/'+r['id'])['id'],r['id'])
        with self.assertRaises(Error): self.svc.dispatch(actor('reader',['team_b'],['use','read_team']),'GET','/submissions/'+r['id'])
    def test_drafts_versions_conflicts_and_archive(self):
        f=seed_form(); f['title']='New title'
        draft=self.svc.save_form(ADMIN,{'form':f,'expected_revision':1})
        self.assertEqual(self.svc.published(f['id'])['title'],'Block an object')
        with self.assertRaises(Conflict): self.svc.save_form(ADMIN,{'form':f,'expected_revision':1})
        published=self.svc.save_form(ADMIN,{'form':f,'expected_revision':draft['revision']},True)
        self.assertEqual(published['version'],2); self.assertEqual(self.svc.published(f['id'])['title'],'New title')
        with self.assertRaises(Conflict): self.submit()
        self.svc.archive(ADMIN,f['id'],published['revision'])
        with self.assertRaises(Error): self.svc.published(f['id'])
    def test_existing_idempotency_key_survives_republish(self):
        first=self.submit(); self.svc.save_form(ADMIN,{'form':seed_form(),'expected_revision':1},True)
        self.assertEqual(self.submit()['id'],first['id'])
    def test_edit_and_publish_capabilities_are_separate(self):
        author=actor('author',['author'],['use','edit'])
        f=seed_form(); f.update(id='custom'); f['access']['edit_roles']=['author']
        self.svc.save_form(author,{'form':f,'expected_revision':0})
        with self.assertRaises(Error): self.svc.save_form(author,{'form':f,'expected_revision':1},True)
        with self.assertRaises(Error): self.svc.save_form(actor('other',['user'],['edit']),{'form':f,'expected_revision':1})
    def test_lock_is_shared_and_released_after_error(self):
        with self.svc.lock('test',self.user):
            with self.assertRaises(Conflict):
                with self.svc.lock('test',self.user): pass
        self.assertIsNone(self.store.get('locks','test'))
        with self.assertRaises(RuntimeError):
            with self.svc.lock('test',self.user): raise RuntimeError()
        self.assertIsNone(self.store.get('locks','test'))
    def test_rate_budget_shared_and_minute_scoped(self):
        peer=Service(SQLiteStore(self.db),self.secrets,self.factory,lambda:ROLES,demo=True)
        with patch('actionstack.service.time.time',return_value=600):
            for i in range(10): (self.svc if i%2 else peer).delivery_budget(self.user)
            with self.assertRaises(Error) as err: peer.delivery_budget(self.user)
            self.assertEqual(err.exception.status,429)
        with patch('actionstack.service.time.time',return_value=660): peer.delivery_budget(self.user)
    def test_settings_secret_not_exposed_and_revision_checked(self):
        result=self.svc.save_settings(ADMIN,{'soar_url':'https://soar.example.test','revision':0,'token':'SECRET'})
        self.assertTrue(result['token_configured']); self.assertNotIn('secret_ref',result); self.assertNotIn('SECRET',str(result))
        with self.assertRaises(Conflict): self.svc.save_settings(ADMIN,{'soar_url':'https://other.example.test','revision':0})
    def test_retry_preserves_original_connection_and_permission(self):
        self.svc.save_settings(ADMIN,{'soar_url':'https://first.example.test','revision':0,'token':'TOKEN_ONE'})
        self.factory.side_effect=lambda s,t:Mock(ensure=Mock(side_effect=Error(504,'Offline')))
        first=self.submit()
        self.svc.save_settings(ADMIN,{'soar_url':'https://second.example.test','revision':1,'token':'TOKEN_TWO'})
        self.factory.side_effect=lambda s,t:self.remote
        self.svc.deliver(self.user,first['id'])
        settings,token=self.factory.call_args.args
        self.assertEqual(settings['soar_url'],'https://first.example.test'); self.assertEqual(token,'TOKEN_ONE')
    def test_retry_rechecks_current_acl(self):
        self.factory.side_effect=lambda s,t:Mock(ensure=Mock(side_effect=Error(504,'Offline')))
        first=self.submit(); f=seed_form(); f['access']['submit_roles']=['analyst']
        self.svc.save_form(ADMIN,{'form':f,'expected_revision':1},True)
        with self.assertRaises(Error): self.svc.deliver(self.user,first['id'])

class AdapterTests(unittest.TestCase):
    def test_certificate_verification_defaults_and_opt_out_are_isolated(self):
        verified=validate_ca('')
        bypass=validate_ca('',True)
        self.assertEqual(verified.verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(verified.check_hostname)
        self.assertEqual(bypass.verify_mode,ssl.CERT_NONE)
        self.assertFalse(bypass.check_hostname)
        restored=validate_ca('',False)
        self.assertEqual(restored.verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(restored.check_hostname)
        self.assertEqual(ssl.create_default_context().verify_mode,ssl.CERT_REQUIRED)
    def test_adapter_uses_saved_certificate_option_and_still_requires_https(self):
        for setting,expected in [(None,ssl.CERT_REQUIRED),(False,ssl.CERT_REQUIRED),(True,ssl.CERT_NONE)]:
            settings={'soar_url':'https://soar.example.test'}
            if setting is not None: settings['ignore_certificate_errors']=setting
            from urllib.request import HTTPSHandler
            remote=Soar(settings,'test')
            ctx=next(h for h in remote.opener.handlers if isinstance(h,HTTPSHandler))._context
            self.assertEqual(ctx.verify_mode,expected)
            self.assertEqual(ctx.check_hostname,expected==ssl.CERT_REQUIRED)
        with self.assertRaises(Error): Soar({'soar_url':'http://soar.example.test','ignore_certificate_errors':True},'test')
    def test_existing_ca_is_loaded_when_validation_enabled(self):
        context=Mock()
        with patch('actionstack.soar.ssl.create_default_context',return_value=context), patch('actionstack.soar.load_system_ca_bundles'):
            self.assertIs(validate_ca('saved-pem',False),context)
        context.load_verify_locations.assert_called_once_with(cadata='saved-pem')
    def test_https_origin_and_ca_required(self):
        for url in ['http://host','https://user:pass@host','https://host/path','https://host?q=x','https://host:bad']:
            with self.subTest(url=url),self.assertRaises(Error): validate_url(url)
        self.assertEqual(validate_url('https://soar.example.test/'),'https://soar.example.test')
        with self.assertRaises(Error): validate_ca('not a certificate')
        with self.assertRaises(Error): NoRedirect().redirect_request(None,None,None,None,None,None,None)
    def test_reconcile_never_adopts_foreign_data(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'test')
        f=seed_form(); f.update(version=1,revision=1)
        payload,_=event_payload(f,actor(),inputs(),'ours','now',{})
        obj=dict(payload,id=123); remote.call=Mock(return_value={'count':1,'data':[obj]})
        self.assertEqual(remote.ensure('container',payload),123); self.assertEqual(remote.call.call_count,1)
        foreign=clone(obj); foreign['data']['actionstack']['submitted_by']['username']='mallory'
        remote.call=Mock(return_value={'count':1,'data':[foreign]})
        with self.assertRaises(Error): remote.ensure('container',payload)
        remote.call=Mock(return_value={'count':2,'data':[obj,obj]})
        with self.assertRaises(Error): remote.ensure('container',payload)
    def test_malformed_lookup_fails_without_a_write(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'test')
        for bad in [{}, {'data':None}, {'data':[{'id':1}]}]:
            remote.call=Mock(return_value=bad)
            with self.subTest(value=bad),self.assertRaises(Error): remote.ensure('container',{'source_data_identifier':'ours'})
            self.assertEqual(remote.call.call_count,1)
            self.assertEqual(remote.call.call_args.args[0],'GET')
    def test_connection_check_uses_documented_read_endpoint(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'test')
        remote.call=Mock(return_value={'label':['events','automation_requests']})
        self.assertEqual(remote.labels(),['automation_requests','events'])
        remote.call.assert_called_once_with('GET','container_options')
    def test_trigger_only_on_final_artifact(self):
        f=seed_form(); f.update(version=1,revision=1); f['mapping']['run_automation']=True
        c,a=event_payload(f,actor(),inputs(),'id','now',{})
        self.assertFalse(c['run_automation']); self.assertTrue(a['run_automation'])
    def test_event_and_artifact_share_published_label_without_enabling_automation(self):
        for label in ['automation_requests','events','custom_intake']:
            with self.subTest(label=label):
                f=seed_form(); f.update(version=1,revision=1); f['mapping']['label']=label
                c,a=event_payload(f,actor(),inputs(),'id','now',{})
                self.assertEqual(c['label'],label); self.assertEqual(a['label'],label)
                self.assertFalse(c['run_automation']); self.assertFalse(a['run_automation'])
    def test_effective_role_expansion_handles_cycles(self):
        user=Mock(); user.call.return_value={'entry':[{'content':{'username':'alice','roles':['analyst'],'capabilities':[PREFIX+'use']}}]}
        system=Mock(); system.call.return_value={'entry':[{'name':'analyst','content':{'imported_roles':['user']}},{'name':'user','content':{'imported_roles':['analyst']}}]}
        resolved=identity(user,system); self.assertEqual(resolved['roles'],['analyst','user']); self.assertEqual(resolved['capabilities'],[PREFIX+'use'])

if __name__=='__main__': unittest.main()

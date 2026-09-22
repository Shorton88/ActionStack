import json
import unittest
from unittest.mock import Mock
import test_pages as fixtures
from actionstack.core import Error, clone, seed_form, validate_definition, validate_inputs, event_payload, approval_policy
from actionstack.soar import Soar
from actionstack.service import Service

def rule(mode='conditional',conditions=None,policy='soar_playbook'):
    return {'mode':mode,'conditions':conditions if conditions is not None else [{'field':'duration','equals':'forever'}] if mode=='conditional' else [],'policy':policy}

class ApprovalTests(unittest.TestCase):
    def test_legacy_forever_requirement_is_preserved(self):
        f=seed_form()
        for duration in ['4h','1d','30d','60d','90d','forever']:
            data=fixtures.inputs(); data['duration']=duration
            policy=approval_policy(f,validate_inputs(f,data))
            self.assertEqual(policy['approval_required'],duration=='forever')
            self.assertEqual(policy['approval_policy'],'soar_playbook' if duration=='forever' else 'none')
    def test_custom_conditions_project_trusted_policy(self):
        f=seed_form()
        f['mapping']['approval']=rule(conditions=[{'field':'duration','equals':'90d'},{'field':'object_type','equals':'domain'}])
        validate_definition(f,fixtures.ROLES)
        f.update(version=2,revision=2)
        for duration,required in [('4h',False),('90d',True),('forever',False)]:
            data=fixtures.inputs(); data['duration']=duration
            c,a=event_payload(f,fixtures.actor(),validate_inputs(f,data),'id','now',{})
            self.assertEqual(c['data']['actionstack']['policy']['approval_required'],required)
            self.assertEqual(a['cef']['actionstack_approval_required'],str(required).lower())
    def test_always_and_never_modes(self):
        f=seed_form()
        for mode in ['always','never']:
            f['mapping']['approval']=rule(mode,policy='soar_playbook')
            validate_definition(f,fixtures.ROLES)
            self.assertEqual(approval_policy(f,fixtures.inputs())['approval_required'],mode=='always')
    def test_invalid_rules_cannot_be_published(self):
        invalid=[None,[],{},rule('maybe'),rule(conditions=[]),rule(policy='arbitrary'),rule('never',[{'field':'duration','equals':'4h'}]),rule(conditions=[{'field':'missing','equals':'x'}]),rule(conditions=[{'field':'duration','equals':'invalid'}]),rule(conditions=[{'field':'reason','equals':'x'}]),rule(conditions=[{'field':'duration','equals':True}]),rule(conditions=[{'field':'duration','equals':'4h'}]*21)]
        for value in invalid:
            f=seed_form(); f['mapping']['approval']=value
            with self.subTest(value=value),self.assertRaises(Error): validate_definition(f,fixtures.ROLES)
    def test_hidden_fields_do_not_require_approval(self):
        f=seed_form(); f['mapping']['approval']=rule(conditions=[{'field':'hash_type','equals':'sha256'}])
        validate_definition(f,fixtures.ROLES)
        self.assertFalse(approval_policy(f,validate_inputs(f,fixtures.inputs()))['approval_required'])
    def test_checkbox_false_is_a_typed_condition(self):
        f=seed_form(); f['fields'].append({'key':'urgent','type':'checkbox','label':'Urgent'})
        f['mapping']['approval']=rule(conditions=[{'field':'urgent','equals':False}])
        validate_definition(f,fixtures.ROLES)
        self.assertTrue(approval_policy(f,{'urgent':False})['approval_required'])
        self.assertTrue(approval_policy(f,validate_inputs(f,fixtures.inputs()))['approval_required'])
        self.assertFalse(approval_policy(f,{})['approval_required'])
        self.assertFalse(approval_policy(f,{'urgent':0})['approval_required'])
        f['mapping']['approval']['conditions'][0]['equals']='false'
        with self.assertRaises(Error): validate_definition(f,fixtures.ROLES)

class ActivityAdapterTests(unittest.TestCase):
    def setUp(self): self.remote=Soar({'soar_url':'https://soar.example.test'},'secret-token')
    def row(self,**kw): return dict(id=4,container=17,status='running',playbook=9,_pretty_playbook='local/block',playbook_run=4,action='block ip',**kw)
    def test_only_event_scoped_safe_summary_is_exposed(self):
        raw=self.row(message='private',targets=[{'token':'private'}],outputs='private',result_data='private')
        self.remote.call=Mock(return_value={'count':1,'data':[raw]})
        result=self.remote.activity(17)
        self.assertEqual(result['playbooks']['items'][0]['name'],'local/block')
        self.assertEqual(result['actions']['items'][0]['name'],'block ip')
        self.assertNotIn('private',json.dumps(result))
        for call in self.remote.call.call_args_list:
            self.assertEqual(call.args[0],'GET')
            if call.args[1].endswith('/block_results'):
                self.assertEqual(call.args[1],'playbook_run/4/block_results')
            else:
                self.assertEqual(call.kwargs['query']['_filter_container'],17)
                self.assertNotIn('include_expensive',call.kwargs['query'])
    def test_foreign_or_malformed_rows_fail_closed(self):
        for raw in [dict(self.row(),container=18),dict(self.row(),id=True),None]:
            self.remote.call=Mock(return_value={'count':1,'data':[raw]})
            result=self.remote.activity(17)
            self.assertTrue(result['playbooks']['error']); self.assertEqual(result['playbooks']['items'],[])
    def test_partial_permissions_keep_other_run_group(self):
        self.remote.call=Mock(side_effect=[Error(403,'private remote message'),{'count':1,'data':[self.row()]},Error(403,'summaries denied')])
        result=self.remote.activity(17)
        self.assertIn('cannot read',result['playbooks']['error'])
        self.assertEqual(len(result['actions']['items']),1)
        self.assertNotIn('private',json.dumps(result))
    def test_empty_is_not_failure_and_truncation_is_explicit(self):
        self.remote.call=Mock(side_effect=[{'count':0,'data':[]},{'count':101,'data':[self.row()]},Error(403,'summaries denied')])
        result=self.remote.activity(17)
        self.assertIsNone(result['playbooks']['error']); self.assertEqual(result['playbooks']['total'],0)
        self.assertTrue(result['actions']['truncated'])
    def test_unknown_status_is_not_success_and_names_redact_token(self):
        row=dict(self.row(),status='new-state',_pretty_playbook='secret-token')
        self.remote.call=Mock(return_value={'count':1,'data':[row]})
        result=self.remote.activity(17)['playbooks']['items'][0]
        self.assertEqual(result['status'],'unknown'); self.assertEqual(result['name'],'[redacted]')

class ActivityServiceTests(unittest.TestCase):
    setUp=fixtures.ServiceTests.setUp
    tearDown=fixtures.ServiceTests.tearDown
    body=fixtures.ServiceTests.body
    submit=fixtures.ServiceTests.submit
    def test_receipt_acl_precedes_remote_access(self):
        receipt=self.submit(); self.factory.reset_mock()
        with self.assertRaises(Error) as exc: self.svc.dispatch(fixtures.actor('bob'),'GET','/submissions/'+receipt['id']+'/activity')
        self.assertEqual(exc.exception.status,404); self.factory.assert_not_called()
        result=self.svc.dispatch(self.user,'GET','/submissions/'+receipt['id']+'/activity')
        self.assertFalse(result['automation_enabled']); self.assertEqual(result['playbooks']['total'],0)
        self.assertEqual(self.store.get('submissions',receipt['id'])['status'],'submitted')
    def test_snapshot_connection_is_used_for_reads(self):
        receipt=self.submit()
        self.factory.reset_mock(); self.svc.activity(self.user,receipt['id'])
        self.assertEqual(self.factory.call_args.args[0],self.store.get('submissions',receipt['id'])['connection'])
    def test_status_budget_is_shared_but_separate_from_delivery(self):
        receipt=self.submit()
        peer=Service(self.store,self.secrets,self.factory,lambda:fixtures.ROLES,demo=True)
        from unittest.mock import patch
        with patch('actionstack.service.time.time',return_value=6000):
            for _ in range(10): self.svc.activity(self.user,receipt['id']); peer.activity(self.user,receipt['id'])
            with self.assertRaises(Error) as exc: self.svc.activity(self.user,receipt['id'])
            self.assertEqual(exc.exception.status,429)
            self.svc.delivery_budget(self.user)
    def test_rule_republish_does_not_rewrite_original_requirement(self):
        first=self.submit()
        f=seed_form(); f['mapping']['approval']=rule('always')
        self.svc.save_form(fixtures.ADMIN,{'form':f,'expected_revision':1},True)
        new=self.body('different-key'); new['form_version']=2
        second=self.svc.submit(self.user,new)
        first_record=self.store.get('submissions',first['id']); second_record=self.store.get('submissions',second['id'])
        self.assertEqual(first_record['artifact_payload']['cef']['actionstack_approval_required'],'false')
        self.assertEqual(second_record['artifact_payload']['cef']['actionstack_approval_required'],'true')
    def test_pending_delivery_has_no_remote_status_call(self):
        self.factory.side_effect=lambda s,t:Mock(ensure=Mock(side_effect=Error(504,'Timeout')))
        receipt=self.submit(); self.factory.reset_mock()
        with self.assertRaises(Error) as exc: self.svc.activity(self.user,receipt['id'])
        self.assertEqual(exc.exception.status,409); self.factory.assert_not_called()

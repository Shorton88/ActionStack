"""Behavioral coverage for field checks, array submissions and catalog lifecycle."""
import json
import unittest
from unittest.mock import Mock
import test_pages as fx
from actionstack.core import Error, Conflict, clone, seed_form, validate_definition, validate_inputs, event_payload
from actionstack.field_validation import validate_field_inputs
from actionstack.lookups import lookup_spl, LookupSearch
from actionstack.service import Service
from dev_server import DemoLookup

CONFIG={'search':'| inputlookup identity_lookup_expanded | fields identity','app':'search','min_chars':3,'debounce_ms':50}
def clean(f):return {k:clone(v) for k,v in f.items() if k not in ['_key','revision','version','state','updated_at','updated_by','validation_policy','validation_policy_id']}
def simple_field(kind='text',rules=None):
    return {'key':'target','label':'Target','type':kind,'required':True,'validation':rules or []}
def check(op,value):return {'operator':op,'value':value,'message':'Choose a valid target.'}
def definition(field):
    f=seed_form();f['mapping'].pop('policy');f['fields']=[field];return f

class FieldChecks(unittest.TestCase):
    def validate(self,kind,rules,value):
        f=validate_definition(definition(simple_field(kind,rules)),fx.ROLES)
        inputs=validate_inputs(f,{'target':value});validate_field_inputs(f,inputs);return inputs
    def test_all_five_comparisons(self):
        for op,pattern,good,bad in [('equals','Alice','Alice','alice'),('not_equals','Alice','Bob','Alice'),('like','a?i*','alice','Alice'),('not_like','*@example.test','alice@other.test','alice@example.test'),('regex',r'(?i)INC-[0-9]+','inc-42','before-INC-42')]:
            with self.subTest(op=op):
                self.validate('text',[check(op,pattern)],good)
                with self.assertRaises(Error) as err:self.validate('text',[check(op,pattern)],bad)
                self.assertEqual(err.exception.fields['target'],'Choose a valid target.')
    def test_wildcard_metacharacters_are_literal(self):
        self.validate('text',[check('like','[ab].*')],'[ab].anything')
        with self.assertRaises(Error):self.validate('text',[check('like','[ab].*')],'ab.anything')
    def test_typed_values(self):
        self.validate('number',[check('equals','0')],0)
        self.validate('checkbox',[check('equals','true')],True)
        with self.assertRaises(Error):self.validate('number',[check('equals','not a number')],2)
    def test_each_list_item_must_pass(self):
        self.assertEqual(self.validate('text_list',[check('like','*@example.test')],[' alice@example.test ','bob@example.test'])['target'],['alice@example.test','bob@example.test'])
        with self.assertRaises(Error):self.validate('text_list',[check('like','*@example.test')],['alice@example.test','invalid'])
    def test_list_shape_uniqueness_and_limit(self):
        for bad in ['alice',['a','a'],['a',' a '],[''],[4],['a'*201],[str(n) for n in range(26)]]:
            with self.subTest(value=bad),self.assertRaises(Error):self.validate('text_list',[],bad)
    def test_invalid_or_unsafe_definitions(self):
        for rule in [check('regex','['),check('regex','a'*513),check('like','a'*201),check('required','x'),check('bogus','x'),dict(check('equals','x'),field='other')]:
            with self.subTest(rule=rule),self.assertRaises(Error):validate_definition(definition(simple_field(rules=[rule])),fx.ROLES)
    def test_hidden_and_optional_fields_are_skipped(self):
        f=definition(simple_field(rules=[check('regex','X')]));f['fields'][0]['required']=False
        validate_field_inputs(f,{})
        f['fields'][0]['show_when']={'field':'enabled','equals':True};validate_field_inputs(f,{'enabled':False,'target':'notX'})
    def test_arrays_reach_soar_as_structured_inputs(self):
        f=definition(simple_field('text_list'));f.update(version=1,revision=1);f['fields'][0]['cef_key']='targets'
        inputs={'target':['alice','bob']};c,a=event_payload(f,fx.actor(),inputs,'sid','now',{})
        self.assertEqual(c['data']['actionstack']['inputs'],inputs)
        self.assertEqual(a['data']['actionstack']['inputs'],inputs)
        self.assertEqual(json.loads(a['cef']['actionstack_target']),['alice','bob'])
        self.assertEqual(json.loads(a['cef']['targets']),['alice','bob'])

class LifecycleTests(unittest.TestCase):
    setUp=fx.ServiceTests.setUp
    tearDown=fx.ServiceTests.tearDown
    def test_editor_migration_is_detached_and_preserves_legacy_behavior(self):
        old=self.svc.published('block-object')
        f=self.svc.dispatch(fx.ADMIN,'GET','/admin/forms')[0]
        self.assertNotIn('validation_policy',f);self.assertNotIn('validation_policy_id',f)
        rules=next(x for x in f['fields'] if x['key']=='object_value')['validation']
        self.assertEqual(len(rules),4);self.assertEqual(self.svc.published('block-object'),old)
        result=self.svc.save_form(fx.ADMIN,{'form':clean(f),'expected_revision':1},True)
        self.assertNotIn('validation_policy',result)
        inputs=validate_inputs(result,fx.inputs());validate_field_inputs(result,inputs)
        _,a=event_payload(result,self.user,inputs,'sid','now',{})
        self.assertEqual(a['cef']['destinationAddress'],'192.0.2.42')
        with self.assertRaises(Error):validate_field_inputs(result,dict(inputs,object_value='bad'))
        next(x for x in result['fields'] if x['key']=='object_value')['validation']=[]
        edited=self.svc.save_form(fx.ADMIN,{'form':clean(result),'expected_revision':2},True)
        validate_field_inputs(edited,dict(inputs,object_value='bad'))
    def test_rejection_happens_before_receipt_and_soar(self):
        self.svc.save_form(fx.ADMIN,{'form':definition(simple_field(rules=[check('regex','OK')])),'expected_revision':1},True)
        with self.assertRaises(Error):self.svc.submit(self.user,{'form_id':'block-object','form_version':2,'inputs':{'target':'bad'},'idempotency_key':'new-validation-1'})
        self.assertEqual(self.store.list('submissions'),[]);self.factory.assert_not_called()
    def test_delete_restore_conflicts_and_submission_history(self):
        receipt=self.svc.submit(self.user,fx.ServiceTests.body(self))
        self.svc.delete_form(fx.ADMIN,'block-object',1)
        self.assertEqual(self.svc.list_forms(self.user),[])
        self.assertEqual(self.svc.dispatch(fx.ADMIN,'GET','/admin/forms')[0]['state'],'deleted')
        self.assertEqual(self.svc.dispatch(self.user,'GET','/submissions/'+receipt['id'])['id'],receipt['id'])
        with self.assertRaises(Error):self.svc.submit(self.user,fx.ServiceTests.body(self,'after-delete'))
        with self.assertRaises(Conflict):self.svc.delete_form(fx.ADMIN,'block-object',1,True)
        with self.assertRaises(Error):self.svc.save_form(fx.ADMIN,{'form':seed_form(),'expected_revision':2})
        self.svc.delete_form(fx.ADMIN,'block-object',2,True)
        self.assertEqual(self.svc.list_forms(self.user),[])
        self.assertEqual(self.svc.latest('block-object')['state'],'archived')
        self.svc.save_form(fx.ADMIN,{'form':seed_form(),'expected_revision':3},False)
        self.assertEqual(self.svc.list_forms(self.user),[])
        with self.assertRaises(Error):self.svc.published('block-object')
        self.svc.save_form(fx.ADMIN,{'form':seed_form(),'expected_revision':4},True)
        self.assertEqual(len(self.svc.list_forms(self.user)),1)
    def test_delete_requires_publish_and_edit_acl(self):
        for actor in [self.user,fx.actor('publisher',['user'],['use','publish']),fx.actor('author',['admin'],['use','edit'])]:
            with self.subTest(actor=actor),self.assertRaises(Error):self.svc.delete_form(actor,'block-object',1)
    def test_favorites_are_private_idempotent_and_survive_other_service(self):
        body={'form_id':'block-object','favorite':True}
        self.assertEqual(self.svc.dispatch(self.user,'POST','/favorites',body),['block-object'])
        self.svc.dispatch(self.user,'POST','/favorites',body)
        self.assertEqual(len(self.store.list('favorites')),1)
        self.assertEqual(self.svc.favorites(fx.actor('bob')),[])
        second=Service(self.store,self.secrets,self.factory,lambda:fx.ROLES,demo=True)
        self.assertEqual(second.favorites(self.user),['block-object'])
        self.svc.dispatch(self.user,'POST','/favorites',dict(body,favorite=False))
        self.assertEqual(self.svc.favorites(self.user),[])
    def test_favorites_obey_permissions_and_delete(self):
        self.svc.set_favorite(self.user,{'form_id':'block-object','favorite':True})
        f=seed_form();f['access']['view_roles']=['admin'];self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1},True)
        self.assertEqual(self.svc.favorites(self.user),[])
        with self.assertRaises(Error):self.svc.set_favorite(self.user,{'form_id':'block-object','favorite':True})
        with self.assertRaises(Error):self.svc.set_favorite(self.user,{'form_id':'block-object','favorite':True,'username':'bob'})
        self.svc.delete_form(fx.ADMIN,'block-object',2)
        self.assertEqual(self.svc.favorites(fx.ADMIN),[])
    def test_multi_lookup_rechecks_every_value_in_one_search(self):
        self.svc.lookup=Mock(wraps=DemoLookup())
        field=dict(simple_field('lookup_multi'),lookup=CONFIG)
        self.svc.save_form(fx.ADMIN,{'form':definition(field),'expected_revision':1},True)
        body={'form_id':'block-object','form_version':2,'inputs':{'target':['alice@example.test','bob@example.test']},'idempotency_key':'multiple-lookup-1'}
        receipt=self.svc.submit(self.user,body)
        self.assertEqual(receipt['status'],'submitted');self.svc.lookup.search.assert_called_once_with(CONFIG,body['inputs']['target'],True)
        body['idempotency_key']='multiple-lookup-2';body['inputs']['target'].append('removed@example.test')
        with self.assertRaises(Error):self.svc.submit(self.user,body)
        self.assertEqual(len(self.store.list('submissions')),1)

class BatchLookupTests(unittest.TestCase):
    def test_quoted_batch_spl_and_limits(self):
        spl,_=lookup_spl(CONFIG,['alice','bob" | delete'],True)
        self.assertIn(' OR ',spl);self.assertIn('head 2',spl);self.assertIn('bob\\" | delete',spl)
        for term in [[],['a']*26,['a`b'],['x\n']]:
            with self.assertRaises(Error):lookup_spl(CONFIG,term,True)
        with self.assertRaises(Error):lookup_spl(CONFIG,['alice'],False)
    def test_batch_adapter_returns_only_exact_selected_values(self):
        rest=Mock();rest.call.side_effect=[{'sid':'123'}, {'entry':[{'content':{'isDone':True}}]}, {'results':[{'identity':'alice'},{'identity':'bob'},{'identity':'foreign'}]},{}]
        result=LookupSearch(rest,'alice').search(CONFIG,['alice','bob'],True)
        self.assertEqual([x['value'] for x in result['options']],['alice','bob'])
        self.assertEqual(rest.call.call_args_list[2].kwargs['params']['count'],2)
        self.assertEqual(rest.call.call_args_list[-1].args[0],'DELETE')

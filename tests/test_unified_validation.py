import unittest
from unittest.mock import patch,Mock
import subprocess
import test_pages as fx
from actionstack.core import Error,clone,seed_form,validate_inputs,event_payload
from actionstack.validation_policies import block_policy,validate_rules,validate_request,regex_matches

def clean(f):return {k:clone(v) for k,v in f.items() if k not in ['_key','revision','version','state','updated_at','updated_by','validation_policy']}
def regex_rule(pattern): return {'field':'ticket_reference','operator':'regex','value':pattern,'message':'Use an INC ticket.'}

class UnifiedPolicyTests(unittest.TestCase):
    setUp=fx.ServiceTests.setUp
    tearDown=fx.ServiceTests.tearDown
    def test_legacy_editor_exposes_editable_policy_without_republishing(self):
        old=self.svc.published('block-object')
        edited=self.svc.list_forms(fx.ADMIN,True)[0]
        self.assertNotIn('policy',edited['mapping'])
        self.assertEqual(edited['validation_policy_id'],'block-object-validation')
        self.assertEqual(edited['mapping']['approval']['conditions'],[{'field':'duration','equals':'forever'}])
        self.assertEqual(self.svc.published('block-object'),old)
        self.assertEqual(len(self.svc.validation_policies(fx.ADMIN)),1)
    def test_policy_changes_are_editable_and_only_take_effect_on_republish(self):
        f=self.svc.list_forms(fx.ADMIN,True)[0]
        first=self.svc.save_form(fx.ADMIN,{'form':clean(f),'expected_revision':1},True)
        p=block_policy();p['rules']=[r for r in p['rules'] if r['operator']!='ip_address']
        self.svc.save_validation_policy(fx.ADMIN,{'policy':p,'expected_revision':1})
        data=fx.inputs();data['object_value']='not-an-ip'
        with self.assertRaises(Error):validate_request(first,validate_inputs(first,data))
        second=self.svc.save_form(fx.ADMIN,{'form':clean(first),'expected_revision':2},True)
        validate_request(second,validate_inputs(second,data))
        self.assertNotIn('policy',second['mapping']);self.assertEqual(second['validation_policy']['revision'],2)
    def test_migrated_checks_preserve_normalization_metadata_and_approval(self):
        f=self.svc.list_forms(fx.ADMIN,True)[0]
        form=self.svc.save_form(fx.ADMIN,{'form':clean(f),'expected_revision':1},True)
        cases=[('ip','2001:0db8::1',None,'2001:db8::1'),('domain','EXAMPLE.TEST.',None,'example.test'),('hash','A'*40,'sha1','a'*40),('hash','B'*64,'sha256','b'*64)]
        for typ,value,hash_type,expected in cases:
            raw=fx.inputs();raw.update(object_type=typ,object_value=value,duration='forever')
            if hash_type:raw['hash_type']=hash_type
            inputs=validate_inputs(form,raw);validate_request(form,inputs)
            self.assertEqual(inputs['object_value'],expected)
            c,a=event_payload(form,self.user,inputs,'sid','now',{})
            self.assertTrue(c['data']['actionstack']['policy']['approval_required'])
            self.assertTrue(c['data']['actionstack']['derived']['permanent'])
            self.assertEqual(a['cef']['actionstack_permanent'],'true')
        for typ,value,algorithm in [('ip','invalid',None),('domain','192.0.2.1',None),('hash','a'*39,'sha1')]:
            raw=fx.inputs();raw.update(object_type=typ,object_value=value)
            if algorithm:raw['hash_type']=algorithm
            with self.assertRaises(Error):validate_request(form,validate_inputs(form,raw))
    def test_existing_custom_policy_is_combined_and_snapshotted_without_loss(self):
        p={'id':'ticket','name':'Ticket','description':'','state':'active','rules':[regex_rule('INC-[0-9]+')]}
        self.svc.save_validation_policy(fx.ADMIN,{'policy':p,'expected_revision':0})
        old=self.svc.latest('block-object');old['validation_policy_id']='ticket';old['validation_policy']=dict(p,revision=1)
        self.store.put('forms',old)
        edit=self.svc.list_forms(fx.ADMIN,True)[0]
        self.assertTrue(edit['validation_policy_id'].startswith('migrated-'))
        self.assertIn(regex_rule('INC-[0-9]+'),edit['validation_policy']['rules'])
        self.assertEqual(len(self.svc.list_forms(fx.ADMIN,True)[0]['validation_policy']['rules']),5)
        self.assertEqual(len(self.svc.validation_policies(fx.ADMIN)),3)
        self.svc.save_form(fx.ADMIN,{'form':clean(edit),'expected_revision':1},True)
    def test_regex_rejection_creates_no_receipt_or_soar_event(self):
        p={'id':'ticket','name':'Ticket','description':'','state':'active','rules':[regex_rule('INC-[0-9]+')]}
        self.svc.save_validation_policy(fx.ADMIN,{'policy':p,'expected_revision':0})
        f=seed_form();f['mapping'].pop('policy');f['validation_policy_id']='ticket'
        self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1},True)
        b=fx.ServiceTests.body(self);b['form_version']=2;b['inputs']['ticket_reference']='BAD-1'
        with self.assertRaises(Error) as err:self.svc.submit(self.user,b)
        self.assertIn('ticket_reference',err.exception.fields)
        self.assertEqual(self.store.list('submissions'),[]);self.factory.assert_not_called()
        b['inputs']['ticket_reference']='INC-42';self.assertEqual(self.svc.submit(self.user,b)['status'],'submitted')

class RegexTests(unittest.TestCase):
    def test_fullmatch_flags_and_unicode(self):
        self.assertEqual(regex_matches([['INC-[0-9]+','INC-42'],['INC-[0-9]+','xINC-42'],['(?i)inc-[0-9]+','Inc-42'],['[é]+','éé']]),[True,False,True,True])
    def test_invalid_patterns_and_nontext_fields_are_rejected_on_save(self):
        for pattern in ['[','a{9999999999999}','a'*513,'']:
            with self.assertRaises(Error):validate_rules([regex_rule(pattern)])
        with self.assertRaises(Error):validate_rules([regex_rule('.*')],[{'key':'ticket_reference','type':'number'}])
    def test_condition_hidden_and_optional_values(self):
        form=seed_form();rule=regex_rule('INC-[0-9]+');rule['when']={'field':'duration','equals':'forever'};form['validation_policy']={'rules':[rule]}
        validate_request(form,{'duration':'4h','ticket_reference':'BAD'})
        validate_request(form,{'duration':'forever'})
        with self.assertRaises(Error):validate_request(form,{'duration':'forever','ticket_reference':'BAD'})
        form['fields'][-1]['show_when']={'field':'duration','equals':'4h'}
        validate_request(form,{'duration':'forever','ticket_reference':'BAD'})
    def test_pathological_pattern_times_out_and_next_evaluation_recovers(self):
        with self.assertRaises(Error) as err:regex_matches([['(a+)+$','a'*100+'!']])
        self.assertEqual(err.exception.status,400)
        self.assertEqual(regex_matches([['a+','aaa']]),[True])
    def test_missing_worker_fails_closed(self):
        with patch('actionstack.validation_policies.subprocess.run',side_effect=OSError()):
            with self.assertRaises(Error) as err:regex_matches([['a','a']])
        self.assertEqual(err.exception.status,503)

class SimplePolicyTests(unittest.TestCase):
    setUp=fx.ServiceTests.setUp
    tearDown=fx.ServiceTests.tearDown
    def test_public_policies_exclude_metadata_and_required_rules(self):
        rows=self.svc.dispatch(fx.ADMIN,'GET','/admin/validation-policies')
        self.assertNotIn('enrichment',rows[0])
        self.assertTrue(all(r['operator']!='required' for r in rows[0]['rules']))
    def test_editing_policy_preserves_legacy_projection_without_hidden_requirements(self):
        p=self.svc.dispatch(fx.ADMIN,'GET','/admin/validation-policies')[0]
        payload={k:p[k] for k in ['id','name','description','state','rules']}
        saved=self.svc.dispatch(fx.ADMIN,'POST','/admin/validation-policies/save',{'policy':payload,'expected_revision':1})
        self.assertNotIn('enrichment',saved)
        stored=self.svc.validation_policies(fx.ADMIN)[0]
        self.assertEqual(stored['enrichment'],'block_object')
        self.assertTrue(all(r['operator']!='required' for r in stored['rules']))
    def test_required_migrates_to_builder_and_can_be_removed(self):
        old=self.svc.latest('block-object');old['validation_policy']={'rules':[{'field':'ticket_reference','operator':'required','message':'Ticket','when':{'field':'duration','equals':'forever'}}]};old['mapping'].pop('policy')
        self.store.put('forms',old)
        f=self.svc.list_forms(fx.ADMIN,True)[0]
        field=next(x for x in f['fields'] if x['key']=='ticket_reference')
        self.assertEqual(field['required_when'],[{'field':'duration','equals':'forever'}])
        with self.assertRaises(Error):validate_inputs(f,dict(fx.inputs(),duration='forever'))
        field['required_when']=[]
        published=self.svc.save_form(fx.ADMIN,{'form':clean(f),'expected_revision':1},True)
        validate_inputs(published,dict(fx.inputs(),duration='forever'))
    def test_required_flags_are_not_reapplied_from_policy(self):
        f=self.svc.list_forms(fx.ADMIN,True)[0]
        for field in f['fields']:
            field['required']=False;field['required_when']=[]
        result=self.svc.save_form(fx.ADMIN,{'form':clean(f),'expected_revision':1},True)
        self.assertFalse(any(x['required'] for x in result['fields']))
    def test_simple_string_values_match_number_and_checkbox_fields(self):
        p={'id':'simple','name':'Simple','description':'','state':'active','rules':[{'field':'count','operator':'equals','value':'5','message':'Enter 5.'},{'field':'enabled','operator':'equals','value':'true','message':'Select the checkbox.'}]}
        self.svc.save_validation_policy(fx.ADMIN,{'policy':p,'expected_revision':0})
        f=seed_form();f['mapping'].pop('policy');f['fields']=[{'key':'count','type':'number','label':'Count'},{'key':'enabled','type':'checkbox','label':'Enabled'}];f['validation_policy_id']='simple'
        result=self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1},True)
        validate_request(result,{'count':5,'enabled':True})
        with self.assertRaises(Error):validate_request(result,{'count':6,'enabled':False})
    def test_conditional_required_accepts_numeric_zero(self):
        form={'fields':[{'key':'mode','type':'number'},{'key':'count','type':'number','required_when':[{'field':'mode','equals':1}]}]}
        self.assertEqual(validate_inputs(form,{'mode':1.0,'count':0})['count'],0)
        with self.assertRaises(Error):validate_inputs(form,{'mode':1.0})

    def test_camel_case_email_field_and_regex_policy(self):
        p={'id':'email-check','name':'Email check','description':'','state':'active','rules':[{'field':'emailAddress','operator':'regex','value':r'[^@\s]+@[^@\s]+\.[^@\s]+','message':'Enter a valid email address.'}]}
        self.svc.save_validation_policy(fx.ADMIN,{'policy':p,'expected_revision':0})
        f=seed_form();f['mapping'].pop('policy');f['fields']=[{'key':'emailAddress','type':'text','label':'Email address','required':True}];f['validation_policy_id']='email-check'
        form=self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1},True)
        validate_request(form,validate_inputs(form,{'emailAddress':'user@example.test'}))
        with self.assertRaises(Error) as err:validate_request(form,validate_inputs(form,{'emailAddress':'invalid'}))
        self.assertEqual(err.exception.fields['emailAddress'],'Enter a valid email address.')
        with self.assertRaises(Error):validate_inputs(form,{})

"""Lookup acceleration must preserve permissions, query semantics and stored values."""
import json
import unittest
from unittest.mock import Mock, patch
import test_pages as fx
from actionstack.core import Error, seed_form
from actionstack.lookups import LookupSearch
from test_management_lookups import CONFIG


def definition(**changes):
    return {'entry':[{'acl':{'app':'identity_app'},'content':dict(external_type='kvstore',collection='identities',fields_list='_key,identity,display',**changes)}]}

SCHEMA={'entry':[{'content':{'field.identity':'string','field.display':'string'}}]}

class KVLookupTests(unittest.TestCase):
    def test_kv_prefix_uses_user_namespace_no_search_job_and_escaped_regex(self):
        rest=Mock(); rest.call.side_effect=[definition(),SCHEMA,[{'identity':'A.b1','display':'Example'}]]
        config=dict(CONFIG,value_field='identity',label_field='display',search='| inputlookup identities local=true | table identity display')
        result=LookupSearch(rest,'alice@example.test').search(config,'a.b')
        self.assertEqual(result['options'],[{'value':'A.b1','label':'Example'}])
        self.assertEqual(rest.call.call_count,3)
        first,_,last=rest.call.call_args_list
        self.assertEqual(first.args,('GET','/servicesNS/alice%40example.test/search/data/transforms/lookups/identities'))
        self.assertEqual(last.args,('GET','/servicesNS/nobody/identity_app/storage/collections/data/identities'))
        self.assertEqual(last.kwargs['params']['limit'],26)
        self.assertEqual(json.loads(last.kwargs['params']['query']),{'$or':[{'identity':{'$regex':r'^a\.b','$options':'i'}},{'display':{'$regex':r'^a\.b','$options':'i'}}]})
    def test_exact_batch_matches_case_insensitively_and_preserves_canonical_values(self):
        rest=Mock();rest.call.side_effect=[definition(),SCHEMA,[{'identity':'Alice'},{'identity':'ALICE'},{'identity':'BOB'},{'identity':'bobby'}]]
        result=LookupSearch(rest,'alice').search(CONFIG,['alice','bob'],True)
        self.assertEqual(result['options'],[{'value':'Alice','label':'Alice'},{'value':'BOB','label':'BOB'}])
        self.assertEqual(json.loads(rest.call.call_args.kwargs['params']['query'])['$or'][0],{'identity':{'$regex':'^alice$','$options':'i'}})
    def test_transformed_queries_do_not_use_the_direct_path(self):
        for tail in ['eval identity=lower(identity) | fields identity','where enabled=1 | fields identity','fields identity | head 5','fields identity | mvexpand identity limit=10','fields - identity','rename identity as display | table display']:
            rest=Mock();rest.call.return_value={'sid':'1'}
            with patch.object(rest,'call',side_effect=Error(503,'dispatch unavailable')) as call:
                with self.assertRaises(Error): LookupSearch(rest,'alice').search(dict(CONFIG,search='| inputlookup identities | '+tail,value_field='identity'), 'ali')
                self.assertEqual(call.call_args_list[0].args[0],'POST')
                self.assertTrue(call.call_args_list[0].args[1].endswith('/search/jobs'))
    def test_filtered_csv_missing_and_unreadable_definitions_fall_back_to_spl(self):
        for entry in [None,definition(filter='enabled=1'),definition(time_field='timestamp'),{'entry':[{'content':{'external_type':'csv'}}]},Error(403,'denied')]:
            rest=Mock();rest.call.side_effect=[entry,{'sid':'1'},{'entry':[{'content':{'isDone':True}}]},{'results':[{'identity':'alice'}]},{}]
            result=LookupSearch(rest,'alice').search(CONFIG,'ali')
            self.assertEqual(result['options'][0]['value'],'alice')
            self.assertTrue(rest.call.call_args_list[1].args[1].endswith('/search/jobs'))
    def test_unreadable_collection_does_not_retry_with_system_credentials(self):
        rest=Mock();rest.call.side_effect=[definition(),SCHEMA,Error(403,'denied'),Error(403,'search denied')]
        with self.assertRaises(Error): LookupSearch(rest,'alice').search(CONFIG,'ali')
        self.assertEqual(rest.call.call_count,4)
        self.assertTrue(rest.call.call_args.args[1].startswith('/servicesNS/alice/'))
    def test_scalar_mvexpand_is_direct_but_arrays_preserve_spl_expansion(self):
        config=dict(CONFIG,search='| inputlookup identities | fields identity | mvexpand identity',value_field='identity')
        for rows,direct in [([{'identity':'alice'}],True),([{'identity':['alice','alicia']}],False)]:
            rest=Mock();rest.call.side_effect=[definition(),SCHEMA,rows]+([] if direct else [{'sid':'1'},{'entry':[{'content':{'isDone':True}}]},{'results':[{'identity':'alice'},{'identity':'alicia'}]},{}])
            result=LookupSearch(rest,'alice').search(config,'ali')
            self.assertEqual(len(result['options']),1 if direct else 2)
            self.assertEqual(rest.call.call_count,3 if direct else 7)
    def test_untyped_or_numeric_columns_preserve_search_string_conversion(self):
        for columns in [{},{'field.identity':'number'}]:
            rest=Mock();rest.call.side_effect=[definition(),{'entry':[{'content':columns}]},{'sid':'1'},{'entry':[{'content':{'isDone':True}}]},{'results':[{'identity':'1234'}]},{}]
            result=LookupSearch(rest,'alice').search(CONFIG,'123')
            self.assertEqual(result['options'],[{'value':'1234','label':'1234'}])
            self.assertTrue(rest.call.call_args_list[2].args[1].endswith('/search/jobs'))
    def test_unknown_definition_namespace_cannot_select_a_collection(self):
        data=definition();data['entry'][0]['acl']['app']='../secret'
        rest=Mock();rest.call.side_effect=[data,Error(503,'search unavailable')]
        with self.assertRaises(Error):LookupSearch(rest,'alice').search(CONFIG,'ali')
        self.assertNotIn('/storage/collections/',str(rest.call.call_args_list))

class CanonicalSubmissionTests(unittest.TestCase):
    setUp=fx.ServiceTests.setUp
    tearDown=fx.ServiceTests.tearDown
    def test_single_and_multi_values_are_canonical_in_soar_and_validation(self):
        for kind,incoming,expected in [('lookup','ALICE','Alice'),('lookup_multi',['ALICE','alice','BOB'],['Alice','Bob'])]:
            f=seed_form();f['mapping']['policy']='none'
            f['fields']=[{'key':'identity','type':kind,'label':'Identity','lookup':CONFIG,'validation':[{'operator':'regex','value':'Alice|Bob','message':'Canonical value required'}]}]
            self.svc.lookup=Mock();self.svc.lookup.search.return_value={'options':[{'value':'Alice','label':'Alice A'},{'value':'Bob','label':'Bob B'}]}
            inputs=self.svc.checked_inputs(self.user,f,{'identity':incoming})
            self.assertEqual(inputs['identity'],expected)
    def test_repeated_reads_do_not_run_bootstrap_migrations(self):
        with patch.object(self.svc,'bootstrap') as bootstrap,patch.object(self.svc,'lookup_options',return_value={'options':[]}) as lookup:
            self.svc.dispatch(self.user,'POST','/lookups/options',{'term':'ali'})
            bootstrap.assert_not_called();lookup.assert_called_once()

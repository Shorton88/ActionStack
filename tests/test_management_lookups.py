import json
import unittest
from unittest.mock import Mock,patch
import test_pages as fx
from actionstack.core import Error,Conflict,seed_form,clone,validate_definition,validate_inputs
from actionstack.validation_policies import validate_rules,validate_request
from actionstack.lookups import validate_source,lookup_spl,LookupSearch
from actionstack.soar import Soar,action_data_preview,MAX_ACTION_DATA_PREVIEW,MAX_ACTIVITY_DATA

CONFIG={'search':'| inputlookup identity_lookup_expanded | fields identity','app':'search','min_chars':3,'debounce_ms':50}
def profile(): return {'id':'ticket-required','name':'Ticket required','description':'Require a ticket for Forever.','state':'active','rules':[{'field':'ticket_reference','operator':'required','message':'Add a ticket for a permanent block.','when':{'field':'duration','equals':'forever'}}]}

class ManagementTests(unittest.TestCase):
    setUp=fx.ServiceTests.setUp
    tearDown=fx.ServiceTests.tearDown
    def workspace(self,state='active',roles=None,revision=0):
        return self.svc.save_workspace(fx.ADMIN,{'workspace':{'id':'team-a','name':'Team A','description':'','roles':roles if roles is not None else ['team_a'],'state':state},'expected_revision':revision})
    def test_workspace_acl_is_enforced_for_catalog_edit_submit_and_lookup(self):
        self.workspace(); f=seed_form();f['workspace_id']='team-a';self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1},True)
        self.assertEqual(self.svc.list_forms(self.user),[])
        self.assertEqual([w['id'] for w in self.svc.list_workspaces(self.user)],['security'])
        for method,args in [(self.svc.submit,(self.user,dict(fx.ServiceTests.body(self),form_version=2))), (self.svc.lookup_options,(self.user,{'form_id':f['id'],'form_version':2,'field':'identity','term':'ali'}))]:
            with self.assertRaises(Error):method(*args)
        team=fx.actor(roles=['team_a']);self.assertEqual(len(self.svc.list_forms(team)),1)
    def test_workspace_revisions_archive_and_receipt_history(self):
        self.workspace(roles=[]);f=seed_form();f['workspace_id']='team-a';self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1},True)
        receipt=self.svc.submit(self.user,dict(fx.ServiceTests.body(self),form_version=2))
        self.workspace('archived',[],1)
        self.assertEqual(self.svc.list_forms(self.user),[])
        self.assertEqual(self.svc.receipt(self.store.get('submissions',receipt['id']),self.user)['id'],receipt['id'])
        with self.assertRaises(Conflict):self.workspace(revision=1)
        with self.assertRaises(Error):self.svc.save_workspace(self.user,{'workspace':{},'expected_revision':0})
        self.workspace('active',[],2);self.assertEqual(len(self.svc.list_forms(self.user)),1)
    def test_custom_rules_reject_before_delivery_and_publish_pins_revision(self):
        p=profile();p['rules'][0].update(operator='regex',value='INC-[0-9]+');self.svc.save_validation_policy(fx.ADMIN,{'policy':p,'expected_revision':0})
        f=seed_form();f['mapping']['policy']='none';f['validation_policy_id']=p['id'];published=self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1},True)
        body=dict(fx.ServiceTests.body(self),form_version=2);body['inputs']['duration']='forever';body['inputs']['ticket_reference']='BAD'
        with self.assertRaises(Error) as err:self.svc.submit(self.user,body)
        self.assertIn('ticket_reference',err.exception.fields);self.factory.assert_not_called()
        p['rules'][0]['when']['equals']='4h';self.svc.save_validation_policy(fx.ADMIN,{'policy':p,'expected_revision':1})
        self.assertEqual(self.svc.published(f['id'])['validation_policy']['revision'],1)
        with self.assertRaises(Error):self.svc.submit(self.user,body)
        body['inputs']['ticket_reference']='INC-1';self.svc.submit(self.user,body)
        fresh=self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':2},True)
        self.assertEqual(fresh['validation_policy']['revision'],2)
        self.assertEqual(published['validation_policy']['revision'],1)
    def test_policy_permissions_types_missing_fields_and_snapshot_forgery(self):
        with self.assertRaises(Error):self.svc.save_validation_policy(self.user,{'policy':profile(),'expected_revision':0})
        p=profile();self.svc.save_validation_policy(fx.ADMIN,{'policy':p,'expected_revision':0})
        f=seed_form();f['validation_policy_id']=p['id'];f['fields']=[x for x in f['fields'] if x['key']!='ticket_reference']
        with self.assertRaises(Error):self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1})
        f=seed_form();f['validation_policy']={'rules':[]}
        with self.assertRaises(Error):validate_definition(f,fx.ROLES)
        with self.assertRaises(Error):validate_rules([{'field':'duration','operator':'min','value':1,'message':'Invalid'}],seed_form()['fields'])
    def lookup_form(self):
        f=seed_form();f['mapping']['policy']='none';f['fields']=[{'key':'identity','type':'lookup','label':'User','required':True,'lookup':clone(CONFIG)}]
        return self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1},True)
    def test_lookup_config_cannot_be_overridden_and_selection_rechecked(self):
        self.lookup_form();self.svc.lookup=Mock();self.svc.lookup.search.return_value={'options':[{'value':'alice','label':'alice'}],'more':False}
        request={'form_id':'block-object','form_version':2,'field':'identity','term':'ali'}
        self.svc.lookup_options(self.user,request);self.svc.lookup.search.assert_called_once_with(CONFIG,'ali',False)
        for body in [dict(request,config=CONFIG),dict(request,form_version=1)]:
            with self.assertRaises(Error):self.svc.lookup_options(self.user,body)
        body=dict(fx.ServiceTests.body(self),form_version=2,inputs={'identity':'forged'})
        with self.assertRaises(Error):self.svc.submit(self.user,body)
        self.factory.assert_not_called()
        body['inputs']['identity']='alice';self.svc.submit(self.user,body)
        self.svc.lookup.search.assert_called_with(CONFIG,'alice',True)
    def test_lookup_minimum_and_role_check_precede_search(self):
        self.lookup_form();self.svc.lookup=Mock()
        request={'form_id':'block-object','form_version':2,'field':'identity','term':'al'}
        self.assertEqual(self.svc.lookup_options(self.user,request)['options'],[]);self.svc.lookup.search.assert_not_called()
        with self.assertRaises(Error):self.svc.lookup_options(self.user,{'config':CONFIG,'term':'ali'},True)
    def test_pasted_values_use_exact_batch_search_with_the_same_acl(self):
        self.lookup_form();self.svc.lookup=Mock();self.svc.lookup.search.return_value={'options':[],'more':False}
        request={'form_id':'block-object','form_version':2,'field':'identity','term':['a','bob']}
        self.svc.lookup_options(self.user,request)
        self.svc.lookup.search.assert_called_once_with(CONFIG,['a','bob'],True)
        for values in [[],['x']*26,[None],['bad\nvalue'],['x'*201]]:
            with self.subTest(values=values),self.assertRaises(Error):self.svc.lookup_options(self.user,dict(request,term=values))
        with self.assertRaises(Error):self.svc.lookup_options(self.user,dict(request,config=CONFIG))
        with self.assertRaises(Error):self.svc.lookup_options(fx.actor(caps=['use']),request)
    def test_lookup_budget_skips_used_slots_but_handles_insert_races(self):
        self.svc.lookup=Mock()
        with patch('actionstack.service.time.time',return_value=6000):
            for _ in range(40):self.svc.run_lookup(self.user,CONFIG,'ali')
            original=self.store.insert
            with patch.object(self.store,'insert',wraps=original) as insert:
                self.svc.run_lookup(self.user,CONFIG,'ali')
                self.assertEqual(insert.call_count,1)
            # A competing member claims the next free slot after our read.
            with patch.object(self.store,'insert',side_effect=[Conflict('claimed'),{}]) as insert:
                self.svc.run_lookup(self.user,CONFIG,'ali')
                self.assertEqual(insert.call_count,2)
                self.assertNotEqual(insert.call_args_list[0].args[1]['_key'],insert.call_args_list[1].args[1]['_key'])
    def test_lookup_budget_is_shared(self):
        self.svc.lookup=Mock();self.svc.lookup.search.return_value={'options':[],'more':False}
        for _ in range(60):self.svc.run_lookup(self.user,CONFIG,'ali')
        with self.assertRaises(Error) as err:self.svc.run_lookup(self.user,CONFIG,'ali')
        self.assertEqual(err.exception.status,429)

class LookupAdapterTests(unittest.TestCase):
    def test_spl_literal_escaping_and_source_allowlist(self):
        term='abc" | outputlookup hacked \\ *'
        spl,_=lookup_spl(CONFIG,term);self.assertIn(json.dumps(term.lower()),spl)
        self.assertIn('head 26',spl)
        for source in ['| inputlookup x | fields y | outputlookup x','| inputlookup `macro` | fields identity','| inputlookup ../secret | fields x']:
            with self.assertRaises(Error):validate_source(dict(CONFIG,search=source))
        for term in ['`macro`','bad\nvalue','a'*201]:
            with self.assertRaises(Error):lookup_spl(CONFIG,term)
    def test_user_namespace_bounded_results_and_cleanup(self):
        rest=Mock();rest.call.side_effect=[{'sid':'123.4'},{'entry':[{'content':{'isDone':'1'}}]},{'results':[{'identity':'alice'+str(i)} for i in range(26)]},{}]
        result=LookupSearch(rest,'alice@example.test').search(CONFIG,'ali')
        self.assertEqual(len(result['options']),25);self.assertTrue(result['more'])
        self.assertTrue(rest.call.call_args_list[0].args[1].startswith('/servicesNS/alice%40example.test/search/'))
        self.assertEqual(rest.call.call_args_list[0].kwargs['form']['max_time'],'5')
        self.assertEqual(rest.call.call_args_list[0].kwargs['form']['exec_mode'],'blocking')
        self.assertEqual(rest.call.call_args_list[-1].args[0],'DELETE')
        self.assertEqual(rest.call.call_args_list[-2].kwargs['params']['count'],26)
    def test_partial_failed_or_malformed_results_fail_closed_and_cleanup(self):
        for c in [{'isFinalized':True},{'isFailed':'1'},{'dispatchState':'FAILED'}]:
            rest=Mock();rest.call.side_effect=[{'sid':'1'},{'entry':[{'content':c}]},{}]
            with self.assertRaises(Error):LookupSearch(rest,'alice').search(CONFIG,'ali')
            self.assertEqual(rest.call.call_args_list[-1].args[0],'DELETE')
        for results in [{'results':[None]},{'results':[],'messages':[{'type':'WARN'}]}]:
            rest=Mock();rest.call.side_effect=[{'sid':'1'},{'entry':[{'content':{'isDone':True}}]},results,{}]
            with self.assertRaises(Error):LookupSearch(rest,'alice').search(CONFIG,'ali')
    def test_exact_search_uses_one_result_and_is_case_sensitive(self):
        spl,_=lookup_spl(CONFIG,'Alice',True);self.assertIn('head 1',spl);self.assertNotIn('lower(',spl)
        rest=Mock();rest.call.side_effect=[{'sid':'1'},{'entry':[{'content':{'isDone':True}}]},{'results':[{'identity':'alice'}]},{}]
        self.assertEqual(LookupSearch(rest,'alice').search(CONFIG,'Alice',True)['options'],[])

class SummaryTests(unittest.TestCase):
    def test_result_projection_includes_data_and_redacts_credentials(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'secret-token')
        remote.call=Mock(return_value={'count':1,'data':[{'id':9,'container':17,'action_run':4,'result_data':[{'status':'success','summary':{'blocked':True,'token':'hidden','note':'secret-token'},'data':[{'identity':'alice','nested':{'password':'hidden','note':'secret-token','header':'Bearer abc123'}}],'parameter':{'password':'private'},'message':'private','logs':['private']}]}]})
        result=remote.action_summaries(17);s=result['items'][4][0]
        self.assertEqual(s['summary']['blocked'],True);self.assertEqual(s['status'],'success')
        self.assertEqual(s['data'][0]['identity'],'alice')
        self.assertEqual(s['data'][0]['nested'],{'password':'[redacted]','note':'[redacted]','header':'Bearer [redacted]'})
        self.assertFalse(s['data_truncated'])
        self.assertNotIn('private',json.dumps(result));self.assertNotIn('secret-token',json.dumps(result));self.assertNotIn('hidden',json.dumps(result))
    def test_documented_action_result_fallback_and_scope_check(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'')
        remote.call=Mock(side_effect=[{'count':1,'data':[{'id':9,'container':17,'action_run':4}]},{'count':1,'data':[{'status':'failure','summary':{'blocked':False}}]}])
        self.assertEqual(remote.action_summaries(17)['items'][4][0]['status'],'failed')
        self.assertEqual(remote.call.call_args_list[-1].args[1],'app_run/9/action_result')
        remote.call=Mock(return_value={'count':1,'data':[{'id':9,'container':18,'action_run':4}]})
        with self.assertRaises(Error):remote.action_summaries(17)

    def test_data_only_results_survive_inline_and_fallback_responses(self):
        for fallback in [False,True]:
            remote=Soar({'soar_url':'https://soar.example.test'},'')
            entries=[{'status':'success','summary':{},'data':[{'identity':'alice'}]}, {'status':'success','data':[]}]
            row={'id':9,'container':17,'action_run':4}
            if not fallback: row['result_data']=entries
            remote.call=Mock(side_effect=[{'count':1,'data':[row]}]+([{'count':2,'data':entries}] if fallback else []))
            results=remote.action_summaries(17)['items'][4]
            self.assertEqual(len(results),2)
            self.assertNotIn('summary',results[0])
            self.assertEqual(results[0]['data'],[{'identity':'alice'}])
            self.assertEqual(results[1]['data'],[])

    def test_summary_only_results_do_not_gain_fabricated_data(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'')
        remote.call=Mock(return_value={'count':1,'data':[{'id':9,'container':17,'action_run':4,'result_data':[{'status':'success','summary':{'count':1}}]}]})
        result=remote.action_summaries(17)['items'][4][0]
        self.assertEqual(result['summary'],{'count':1})
        self.assertNotIn('data',result)

    def test_data_previews_bound_large_and_deep_results(self):
        data=[{'value':'a'*1000}]*30
        preview,limited=action_data_preview(data,'')
        self.assertTrue(limited)
        self.assertEqual(len(preview),25)
        self.assertEqual(len(preview[0]['value']),600)
        deep={'a':{'b':{'c':{'d':{'e':{'f':{'g':1}}}}}}}
        self.assertTrue(action_data_preview(deep,'')[1])
        large=[{'value':'x'*600,'other':'y'*600}]*25
        preview,limited=action_data_preview(large,'')
        self.assertTrue(limited)
        self.assertIsInstance(preview,str)
        self.assertLessEqual(len(preview),MAX_ACTION_DATA_PREVIEW+2)
        self.assertIn('value',preview)

    def test_result_count_and_refresh_data_budget_are_bounded(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'')
        entry={'status':'success','data':[{'value':'x'*600,'other':'y'*600}]*25}
        rows=[{'id':n+1,'container':17,'action_run':n+1,'result_data':[entry]*6} for n in range(30)]
        remote.call=Mock(return_value={'count':len(rows),'data':rows})
        result=remote.action_summaries(17)
        entries=[entry for group in result['items'].values() for entry in group]
        self.assertTrue(result['truncated'])
        self.assertEqual(len(entries),150)
        self.assertTrue(all(len(group)==5 for group in result['items'].values()))
        self.assertIn('Preview limit reached.',entries[-1]['data'])
        # The preview budget plus small notices/metadata, never full remote output.
        self.assertLess(len(json.dumps(result)),MAX_ACTIVITY_DATA+40000)

    def test_activity_matches_result_data_to_its_action_run(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'')
        remote.call=Mock(side_effect=[{'count':0,'data':[]},
            {'count':2,'data':[{'id':4,'container':17,'action':'lookup user','status':'success'}, {'id':5,'container':17,'action':'lookup device','status':'running'}]},
            {'count':1,'data':[{'id':9,'container':17,'action_run':4,'result_data':[{'status':'success','data':[{'identity':'alice'}]}]}]}])
        actions=remote.activity(17)['actions']['items']
        self.assertEqual(actions[0]['summaries'][0]['data'],[{'identity':'alice'}])
        self.assertEqual(actions[1]['summaries'],[])

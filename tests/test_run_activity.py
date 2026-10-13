import json
import unittest
from unittest.mock import Mock, patch
import test_pages as fx
from actionstack.core import Error,seed_form,validate_definition
from actionstack.soar import Soar, ACTION_RESULT_PAGE_SIZE, MAX_ACTION_RESULT_READS
from actionstack.run_activity import block_rows,utility_rows

class RunActivityTests(unittest.TestCase):
    def action_activity(self, app_runs, status='success'):
        remote=Soar({'soar_url':'https://soar.example.test'},'secret-token')
        remote.call=Mock(side_effect=[{'count':0,'data':[]},
            {'count':1,'data':[{'id':4,'container':17,'name':'Sign out users','status':status}]},
            {'count':len(app_runs),'data':app_runs}])
        return remote.activity(17)['actions']

    def test_each_action_result_keeps_its_summary_data_and_status_when_reordered(self):
        entries=[
            {'parameter':{'user':'alice@example.test'},'status':'success','summary':{'task_id':'task-alice','accepted':1},'data':[{'task_id':'task-alice'}]},
            {'parameter':{'user':'bob@example.test'},'status':'failure','summary':{'task_id':'task-bob','accepted':0},'data':[]},
        ]
        for ordered in [entries,entries[::-1]]:
            group=self.action_activity([{'id':9,'container':17,'action_run':4,'result_data':ordered}])
            run=group['items'][0]
            self.assertEqual(run['status'],'mixed')
            self.assertEqual(run['reported_status'],'success')
            self.assertEqual(run['result_counts'],{'success':1,'failed':1})
            self.assertEqual(group['counts']['mixed'],0)
            self.assertEqual(group['counts']['success'],1)
            self.assertEqual(group['counts_basis'],'soar_run_status')
            self.assertEqual(run['summaries'],[{'app_run_id':9,'status':'failed' if result['status']=='failure' else result['status'],
                'summary':result['summary'],'data':result['data'],'data_truncated':False} for result in ordered])
            self.assertNotIn('parameter',json.dumps(run))

    def test_async_app_runs_remain_attached_to_their_action_run(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'')
        actions=[{'id':4,'container':17,'name':'First action','status':'success'},
            {'id':5,'container':17,'name':'Second action','status':'success'}]
        result_a={'status':'success','summary':{'task':'A'},'data':[{'task':'A'}]}
        result_b={'status':'failure','summary':{'task':'B'},'data':[{'task':'B'}]}
        apps=[{'id':90,'container':17,'action_run':5,'result_data':[result_b]},
            {'id':91,'container':17,'action_run':4,'result_data':[result_a]}]
        for ordered in [apps,apps[::-1]]:
            remote.call=Mock(side_effect=[{'count':0,'data':[]},{'count':2,'data':actions},{'count':2,'data':ordered}])
            runs={run['id']:run for run in remote.activity(17)['actions']['items']}
            self.assertEqual(runs[4]['summaries'][0]['summary'],result_a['summary'])
            self.assertEqual(runs[4]['summaries'][0]['data'],result_a['data'])
            self.assertEqual(runs[5]['summaries'][0]['summary'],result_b['summary'])
            self.assertEqual(runs[5]['summaries'][0]['data'],result_b['data'])

    def test_fallback_keeps_reversed_results_and_empty_payloads_separate(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'')
        entries=[{'status':'failure','data':[]}, {'status':'success','summary':{'task':'A'},'data':[{'task':'A'}]}]
        remote.call=Mock(side_effect=[{'count':1,'data':[{'id':9,'container':17,'action_run':4}]}, {'count':2,'data':entries}])
        results=remote.action_summaries(17)['items'][4]
        self.assertEqual(results[0],{'app_run_id':9,'status':'failed','data':[],'data_truncated':False})
        self.assertEqual(results[1]['summary'],entries[1]['summary'])
        self.assertEqual(results[1]['data'],entries[1]['data'])

    def test_failed_items_beyond_preview_and_across_app_runs_still_mark_mixed(self):
        rows=[{'id':9,'container':17,'action_run':4,'result_data':[{'status':'success','data':[]}]*5},
            {'id':10,'container':17,'action_run':4,'result_data':[{'status':'failure'}]*2}]
        group=self.action_activity(rows)
        run=group['items'][0]
        self.assertEqual(run['status'],'mixed')
        self.assertEqual(run['result_counts'],{'success':5,'failed':2})
        self.assertEqual(len(run['summaries']),5)
        self.assertTrue(group['summary_truncated'])
        rows[0]['result_data'] += rows.pop()['result_data']
        self.assertEqual(self.action_activity(rows)['items'][0]['result_counts'],run['result_counts'])

    def test_status_only_and_unknown_items_survive_without_fabricated_payloads(self):
        group=self.action_activity([{'id':9,'container':17,'action_run':4,'result_data':[
            {'status':'failure'}, {'status':'cancelled'}, {'status':'future-status'},
        ]}],status='running')
        run=group['items'][0]
        self.assertEqual(run['status'],'running')
        self.assertNotIn('reported_status',run)
        self.assertEqual(run['result_counts'],{'failed':1,'cancelled':1,'unknown':1})
        self.assertEqual(run['summaries'],[{'app_run_id':9,'status':s} for s in ['failed','cancelled','unknown']])

    def test_single_outcome_retains_the_reported_run_status(self):
        for status in ['success','failed','running','pending','cancelled','unknown']:
            with self.subTest(status=status):
                group=self.action_activity([{'id':9,'container':17,'action_run':4,'result_data':[{'status':status,'data':[]}]}],status)
                self.assertEqual(group['items'][0]['status'],status)
                self.assertNotIn('reported_status',group['items'][0])

    def paginated_activity(self,pages,app_count=1):
        remote=Soar({'soar_url':'https://soar.example.test'},'')
        remote.call=Mock(side_effect=[{'count':0,'data':[]},
            {'count':1,'data':[{'id':4,'container':17,'name':'Sign out users','status':'success'}]},
            {'count':app_count,'data':[{'id':9,'container':17,'action_run':4}]}]+pages)
        return remote,remote.activity(17)['actions']

    def test_paginated_failure_after_first_page_marks_mixed(self):
        size=ACTION_RESULT_PAGE_SIZE
        remote,group=self.paginated_activity([
            {'count':size+1,'data':[{'status':'success'}]*size},
            {'count':size+1,'data':[{'status':'failure'}]}])
        run=group['items'][0]
        self.assertEqual(run['status'],'mixed')
        self.assertEqual(run['result_counts'],{'success':size,'failed':1})
        self.assertTrue(run['result_counts_complete'])
        self.assertEqual(run['result_total'],size+1)
        self.assertEqual(len(run['summaries']),5)
        self.assertEqual([c.kwargs['query']['page'] for c in remote.call.call_args_list[3:]],[0,1])
        self.assertEqual(remote.timeout,15)

    def test_exhausted_read_budget_does_not_claim_all_results_succeeded(self):
        size=ACTION_RESULT_PAGE_SIZE; budget=MAX_ACTION_RESULT_READS
        remote,group=self.paginated_activity([{'count':size*budget+1,'data':[{'status':'success'}]*size}]*budget)
        run=group['items'][0]
        self.assertEqual(remote.call.call_count,3+budget)
        self.assertEqual(run['status'],'incomplete')
        self.assertEqual(run['reported_status'],'success')
        self.assertFalse(run['result_counts_complete'])
        self.assertEqual(run['result_total'],size*budget+1)
        self.assertEqual(run['result_counts'],{'success':size*budget})
        self.assertTrue(group['summary_truncated'])

    def test_short_or_changing_pages_are_marked_incomplete(self):
        for pages in [
            [{'count':6,'data':[{'status':'success'}]*5}],
            [{'count':26,'data':[{'status':'success'}]*25},{'count':27,'data':[{'status':'failure'}]*2}],
        ]:
            remote,group=self.paginated_activity(pages)
            self.assertEqual(group['items'][0]['status'],'incomplete')
            self.assertFalse(group['items'][0]['result_counts_complete'])

    def test_omitted_app_runs_do_not_claim_complete_outcomes(self):
        _,group=self.paginated_activity([{'count':1,'data':[{'status':'success'}]}],app_count=2)
        self.assertEqual(group['items'][0]['status'],'incomplete')
        self.assertIsNone(group['items'][0]['result_total'])

    def test_inline_counts_and_paginated_counts_agree(self):
        entries=[{'status':'success'}]*5+[{'status':'failure'}]
        _,paged=self.paginated_activity([{'count':6,'data':entries}])
        inline=self.action_activity([{'id':9,'container':17,'action_run':4,'result_data':entries}])
        self.assertEqual(paged,inline)

    def test_table_and_receipt_count_the_same_soar_run_status(self):
        detailed=self.action_activity([{'id':9,'container':17,'action_run':4,'result_data':[{'status':'success'},{'status':'failure'}]}])
        remote=Soar({'soar_url':'https://soar.example.test'},'')
        remote.call=Mock(side_effect=[{'count':0,'data':[]},{'count':1,'data':[{'id':4,'container':17,'status':'success'}]}])
        summary=remote.activity(17,details=False)['actions']
        self.assertEqual(detailed['counts'],summary['counts'])
        self.assertEqual(detailed['counts_basis'],summary['counts_basis'])
        self.assertEqual(detailed['items'][0]['status'],'mixed')
        self.assertEqual(remote.call.call_count,2)

    def test_custom_names_status_counts_and_summary_reads_skip_details(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'token')
        remote.call=Mock(side_effect=[{'count':1,'data':[{'id':2,'container':17,'playbook':3,'status':'running'}]},
            {'count':4,'data':[dict(id=i,container=17,name=name,action='run query',status=status) for i,name,status in [(3,'Scan workstation','success'),(4,'Check scan completion','failure'),(5,'Fetch results','running'),(6,'Post processing','future-state')]]}])
        result=remote.activity(17,details=False)
        self.assertEqual(remote.call.call_count,2)
        self.assertEqual(result['actions']['items'][0]['name'],'Scan workstation')
        self.assertEqual(result['actions']['items'][0]['action'],'run query')
        self.assertEqual(result['actions']['counts'],dict(success=1,failed=1,mixed=0,running=1,pending=0,cancelled=0,unknown=1))
        self.assertNotIn('blocks',result)
    def test_missing_status_group_is_not_zero_success(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'token');remote.call=Mock(side_effect=Error(403,'denied'))
        result=remote.activity(17,details=False)
        self.assertIsNone(result['playbooks']['total']);self.assertIsNone(result['playbooks']['counts'])
    def test_block_results_are_scoped_to_verified_runs_and_separate_from_actions(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'token')
        remote.call=Mock(side_effect=[{'count':1,'data':[{'id':2,'container':17,'status':'success'}]},{'count':0,'data':[]},
            {'block_results':{'scan_message:formatted_data':'private result','filtered-data:choose_targets:condition_1':{},'filtered-data:choose_targets:condition_1:status':'success','decision_1:condition_2':{'result':False}}}])
        result=remote.activity(17)
        self.assertEqual(remote.call.call_args.args,('GET','playbook_run/2/block_results'))
        blocks=result['blocks']['items']
        self.assertEqual([(b['name'],b['status']) for b in blocks],[('scan_message','unknown'),('choose_targets:condition_1','success'),('decision_1:condition_2','unknown')])
        self.assertEqual(blocks[0]['block_type'],'Format');self.assertEqual(result['actions']['total'],0)
        self.assertNotIn('private result',json.dumps(result))
    def test_foreign_runs_never_trigger_block_reads(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'');remote.call=Mock(return_value={'count':1,'data':[{'id':3,'container':99}]})
        remote.activity(17)
        self.assertEqual(remote.call.call_count,2)
    def test_utility_requires_explicit_run_header_and_never_uses_overall_status(self):
        report={'playbook_run_id':4,'status':'success','result':[{'name':'Normalize usernames','custom_function_name':'to_lower','custom_function_run_id':19,'status':'failure','custom_function_results':[{'data':'private'}]}]}
        rows=utility_rows(json.dumps(report),4)
        self.assertEqual(rows[0]['name'],'Normalize usernames');self.assertEqual(rows[0]['status'],'failed')
        self.assertNotIn('private',json.dumps(rows));self.assertEqual(utility_rows(report,99),[])
        report['result'][0].pop('status');self.assertEqual(utility_rows(report,4)[0]['status'],'unknown')
    def test_token_in_block_key_is_not_exposed_in_name_or_id(self):
        self.assertNotIn('secret-token',json.dumps(block_rows({'secret-token:formatted_data':'private'},4,'secret-token')))
    def test_large_block_histories_are_bounded(self):
        rows=block_rows({f'block_{n}:formatted_data':'x'*50 for n in range(2000)},4)
        self.assertEqual(len(rows),100)
    def test_new_icons_survive_definition_validation_and_explicit_automation_choice(self):
        for icon in ['scan','server','user']:
            f=seed_form();f['icon']=icon
            for enabled in [True,False]:
                f['mapping']['run_automation']=enabled
                saved=validate_definition(f,fx.ROLES)
                self.assertEqual(saved['icon'],icon);self.assertEqual(saved['mapping']['run_automation'],enabled)

class ActivitySummaryServiceTests(unittest.TestCase):
    setUp=fx.ServiceTests.setUp
    tearDown=fx.ServiceTests.tearDown
    def test_summary_acl_and_payload_excludes_action_results(self):
        receipt=self.svc.submit(self.user,fx.ServiceTests.body(self));remote=Mock();remote.timeout=15
        remote.activity.return_value={'actions':{'items':[{'summaries':['private']}],'total':1,'counts':{'success':1},'counts_basis':'soar_run_status','truncated':False,'error':None},'playbooks':{'items':[],'total':0,'counts':{},'truncated':False,'error':None}}
        self.factory.reset_mock();self.factory.return_value=remote;self.factory.side_effect=None
        with self.assertRaises(Error):self.svc.activity(fx.actor('bob'),receipt['id'],True)
        self.factory.assert_not_called()
        result=self.svc.dispatch(self.user,'GET','/submissions/'+receipt['id']+'/activity-summary')
        remote.activity.assert_called_once_with(receipt['container_id'],details=False)
        self.assertEqual(remote.timeout,5);self.assertNotIn('private',json.dumps(result));self.assertNotIn('items',result['actions'])
        self.assertEqual(result['actions']['counts_basis'],'soar_run_status')
    def test_summary_budget_does_not_consume_receipt_or_delivery_budget(self):
        receipt=self.svc.submit(self.user,fx.ServiceTests.body(self))
        with patch('actionstack.service.time.time',return_value=6000):
            for _ in range(60): self.svc.activity(self.user,receipt['id'],True)
            with self.assertRaises(Error) as err:self.svc.activity(self.user,receipt['id'],True)
            self.assertEqual(err.exception.status,429)
            self.svc.activity(self.user,receipt['id']);self.svc.delivery_budget(self.user)

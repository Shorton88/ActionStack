import json
import unittest
from unittest.mock import Mock, patch
import test_pages as fx
from actionstack.core import Error,seed_form,validate_definition
from actionstack.soar import Soar
from actionstack.run_activity import block_rows,utility_rows

class RunActivityTests(unittest.TestCase):
    def test_custom_names_status_counts_and_summary_reads_skip_details(self):
        remote=Soar({'soar_url':'https://soar.example.test'},'token')
        remote.call=Mock(side_effect=[{'count':1,'data':[{'id':2,'container':17,'playbook':3,'status':'running'}]},
            {'count':4,'data':[dict(id=i,container=17,name=name,action='run query',status=status) for i,name,status in [(3,'Scan workstation','success'),(4,'Check scan completion','failure'),(5,'Fetch results','running'),(6,'Post processing','future-state')]]}])
        result=remote.activity(17,details=False)
        self.assertEqual(remote.call.call_count,2)
        self.assertEqual(result['actions']['items'][0]['name'],'Scan workstation')
        self.assertEqual(result['actions']['items'][0]['action'],'run query')
        self.assertEqual(result['actions']['counts'],dict(success=1,failed=1,running=1,pending=0,cancelled=0,unknown=1))
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
        remote.activity.return_value={'actions':{'items':[{'summaries':['private']}],'total':1,'counts':{'success':1},'truncated':False,'error':None},'playbooks':{'items':[],'total':0,'counts':{},'truncated':False,'error':None}}
        self.factory.reset_mock();self.factory.return_value=remote;self.factory.side_effect=None
        with self.assertRaises(Error):self.svc.activity(fx.actor('bob'),receipt['id'],True)
        self.factory.assert_not_called()
        result=self.svc.dispatch(self.user,'GET','/submissions/'+receipt['id']+'/activity-summary')
        remote.activity.assert_called_once_with(receipt['container_id'],details=False)
        self.assertEqual(remote.timeout,5);self.assertNotIn('private',json.dumps(result));self.assertNotIn('items',result['actions'])
    def test_summary_budget_does_not_consume_receipt_or_delivery_budget(self):
        receipt=self.svc.submit(self.user,fx.ServiceTests.body(self))
        with patch('actionstack.service.time.time',return_value=6000):
            for _ in range(60): self.svc.activity(self.user,receipt['id'],True)
            with self.assertRaises(Error) as err:self.svc.activity(self.user,receipt['id'],True)
            self.assertEqual(err.exception.status,429)
            self.svc.activity(self.user,receipt['id']);self.svc.delivery_budget(self.user)

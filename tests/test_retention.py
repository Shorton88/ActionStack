import json
import unittest
from unittest.mock import patch, Mock
import test_pages as fx
from actionstack.core import Error, clone
from actionstack.retention import age_out_submissions
from actionstack.splunk_store import KVStore

NOW='2026-09-22T12:00:00Z'

class RetentionTests(unittest.TestCase):
    setUp=fx.ServiceTests.setUp
    tearDown=fx.ServiceTests.tearDown

    def old_receipt(self):
        r=self.svc.submit(self.user,fx.ServiceTests.body(self))
        record=self.store.get('submissions',r['id'])
        record['updated_at']='2025-01-01T00:00:00Z'
        self.store.put('submissions',record)
        return record

    def enable(self,days=30):
        return self.svc.save_settings(fx.ADMIN,{'soar_url':'https://soar.example.test','revision':self.svc.settings()['revision'],'retention_days':days})

    def test_default_keeps_receipts_and_only_admin_can_change_retention(self):
        record=self.old_receipt()
        self.assertEqual(self.svc.public_settings()['retention_days'],0)
        with patch('actionstack.retention.utcnow',return_value=NOW):age_out_submissions(self.svc)
        self.assertEqual(self.store.get('submissions',record['id'])['status'],'submitted')
        with self.assertRaises(Error): self.svc.save_settings(self.user,{'soar_url':'https://soar.example.test','revision':0,'retention_days':7})
        for value in [True,-1,1,'30',30.0,None]:
            with self.subTest(value=value),self.assertRaises(Error):self.enable(value)

    def test_old_delivered_receipt_is_compacted_without_touching_soar_or_audit(self):
        record=self.old_receipt();self.enable()
        self.factory.reset_mock()
        with patch('actionstack.retention.utcnow',return_value=NOW):
            self.assertEqual(self.svc.list_submissions(self.user,{}),[])
        marker=self.store.get('submissions',record['id'])
        self.assertEqual(set(marker),{'_key','id','status','expired_at'})
        self.assertEqual(marker['status'],'expired')
        self.assertNotIn('192.0.2.42',json.dumps(marker))
        self.factory.assert_not_called()
        self.assertEqual(len(self.store.list('remote_container')),1)
        self.assertEqual(len(self.store.list('remote_artifact')),1)
        self.assertTrue(any(r['event']=='submission.accepted' for r in self.store.list('audit')))
        self.assertTrue(any(r['event']=='submissions.expired' for r in self.store.list('audit')))
        with self.assertRaises(Error) as expired:self.svc.submit(self.user,fx.ServiceTests.body(self))
        self.assertEqual(expired.exception.status,410)
        for call in [lambda:self.svc.deliver(self.user,record['id']),lambda:self.svc.activity(self.user,record['id']),lambda:self.svc.dispatch(self.user,'GET','/submissions/'+record['id'])]:
            with self.assertRaises(Error) as hidden:call()
            self.assertEqual(hidden.exception.status,404)
        self.assertEqual(len(self.store.list('remote_container')),1)

    def test_recent_unfinished_locked_and_invalid_timestamps_are_preserved(self):
        record=self.old_receipt();self.enable()
        for n,status in enumerate(['pending','submitting','failed','needs_attention']):
            r=clone(record);r.update(_key=f'unfinished-{n}',id=f'unfinished-{n}',status=status);self.store.insert('submissions',r)
        for name,at in [('recent','2026-09-21T00:00:00Z'),('boundary','2026-08-23T12:00:00Z'),('invalid','2020-invalid'),('naive','2020-01-01T00:00:00')]:
            r=clone(record);r.update(_key=name,id=name,updated_at=at);self.store.insert('submissions',r)
        self.store.insert('locks',{'_key':'delivery:'+record['id']})
        with patch('actionstack.retention.utcnow',return_value=NOW):age_out_submissions(self.svc)
        self.assertFalse(any(r['status']=='expired' for r in self.store.list('submissions')))

    def test_cleanup_is_bounded_shared_across_instances_and_settings_omission_preserves_policy(self):
        record=self.old_receipt();self.enable()
        for n in range(104):
            r=clone(record);r.update(_key=f'old-{n:03}',id=f'old-{n:03}');self.store.insert('submissions',r)
        with patch('actionstack.retention.utcnow',return_value=NOW):
            age_out_submissions(self.svc)
            age_out_submissions(self.svc)
        self.assertEqual(len(self.store.list('submissions',{'status':'expired'})),100)
        with patch('actionstack.retention.utcnow',return_value='2026-09-22T13:00:00Z'):age_out_submissions(self.svc)
        self.assertEqual(len(self.store.list('submissions',{'status':'expired'})),105)
        result=self.svc.save_settings(fx.ADMIN,{'soar_url':'https://soar.example.test','revision':1})
        self.assertEqual(result['retention_days'],30)

    def test_atomic_replacement_never_deletes_the_idempotency_key(self):
        record=self.old_receipt();self.enable()
        with patch.object(self.store,'delete',wraps=self.store.delete) as delete,patch('actionstack.retention.utcnow',return_value=NOW):
            age_out_submissions(self.svc)
        delete.assert_not_called()
        self.assertIsNotNone(self.store.get('submissions',record['id']))

class RetentionStoreTests(unittest.TestCase):
    def test_kv_query_uses_bounded_limit_and_retention_filter(self):
        rest=Mock();rest.call.return_value=[{'_key':str(i)} for i in range(100)]
        query={'status':'submitted','updated_at':{'$lt':'2026-01-01T00:00:00Z'}}
        self.assertEqual(len(KVStore(rest).list('submissions',query,limit=100)),100)
        rest.call.assert_called_once()
        params=rest.call.call_args.kwargs['params']
        self.assertEqual(params['limit'],100);self.assertEqual(json.loads(params['query']),query)

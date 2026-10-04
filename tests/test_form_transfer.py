import unittest
import test_pages as fx
from actionstack.core import Error, clone
from actionstack.form_transfer import PORTABLE_FIELDS

class FormTransferTests(unittest.TestCase):
    setUp=fx.ServiceTests.setUp
    tearDown=fx.ServiceTests.tearDown

    def body(self):
        source=self.svc.dispatch(fx.ADMIN,'GET','/admin/forms')[0]
        return {'workspace_id':'security','document':{'format':'actionstack-form','format_version':1,'app_version':'0.5.9','form':{k:clone(v) for k,v in source.items() if k in PORTABLE_FIELDS}}}

    def imported(self,body,actor=fx.ADMIN):
        return self.svc.dispatch(actor,'POST','/admin/forms/import',body)

    def test_import_preserves_configuration_as_unsaved_draft_with_new_identity(self):
        body=self.body(); source=clone(body['document']['form']); forms=clone(self.store.list('forms'))
        self.factory.reset_mock()
        result=self.imported(body)
        self.assertNotEqual(result['id'],'block-object')
        self.assertRegex(result['id'],r'^block-an-object-[a-f0-9]{4}$')
        self.assertEqual((result['state'],result['revision'],result['version']),('draft',0,0))
        for key in ['fields','mapping','category','icon','accent']: self.assertEqual(result[key],source[key])
        self.assertEqual(result['access'],{'view_roles':[],'submit_roles':[],'edit_roles':['admin'],'team_roles':[]})
        self.assertEqual(self.store.list('forms'),forms)
        self.assertEqual(self.store.list('submissions'),[])
        self.factory.assert_not_called()
        definition={k:v for k,v in result.items() if k not in ['revision','version','state']}
        saved=self.svc.save_form(fx.ADMIN,{'form':definition,'expected_revision':0})
        self.assertEqual(saved['state'],'draft')
        self.assertEqual(self.svc.published('block-object')['id'],'block-object')

    def test_destination_defaults_and_create_permissions_are_enforced(self):
        body=self.body()
        self.svc.save_workspace(fx.ADMIN,{'workspace':{'id':'hr','name':'HR','description':'','roles':['team_a'],'state':'active','role_groups':{'viewer':['team_a'],'user':['team_a'],'admin':['team_b']}},'expected_revision':0})
        body['workspace_id']='hr'
        for actor in [self.user,fx.actor('editor',['team_a'],['use','edit'])]:
            with self.assertRaises(Error) as denied:self.imported(body,actor)
            self.assertEqual(denied.exception.status,403)
        admin=fx.actor('hr_admin',['team_b'],['use','edit'])
        result=self.imported(body,admin)
        self.assertEqual(result['access'],self.svc.workspace_records()['hr']['default_access'])
        body['workspace_id']='missing'
        with self.assertRaises(Error):self.imported(body)
        w=self.svc.workspace_records()['hr']
        w['state']='archived';self.store.put('workspaces',w)
        body['workspace_id']='hr'
        with self.assertRaises(Error):self.imported(body)

    def test_invalid_files_and_source_permissions_are_rejected(self):
        base=self.body()
        bad=[None,[],{},dict(base['document'],format_version=True),dict(base['document'],format_version=2),dict(base['document'],format='receipt')]
        for field,value in [('access',{}),('workspace_id','foreign'),('id','block-object'),('revision',8),('validation_policy_id','missing')]:
            document=clone(base['document']);document['form'][field]=value;bad.append(document)
        for value in [None,[],{'fields':[]},dict(base['document']['form'],mapping=None),dict(base['document']['form'],fields=[{'key':'bad','type':[],'label':'Bad'}])]:
            bad.append(dict(base['document'],form=value))
        bad.append(dict(base['document'],app_version='x'*210000))
        for document in bad:
            with self.subTest(document=str(document)[:120]),self.assertRaises(Error) as rejected:self.imported(dict(base,document=document))
            self.assertEqual(rejected.exception.status,400)
        self.assertEqual(len(self.store.list('forms')),1)

    def test_lookup_spl_and_conditional_fields_are_validated_without_running_search(self):
        body=self.body();form=body['document']['form']
        form['mapping'].pop('enrichment',None);form['mapping'].pop('approval',None)
        form['fields']=[{'key':'enabled','type':'checkbox','label':'Enabled','default':True},{'key':'user','type':'lookup','label':'User','show_when':{'field':'enabled','equals':True},'lookup':{'search':'| inputlookup identities | eval label=upper(identity) | table identity label','app':'search','value_field':'identity','label_field':'label','min_chars':3,'debounce_ms':50}}]
        self.factory.reset_mock()
        result=self.imported(body)
        self.assertEqual(result['fields'],form['fields'])
        self.factory.assert_not_called()
        form['fields'][1]['lookup']['search']='| inputlookup identities | outputlookup stolen'
        with self.assertRaises(Error):self.imported(body)

    def test_import_has_same_field_validation_as_form_save(self):
        body=self.body()
        body['document']['form']['fields'][0]['default']='invalid-choice'
        with self.assertRaises(Error):self.imported(body)

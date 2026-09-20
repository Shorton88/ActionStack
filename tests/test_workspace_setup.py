"""Workspace onboarding, scoped defaults, previews and user preferences."""
import json
import unittest
from unittest.mock import Mock
import test_pages as fx
from actionstack.core import Error, Conflict, PREFIX, seed_form, clone
from actionstack.service import Service, DEFAULT_SETTINGS
from actionstack.field_validation import inline_form
from actionstack.workspace_roles import WorkspaceRoles, role_groups, ROLE_CAPABILITIES
from dev_server import DemoRoles

class SetupTests(unittest.TestCase):
    setUp=fx.ServiceTests.setUp
    tearDown=fx.ServiceTests.tearDown

    def create(self, namespace='helpdesk'):
        manager=DemoRoles(self.store)
        self.svc.role_manager=manager
        self.svc.roles=lambda:fx.ROLES+[r['name'] for r in self.store.list('demo_roles')]
        return self.svc.dispatch(fx.ADMIN,'POST','/admin/workspaces/save',{
            'workspace':{'id':namespace,'name':namespace.title(),'description':'Team requests','roles':[],'state':'active'},
            'expected_revision':0,'create_roles':True})

    def new_form(self,w):
        f=seed_form(); f.update(id='helpdesk-request',workspace_id=w['id']); f.pop('access')
        return self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':0},True)

    def test_fresh_production_setup_has_no_published_example_or_security_workspace(self):
        for c in ['workspaces','forms']:
            for r in self.store.list(c):self.store.delete(c,r['_key'])
        self.svc.demo=False
        self.svc.bootstrap()
        self.assertEqual(self.store.list('workspaces'),[])
        self.assertEqual(self.store.list('forms'),[])
        self.assertTrue(self.svc.dispatch(fx.ADMIN,'GET','/context')['setup_required'])

    def test_upgrade_retains_existing_workspace_and_form(self):
        self.svc.demo=False
        self.svc.bootstrap()
        self.assertEqual(self.svc.latest('block-object')['revision'],1)
        self.assertEqual(list(self.svc.workspace_records()),['security'])

    def test_namespace_defaults_protect_submission_and_editing(self):
        w=self.create(); f=self.new_form(w)
        self.assertEqual(f['access'],w['default_access'])
        groups=role_groups('helpdesk')
        users={level:fx.actor(level,roles=groups[level],caps=ROLE_CAPABILITIES[level]) for level in groups}
        body={'form_id':f['id'],'form_version':1,'inputs':fx.inputs(),'idempotency_key':'request-001'}
        receipt=self.svc.submit(users['user'],body)
        self.assertEqual(self.svc.list_submissions(users['viewer'],{'workspace_id':w['id']})[0]['id'],receipt['id'])
        # A viewer may also inherit the standard Splunk user submit capability.
        users['viewer']['capabilities'].append(PREFIX+'submit')
        with self.assertRaises(Error):self.svc.submit(users['viewer'],dict(body,idempotency_key='request-002'))
        with self.assertRaises(Error):self.svc.save_form(users['viewer'],{'form':fx.editable(inline_form(f)),'expected_revision':1})
        updated=self.svc.save_form(users['admin'],{'form':fx.editable(inline_form(f)),'expected_revision':1},True)
        self.assertEqual(updated['version'],2)
        with self.assertRaises(Error):self.svc.dispatch(users['admin'],'GET','/settings')
        outsider=fx.actor('other',roles=['team_b'],caps=ROLE_CAPABILITIES['admin'])
        self.assertEqual(self.svc.list_submissions(outsider,{'workspace_id':w['id']}),[])
        with self.assertRaises(Error):self.svc.save_form(outsider,{'form':fx.editable(inline_form(updated)),'expected_revision':2})
        # An admin of another workspace with local viewer access cannot invent
        # an editable form here using its global edit capability.
        other_admin=fx.actor('other-admin',roles=['team_b',groups['viewer'][0]],caps=ROLE_CAPABILITIES['admin'])
        forged=fx.editable(inline_form(updated));forged['id']='forged-form';forged['access']['edit_roles']=['team_b']
        with self.assertRaises(Error):self.svc.save_form(other_admin,{'form':forged,'expected_revision':0})

    def test_creation_authorization_revision_and_roles_are_checked_before_role_writes(self):
        self.svc.role_manager=Mock()
        body={'workspace':{'id':'test','name':'Test','description':'','roles':[],'state':'active'},'expected_revision':0,'create_roles':True}
        with self.assertRaises(Error):self.svc.save_workspace(self.user,body)
        with self.assertRaises(Conflict):self.svc.save_workspace(fx.ADMIN,dict(body,expected_revision=3))
        with self.assertRaises(Error):self.svc.save_workspace(fx.ADMIN,dict(body,workspace=dict(body['workspace'],id='bad/id')))
        self.svc.role_manager.ensure.assert_not_called()

    def test_existing_role_mapping_requires_admin_and_never_provisions_roles(self):
        self.svc.role_manager=Mock()
        w={'id':'it','name':'IT','description':'','roles':[],'state':'active','role_groups':{'viewer':['team_a'],'user':['user'],'admin':['author']}}
        saved=self.svc.save_workspace(fx.ADMIN,{'workspace':w,'expected_revision':0})
        self.assertEqual(saved['default_access']['team_roles'],['author','team_a','user'])
        self.svc.role_manager.ensure.assert_not_called()
        w['id']='it-two';w['role_groups']['admin']=[]
        with self.assertRaises(Error):self.svc.save_workspace(fx.ADMIN,{'workspace':w,'expected_revision':0})

    def test_submissions_filters_apply_before_limit_and_cannot_grant_access(self):
        receipt=self.svc.submit(self.user,fx.ServiceTests.body(self))
        base=self.store.get('submissions',receipt['id'])
        for n in range(205):
            row=clone(base);row.update(_key='other-'+str(n),id='other-'+str(n),submitted_at='2099-01-01T00:00:00Z')
            row['actor']['username']='bob';row['form']['workspace_id']='elsewhere'
            self.store.insert('submissions',row)
        rows=self.svc.list_submissions(fx.ADMIN,{'workspace_id':'security'})
        self.assertEqual([r['id'] for r in rows],[receipt['id']])
        rows=self.svc.list_submissions(self.user,{'workspace_id':'*','mine':True})
        self.assertEqual([r['id'] for r in rows],[receipt['id']])
        self.assertEqual(self.svc.list_submissions(fx.actor('eve'),{'workspace_id':'elsewhere'}),[])

    def test_prefix_filters_labels_and_publish_but_preserves_existing_routing(self):
        self.svc.save_settings(fx.ADMIN,dict(DEFAULT_SETTINGS,soar_url='https://soar.example.test',label_prefix='service_'))
        self.assertEqual(self.svc.available_labels(fx.ADMIN),{'prefix':'service_','labels':['service_requests']})
        with self.assertRaises(Error):self.svc.available_labels(self.user)
        f=seed_form()
        self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1},True)
        f['id']='new-request'
        with self.assertRaises(Error):self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':0},True)
        self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':0})
        with self.assertRaises(Error):self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1},True)
        f['mapping']['label']='service_requests'
        self.assertEqual(self.svc.save_form(fx.ADMIN,{'form':f,'expected_revision':1},True)['version'],1)
        with self.assertRaises(Error):self.svc.save_settings(fx.ADMIN,dict(DEFAULT_SETTINGS,soar_url='https://soar.example.test',label_prefix='bad prefix',revision=1))

    def test_theme_preferences_are_private_and_revision_checked(self):
        a=self.svc.dispatch(self.user,'GET','/preferences');self.assertEqual(a,{'theme':'dark','revision':0})
        self.svc.dispatch(self.user,'POST','/preferences',{'theme':'light','revision':0})
        self.assertEqual(self.svc.dispatch(fx.actor('bob'),'GET','/preferences')['theme'],'dark')
        with self.assertRaises(Conflict):self.svc.dispatch(self.user,'POST','/preferences',{'theme':'system','revision':0})
        with self.assertRaises(Error):self.svc.dispatch(self.user,'POST','/preferences',{'theme':'light','revision':1,'username':'bob'})
        self.assertEqual(self.svc.dispatch(self.user,'GET','/preferences')['theme'],'light')

    def test_preview_runs_actual_validation_without_submissions_or_remote_writes(self):
        f=seed_form();f.update(id='preview-only',fields=[{'key':'emailAddress','label':'Email','type':'text','required':True,'validation':[{'operator':'regex','value':r'[^@]+@example\.test','message':'Use your work email.'}]}])
        f['mapping'].pop('policy',None); f['mapping']['enrichment']='none';f['mapping']['approval']={'mode':'never','policy':'soar_playbook','conditions':[]}
        before=len(self.store.list('forms'))
        for inputs in [{},{'emailAddress':'alice@outside.test'}]:
            with self.assertRaises(Error) as exc:self.svc.preview_validation(fx.ADMIN,{'form':f,'inputs':inputs})
            self.assertIn('emailAddress',exc.exception.fields)
        result=self.svc.preview_validation(fx.ADMIN,{'form':f,'inputs':{'emailAddress':'alice@example.test'}})
        self.assertTrue(result['valid']);self.assertEqual(len(self.store.list('forms')),before)
        self.assertEqual(self.store.list('submissions'),[]);self.factory.assert_not_called()
        with self.assertRaises(Error):self.svc.preview_validation(self.user,{'form':f,'inputs':{}})

    def test_preview_checks_lookup_values_as_requesting_user(self):
        f=seed_form();f['fields'].append({'key':'identity','label':'Identity','type':'lookup','lookup':{'search':'| inputlookup people | fields identity','app':'search','min_chars':3,'debounce_ms':50}})
        self.svc.lookup=Mock();self.svc.lookup.search.return_value={'options':[],'more':False}
        with self.assertRaises(Error) as exc:self.svc.preview_validation(fx.ADMIN,{'form':f,'inputs':dict(fx.inputs(),identity='missing')})
        self.assertIn('identity',exc.exception.fields)
        self.assertEqual(self.svc.lookup.search.call_args.args[1],'missing')
        self.assertEqual(self.store.list('submissions'),[]);self.factory.assert_not_called()

class RoleAdapterTests(unittest.TestCase):
    def test_names_and_capabilities_are_namespace_scoped(self):
        rest=Mock();rest.call.return_value=None
        result=WorkspaceRoles(rest).ensure('service-desk')
        self.assertEqual(result['admin'],['as_service_desk_admin'])
        posts=[c for c in rest.call.call_args_list if c.args[0]=='POST']
        self.assertEqual(len(posts),3)
        for c in posts:
            self.assertEqual(c.args[1],'/services/authorization/roles')
            self.assertNotIn(PREFIX+'admin',c.kwargs['form']['capabilities'])
            self.assertNotIn('imported_roles',c.kwargs['form'])
        self.assertIn(PREFIX+'read_team',posts[0].kwargs['form']['capabilities'])
        self.assertNotIn(PREFIX+'submit',posts[0].kwargs['form']['capabilities'])

    def test_conflicting_existing_role_is_not_changed(self):
        rest=Mock();rest.call.side_effect=[None,{'entry':[{'content':{'capabilities':['admin_all_objects']}}]}]
        with self.assertRaises(Error):WorkspaceRoles(rest).ensure('it')
        self.assertTrue(all(c.args[0]=='GET' for c in rest.call.call_args_list))

    def test_partial_creation_can_be_retried_without_overwriting(self):
        rest=Mock();rest.call.side_effect=[{'entry':[{'content':{'capabilities':[PREFIX+c for c in ROLE_CAPABILITIES['viewer']],'imported_roles':[]}}]},None,None,None,None]
        WorkspaceRoles(rest).ensure('it')
        posts=[c for c in rest.call.call_args_list if c.args[0]=='POST']
        self.assertEqual([c.kwargs['form']['name'] for c in posts],['as_it_user','as_it_admin'])

    def test_write_failure_explains_retry_and_does_not_delete_roles(self):
        rest=Mock();rest.call.side_effect=[None,None,None,None,Error(503,'denied')]
        with self.assertRaises(Error) as exc:WorkspaceRoles(rest).ensure('it')
        self.assertIn('Some roles may already have been created',exc.exception.message)
        self.assertNotIn('DELETE',[c.args[0] for c in rest.call.call_args_list])

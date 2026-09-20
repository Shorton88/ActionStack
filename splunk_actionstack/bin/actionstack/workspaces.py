"""Role-scoped workspaces, stored as immutable revisions in shared KV Store."""
from .core import Error, Conflict, SLUG, capable, require, clone, utcnow
from .workspace_roles import role_groups, default_access

DEFAULT_WORKSPACE='security'

class Workspaces:
    def workspace_records(self):
        latest={}
        for row in self.store.list('workspaces'):
            if row['id'] not in latest or row['revision']>latest[row['id']]['revision']: latest[row['id']]=row
        return latest

    def workspace_allowed(self,actor,workspace_id,active=True):
        w=self.workspace_records().get(workspace_id)
        return bool(w and (not active or w['state']=='active') and (capable(actor,'admin') or not w['roles'] or set(w['roles'])&set(actor['roles'])))

    def list_workspaces(self,actor,admin=False):
        require(actor,'admin' if admin else 'use')
        rows=self.workspace_records().values()
        return sorted([clone(w) for w in rows if admin or capable(actor,'admin') or not w['roles'] or set(w['roles'])&set(actor['roles'])],key=lambda w:(w['id']!=DEFAULT_WORKSPACE,w['name'].lower()))

    def save_workspace(self,actor,body):
        require(actor,'admin')
        if set(body)-{'workspace','expected_revision','create_roles'} or not {'workspace','expected_revision'}<=set(body): raise Error(400,'Invalid workspace update.')
        create_roles=body.get('create_roles',False)
        if type(create_roles) is not bool: raise Error(400,'Invalid role creation option.')
        w=body['workspace']
        if not isinstance(w,dict) or set(w)-{'id','name','description','roles','state','role_groups'} or not {'id','name','description','roles','state'}<=set(w): raise Error(400,'Invalid workspace.')
        if not isinstance(w['id'],str) or not SLUG.fullmatch(w['id']): raise Error(400,'Use a lowercase workspace ID with letters, numbers and hyphens.')
        if not isinstance(w['name'],str) or not 1<=len(w['name'].strip())<=80 or not isinstance(w['description'],str) or len(w['description'])>500: raise Error(400,'Enter a workspace name and a description of up to 500 characters.')
        if not isinstance(w['roles'],list) or len(w['roles'])>100 or any(not isinstance(r,str) or r not in self.roles() for r in w['roles']): raise Error(400,'Choose existing Splunk roles for workspace membership.')
        if w['state'] not in ['active','archived']: raise Error(400,'Invalid workspace state.')
        if w['id']==DEFAULT_WORKSPACE and w['state']!='active': raise Error(400,'The default workspace must remain active for existing forms.')
        current=self.workspace_records().get(w['id']); revision=current['revision'] if current else 0
        if type(body['expected_revision']) is not int or body['expected_revision']!=revision: raise Conflict()
        if create_roles and current: raise Error(400,'Automatic role creation is only available for a new workspace.')
        if create_roles and not self.role_manager: raise Error(403,'Role creation is unavailable. Ask a Splunk administrator to create the roles, then select them here.')
        groups=role_groups(w['id']) if create_roles else w.get('role_groups',current.get('role_groups') if current else None)
        if groups is not None:
            if not isinstance(groups,dict) or set(groups)!={'viewer','user','admin'}: raise Error(400,'Choose viewer, user and admin roles.')
            for names in groups.values():
                if not isinstance(names,list) or len(names)>100 or any(not isinstance(n,str) or (not create_roles and n not in self.roles()) for n in names): raise Error(400,'Choose existing Splunk roles.')
            # Empty submit/edit ACLs mean public in legacy forms; do not generate
            # accidentally open defaults from an incomplete role mapping.
            if not groups['admin']: raise Error(400,'Choose at least one workspace admin role.')
        with self.lock('workspace:'+w['id'],actor):
            fresh=self.workspace_records().get(w['id'])
            if (fresh['revision'] if fresh else 0)!=revision: raise Conflict()
            if create_roles:
                groups=self.role_manager.ensure(w['id'])
                self.audit(actor,'workspace.roles_created',w['id'])
            out=clone(w)
            if groups is not None:
                out['role_groups']=clone(groups)
                out['default_access']=default_access(groups)
                out['roles']=sorted(set(w['roles']+out['default_access']['view_roles']))
            out.update(name=w['name'].strip(),roles=sorted(set(out['roles'])),revision=revision+1,_key=w['id']+':'+str(revision+1).zfill(8),updated_at=utcnow(),updated_by=actor['username'])
            self.store.insert('workspaces',out)
        self.audit(actor,'workspace.updated',w['id'])
        return out

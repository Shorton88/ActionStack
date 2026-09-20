"""Optional namespace roles, created with the requesting user's Splunk token."""
from urllib.parse import quote
from .core import Error, PREFIX, SLUG

ROLE_CAPABILITIES={
    'viewer':['use','read_team'],
    'user':['use','read_team','submit'],
    'admin':['use','read_team','submit','edit','publish'],
}

def role_groups(namespace):
    if not isinstance(namespace,str) or not SLUG.fullmatch(namespace): raise Error(400,'Invalid workspace ID.')
    return {level:['as_'+namespace.replace('-','_')+'_'+level] for level in ROLE_CAPABILITIES}

def default_access(groups):
    everyone=sorted(set(groups['viewer']+groups['user']+groups['admin']))
    return {'view_roles':everyone,'team_roles':everyone,'submit_roles':sorted(set(groups['user']+groups['admin'])),'edit_roles':sorted(set(groups['admin']))}

class WorkspaceRoles:
    def __init__(self,user_rest): self.rest=user_rest

    def ensure(self,namespace):
        groups=role_groups(namespace)
        # Check every existing role before any write. Never alter existing roles.
        missing=[]
        for level,names in groups.items():
            name=names[0]
            caps=[PREFIX+c for c in ROLE_CAPABILITIES[level]]
            result=self.rest.call('GET','/services/authorization/roles/'+quote(name,safe=''))
            if result:
                content=result.get('entry',[{}])[0].get('content',{})
                if set(content.get('capabilities',[]))!=set(caps) or content.get('imported_roles'):
                    raise Error(409,'Role '+name+' already exists with different permissions. Use existing roles or choose a different workspace ID.')
            else: missing.append((name,caps))
        for name,caps in missing:
            try: self.rest.call('POST','/services/authorization/roles',form={'name':name,'capabilities':caps})
            except Error:
                raise Error(503,'Could not create workspace role '+name+'. Your Splunk account needs permission to create roles and grant these app capabilities. Some roles may already have been created; retry safely after correcting permissions.')
        return groups

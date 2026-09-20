"""Splunk adapters. User identity and privileged storage are deliberately separate."""
import json
from urllib.parse import quote
from .core import APP, Error, Conflict

class SplunkREST:
    def __init__(self,token): self.token=token
    def call(self,method,path,body=None,params=None,form=None):
        import splunk.rest
        kwargs={'sessionKey':self.token,'method':method,'getargs':dict(params or {},output_mode='json'),'raiseAllErrors':True}
        if body is not None: kwargs['jsonargs']=json.dumps(body,allow_nan=False)
        if form is not None: kwargs['postargs']=form
        try:
            response,content=splunk.rest.simpleRequest(path,**kwargs)
            if isinstance(content,bytes): content=content.decode('utf-8')
            return json.loads(content) if content else {}
        except Exception as exc:
            status=getattr(exc,'statusCode',getattr(exc,'status',500))
            try: status=int(status)
            except (ValueError,TypeError): status=500
            if status==404: return None
            if status==409 or (status==400 and 'duplicate' in str(exc).lower()): raise Conflict()
            raise Error(503,'Splunk storage is unavailable or its permissions are not configured. Check the app installation.')

class KVStore:
    def __init__(self,rest): self.rest=rest
    def path(self,collection,key=None):
        base='/servicesNS/nobody/'+APP+'/storage/collections/data/actionstack_'+collection
        return base+('/'+quote(key,safe='') if key is not None else '')
    def get(self,collection,key): return self.rest.call('GET',self.path(collection,key))
    def list(self,collection,query=None):
        output=[]; offset=0
        while True:
            batch=self.rest.call('GET',self.path(collection),params={'query':json.dumps(query or {}),'limit':500,'skip':offset,'sort':'_key:1'})
            if batch is None: raise Error(503,'App KV Store collections are missing. Install the full app bundle.')
            output.extend(batch)
            if len(batch)<500: return output
            offset+=500
            if offset>=50000: raise Error(503,'Collection size exceeded this release’s limit. Apply the retention runbook.')
    def insert(self,collection,record): self.rest.call('POST',self.path(collection),body=record)
    def put(self,collection,record): self.rest.call('POST',self.path(collection,record['_key']),body=record)
    def delete(self,collection,key): self.rest.call('DELETE',self.path(collection,key))

class SplunkSecrets:
    def __init__(self,rest): self.rest=rest
    def put(self,key,token):
        self.rest.call('POST','/servicesNS/nobody/'+APP+'/storage/passwords',form={'name':key,'realm':'actionstack','password':token})
    def get(self,key):
        if not key: return ''
        entry=quote('actionstack:'+key+':',safe='')
        result=self.rest.call('GET','/servicesNS/nobody/'+APP+'/storage/passwords/'+entry)
        if not result: raise Error(503,'The configured SOAR credential is unavailable on this search head.')
        value=result.get('entry',[{}])[0].get('content',{}).get('clear_password')
        if not value: raise Error(503,'The SOAR credential cannot be read. Check credential replication and permissions.')
        return value

def identity(user_rest,system_rest=None):
    result=user_rest.call('GET','/services/authentication/current-context')
    content=(result or {}).get('entry',[{}])[0].get('content',{})
    if not content.get('username') or content['username'] in ['nobody','splunk-system-user']: raise Error(401,'An authenticated Splunk user is required.')
    roles=set(content.get('roles',[]))
    if system_rest:
        result=system_rest.call('GET','/services/authorization/roles',params={'count':0})
        imports={e['name']:e.get('content',{}).get('imported_roles',[]) for e in (result or {}).get('entry',[])}
        pending=list(roles)
        while pending:
            for name in imports.get(pending.pop(),[]):
                if name not in roles: roles.add(name); pending.append(name)
    return {'username':content['username'],'roles':sorted(roles),'capabilities':content.get('capabilities',[]),'email':content.get('email',''),'display_name':content.get('realname','')}

def role_names(system_rest):
    result=system_rest.call('GET','/services/authorization/roles',params={'count':0})
    return sorted(e['name'] for e in (result or {}).get('entry',[]))

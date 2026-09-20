"""Authenticated persistent REST entrypoint for Splunk Enterprise 10.2.4."""
import json
import os
import sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from splunk.persistconn.application import PersistentServerConnectionApplication
from actionstack.core import Error
from actionstack.service import Service
from actionstack.soar import Soar
from actionstack.splunk_store import SplunkREST, KVStore, SplunkSecrets, identity, role_names

class ActionStackHandler(PersistentServerConnectionApplication):
    def __init__(self,command_line,command_arg):
        super().__init__()
    def handle(self,in_string):
        try:
            request=json.loads(in_string)
            user_token=request.get('session',{}).get('authtoken')
            system_token=request.get('system_authtoken')
            if not user_token: raise Error(401,'Sign in to Splunk to continue.')
            if not system_token: raise Error(503,'The REST handler requires passSystemAuth in restmap.conf.')
            system=SplunkREST(system_token)
            actor=identity(SplunkREST(user_token),system)
            from actionstack.lookups import LookupSearch
            from actionstack.workspace_roles import WorkspaceRoles
            service=Service(KVStore(system),SplunkSecrets(system),Soar,lambda:role_names(system),lookup=LookupSearch(SplunkREST(user_token),actor['username']),role_manager=WorkspaceRoles(SplunkREST(user_token)))
            raw=request.get('payload') or '{}'
            if len(raw.encode('utf-8'))>256*1024: raise Error(413,'Request exceeds 256 KB.')
            body=json.loads(raw,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('non-finite')))
            if not isinstance(body,dict): raise Error(400,'Request body must be an object.')
            path=request.get('path_info','')
            if path.startswith('/actionstack'): path=path[len('/actionstack'):]
            data=service.dispatch(actor,request['method'].upper(),'/'+path.strip('/'),body)
            return self.response(200,{'data':data})
        except Error as exc: return self.response(exc.status,{'error':exc.message,'fields':exc.fields})
        except (ValueError,TypeError,KeyError): return self.response(400,{'error':'Invalid request.'})
        except Exception: return self.response(500,{'error':'The request could not be completed. Check the app configuration and retry.'})
    @staticmethod
    def response(status,body):
        return {'status':status,'headers':{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'},'payload':json.dumps(body,allow_nan=False)}

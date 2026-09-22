"""Local-only demo API. Never packaged in the Splunk app; no live network delivery."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'splunk_actionstack'/'bin'))
import json
import sqlite3
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from actionstack.core import Conflict, Error, PREFIX, seed_form, clone
from actionstack.service import Service

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'.dev-data'/'actionstack.sqlite3'
class SQLiteStore:
    def __init__(self,db):
        self.db=str(db)
        with self.connect() as conn: conn.execute('CREATE TABLE IF NOT EXISTS records (collection TEXT, key TEXT, document TEXT, PRIMARY KEY(collection,key))')
    @contextmanager
    def connect(self):
        conn=sqlite3.connect(self.db,timeout=10)
        try:
            with conn: yield conn
        finally: conn.close()
    def get(self,c,k):
        with self.connect() as conn:
            row=conn.execute('SELECT document FROM records WHERE collection=? AND key=?',(c,k)).fetchone()
        return json.loads(row[0]) if row else None
    def list(self,c,query=None):
        with self.connect() as conn: rows=conn.execute('SELECT document FROM records WHERE collection=? ORDER BY key',(c,)).fetchall()
        items=[json.loads(row[0]) for row in rows]
        return [x for x in items if all(x.get(k)==v for k,v in (query or {}).items())]
    def insert(self,c,r):
        try:
            with self.connect() as conn: conn.execute('INSERT INTO records VALUES (?,?,?)',(c,r['_key'],json.dumps(r)))
        except sqlite3.IntegrityError: raise Conflict()
    def put(self,c,r):
        with self.connect() as conn: conn.execute('UPDATE records SET document=? WHERE collection=? AND key=?',(json.dumps(r),c,r['_key']))
    def delete(self,c,k):
        with self.connect() as conn: conn.execute('DELETE FROM records WHERE collection=? AND key=?',(c,k))

class DemoSecrets:
    def put(self,key,token): pass
    def get(self,key): return 'demo-only'

class DemoSoar:
    def __init__(self,store): self.store=store
    def labels(self): return ['automation_requests','events','phishing','service_requests']
    def activity(self,container_id,details=True):
        return {key:{'items':[],'total':0,'truncated':False,'error':None,'counts':dict.fromkeys(['success','failed','running','pending','cancelled','unknown'],0)} for key in (['playbooks','actions','blocks'] if details else ['playbooks','actions'])}
    def ensure(self,kind,payload):
        key=payload['source_data_identifier']; existing=self.store.get('remote_'+kind,key)
        if existing: return existing['id']
        record=dict(payload,_key=key,id=10000+len(self.store.list('remote_'+kind)))
        try: self.store.insert('remote_'+kind,record)
        except Conflict: return self.store.get('remote_'+kind,key)['id']
        return record['id']

class DemoLookup:
    def search(self,config,term,exact=False):
        from actionstack.lookups import lookup_spl,lookup_fields
        lookup_spl(config,term,exact)
        values=['alice@example.test','alicia@example.test','alex@example.test','bob@example.test','scott@example.test']
        value_field,label_field=lookup_fields(config)
        options=[{'value':v,'label':v if value_field==label_field else v.split('@')[0].title()+' Example'} for v in values]
        matches=[o for o in options if ((o['value'].lower() in [v.lower() for v in term] if isinstance(term,list) else o['value'].lower()==term.lower()) if exact else any(o[k].lower().startswith(term.lower()) for k in ['value','label']))]
        return {'options':matches,'more':False}

ACTOR={'username':'demo.user','display_name':'Demo workspace','email':'demo@example.test','roles':['admin','user'],'capabilities':[PREFIX+x for x in ['use','submit','edit','publish','admin','audit','read_team']]}

class DemoRoles:
    def __init__(self,store): self.store=store
    def ensure(self,namespace):
        from actionstack.workspace_roles import role_groups
        groups=role_groups(namespace)
        for names in groups.values():
            try: self.store.insert('demo_roles',{'_key':names[0],'name':names[0]})
            except Conflict: pass
        return groups

def make_service(db):
    store=SQLiteStore(db)
    return Service(store,DemoSecrets(),lambda settings,token:DemoSoar(store),lambda:sorted(set(['admin','user','security_analyst']+[r['name'] for r in store.list('demo_roles')])),demo=True,lookup=DemoLookup(),role_manager=DemoRoles(store))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self): self.handle_api()
    def do_POST(self): self.handle_api()
    def log_message(self,*args): pass
    def handle_api(self):
        try:
            if self.headers.get('Host','').split(':')[0] not in ['127.0.0.1','localhost']: raise Error(403,'Local demo only.')
            if not self.path.startswith('/api/'): raise Error(404,'Not found.')
            if self.command=='POST':
                if self.headers.get('X-ActionStack-Request')!='1': raise Error(403,'Invalid demo request.')
                origin=self.headers.get('Origin')
                if origin and origin not in ['http://127.0.0.1:5173','http://localhost:5173','http://127.0.0.1:8765']: raise Error(403,'Invalid origin.')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<=length<=256*1024: raise Error(413,'Request too large.')
            body=json.loads(self.rfile.read(length) or '{}')
            result=self.server.service.dispatch(ACTOR,self.command,self.path[4:].split('?')[0],body)
            self.respond(200,{'data':result})
        except Error as exc: self.respond(exc.status,{'error':exc.message,'fields':exc.fields})
        except (ValueError,TypeError): self.respond(400,{'error':'Invalid request.'})
        except Exception:
            import traceback; traceback.print_exc()
            self.respond(500,{'error':'Demo request failed. Check the development terminal.'})
    def respond(self,status,body):
        data=json.dumps(body).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

if __name__=='__main__':
    DB.parent.mkdir(exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',8765),Handler)
    server.service=make_service(DB)
    print('Demo API: http://127.0.0.1:8765 — simulated SOAR, no live actions',flush=True)
    server.serve_forever()

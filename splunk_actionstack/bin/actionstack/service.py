"""Application service; persistence provides atomic insert for cluster-wide coordination."""
import json
import hashlib
import uuid
import time
import re
from contextlib import contextmanager
from .core import APP, Error, Conflict, allowed, capable, require, clone, digest, utcnow, seed_form, validate_definition, validate_inputs, event_payload

from .workspaces import Workspaces, DEFAULT_WORKSPACE
from .validation_policies import ValidationPolicies, validate_request, block_policy, public_policy
from .lookups import validate_source,lookup_spl
from .field_validation import inline_form, validate_field_inputs

DEFAULT_SETTINGS={'soar_url':'','instance_name':'Splunk Enterprise','asset_id':None,'ca_pem':'','ignore_certificate_errors':False,'request_timeout':15,'label_prefix':'','revision':0}

class Service(Workspaces,ValidationPolicies):
    def __init__(self, store, secrets, remote_factory, roles, demo=False, lookup=None,role_manager=None):
        self.store,self.secrets,self.remote_factory,self.roles,self.demo=store,secrets,remote_factory,roles,demo
        self.lookup=lookup
        self.role_manager=role_manager

    def delivery_budget(self,actor):
        # Unique slots bound concurrent requests across SHC members; no local counter.
        minute=int(time.time()//60)
        prefix=digest(actor['username'])+':'+str(minute)+':'
        for slot in range(10):
            try:
                self.store.insert('ratelimits',{'_key':prefix+str(slot),'minute':minute})
                return
            except Conflict: pass
        raise Error(429,'Delivery limit reached. Wait a minute before retrying this request.')

    @contextmanager
    def lock(self,key,actor):
        token=str(uuid.uuid4())
        try: self.store.insert('locks',{'_key':key,'token':token,'created_at':utcnow(),'actor':actor['username']})
        except Conflict: raise Conflict('This operation is already in progress. An interrupted operation may need administrator recovery; see the runbook.')
        try: yield
        finally: self.store.delete('locks',key)

    def audit(self,actor,event,entity):
        self.store.insert('audit',{'_key':str(uuid.uuid4()),'at':utcnow(),'actor':actor['username'],'event':event,'entity':entity})

    def bootstrap(self):
        self.seed_validation_policy(block_policy())
        # Existing installations keep the compatibility workspace. A fresh
        # production installation starts with the admin's setup wizard.
        if not self.store.list('workspaces') and (self.demo or self.store.list('forms')):
            try: self.store.insert('workspaces',{'_key':'security:00000001','id':'security','name':'Security workspace','description':'Default workspace for existing forms.','roles':[],'state':'active','revision':1,'updated_at':utcnow(),'updated_by':'system'})
            except Conflict: pass
        if self.demo and not self.store.list('forms'):
            f=seed_form(); f.update(revision=1,version=1,state='published',updated_at=utcnow(),updated_by='system')
            try: self.store.insert('forms',dict(f,_key='block-object:00000001'))
            except Conflict: pass

    def settings(self):
        values=self.store.list('settings'); return max(values,key=lambda x:x['revision']) if values else clone(DEFAULT_SETTINGS)

    def public_settings(self):
        s=self.settings()
        # KV Store adds metadata such as _user. Only expose editable fields;
        # returning the stored document makes a subsequent save reject itself.
        return {k:clone(s.get(k,default)) for k,default in DEFAULT_SETTINGS.items()}|{'token_configured':bool(s.get('secret_ref')),'demo':self.demo}

    def preferences(self,actor,body=None):
        records=self.store.list('preferences',{'username':actor['username']})
        current=max(records,key=lambda r:r['revision']) if records else {'theme':'dark','revision':0}
        if body is None: return {k:current[k] for k in ['theme','revision']}
        if set(body)!={'theme','revision'} or body['theme'] not in ['dark','light','system']: raise Error(400,'Choose Dark, Light or System theme.')
        if type(body['revision']) is not int or body['revision']!=current['revision']: raise Conflict()
        revision=current['revision']+1
        self.store.insert('preferences',{'_key':digest(actor['username'])+':'+str(revision).zfill(8),'username':actor['username'],'theme':body['theme'],'revision':revision})
        return {'theme':body['theme'],'revision':revision}

    def available_labels(self,actor):
        require(actor,'edit'); s=self.settings()
        if not self.demo and not s.get('secret_ref'): raise Error(409,'Ask an app administrator to save the SOAR connection first.')
        labels=self.remote_factory(s,self.secrets.get(s.get('secret_ref'))).labels()
        prefix=s.get('label_prefix','')
        return {'prefix':prefix,'labels':[label for label in labels if label.startswith(prefix)]}

    def preview_validation(self,actor,body):
        require(actor,'edit')
        if set(body)!={'form','inputs'}: raise Error(400,'Invalid form preview.')
        f=validate_definition(body['form'],self.roles())
        if not self.workspace_allowed(actor,f['workspace_id']): raise Error(403,'This workspace is unavailable to your roles.')
        records=self.records(f['id'])
        if records and not self.form_editable(actor,records[-1]): raise Error(403,'You cannot preview this form.')
        f=self.editable_validation(f); self.attach_validation(actor,f)
        inputs=self.checked_inputs(actor,f,body['inputs'])
        return {'valid':True,'inputs':inputs,'message':'Validation passed. No submission or SOAR event was created.'}

    def checked_inputs(self,actor,f,incoming):
        inputs=validate_inputs(f,incoming)
        for field in f['fields']:
            if field['type'] in ['lookup','lookup_multi'] and field['key'] in inputs:
                result=self.run_lookup(actor,field['lookup'],inputs[field['key']],exact=True)
                expected=inputs[field['key']] if isinstance(inputs[field['key']],list) else [inputs[field['key']]]
                found={o['value'].lower():o['value'] for o in result['options']}
                if any(v.lower() not in found for v in expected): raise Error(400,'Choose a current lookup value.',{field['key']:'This value is unavailable in the lookup. Search and select again.'})
                canonical=list(dict.fromkeys(found[v.lower()] for v in expected))
                inputs[field['key']]=canonical if field['type']=='lookup_multi' else canonical[0]
        validate_request(f,inputs)
        validate_field_inputs(f,inputs)
        return inputs

    def list_submissions(self,actor,body):
        if set(body)-{'workspace_id','mine'} or not isinstance(body.get('workspace_id','*'),str) or type(body.get('mine',False)) is not bool: raise Error(400,'Invalid submission filter.')
        workspace=body.get('workspace_id','*'); out=[]
        for r in self.store.list('submissions'):
            if workspace!='*' and r['form'].get('workspace_id',DEFAULT_WORKSPACE)!=workspace: continue
            if body.get('mine') and r['actor']['username']!=actor['username']: continue
            try: out.append(self.receipt(r,actor))
            except Error: pass
        return sorted(out,key=lambda x:x['submitted_at'],reverse=True)[:200]

    def records(self,form_id):
        return sorted(self.store.list('forms',{'id':form_id}),key=lambda f:f['revision'])

    def latest(self,form_id):
        records=self.records(form_id)
        if not records: raise Error(404,'Form not found.')
        return records[-1]

    def published(self,form_id):
        records=self.records(form_id)
        if not records or records[-1]['state'] in ['archived','deleted']: raise Error(404,'This form is not available.')
        withdrawn=max([f['revision'] for f in records if f['state'] in ['archived','deleted']] or [0])
        pubs=[f for f in records if f['state']=='published' and f['revision']>withdrawn]
        if not pubs: raise Error(404,'This form is not published.')
        return pubs[-1]

    def form_editable(self,actor,form):
        return capable(actor,'edit') and allowed(actor,form,'edit') and self.workspace_allowed(actor,form.get('workspace_id',DEFAULT_WORKSPACE))

    def list_forms(self,actor,editing=False):
        require(actor,'edit' if editing else 'use')
        grouped={}
        for f in self.store.list('forms'): grouped.setdefault(f['id'],[]).append(f)
        out=[]
        for records in grouped.values():
            records.sort(key=lambda f:f['revision']); latest=records[-1]
            if editing:
                if self.form_editable(actor,latest): out.append(self.editable_validation(latest))
            elif latest['state'] not in ['archived','deleted']:
                withdrawn=max([f['revision'] for f in records if f['state'] in ['archived','deleted']] or [0])
                pubs=[f for f in records if f['state']=='published' and f['revision']>withdrawn]
                if pubs and allowed(actor,pubs[-1],'view') and self.workspace_allowed(actor,pubs[-1].get('workspace_id',DEFAULT_WORKSPACE)): out.append(pubs[-1])
        return sorted(out,key=lambda f:f['title'])

    def save_form(self,actor,body,publish=False):
        require(actor,'edit')
        if publish: require(actor,'publish')
        if set(body)-{'form','expected_revision'}: raise Error(400,'Unknown form update properties.')
        raw=clone(body.get('form'))
        if isinstance(raw,dict) and 'access' not in raw:
            workspace=self.workspace_records().get(raw.get('workspace_id',DEFAULT_WORKSPACE),{})
            if workspace.get('default_access'): raw['access']=clone(workspace['default_access'])
        f=validate_definition(raw,self.roles())
        if not self.workspace_allowed(actor,f['workspace_id']): raise Error(403,'This workspace is unavailable to your roles.')
        f=self.editable_validation(f)
        self.attach_validation(actor,f)
        if not allowed(actor,f,'edit'): raise Error(403,'You must retain edit access to this form.')
        records=self.records(f['id']); current=records[-1] if records else None
        workspace=self.workspace_records()[f['workspace_id']]
        if not current and workspace.get('role_groups') and not capable(actor,'admin') and not set(workspace['role_groups']['admin'])&set(actor['roles']): raise Error(403,'Only workspace admins can create forms in this workspace.')
        if current and current['state']=='deleted': raise Error(409,'Restore this form from Trash before editing.')
        if current and current.get('workspace_id',DEFAULT_WORKSPACE)!=f['workspace_id'] and not capable(actor,'admin'): raise Error(403,'Only an app administrator may move a form between workspaces.')
        if current and not self.form_editable(actor,current): raise Error(403,'You cannot edit this form.')
        revision=current['revision'] if current else 0
        if body.get('expected_revision')!=revision: raise Conflict()
        if publish:
            s=self.settings()
            published=[r for r in records if r['state']=='published']
            prior_label=published[-1]['mapping']['label'] if published else None
            if not f['mapping']['label'].startswith(s.get('label_prefix','')) and prior_label!=f['mapping']['label']: raise Error(400,'Choose a SOAR label beginning with the configured prefix: '+s['label_prefix'])
            if not self.demo:
                if not s.get('soar_url') or not s.get('secret_ref'): raise Error(409,'Configure and test the SOAR connection before publishing.')
                labels=self.remote_factory(s,self.secrets.get(s['secret_ref'])).labels()
                if f['mapping']['label'] not in labels: raise Error(400,'The configured label does not exist in SOAR or is not visible to the integration identity.')
        version=max([r.get('version',0) for r in records if r['state']=='published'] or [0])+(1 if publish else 0)
        f.update(_key=f['id']+':'+str(revision+1).zfill(8),revision=revision+1,version=version,state='published' if publish else 'draft',updated_at=utcnow(),updated_by=actor['username'])
        self.store.insert('forms',f)  # Immutable unique revision is the cluster-wide compare-and-set.
        self.audit(actor,'form.published' if publish else 'form.saved',f['id'])
        return f

    def archive(self,actor,form_id,revision):
        require(actor,'publish'); f=self.latest(form_id)
        if not self.form_editable(actor,f): raise Error(403,'You cannot archive this form.')
        if f['state']=='deleted': raise Error(409,'Restore this form from Trash first.')
        if revision!=f['revision']: raise Conflict()
        f=clone(f); f.update(revision=revision+1,_key=form_id+':'+str(revision+1).zfill(8),state='archived',updated_at=utcnow(),updated_by=actor['username'])
        self.store.insert('forms',f); self.audit(actor,'form.archived',form_id); return f

    def delete_form(self,actor,form_id,revision,restore=False):
        require(actor,'publish'); f=self.latest(form_id)
        if not self.form_editable(actor,f): raise Error(403,'You cannot change this form.')
        if type(revision) is not int or revision!=f['revision']: raise Conflict()
        if (f['state']=='deleted')!=restore: raise Error(409,'The form is already deleted.' if not restore else 'This form is not in Trash.')
        f=clone(f)
        # Restored forms stay archived until explicitly republished.
        f.update(revision=revision+1,_key=form_id+':'+str(revision+1).zfill(8),state='archived' if restore else 'deleted',updated_at=utcnow(),updated_by=actor['username'])
        self.store.insert('forms',f); self.audit(actor,'form.restored' if restore else 'form.deleted',form_id)
        return {'id':form_id,'state':f['state']}

    def favorites(self,actor):
        visible={f['id'] for f in self.list_forms(actor)}
        return [r['form_id'] for r in self.store.list('favorites',{'username':actor['username']}) if r['form_id'] in visible]

    def set_favorite(self,actor,body):
        if set(body)!={'form_id','favorite'} or not isinstance(body['form_id'],str) or type(body['favorite']) is not bool: raise Error(400,'Invalid favorite update.')
        f=self.published(body['form_id'])
        if not allowed(actor,f,'view') or not self.workspace_allowed(actor,f.get('workspace_id',DEFAULT_WORKSPACE)): raise Error(404,'Form not found.')
        key=digest({'username':actor['username'],'form_id':f['id']})
        if body['favorite']:
            try: self.store.insert('favorites',{'_key':key,'username':actor['username'],'form_id':f['id']})
            except Conflict: pass
        else: self.store.delete('favorites',key)
        return self.favorites(actor)

    def save_settings(self,actor,body):
        require(actor,'admin')
        allowed_keys=set(DEFAULT_SETTINGS)|{'token'}
        if set(body)-allowed_keys: raise Error(400,'Unknown connection settings.')
        from .soar import validate_url, validate_ca
        s={k:body.get(k,DEFAULT_SETTINGS[k]) for k in DEFAULT_SETTINGS}
        s['soar_url']=validate_url(s['soar_url'])
        validate_ca(s['ca_pem'],s['ignore_certificate_errors'])
        if not isinstance(s['instance_name'],str) or not 1<=len(s['instance_name'])<=120: raise Error(400,'Enter an instance name.')
        if not isinstance(s['label_prefix'],str) or not re.fullmatch(r'[a-zA-Z0-9_-]{0,64}',s['label_prefix']): raise Error(400,'Use up to 64 letters, numbers, underscores or hyphens for the label prefix.')
        if s['request_timeout'] not in [5,10,15,20,30]: raise Error(400,'Choose a supported timeout.')
        if s['asset_id'] is not None and (type(s['asset_id'])!=int or s['asset_id']<=0): raise Error(400,'Source asset ID must be a positive integer.')
        current=self.settings()
        if body.get('revision')!=current['revision']: raise Conflict()
        token=body.get('token')
        if token is not None and (not isinstance(token,str) or len(token)>4096 or any(c in token for c in '\r\n')): raise Error(400,'Invalid token.')
        secret_ref=current.get('secret_ref')
        if token:
            secret_ref=str(uuid.uuid4()); self.secrets.put(secret_ref,token)
        if not secret_ref and not self.demo: raise Error(400,'A SOAR automation token is required.')
        s.update(secret_ref=secret_ref,revision=current['revision']+1,_key=str(current['revision']+1).zfill(8))
        self.store.insert('settings',s); self.audit(actor,'settings.updated',str(s['revision'])); return self.public_settings()

    def connection_test(self,actor):
        require(actor,'admin'); s=self.settings()
        if not self.demo and not s.get('secret_ref'): raise Error(409,'Save the connection first.')
        labels=self.remote_factory(s,self.secrets.get(s.get('secret_ref'))).labels()
        unavailable=[f['title']+' → '+f['mapping']['label'] for f in self.list_forms(actor) if f['mapping']['label'] not in labels]
        message='Demo connection is ready.' if self.demo else 'Connected to SOAR. Read access verified. To test event creation, publish a form with an available label and automation disabled, then submit it.'
        if unavailable: message+=' Published forms with unavailable labels: '+', '.join(unavailable[:5])+'.'
        return {'ok':True,'labels':labels,'demo':self.demo,'message':message}

    def receipt(self,record,actor):
        own=record['actor']['username']==actor['username']
        team=record['form'].get('access',{}).get('team_roles',[])
        if not (own or capable(actor,'admin') or (capable(actor,'read_team') and bool(set(team)&set(actor['roles'])) and self.workspace_allowed(actor,record['form'].get('workspace_id',DEFAULT_WORKSPACE),active=False))): raise Error(404,'Submission not found.')
        return {k:v for k,v in record.items() if k not in ['_key','fingerprint','connection','actor','container_payload','artifact_payload']}|{'submitted_by':record['actor']['username'],'approval':clone(record['container_payload']['data']['actionstack']['policy'])}

    def submission_fingerprint(self,actor,body):
        require(actor,'submit')
        if set(body)!={'value'} or not isinstance(body['value'],str) or len(body['value'].encode('utf-8'))>256*1024:
            raise Error(400,'Invalid fingerprint request.')
        try: material=json.loads(body['value'])
        except ValueError: raise Error(400,'Invalid fingerprint request.')
        if not isinstance(material,dict) or set(material)!={'user','form','version','values'} or material['user']!=actor['username'] or not isinstance(material['form'],str) or type(material['version']) is not int or not isinstance(material['values'],dict):
            raise Error(400,'Invalid fingerprint request.')
        form=self.published(material['form'])
        if not self.workspace_allowed(actor,form.get('workspace_id',DEFAULT_WORKSPACE)) or not allowed(actor,form,'view') or not allowed(actor,form,'submit'):
            raise Error(403,'This form is not available to your roles.')
        # Hash the original UTF-8 string, matching SubtleCrypto exactly (including
        # property order and Unicode). submit() still performs full validation.
        return {'fingerprint':hashlib.sha256(body['value'].encode('utf-8')).hexdigest()}

    def run_lookup(self,actor,config,term,exact=False):
        lookup_spl(config,term,exact)
        if not self.lookup: raise Error(503,'Lookup search is not configured on this search head.')
        minute=int(time.time()//60)
        bucket='lookup:'+digest(actor['username'])
        # Avoid an HTTP conflict for every prior lookup this minute. The unique
        # insert still arbitrates concurrent callers and pre-upgrade records.
        occupied={r['_key'] for r in self.store.list('ratelimits',{'minute':minute,'bucket':bucket})}
        for slot in range(60):
            key=bucket+':'+str(minute)+':'+str(slot)
            if key in occupied: continue
            try:
                self.store.insert('ratelimits',{'_key':key,'minute':minute,'bucket':bucket})
                break
            except Conflict: pass
        else: raise Error(429,'Lookup search limit reached. Pause briefly before searching again.')
        return self.lookup.search(config,term,exact)

    def lookup_options(self,actor,body,preview=False):
        require(actor,'edit' if preview else 'submit')
        if preview:
            if set(body)!={'config','term'}: raise Error(400,'Invalid lookup preview.')
            config=body['config']
        else:
            if set(body)!={'form_id','form_version','field','term'}: raise Error(400,'Invalid lookup request.')
            if not isinstance(body['form_id'],str) or type(body['form_version']) is not int or not isinstance(body['field'],str): raise Error(400,'Invalid form reference.')
            f=self.published(body['form_id'])
            if not self.workspace_allowed(actor,f.get('workspace_id',DEFAULT_WORKSPACE)) or not allowed(actor,f,'view') or not allowed(actor,f,'submit'): raise Error(403,'This form is unavailable to your roles.')
            if body['form_version']!=f['version']: raise Conflict('This form changed. Reload before searching.')
            field=next((x for x in f['fields'] if x['key']==body['field'] and x['type'] in ['lookup','lookup_multi']),None)
            if not field: raise Error(400,'Lookup field not found.')
            config=field['lookup']
        validate_source(config)
        term=body['term']
        if isinstance(term,list): return self.run_lookup(actor,config,term,exact=True)
        if not isinstance(term,str): raise Error(400,'Enter a search term.')
        if len(term)<config['min_chars']: return {'options':[],'more':False}
        return self.run_lookup(actor,config,term)

    def activity(self,actor,sid,summary=False):
        require(actor,'use')
        record=self.store.get('submissions',sid)
        if not record: raise Error(404,'Submission not found.')
        self.receipt(record,actor)  # Enforce the same owner/team/admin receipt ACL.
        if not record.get('container_id'): raise Error(409,'SOAR event delivery is still pending.')
        # Separate read budget, shared across search heads; never consumes delivery slots.
        minute=int(time.time()//60)
        bucket=('activity-summary:' if summary else 'activity:')+digest(actor['username'])
        used={r['_key'] for r in self.store.list('ratelimits',{'minute':minute,'bucket':bucket})}
        for slot in range(60 if summary else 20):
            key=bucket+':'+str(minute)+':'+str(slot)
            if key in used: continue
            try:
                self.store.insert('ratelimits',{'_key':key,'minute':minute,'bucket':bucket})
                break
            except Conflict: pass
        else: raise Error(429,'Status refresh limit reached. Wait a minute and refresh again.')
        s=record['connection']
        remote=self.remote_factory(s,self.secrets.get(s.get('secret_ref')))
        if summary:
            remote.timeout=min(getattr(remote,'timeout',5),5)
            result=remote.activity(record['container_id'],details=False)
            result={key:{k:group.get(k) for k in ['total','counts','truncated','error']} for key,group in result.items() if key in ['playbooks','actions']}
        else: result=remote.activity(record['container_id'])
        return dict(result,checked_at=utcnow(),automation_enabled=bool(record['artifact_payload'].get('run_automation')),demo=self.demo)

    def submit(self,actor,body):
        require(actor,'submit')
        if set(body)!={'form_id','form_version','inputs','idempotency_key'}: raise Error(400,'Invalid submission properties.')
        if not isinstance(body['form_id'],str) or type(body['form_version']) is not int: raise Error(400,'Invalid form reference.')
        key=body['idempotency_key']
        if not isinstance(key,str) or not 8<=len(key)<=128: raise Error(400,'A valid idempotency key is required.')
        f=self.published(body['form_id'])
        if not self.workspace_allowed(actor,f.get('workspace_id',DEFAULT_WORKSPACE)) or not allowed(actor,f,'view') or not allowed(actor,f,'submit'): raise Error(403,'This form is not available to your roles.')
        # Reusing a key after a new version is published must return its original receipt.
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,APP+':'+actor['username']+':'+body['form_id']+':'+key))
        fingerprint=digest({'form_version':body['form_version'],'inputs':body['inputs']})
        existing=self.store.get('submissions',sid)
        if existing:
            if existing['fingerprint']!=fingerprint: raise Conflict('This submission key was already used for different data.')
            return self.receipt(existing,actor)
        if body['form_version']!=f['version']: raise Conflict('This form has a newer version. Refresh before submitting.')
        inputs=self.checked_inputs(actor,f,body['inputs'])
        settings=self.settings()
        at=utcnow(); container,artifact=event_payload(f,actor,inputs,sid,at,settings)
        record={'_key':sid,'id':sid,'form_id':f['id'],'form_title':f['title'],'form_version':f['version'],'form':f,'inputs':inputs,'actor':clone(actor),'fingerprint':fingerprint,'submitted_at':at,'updated_at':at,'status':'pending','attempts':0,'container_id':None,'artifact_id':None,'event_url':None,'error':None,'connection':clone(settings),'container_payload':container,'artifact_payload':artifact,'demo':self.demo}
        # Actor capabilities are not part of the event or receipt; record attribution only.
        record['actor']={k:v for k,v in record['actor'].items() if k!='capabilities'}
        try: self.store.insert('submissions',record)
        except Conflict:
            existing=self.store.get('submissions',sid)
            if not existing or existing['fingerprint']!=fingerprint: raise Conflict()
            return self.receipt(existing,actor)
        self.audit(actor,'submission.accepted',sid)
        return self.deliver(actor,sid)

    def deliver(self,actor,sid):
        require(actor,'submit')
        record=self.store.get('submissions',sid)
        if not record: raise Error(404,'Submission not found.')
        self.receipt(record,actor)
        if record['status']=='submitted': return self.receipt(record,actor)
        current=self.published(record['form_id'])
        if not self.workspace_allowed(actor,current.get('workspace_id',DEFAULT_WORKSPACE)) or not allowed(actor,current,'view') or not allowed(actor,current,'submit'): raise Error(403,'Current form permissions do not allow delivery.')
        if record['actor']['username']!=actor['username']:
            raise Error(403,'Only the original requester may retry. Administrators can reconcile interrupted deliveries using the runbook.')
        with self.lock('delivery:'+sid,actor):
            record=self.store.get('submissions',sid)
            if record['status']=='submitted': return self.receipt(record,actor)
            self.delivery_budget(actor)
            record.update(status='submitting',attempts=record['attempts']+1,updated_at=utcnow(),error=None)
            self.store.put('submissions',record)
            try:
                s=record['connection']
                # A request accepted before connection setup may bind once; existing remote IDs pin the destination.
                if not s.get('soar_url') and not record['container_id']:
                    s=self.settings(); record['connection']=clone(s)
                if not self.demo and (not s.get('soar_url') or not s.get('secret_ref')): raise Error(409,'SOAR connection is not configured. An administrator can configure it, then you can retry.')
                remote=self.remote_factory(s,self.secrets.get(s.get('secret_ref')))
                for stage in ['container','artifact']:
                    id_field=stage+'_id'
                    if record[id_field]: continue
                    payload=clone(record[stage+'_payload'])
                    if stage=='artifact': payload['container_id']=record['container_id']
                    record[id_field]=remote.ensure(stage,payload)
                    record['updated_at']=utcnow(); self.store.put('submissions',record)
                record.update(status='submitted',error=None,event_url=(s.get('soar_url','').rstrip('/')+'/mission/'+str(record['container_id'])) if not self.demo else None)
            except Error as exc:
                record.update(status='needs_attention' if exc.status in [502,503,504] else 'failed',error=exc.message)
            except Exception:
                record.update(status='needs_attention',error='Delivery could not be confirmed. Retry will reconcile the existing SOAR event before continuing.')
            record['updated_at']=utcnow(); self.store.put('submissions',record)
            self.audit(actor,'submission.'+record['status'],sid)
        return self.receipt(record,actor)

    def dispatch(self,actor,method,path,body=None):
        require(actor,'use'); body=body or {}
        # Interactive reads must not scan/migrate app configuration on every keystroke.
        # Context/setup and edit routes initialize it before these reads are available.
        if path not in ['/lookups/options','/admin/lookups/preview'] and not path.endswith(('/activity','/activity-summary')): self.bootstrap()
        parts=path.strip('/').split('/')
        if path=='/context' and method=='GET':
            ready=bool(self.settings().get('secret_ref')) or self.demo
            return dict(actor,demo=self.demo,roles_available=self.roles() if capable(actor,'edit') or capable(actor,'admin') else [],connection_ready=ready,setup_required=not self.workspace_records() or not ready,can_create_roles=bool(self.role_manager) and (self.demo or bool(set(actor['capabilities'])&{'edit_roles','edit_roles_grantable'})))
        if path=='/preferences' and method in ['GET','POST']: return self.preferences(actor,body if method=='POST' else None)
        if path=='/admin/soar-labels' and method=='GET': return self.available_labels(actor)
        if path=='/admin/forms/validate' and method=='POST': return self.preview_validation(actor,body)
        if path=='/submission-fingerprint' and method=='POST': return self.submission_fingerprint(actor,body)
        if path=='/workspaces' and method=='GET': return self.list_workspaces(actor)
        if path=='/admin/workspaces' and method=='GET': return self.list_workspaces(actor,True)
        if path=='/admin/workspaces/save' and method=='POST': return self.save_workspace(actor,body)
        if path=='/validation-policies' and method=='GET': return [public_policy(p) for p in self.validation_policies(actor)]
        if path=='/admin/validation-policies' and method=='GET': return [public_policy(p) for p in self.validation_policies(actor,True)]
        if path=='/admin/validation-policies/save' and method=='POST': return public_policy(self.save_validation_policy(actor,body))
        if path=='/lookups/options' and method=='POST': return self.lookup_options(actor,body)
        if path=='/admin/lookups/preview' and method=='POST': return self.lookup_options(actor,body,True)
        if path=='/favorites':
            if method=='GET': return self.favorites(actor)
            if method=='POST': return self.set_favorite(actor,body)
        if len(parts)==4 and parts[:2]==['admin','forms'] and parts[3] in ['delete','restore'] and method=='POST': return self.delete_form(actor,parts[2],body.get('expected_revision'),parts[3]=='restore')
        if path=='/forms' and method=='GET': return self.list_forms(actor)
        if path=='/audit' and method=='GET':
            require(actor,'audit')
            return sorted(self.store.list('audit'),key=lambda x:x['at'],reverse=True)[:1000]
        if path=='/admin/forms' and method=='GET': return [inline_form(f) for f in self.list_forms(actor,True)]
        if path in ['/admin/forms/save','/admin/forms/publish'] and method=='POST': return self.save_form(actor,body,path.endswith('publish'))
        if len(parts)==4 and parts[:2]==['admin','forms'] and parts[3]=='archive' and method=='POST': return self.archive(actor,parts[2],body.get('expected_revision'))
        if len(parts)==4 and parts[:2]==['admin','forms'] and parts[3]=='versions' and method=='GET':
            require(actor,'edit')
            if not self.form_editable(actor,self.latest(parts[2])): raise Error(403,'You cannot edit this form.')
            return [inline_form(self.editable_validation(f)) for f in self.records(parts[2])]
        if path=='/settings':
            require(actor,'admin')
            if method=='GET': return self.public_settings()
            if method=='POST': return self.save_settings(actor,body)
        if path=='/settings/test' and method=='POST': return self.connection_test(actor)
        if path=='/submissions' and method=='POST': return self.submit(actor,body)
        if path=='/submissions/list' and method=='POST': return self.list_submissions(actor,body)
        if path=='/submissions' and method=='GET': return self.list_submissions(actor,{})
        if len(parts)==2 and parts[0]=='submissions' and method=='GET':
            r=self.store.get('submissions',parts[1])
            if not r: raise Error(404,'Submission not found.')
            return self.receipt(r,actor)
        if len(parts)==3 and parts[0]=='submissions' and parts[2] in ['activity','activity-summary'] and method=='GET': return self.activity(actor,parts[1],parts[2]=='activity-summary')
        if len(parts)==3 and parts[0]=='submissions' and parts[2]=='retry' and method=='POST': return self.deliver(actor,parts[1])
        raise Error(404,'Endpoint not found.')

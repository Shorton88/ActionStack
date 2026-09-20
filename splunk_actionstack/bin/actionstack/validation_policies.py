"""Reusable declarative validation; published forms pin immutable rule snapshots."""
import math
import json
import re
import ipaddress
import subprocess
import sys
from pathlib import Path
from .core import Error, Conflict, KEY, SLUG, require, clone, utcnow, visible, digest, approval_rule, DURATIONS

def scalar(value):
    return (isinstance(value,(str,bool)) and (not isinstance(value,str) or len(value)<=200)) or (type(value) in [int,float] and math.isfinite(value))

def validate_rules(rules,fields=None):
    if not isinstance(rules,list) or not 0<=len(rules)<=64: raise Error(400,'Use at most 64 validation rules.')
    by_key={f['key']:f for f in fields} if fields is not None else None
    for r in rules:
        if not isinstance(r,dict) or set(r)-{'field','operator','value','message','when'} or not {'field','operator','message'}.issubset(r): raise Error(400,'Invalid validation rule.')
        if not isinstance(r['field'],str) or not KEY.fullmatch(r['field']) or r['operator'] not in ['required','equals','not_equals','min','max','regex','ip_address','domain','sha1','sha256']: raise Error(400,'Choose a valid validation field and check.')
        if not isinstance(r['message'],str) or not 1<=len(r['message'].strip())<=240: raise Error(400,'Each validation rule needs a message of up to 240 characters.')
        if r['operator'] in ['equals','not_equals','min','max'] and ('value' not in r or not scalar(r['value'])): raise Error(400,'The validation rule needs a text, boolean or finite numeric value.')
        if r['operator'] in ['min','max'] and type(r['value']) not in [int,float]: raise Error(400,'Minimum and maximum rules require a number.')
        if r['operator']=='regex':
            if not isinstance(r.get('value'),str) or not 1<=len(r['value'])<=512: raise Error(400,'Enter a regex pattern of 1–512 characters.')
            try: re.compile(r['value'])
            except (re.error,RecursionError,OverflowError): raise Error(400,'Invalid regex pattern for '+r['field']+'.')
        condition=r.get('when')
        if condition is not None and (not isinstance(condition,dict) or set(condition)!={'field','equals'} or not isinstance(condition['field'],str) or not KEY.fullmatch(condition['field']) or not scalar(condition['equals'])): raise Error(400,'Invalid validation condition.')
        if by_key is not None:
            f=by_key.get(r['field'])
            if not f or f['type']=='section': raise Error(400,'Validation policy references missing field: '+r['field'])
            if r['operator'] in ['min','max'] and f['type']!='number': raise Error(400,'Numeric validation requires a number field: '+r['field'])
            if r['operator'] in ['regex','ip_address','domain','sha1','sha256'] and f['type'] in ['number','checkbox','multiselect']: raise Error(400,'This validation requires a text field: '+r['field'])
            for field_key,value in ([(r['field'],r['value'])] if r['operator'] in ['equals','not_equals'] else [])+([(condition['field'],condition['equals'])] if condition else []):
                target=by_key.get(field_key)
                if not target or target['type'] in ['section','multiselect']: raise Error(400,'Validation comparisons require an existing scalar field: '+field_key)
                if target['type']=='number' and type(value) not in [int,float] or target['type']=='checkbox' and type(value) is not bool or target['type'] not in ['number','checkbox'] and not isinstance(value,str): raise Error(400,'Validation value type does not match field: '+field_key)
                if target['type'] in ['select','radio'] and value not in [o['value'] for o in target.get('options',[])]: raise Error(400,'Validation value is not a choice for field: '+field_key)

def equal(left,right):
    return left==right and ((type(left) in [int,float] and type(right) in [int,float]) or type(left) is type(right))

def regex_matches(jobs):
    if not jobs: return []
    try:
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('regex_worker.py'))],input=json.dumps(jobs),text=True,capture_output=True,timeout=1,check=True)
        values=json.loads(result.stdout)
        if not isinstance(values,list) or len(values)!=len(jobs) or any(type(v) is not bool for v in values): raise ValueError()
        return values
    except subprocess.TimeoutExpired: raise Error(400,'Regex validation exceeded its time limit. Ask an administrator to simplify the policy pattern.')
    except (OSError,subprocess.SubprocessError,ValueError): raise Error(503,'Regex validation is unavailable. No request was accepted.')

def validate_request(form,inputs):
    policy=form.get('validation_policy')
    if not policy: return
    errors={}; fields={f['key']:f for f in form['fields']}; regex_jobs=[]; regex_rules=[]; normalized={}
    for r in policy['rules']:
        condition=r.get('when')
        if condition and (condition['field'] not in inputs or not equal(inputs[condition['field']],condition['equals'])): continue
        if not visible(fields[r['field']],inputs): continue
        value=inputs.get(r['field']); op=r['operator']; expected=r.get('value')
        empty=value is None or value=='' or value==[]
        if op=='required': valid=not empty and value is not False
        elif empty: continue
        elif op=='equals': valid=equal(value,expected)
        elif op=='not_equals': valid=not equal(value,expected)
        elif op=='min': valid=type(value) in [int,float] and value>=expected
        elif op=='max': valid=type(value) in [int,float] and value<=expected
        elif op=='regex':
            if not isinstance(value,str) or len(value)>16000: valid=False
            else: regex_jobs.append([expected,value]); regex_rules.append(r); continue
        else:
            try:
                if not isinstance(value,str): raise ValueError()
                if op=='ip_address': normalized[r['field']]=str(ipaddress.ip_address(value))
                elif op=='domain':
                    domain=value.rstrip('.').encode('idna').decode('ascii').lower()
                    if len(domain)>253 or '.' not in domain or any(not re.fullmatch(r'(?!-)[a-z0-9-]{1,63}(?<!-)',part) for part in domain.split('.')): raise ValueError()
                    try: ipaddress.ip_address(domain)
                    except ValueError: pass
                    else: raise ValueError()
                    normalized[r['field']]=domain
                elif op in ['sha1','sha256']:
                    if not re.fullmatch('[a-fA-F0-9]{%d}'%({'sha1':40,'sha256':64}[op]),value): raise ValueError()
                    normalized[r['field']]=value.lower()
                else: raise ValueError()
                valid=True
            except (ValueError,UnicodeError): valid=False
        if not valid: errors[r['field']]=r['message']
    if errors: raise Error(400,'Check the highlighted fields.',errors)
    for r,valid in zip(regex_rules,regex_matches(regex_jobs)):
        if not valid: errors[r['field']]=r['message']
    if errors: raise Error(400,'Check the highlighted fields.',errors)
    inputs.update(normalized)

def block_policy():
    rules=[{'field':key,'operator':'required','message':'This field is required.'} for key in ['object_type','object_value','duration','reason']]
    rules.append({'field':'hash_type','operator':'required','message':'Choose a hash type.','when':{'field':'object_type','equals':'hash'}})
    for operator,field,value in [('ip_address','object_type','ip'),('domain','object_type','domain'),('sha1','hash_type','sha1'),('sha256','hash_type','sha256')]:
        rules.append({'field':'object_value','operator':operator,'message':'Enter a valid '+operator.replace('_',' ')+'.','when':{'field':field,'equals':value}})
    return {'id':'block-object-validation','name':'Block object validation','description':'Editable IP, domain and hash checks for the block-object form.','state':'active','rules':rules,'enrichment':'block_object'}

def public_policy(policy):
    p=clone(policy)
    p.pop('enrichment',None)
    p['rules']=[r for r in p['rules'] if r['operator']!='required']
    return p

def form_requirements(form):
    fields={f['key']:f for f in form['fields']}
    policy=form.get('validation_policy',{})
    if policy: validate_rules(policy.get('rules',[]),form['fields'])
    for rule in policy.get('rules',[]):
        if rule['operator']!='required' or rule['field'] not in fields: continue
        field=fields[rule['field']]
        if rule.get('when'):
            conditions=field.setdefault('required_when',[])
            if rule['when'] not in conditions: conditions.append(clone(rule['when']))
        else: field['required']=True
    if policy: policy['rules']=[r for r in policy['rules'] if r['operator']!='required']
    return form

class ValidationPolicies:
    def seed_validation_policy(self,policy):
        rows=self.store.list('validation_policies',{'id':policy['id']})
        if rows: return max(rows,key=lambda p:p['revision'])
        p=clone(policy); p.update(revision=1,_key=p['id']+':00000001',updated_at=utcnow(),updated_by='system')
        try: self.store.insert('validation_policies',p)
        except Conflict: return max(self.store.list('validation_policies',{'id':p['id']}),key=lambda p:p['revision'])
        return p

    def editable_validation(self,form):
        f=clone(form)
        if f['mapping'].get('policy')!='block_object': return form_requirements(f)
        original=approval_rule(f)
        p=self.seed_validation_policy(block_policy())
        if f.get('validation_policy_id'):
            prior=f.get('validation_policy')
            if not prior:
                candidates=self.store.list('validation_policies',{'id':f['validation_policy_id']})
                if not candidates: raise Error(400,'Choose an active validation policy.')
                prior=max(candidates,key=lambda p:p['revision'])
            combined=block_policy()
            combined.update(id='migrated-'+digest({'form':f['id'],'policy':prior})[:24],name=('Block checks · '+f['title'])[:80],description='Migrated block checks plus the form’s saved custom rules.',rules=block_policy()['rules']+clone(prior['rules']))
            p=self.seed_validation_policy(combined)
        f['mapping'].pop('policy',None)
        f['mapping']['approval']=clone(original)
        f['validation_policy_id']=p['id']
        f['validation_policy']={k:clone(p[k]) for k in ['id','name','revision','rules','enrichment'] if k in p}
        return form_requirements(f)

    def validation_policies(self,actor,admin=False):
        require(actor,'admin' if admin else 'edit')
        latest={}
        for p in self.store.list('validation_policies'):
            if p['id'] not in latest or p['revision']>latest[p['id']]['revision']: latest[p['id']]=p
        return sorted([clone(p) for p in latest.values() if admin or p['state']=='active'],key=lambda p:p['name'].lower())

    def save_validation_policy(self,actor,body):
        require(actor,'admin')
        if set(body)!={'policy','expected_revision'}: raise Error(400,'Invalid validation policy update.')
        p=body['policy']
        if not isinstance(p,dict) or (set(p)-{'id','name','description','rules','state','enrichment'} or not {'id','name','description','rules','state'}.issubset(p)) or not isinstance(p['id'],str) or not SLUG.fullmatch(p['id']): raise Error(400,'Invalid validation policy.')
        if not isinstance(p['name'],str) or not 1<=len(p['name'].strip())<=80 or not isinstance(p['description'],str) or len(p['description'])>500 or p['state'] not in ['active','archived']: raise Error(400,'Enter a policy name, description and state.')
        if p.get('enrichment','none') not in ['none','block_object']: raise Error(400,'Choose a supported metadata option.')
        validate_rules(p['rules'])
        current=next((x for x in self.validation_policies(actor,True) if x['id']==p['id']),None)
        revision=current['revision'] if current else 0
        p=clone(p)
        if current and 'enrichment' not in p and current.get('enrichment'): p['enrichment']=current['enrichment']
        if type(body['expected_revision']) is not int or body['expected_revision']!=revision: raise Conflict()
        p=clone(p); p.update(name=p['name'].strip(),revision=revision+1,_key=p['id']+':'+str(revision+1).zfill(8),updated_at=utcnow(),updated_by=actor['username'])
        self.store.insert('validation_policies',p); self.audit(actor,'validation_policy.updated',p['id']); return p

    def attach_validation(self,actor,form):
        key=form.get('validation_policy_id','')
        form.pop('validation_policy',None)
        if not key: return
        p=next((p for p in self.validation_policies(actor) if p['id']==key),None)
        if not p: raise Error(400,'Choose an active validation policy.')
        p=clone(p)
        p['rules']=[r for r in p['rules'] if r['operator']!='required']
        fields={f['key']:f for f in form['fields']}
        for r in p['rules']:
            target=fields.get(r['field'],{})
            if r['operator'] in ['equals','not_equals'] and isinstance(r.get('value'),str):
                if target.get('type')=='number':
                    try: r['value']=float(r['value'])
                    except ValueError: raise Error(400,'Enter a numeric validation value for '+r['field']+'.')
                elif target.get('type')=='checkbox':
                    if r['value'].lower() not in ['true','false']: raise Error(400,'Enter true or false for '+r['field']+'.')
                    r['value']=r['value'].lower()=='true'
        validate_rules(p['rules'],form['fields'])
        form['validation_policy']={k:clone(p[k]) for k in ['id','name','revision','rules','enrichment'] if k in p}
        form_requirements(form)

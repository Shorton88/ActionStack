"""Framework-independent form validation, authorization and event contracts."""
import copy
import hashlib
import ipaddress
import json
import math
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

APP = 'splunk_actionstack'
PREFIX = 'actionstack_'
DURATIONS = {'4h': 14400, '1d': 86400, '30d': 2592000, '60d': 5184000, '90d': 7776000, 'forever': None}
TYPES = {'text', 'textarea', 'number', 'email', 'url', 'date', 'datetime', 'select', 'multiselect', 'radio', 'checkbox', 'section', 'lookup', 'text_list', 'lookup_multi'}
KEY = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')
RESERVED_FIELDS = {'submission_id','form_id','form_version','submitted_at','submitted_by','approval_required','approval_policy','permanent'}
SLUG = re.compile(r'^[a-z][a-z0-9-]{0,63}$')

class Error(Exception):
    def __init__(self, status, message, fields=None):
        super().__init__(message)
        self.status, self.message, self.fields = status, message, fields or {}

class Conflict(Error):
    def __init__(self, message='This record changed. Refresh before continuing.'):
        super().__init__(409, message)

def utcnow():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

def clone(value):
    return copy.deepcopy(value)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def capable(actor, capability):
    caps = actor.get('capabilities', [])
    return PREFIX + 'admin' in caps or PREFIX + capability in caps

def require(actor, capability):
    if not capable(actor, capability):
        raise Error(403, 'Your Splunk roles do not permit this action.')

def allowed(actor, form, action):
    if capable(actor, 'admin'):
        return True
    roles = form.get('access', {}).get(action + '_roles', [])
    return not roles or bool(set(roles).intersection(actor.get('roles', [])))

def visible(field, values):
    rule = field.get('show_when')
    return not rule or values.get(rule['field']) == rule['equals']

def seed_form():
    return {
        'id': 'block-object', 'title': 'Block an object', 'description': 'Submit an IP address, domain, or file hash to your security automation.',
        'category': 'Threat response', 'icon': 'shield', 'owner': 'Security operations', 'accent': 'violet',
        'intro': 'Provide the object and how long you would like it blocked. Your request will be delivered to Splunk SOAR.',
        'fields': [
            {'key': 'object_type', 'type': 'select', 'label': 'Object type', 'required': True, 'default': 'ip', 'options': [{'value': 'ip', 'label': 'IP address'}, {'value': 'domain', 'label': 'Domain'}, {'value': 'hash', 'label': 'File hash'}]},
            {'key': 'hash_type', 'type': 'select', 'label': 'Hash type', 'required': True, 'options': [{'value': 'sha1', 'label': 'SHA-1'}, {'value': 'sha256', 'label': 'SHA-256'}], 'show_when': {'field': 'object_type', 'equals': 'hash'}},
            {'key': 'object_value', 'type': 'text', 'label': 'Object value', 'required': True, 'placeholder': 'Enter an IP address, domain, or hash', 'help': 'One object per request. Values are validated before submission.', 'max_length': 253},
            {'key': 'duration', 'type': 'select', 'label': 'Block duration', 'required': True, 'default': '4h', 'options': [{'value': k, 'label': v} for k, v in [('4h','4 hours'),('1d','1 day'),('30d','30 days'),('60d','60 days'),('90d','90 days'),('forever','Forever')]]},
            {'key': 'reason', 'type': 'textarea', 'label': 'Reason for blocking', 'required': True, 'placeholder': 'Add context for the team handling this request…', 'max_length': 4000},
            {'key': 'ticket_reference', 'type': 'text', 'label': 'Ticket or reference', 'required': False, 'placeholder': 'e.g. INC-1042', 'max_length': 200},
        ],
        'mapping': {'label': 'automation_requests', 'tags': ['automation:block_object', 'source:splunk_actionstack'], 'severity': 'low', 'sensitivity': 'amber', 'run_automation': False, 'policy': 'block_object', 'title_prefix': 'Block object request'},
        'access': {'view_roles': [], 'submit_roles': [], 'edit_roles': ['admin'], 'team_roles': []},
    }

def validate_definition(raw, roles):
    if not isinstance(raw, dict):
        raise Error(400, 'A form definition must be an object.')
    allowed_keys = {'id','title','description','category','icon','owner','accent','intro','fields','mapping','access','workspace_id','validation_policy_id'}
    if set(raw) - allowed_keys:
        raise Error(400, 'Unknown form properties.')
    f = clone(raw)
    if not isinstance(f.get('id'), str) or not SLUG.fullmatch(f['id']):
        raise Error(400, 'Use a lowercase form ID with letters, numbers and hyphens.')
    for key, limit in [('title',120),('description',600),('category',80),('owner',120),('intro',2000)]:
        value = f.get(key, '')
        if not isinstance(value, str) or len(value) > limit or (key == 'title' and not value.strip()):
            raise Error(400, 'Invalid form ' + key + '.')
        f[key] = value.strip()
    f['icon'] = f.get('icon') if f.get('icon') in ['shield','workflow','search','file','globe','zap'] else 'workflow'
    f['accent'] = f.get('accent') if f.get('accent') in ['violet','cyan','rose','mint','amber','indigo','pearl','sunset'] else 'violet'
    f['workspace_id']=f.get('workspace_id','security')
    if not isinstance(f['workspace_id'],str) or not SLUG.fullmatch(f['workspace_id']): raise Error(400,'Choose a valid workspace.')
    if not isinstance(f.get('validation_policy_id',''),str) or (f.get('validation_policy_id') and not SLUG.fullmatch(f['validation_policy_id'])): raise Error(400,'Choose a valid validation policy.')
    fields = f.get('fields')
    if not isinstance(fields, list) or not 1 <= len(fields) <= 60:
        raise Error(400, 'Add between 1 and 60 fields.')
    keys = set()
    for field in fields:
        if not isinstance(field, dict) or set(field) - {'key','type','label','required','default','placeholder','help','options','show_when','min','max','min_length','max_length','cef_key','lookup','required_when','validation','collapsed'}:
            raise Error(400, 'Invalid field configuration.')
        key = field.get('key', '')
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in keys or key in RESERVED_FIELDS:
            raise Error(400, 'Field IDs must be unique identifiers using letters, numbers and underscores.')
        keys.add(key)
        if field.get('type') not in TYPES or not isinstance(field.get('label'), str) or not 1 <= len(field['label']) <= 150:
            raise Error(400, 'Every field needs a valid type and label.')
        if 'collapsed' in field and (field['type']!='section' or type(field['collapsed']) is not bool): raise Error(400,'Collapsed by default is a section option and must be true or false.')
        if field['type'] in ['lookup','lookup_multi']:
            from .lookups import validate_source
            validate_source(field.get('lookup'))
        elif 'lookup' in field: raise Error(400,'Lookup configuration belongs only on lookup fields.')
        for name in ['placeholder','help']:
            if not isinstance(field.get(name,''),str) or len(field.get(name,'')) > 2000:
                raise Error(400, 'Invalid field help or placeholder.')
        if 'required' in field and not isinstance(field['required'],bool):
            raise Error(400, 'Required must be a boolean.')
        for name in ['min','max','min_length','max_length']:
            if name in field and (isinstance(field[name],bool) or not isinstance(field[name],(int,float)) or not math.isfinite(field[name])):
                raise Error(400, 'Field limits must be finite numbers.')
        if any(n in field and type(field[n]) is not int for n in ['min_length','max_length']) or field.get('min_length',0) < 0 or field.get('max_length',16000) > 16000 or field.get('min_length',0)>field.get('max_length',16000):
            raise Error(400, 'Invalid text length limits.')
        if field.get('min',-math.inf)>field.get('max',math.inf):
            raise Error(400, 'Minimum must be below maximum.')
        if field['type'] in ['select','radio','multiselect']:
            options=field.get('options',[])
            if not isinstance(options,list) or not 1<=len(options)<=100:
                raise Error(400, 'Choice fields need 1–100 options.')
            values=[]
            for option in options:
                if not isinstance(option,dict) or set(option)!={'value','label'} or not all(isinstance(option[n],str) and 0<len(option[n])<=200 for n in ['value','label']):
                    raise Error(400, 'Options require a value and label.')
                values.append(option['value'])
            if len(values)!=len(set(values)):
                raise Error(400, 'Option values must be unique.')
        if field.get('cef_key') and (not isinstance(field['cef_key'],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',field['cef_key']) or field['cef_key'].startswith('actionstack_')):
            raise Error(400, 'CEF mappings must be identifiers outside the reserved actionstack_ namespace.')
    if sum(f['type'] in ['lookup','lookup_multi'] for f in fields)>5: raise Error(400,'A form supports up to five lookup fields.')
    cef_keys = [field['cef_key'] for field in fields if field.get('cef_key')]
    if len(cef_keys) != len(set(cef_keys)):
        raise Error(400, 'Each CEF mapping must be unique.')
    for field in fields:
        if 'default' in field and field['default'] is not None:
            sample = clone(field)
            sample.pop('show_when', None)
            sample.pop('required_when',None)
            sample['required'] = False
            try: validate_inputs({'fields':[sample]}, {field['key']:field['default']})
            except Error: raise Error(400, 'Invalid default value for '+field['label']+'.')
    seen = set()
    for field in fields:
        rule=field.get('show_when')
        if rule:
            if not isinstance(rule,dict) or set(rule)!={'field','equals'} or rule['field'] not in seen or not isinstance(rule['equals'],(str,bool,int,float)):
                raise Error(400, 'Conditions must reference an earlier field and a scalar value.')
        seen.add(field['key'])
    m=f.setdefault('mapping',{})
    if not isinstance(m,dict) or set(m)-{'label','tags','severity','sensitivity','run_automation','policy','title_prefix','approval','enrichment'}:
        raise Error(400, 'Invalid SOAR mapping.')
    if not isinstance(m.get('label'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',m['label']):
        raise Error(400, 'Choose a valid SOAR label.')
    tags=m.get('tags',[])
    if not isinstance(tags,list) or len(tags)>20 or any(not isinstance(t,str) or not 1<=len(t)<=100 for t in tags):
        raise Error(400, 'Invalid SOAR tags.')
    if m.get('severity','low') not in ['low','medium','high'] or m.get('sensitivity','amber') not in ['white','green','amber','red']:
        raise Error(400, 'Invalid event severity or sensitivity.')
    if not isinstance(m.get('run_automation',False),bool) or m.get('policy','none') not in ['none','block_object']:
        raise Error(400, 'Invalid automation policy.')
    if not isinstance(m.get('title_prefix','Form submission'),str) or len(m.get('title_prefix',''))>100:
        raise Error(400, 'Invalid title prefix.')
    if m.get('policy')=='block_object':
        by_key={x['key']:x for x in fields}
        required={'object_type','object_value','hash_type','duration','reason'}
        if not required.issubset(keys):
            raise Error(400, 'Block object policy requires object_type, object_value, hash_type, duration and reason fields.')
        for name,options in [('object_type',{'ip','domain','hash'}),('hash_type',{'sha1','sha256'}),('duration',set(DURATIONS))]:
            if by_key[name]['type']!='select' or {o['value'] for o in by_key[name].get('options',[])}!=options:
                raise Error(400, 'The block object policy requires its standard choice fields.')
    for field in fields:
        if 'required_when' in field:
            conditions=field['required_when']
            if not isinstance(conditions,list) or len(conditions)>64: raise Error(400,'Invalid conditional requirement.')
            if conditions:
                from .validation_policies import validate_rules
                validate_rules([{'field':field['key'],'operator':'required','message':'Required','when':c} for c in conditions],fields)
    if m.get('enrichment','none') not in ['none','block_object']: raise Error(400,'Invalid metadata mapping.')
    from .field_validation import definition_checks
    definition_checks(fields)
    validate_approval(f)
    acl=f.setdefault('access',{})
    if not isinstance(acl,dict) or set(acl)-{'view_roles','submit_roles','edit_roles','team_roles'}:
        raise Error(400, 'Invalid form permissions.')
    for kind in ['view','submit','edit','team']:
        names=acl.setdefault(kind+'_roles',[])
        if not isinstance(names,list) or any(not isinstance(r,str) or r not in roles for r in names):
            raise Error(400, 'Select existing Splunk roles.')
    return f

def validate_inputs(form, incoming):
    if not isinstance(incoming,dict):
        raise Error(400,'Form inputs must be an object.')
    fields=form['fields']; known={f['key'] for f in fields if f['type']!='section'}
    if set(incoming)-known:
        raise Error(400,'Unexpected form fields.',{k:'Unknown field' for k in set(incoming)-known})
    output={}; errors={}
    for f in fields:
        k=f['key']; t=f['type']
        if t=='section':
            continue
        if not visible(f,output):
            if k in incoming and incoming[k] not in [None,'',[]]:
                errors[k]='This field is not applicable.'
            continue
        v=incoming.get(k, f.get('default',False if t=='checkbox' else None))
        if v is None or v=='' or v==[]:
            if f.get('required'):
                errors[k]='This field is required.'
            continue
        if t=='checkbox':
            if not isinstance(v,bool): errors[k]='Choose true or false.'
            elif f.get('required') and not v: errors[k]='Please select this checkbox.'
        elif t=='number':
            if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v): errors[k]='Enter a valid number.'
            elif v<f.get('min',-math.inf) or v>f.get('max',math.inf): errors[k]='Value is outside the allowed range.'
        elif t in ['text_list','lookup_multi']:
            if not isinstance(v,list) or len(v)>25 or any(not isinstance(x,str) for x in v):
                errors[k]='Enter up to 25 text values.'; continue
            v=[x.strip() if t=='text_list' else x for x in v]
            if any(not x.strip() or len(x)>200 for x in v) or len(set(v))!=len(v): errors[k]='Use unique, non-empty values of at most 200 characters.'
        elif t=='multiselect':
            options={o['value'] for o in f['options']}
            if not isinstance(v,list) or len(v)>100 or any(not isinstance(x,str) or x not in options for x in v) or len(set(v))!=len(v): errors[k]='Choose valid, unique options.'
        else:
            if not isinstance(v,str):
                errors[k]='Enter text.'; continue
            v=v if t=='lookup' else v.strip()
            if t=='lookup' and len(v)>200: errors[k]='Lookup values must be at most 200 characters.'
            if (f.get('required') and not v) or not f.get('min_length',0)<=len(v)<=f.get('max_length',16000): errors[k]='Check the text length.'
            elif t in ['select','radio'] and v not in {o['value'] for o in f['options']}: errors[k]='Choose an available option.'
            elif t=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',v): errors[k]='Enter a valid email address.'
            elif t=='url' and (urlparse(v).scheme not in ['http','https'] or not urlparse(v).hostname): errors[k]='Enter an HTTP or HTTPS URL.'
            elif t in ['date','datetime']:
                try:
                    if t=='date': datetime.strptime(v,'%Y-%m-%d')
                    else: datetime.fromisoformat(v.replace('Z','+00:00'))
                except ValueError: errors[k]='Enter a valid date.'
        output[k]=v
    if form.get('mapping',{}).get('policy')=='block_object':
        typ=output.get('object_type'); v=output.get('object_value','')
        try:
            if typ=='ip': output['object_value']=str(ipaddress.ip_address(v))
            elif typ=='domain':
                domain=v.rstrip('.').encode('idna').decode('ascii').lower()
                if len(domain)>253 or '.' not in domain or any(not re.fullmatch(r'(?!-)[a-z0-9-]{1,63}(?<!-)',part) for part in domain.split('.')): raise ValueError()
                try: ipaddress.ip_address(domain)
                except ValueError: pass
                else: raise ValueError()
                output['object_value']=domain
            elif typ=='hash':
                algorithm=output.get('hash_type'); size={'sha1':40,'sha256':64}.get(algorithm)
                if not size or not re.fullmatch('[a-fA-F0-9]{%d}'%size,v): raise ValueError()
                output['object_value']=v.lower()
            else: errors['object_type']='Choose an object type.'
        except (ValueError,UnicodeError,TypeError,AttributeError): errors['object_value']='Enter a valid value for the selected object type.'
        if output.get('duration') not in DURATIONS: errors['duration']='Choose a block duration.'
        if not output.get('reason'): errors['reason']='A reason is required.'
    for field in fields:
        if not visible(field,output): continue
        if any(c['field'] in output and (type(output[c['field']]) is type(c['equals']) or type(output[c['field']]) in [int,float] and type(c['equals']) in [int,float]) and output[c['field']]==c['equals'] for c in field.get('required_when',[])):
            value=output.get(field['key'])
            if value is None or value=='' or value==[] or value is False: errors[field['key']]='This field is required.'
    if errors: raise Error(400,'Check the highlighted fields.',errors)
    return output

def approval_rule(form):
    rule=form['mapping'].get('approval')
    if rule is not None: return rule
    if form['mapping'].get('policy')=='block_object':
        return {'mode':'conditional','conditions':[{'field':'duration','equals':'forever'}],'policy':'soar_playbook'}
    return {'mode':'never','conditions':[],'policy':'soar_playbook'}

def validate_approval(form):
    if 'approval' in form['mapping'] and form['mapping']['approval'] is None:
        raise Error(400,'Approval rules cannot be null.')
    rule=approval_rule(form)
    if not isinstance(rule,dict) or set(rule)!={'mode','conditions','policy'} or rule.get('mode') not in ['never','always','conditional'] or rule.get('policy') != 'soar_playbook':
        raise Error(400,'Choose a valid approval mode and workflow.')
    conditions=rule['conditions']
    if not isinstance(conditions,list) or len(conditions)>20 or (rule['mode']=='conditional' and not conditions) or (rule['mode']!='conditional' and conditions):
        raise Error(400,'Conditional approval needs 1–20 conditions; other modes must have no conditions.')
    fields={f['key']:f for f in form['fields']}
    for condition in conditions:
        if not isinstance(condition,dict) or set(condition)!={'field','equals'} or not isinstance(condition['field'],str):
            raise Error(400,'Invalid approval condition.')
        f=fields.get(condition['field']); value=condition['equals']
        if not f or f['type'] not in ['select','radio','checkbox']:
            raise Error(400,'Approval conditions must reference an existing dropdown, radio, or checkbox field.')
        if f['type']=='checkbox':
            if type(value) is not bool: raise Error(400,'Checkbox approval conditions require true or false.')
        elif not isinstance(value,str) or value not in [o['value'] for o in f.get('options',[])]:
            raise Error(400,'Approval condition value must be one of the field choices.')

def approval_policy(form, inputs):
    rule=approval_rule(form)
    required=rule['mode']=='always' or (rule['mode']=='conditional' and any(c['field'] in inputs and type(inputs[c['field']]) is type(c['equals']) and inputs[c['field']]==c['equals'] for c in rule['conditions']))
    return {'approval_required':required,'approval_policy':rule['policy'] if required else 'none'}

def event_payload(form, actor, inputs, submission_id, submitted_at, settings):
    m=form['mapping']; derived={}; policy=approval_policy(form, inputs)
    if m.get('policy')=='block_object' or m.get('enrichment')=='block_object' or form.get('validation_policy',{}).get('enrichment')=='block_object':
        if inputs.get('duration') in DURATIONS:
            permanent=inputs['duration']=='forever'
            derived={'requested_duration_seconds':DURATIONS[inputs['duration']],'permanent':permanent}
    who={k:clone(actor[k]) for k in ['username','roles','email','display_name'] if actor.get(k)}
    envelope={'contract_version':1,'submission_id':submission_id,'submitted_at':submitted_at,'source':{'app':APP,'instance':settings.get('instance_name','Splunk Enterprise')},'form':{'workspace_id':form.get('workspace_id','security'),'id':form['id'],'title':form['title'],'version':form['version'],'fields':{f['key']:f['label'] for f in form['fields'] if f['type']!='section'}},'submitted_by':who,'routing':{'mapping_version':form['revision'],'label':m['label'],'tags':m.get('tags',[])},'inputs':inputs,'derived':derived,'policy':policy}
    if form.get('validation_policy'): envelope['form']['validation_policy']={k:form['validation_policy'][k] for k in ['id','revision']}
    container={'name':m.get('title_prefix',form['title'])+' · '+submission_id,'label':m['label'],'container_type':'default','description':'Submitted through ActionStack by '+actor['username'],'severity':m.get('severity','low'),'sensitivity':m.get('sensitivity','amber'),'status':'new','source_data_identifier':'splunk_actionstack:'+submission_id,'tags':m.get('tags',[]),'run_automation':False,'data':{'actionstack':envelope}}
    if settings.get('asset_id'): container['asset_id']=int(settings['asset_id'])
    cef={'actionstack_submission_id':submission_id,'actionstack_form_id':form['id'],'actionstack_form_version':str(form['version']),'actionstack_submitted_at':submitted_at,'actionstack_submitted_by':actor['username'],'actionstack_approval_required':str(policy['approval_required']).lower(),'actionstack_approval_policy':policy['approval_policy']}
    for k,v in inputs.items():
        if isinstance(v,(str,int,float,bool)):
            cef['actionstack_'+k]=str(v).lower() if isinstance(v,bool) else str(v)
        elif isinstance(v,list): cef['actionstack_'+k]=json.dumps(v,ensure_ascii=False)
    for f in form['fields']:
        if f.get('cef_key') and f['key'] in inputs and isinstance(inputs[f['key']],(str,int,float,bool,list)): cef[f['cef_key']]=json.dumps(inputs[f['key']],ensure_ascii=False) if isinstance(inputs[f['key']],list) else str(inputs[f['key']])
    if m.get('policy')=='block_object' or m.get('enrichment')=='block_object' or form.get('validation_policy',{}).get('enrichment')=='block_object':
        object_cef={'ip':'destinationAddress','domain':'destinationDnsDomain','hash':'fileHash'}.get(inputs.get('object_type'))
        if object_cef and 'object_value' in inputs: cef[object_cef]=inputs['object_value']
        if 'permanent' in derived: cef['actionstack_permanent']=str(derived['permanent']).lower()
    artifact={'name':'Form submission','label':m['label'],'severity':m.get('severity','low'),'source_data_identifier':'splunk_actionstack:'+submission_id+':submission','run_automation':m.get('run_automation',False),'cef':cef,'data':{'actionstack':{'contract_version':1,'submission_id':submission_id,'projection_version':1,'inputs':clone(inputs)}}}
    return container,artifact

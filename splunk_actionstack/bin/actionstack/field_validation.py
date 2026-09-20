"""Field-owned checks; migration keeps published policy snapshots intact."""
import re
from .core import clone, Error, visible
from .validation_policies import validate_rules, validate_request, regex_matches, equal

MULTI_TYPES={'text_list','lookup_multi'}

def inline_form(form):
    f=clone(form)
    policy=f.pop('validation_policy',{})
    f.pop('validation_policy_id',None)
    fields={x['key']:x for x in f['fields']}
    for original in policy.get('rules',[]):
        rule=clone(original); field=fields.get(rule.pop('field'))
        if field is None: raise Error(400,'An older validation rule refers to a removed field.')
        rules=field.setdefault('validation',[])
        if rule not in rules: rules.append(rule)
    if policy.get('enrichment')=='block_object': f['mapping']['enrichment']='block_object'
    return f

def definition_checks(fields):
    for field in fields:
        rules=field.get('validation',[])
        if not isinstance(rules,list) or len(rules)>64: raise Error(400,'Use at most 64 validation checks per field.')
        if field['type']=='section' and rules: raise Error(400,'Sections cannot have validation checks.')
        for rule in rules:
            if not isinstance(rule,dict) or 'field' in rule or rule.get('operator')=='required': raise Error(400,'Set Required in the field settings.')
            op=rule.get('operator')
            if op in ['equals','not_equals'] and isinstance(rule.get('value'),str):
                if field['type']=='number':
                    try: rule['value']=float(rule['value'])
                    except ValueError: raise Error(400,'Enter a number for '+field['label']+'.')
                elif field['type']=='checkbox':
                    if rule['value'].lower() not in ['true','false']: raise Error(400,'Use true or false for checkbox validation.')
                    rule['value']=rule['value'].lower()=='true'
            check=dict(rule,field=field['key'])
            if op in ['like','not_like']:
                if not isinstance(rule.get('value'),str) or not 1<=len(rule['value'])<=200: raise Error(400,'Enter a wildcard pattern of 1–200 characters.')
                check.update(operator='regex',value='.')
            # Each member of a list is checked as text.
            targets=[dict(x,type='text') if x['type'] in MULTI_TYPES|{'multiselect'} else x for x in fields]
            validate_rules([check],targets)

def wildcard(pattern):
    return '(?s)'+''.join('.*' if c=='*' else '.' if c=='?' else re.escape(c) for c in pattern)

def validate_field_inputs(form,inputs):
    jobs=[]; messages=[]; errors={}
    for field in form['fields']:
        key=field['key']
        if not visible(field,inputs) or key not in inputs: continue
        value=inputs[key]
        if value is None or value=='' or value==[]: continue
        values=value if isinstance(value,list) else [value]
        normalized=[]
        for item in values:
            item_inputs=dict(inputs); item_inputs[key]=item
            checks=[]
            for rule in field.get('validation',[]):
                condition=rule.get('when')
                if condition and (condition['field'] not in inputs or not equal(inputs[condition['field']],condition['equals'])): continue
                if rule['operator'] in ['like','not_like','regex']:
                    if not isinstance(item,str): errors[key]=rule['message']; continue
                    pattern=wildcard(rule['value']) if rule['operator']!='regex' else rule['value']
                    jobs.append([pattern,item]); messages.append((key,rule))
                else: checks.append(dict(rule,field=key))
            try: validate_request({'fields':form['fields'],'validation_policy':{'rules':checks}},item_inputs)
            except Error as exc: errors.update(exc.fields)
            normalized.append(item_inputs[key])
        inputs[key]=normalized if isinstance(value,list) else normalized[0]
    if errors: raise Error(400,'Check the highlighted fields.',errors)
    for (key,rule),matched in zip(messages,regex_matches(jobs)):
        if matched == (rule['operator']=='not_like'): errors[key]=rule['message']
    if errors: raise Error(400,'Check the highlighted fields.',errors)

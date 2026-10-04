"""Validate portable form files without saving or running their lookups."""
import json
import re
import uuid
from .core import Error, capable, require, clone, validate_definition

PORTABLE_FIELDS={'title','description','category','icon','accent','intro','fields','mapping'}

def import_form(service, actor, body):
    require(actor,'edit')
    if not isinstance(body,dict) or set(body)!={'document','workspace_id'} or not isinstance(body['workspace_id'],str):
        raise Error(400,'Choose a form file and destination workspace.')
    workspace=service.workspace_records().get(body['workspace_id'])
    if not workspace or not service.workspace_allowed(actor,body['workspace_id']):
        raise Error(403,'This workspace is unavailable.')
    if workspace.get('role_groups') and not capable(actor,'admin') and not set(workspace['role_groups']['admin'])&set(actor['roles']):
        raise Error(403,'Only workspace admins can create forms in this workspace.')
    document=body['document']
    if not isinstance(document,dict) or set(document)-{'format','format_version','app_version','form'} or document.get('format')!='actionstack-form' or type(document.get('format_version')) is not int or document['format_version']!=1:
        raise Error(400,'Choose an ActionStack form export (format version 1).')
    try:
        if len(json.dumps(document,ensure_ascii=False,allow_nan=False).encode('utf-8'))>200*1024:
            raise Error(400,'Choose an ActionStack form JSON file under 200 KB.')
        raw=document.get('form')
        if not isinstance(raw,dict) or set(raw)-PORTABLE_FIELDS:
            raise Error(400,'The form file contains unsupported properties.')
        f=clone(raw)
        title=f.get('title','')
        if not isinstance(title,str): raise Error(400,'Enter a valid form title.')
        slug=re.sub('[^a-z0-9]+','-',title.lower()).strip('-')
        slug=re.sub('^[^a-z]+','',slug)[:48].rstrip('-') or 'form'
        f['id']=slug+'-'+uuid.uuid4().hex[:4]
        f['workspace_id']=workspace['id']
        f['access']=clone(workspace.get('default_access') or {'view_roles':[],'submit_roles':[],'edit_roles':actor['roles'],'team_roles':[]})
        f=validate_definition(f,service.roles())
        # Portable files contain inline validation, never policy IDs from another instance.
        if f['mapping'].get('policy') not in [None,'none']:
            raise Error(400,'Export this form again from the current form builder to include its field validation.')
    except (TypeError,ValueError,KeyError,AttributeError,RecursionError):
        raise Error(400,'The form file has an invalid structure. Export it again from ActionStack.')
    f.update(revision=0,version=0,state='draft')
    return f

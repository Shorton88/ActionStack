"""SOAR 8.6 HTTPS adapter. Creates events/artifacts only; no playbook invocation."""
from .run_activity import counts, run_status, block_rows, utility_rows
import json
import ssl
import re
from urllib import request, parse, error
from .core import Error

MAX_RESPONSE=4*1024*1024
MAX_ACTION_DATA_PREVIEW=16000
MAX_ACTIVITY_DATA=256000

def action_data_preview(value,token):
    """Bound and redact connector data before exposing it in a receipt."""
    truncated=False
    def clean(item,depth=0):
        nonlocal truncated
        if depth>5:
            truncated=True
            return '[truncated]'
        if isinstance(item,str):
            if len(item)>600: truncated=True
            return response_detail({'message':item},token)
        if item is None or type(item) in [bool,int,float]: return item
        if isinstance(item,list):
            if len(item)>25: truncated=True
            return [clean(v,depth+1) for v in item[:25]]
        if isinstance(item,dict):
            if len(item)>30: truncated=True
            out={}
            for k,v in list(item.items())[:30]:
                if len(str(k))>80: truncated=True
                key=response_detail({'message':str(k)},token)[:80]
                out[key]='[redacted]' if re.search(r'(?i)password|secret|token|authorization|cookie',str(k)) else clean(v,depth+1)
            return out
        return None
    preview=clean(value)
    # For an oversized object, retain a readable prefix of the sanitized JSON.
    encoded=json.dumps(preview,ensure_ascii=False,indent=2)
    if len(encoded)>MAX_ACTION_DATA_PREVIEW:
        preview=encoded[:MAX_ACTION_DATA_PREVIEW]+'\n…'
        truncated=True
    return preview,truncated

def validate_url(value):
    if not isinstance(value,str): raise Error(400,'Enter an HTTPS SOAR URL.')
    p=parse.urlsplit(value.strip())
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ['','/']:
        raise Error(400,'Use the SOAR HTTPS origin, without a path or embedded credentials.')
    try: p.port
    except ValueError: raise Error(400,'Invalid SOAR port.')
    return value.strip().rstrip('/')

def validate_ca(pem,ignore_certificate_errors=False):
    if type(ignore_certificate_errors) is not bool: raise Error(400,'Ignore certificate validation must be a boolean.')
    if not isinstance(pem,str) or len(pem)>128000: raise Error(400,'Invalid CA certificate.')
    if ignore_certificate_errors:
        # Per-connection context only; never modify Python's global trust settings.
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname=False
        ctx.verify_mode=ssl.CERT_NONE
        return ctx
    ctx=ssl.create_default_context()
    if pem:
        try: ctx.load_verify_locations(cadata=pem)
        except (ssl.SSLError,ValueError): raise Error(400,'Enter a valid PEM certificate chain.')
    return ctx

def response_detail(result, token):
    """Only display bounded JSON error fields; never echo HTML, headers or bodies."""
    if not isinstance(result,dict): return ''
    parts=[]
    for key in ['message','error','detail']:
        value=result.get(key)
        if isinstance(value,str) and value.strip(): parts.append(value)
    text='; '.join(parts)
    # A proxy error page/stack trace is not a user-facing diagnostic.
    if re.search(r'<(?:!doctype|html|body|script)\b',text,re.I): return ''
    if token:
        for secret in [token,parse.quote(token,safe=''),json.dumps(token)[1:-1]]:
            text=text.replace(secret,'[redacted]')
    text=re.sub(r'(?i)(bearer\s+)[^\s,;"<>]+',r'\1[redacted]',text)
    text=re.sub(r'''(?i)((?:["']?)(?:ph-auth-token|authorization|password|secret|access_token|token|cookie)(?:["']?)\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}]+)''',r'\1[redacted]',text)
    text=re.sub(r'[\x00-\x1f\x7f]+',' ',text)
    return text[:600]

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise Error(502,'SOAR redirected the request. Configure its final HTTPS origin.')

class Soar:
    def __init__(self,settings,token):
        self.base=validate_url(settings['soar_url']); self.token=token
        self.timeout=settings.get('request_timeout',15)
        self.opener=request.build_opener(request.HTTPSHandler(context=validate_ca(settings.get('ca_pem',''),settings.get('ignore_certificate_errors',False))),NoRedirect())

    def rejected(self,method,path,http_status,result):
        context=f'{method} /rest/{path} (HTTP {http_status})'
        detail=response_detail(result,self.token)
        suffix=(' SOAR: '+detail) if detail else ' No JSON error detail was returned.'
        if http_status in [401,403]:
            raise Error(403,'SOAR rejected authentication or access during '+context+'.'+suffix)
        if http_status in [429,500,502,503,504]:
            raise Error(503,'SOAR is temporarily unavailable during '+context+'.'+suffix)
        status=400 if http_status in [400,404,405,409,413,415,422] else 502
        raise Error(status,'SOAR rejected '+context+'.'+suffix)

    def call(self,method,path,payload=None,query=None):
        url=self.base+'/rest/'+path
        if query: url+='?'+parse.urlencode(query)
        data=json.dumps(payload,allow_nan=False).encode() if payload is not None else None
        req=request.Request(url,data=data,method=method,headers={'ph-auth-token':self.token,'Content-Type':'application/json','Accept':'application/json'})
        try:
            with self.opener.open(req,timeout=self.timeout) as response:
                raw=response.read(MAX_RESPONSE+1)
                if len(raw)>MAX_RESPONSE: raise Error(502,f'SOAR response exceeded the supported size during {method} /rest/{path}.')
                result=json.loads(raw)
                duplicate=method=='POST' and isinstance(result,dict) and (result.get('existing_container_id') or result.get('existing_artifact_id'))
                if isinstance(result,dict) and (result.get('failed') is True or result.get('success') is False) and not duplicate:
                    self.rejected(method,path,response.getcode(),result)
                return result
        except error.HTTPError as exc:
            try: raw=exc.read(MAX_RESPONSE)
            finally: exc.close()
            try: result=json.loads(raw)
            except (ValueError,UnicodeError): result={}
            if method=='POST' and isinstance(result,dict) and (result.get('existing_container_id') or result.get('existing_artifact_id')): return result
            self.rejected(method,path,exc.code,result)
        except (error.URLError,TimeoutError,OSError): raise Error(504,f'SOAR delivery could not be confirmed during {method} /rest/{path}. Check connectivity and the CA chain before retrying.')
        except (ValueError,UnicodeError): raise Error(502,f'SOAR returned an invalid response during {method} /rest/{path}.')

    def labels(self):
        # SOAR 8.6 documents container_options, including its label array.
        result=self.call('GET','container_options')
        if not isinstance(result,dict) or not isinstance(result.get('label'),list) or any(not isinstance(x,str) for x in result['label']):
            raise Error(502,'SOAR returned unexpected container options.')
        return sorted(set(result['label']))

    def activity(self,container_id,details=True):
        """Event-scoped status with bounded summaries and action data previews."""
        if type(container_id) is not int or container_id<=0: raise Error(400,'Invalid SOAR event ID.')
        output={}; reports={}
        for key,endpoint,limit in [('playbooks','playbook_run',25),('actions','action_run',100)]:
            try:
                result=self.call('GET',endpoint,query={'_filter_container':container_id,'page':0,'page_size':limit,'sort':'id','order':'desc','pretty':''})
                if not isinstance(result,dict) or not isinstance(result.get('data'),list): raise Error(502,'Unexpected run list.')
                count=result.get('count')
                if type(count) is not int or count<0 or len(result['data'])>limit or count<len(result['data']): raise Error(502,'Unexpected run count.')
                rows=[]
                for row in result['data']:
                    if not isinstance(row,dict) or type(row.get('id')) is not int or row['id']<=0 or type(row.get('container')) is not int or row['container']!=container_id:
                        raise Error(502,'Run does not match the requested event.')
                    def safe(value,limit=180):
                        if not isinstance(value,str): return None
                        return re.sub(r'[\x00-\x1f\x7f]+',' ',value.replace(self.token,'[redacted]') if self.token else value)[:limit]
                    pb=row.get('playbook')
                    name=(row.get('_pretty_playbook') or ('Playbook #'+str(pb) if type(pb) is int else 'Playbook')) if key=='playbooks' else (row.get('name') or row.get('action') or 'Action')
                    status=row.get('status')
                    if row.get('cancelled'): status='cancelled'
                    status=run_status(status)
                    if key=='playbooks' and details: reports[row['id']]=row.get('message')
                    rows.append({'id':row['id'],'name':safe(name) or 'Unnamed run','status':status,'action':safe(row.get('action')) if key=='actions' else None,'playbook_run_id':row.get('playbook_run') if type(row.get('playbook_run')) is int else None,'updated_at':safe(row.get('update_time'),60)})
                output[key]={'items':rows,'total':count,'truncated':count>len(rows),'error':None}
            except Error as exc:
                reason='The SOAR identity cannot read these runs.' if exc.status==403 else 'SOAR run status is unavailable. Check the connection and run-read permissions.'
                output[key]={'items':[],'total':None,'truncated':False,'error':reason}
        actions=output['actions']
        if details and actions['items']:
            try:
                summaries=self.action_summaries(container_id)
                for row in actions['items']:
                    row['summaries']=summaries['items'].get(row['id'],[])
                actions['summary_truncated']=summaries['truncated']
            except Error:
                actions['summary_error']='Action results are unavailable. Check SOAR app-run read permissions.'
        for group in output.values(): group['counts']=counts(group)
        if details:
            blocks=[]; unavailable=False; limited=output['playbooks']['truncated'] or len(reports)>3
            old_timeout=self.timeout
            try:
                self.timeout=min(self.timeout,3)
                for run in output['playbooks']['items'][:3]:
                    blocks.extend(utility_rows(reports.get(run['id']),run['id'],self.token))
                    try:
                        result=self.call('GET','playbook_run/'+str(run['id'])+'/block_results')
                        if not isinstance(result,dict) or not isinstance(result.get('block_results'),dict): raise Error(502,'Unexpected block results.')
                        raw=result['block_results']
                        projected=block_rows(raw,run['id'],self.token)
                        limited=limited or len(raw)>1000 or len(projected)>=100
                        blocks.extend(projected)
                    except Error: unavailable=True
            finally: self.timeout=old_timeout
            output['blocks']={'items':blocks,'total':len(blocks),'truncated':limited,'error':None,
                'notice':'Only blocks with results reported by SOAR are listed. Utility blocks appear when SOAR includes their run headers. An unreported status is shown as Unknown.',
                'summary_error':'Some block results are unavailable. Check SOAR permissions and version support.' if unavailable or output['playbooks']['error'] else None}
        return output

    def action_summaries(self,container_id):
        # Keep the summaries response key for compatibility; each result may
        # contain a summary, data, or both inside app_run.result_data.
        result=self.call('GET','app_run',query={'_filter_container':container_id,'page':0,'page_size':100,'sort':'id','order':'desc'})
        if not isinstance(result,dict) or not isinstance(result.get('data'),list) or type(result.get('count')) is not int or result['count']<len(result['data']) or len(result['data'])>100: raise Error(502,'Invalid app run list.')
        items={}; truncated=result['count']>len(result['data']); fetched=0; data_budget=MAX_ACTIVITY_DATA
        def clean(value,depth=0):
            if depth>3: return '[truncated]'
            if isinstance(value,str): return response_detail({'message':value},self.token)[:500]
            if value is None or type(value) in [bool,int,float]: return value
            if isinstance(value,list): return [clean(v,depth+1) for v in value[:10]]+(['[truncated]'] if len(value)>10 else [])
            if isinstance(value,dict):
                out={}
                for k,v in list(value.items())[:20]:
                    key=response_detail({'message':str(k)},self.token)[:80]
                    out[key]='[redacted]' if re.search(r'(?i)password|secret|token|authorization|cookie',str(k)) else clean(v,depth+1)
                if len(value)>20: out['…']='Additional fields omitted'
                return out
            return None
        for row in result['data']:
            if not isinstance(row,dict) or type(row.get('container')) is not int or row['container']!=container_id or type(row.get('id')) is not int or type(row.get('action_run')) is not int: raise Error(502,'App run does not match the event.')
            target=items.setdefault(row['action_run'],[])
            data=row.get('result_data')
            if data is None:
                if fetched>=5: truncated=True; continue
                fetched+=1
                prior_timeout=self.timeout
                try:
                    self.timeout=min(self.timeout,5)
                    detail=self.call('GET','app_run/'+str(row['id'])+'/action_result',query={'page':0,'page_size':5})
                finally: self.timeout=prior_timeout
                if not isinstance(detail,dict) or not isinstance(detail.get('data'),list) or type(detail.get('count')) is not int or detail['count']<len(detail['data']) or len(detail['data'])>5: raise Error(502,'Invalid action results.')
                data=detail['data']; truncated=truncated or detail['count']>len(data)
            if not isinstance(data,list): raise Error(502,'Invalid action result list.')
            for entry in data:
                if not isinstance(entry,dict): raise Error(502,'Invalid action result.')
                if not entry.get('summary') and 'data' not in entry: continue
                if len(target)>=5: truncated=True; break
                status=entry.get('status')
                projected={'app_run_id':row['id'],'status':'failed' if status=='failure' else status if status in ['success','failed','pending','running'] else 'unknown'}
                if entry.get('summary'):
                    summary=clean(entry['summary'])
                    if len(json.dumps(summary))>4000: summary={'notice':'Summary exceeds display limit. Open SOAR for the full summary.'}; truncated=True
                    projected['summary']=summary
                if 'data' in entry:
                    preview,limited=action_data_preview(entry['data'],self.token)
                    size=len(json.dumps(preview))
                    if size>data_budget:
                        preview='Preview limit reached. Open SOAR for this result.'
                        limited=True
                        size=len(json.dumps(preview))
                    data_budget=max(0,data_budget-size)
                    projected['data']=preview
                    projected['data_truncated']=limited
                    truncated=truncated or limited
                target.append(projected)
        return {'items':items,'truncated':truncated}

    def lookup(self,kind,payload):
        query={'_filter_source_data_identifier':json.dumps(payload['source_data_identifier']),'page_size':100}
        if kind=='artifact': query['_filter_container_id']=str(payload['container_id'])
        elif payload.get('asset_id'): query['_filter_asset']=str(payload['asset_id'])
        result=self.call('GET',kind,query=query)
        if not isinstance(result,dict) or not isinstance(result.get('data'),list):
            raise Error(502,'SOAR lookup could not be verified. No object was created.')
        matches=result['data']
        if result.get('count',len(matches))>1: raise Error(502,'Multiple SOAR objects match this submission. Administrator reconciliation is required.')
        if not matches: return None
        obj=matches[0]
        if not isinstance(obj,dict) or type(obj.get('id')) is not int or obj['id']<=0 or obj.get('source_data_identifier')!=payload['source_data_identifier']:
            raise Error(502,'SOAR lookup returned unexpected object identifiers.')
        expected=payload.get('data',{}).get('actionstack',{}).get('submission_id')
        actual=obj.get('data',{}).get('actionstack',{}).get('submission_id')
        if actual!=expected or (kind=='container' and obj.get('label')!=payload['label']): raise Error(502,'Existing SOAR data does not match this submission. Administrator reconciliation is required.')
        if kind=='artifact' and obj.get('cef')!=payload.get('cef'): raise Error(502,'Existing SOAR artifact fields differ from this submission.')
        if kind=='container' and obj.get('data',{}).get('actionstack')!=payload.get('data',{}).get('actionstack'): raise Error(502,'Existing SOAR event data differs from this submission.')
        return obj['id']

    def ensure(self,kind,payload):
        existing=self.lookup(kind,payload)
        if existing: return existing
        if kind=='container':
            labels=self.labels()
            if payload.get('label') not in labels:
                raise Error(400,'SOAR label '+repr(payload.get('label'))+' is not available to the integration identity. No new event was created. Create that exact label in SOAR, or publish a form using an existing label and make a new request. Retry retains this request’s original label.')
        result=self.call('POST',kind,payload)
        if isinstance(result,dict) and result.get('success') is True and type(result.get('id')) is int and result['id']>0: return result['id']
        # A duplicate reply must be verified through a read, never blindly adopted.
        existing=self.lookup(kind,payload)
        if existing: return existing
        raise Error(502,'SOAR did not confirm object creation. Retry will reconcile before sending again.')

"""Bounded, read-only lookup searches in the authenticated user's context."""
import json
import re
import time
from urllib.parse import quote
from .core import Error

SOURCE=re.compile(r'\s*\|\s*inputlookup\s+([A-Za-z0-9_][A-Za-z0-9_.-]{0,127})\s*\|\s*fields\s+([A-Za-z_][A-Za-z0-9_]{0,63})\s*',re.I)

# Only data-transforming commands: no dispatch, writes, macros or subsearches.
READ_COMMANDS={'eval','where','search','fields','table','rename','dedup','sort','head','tail','fillnull','rex','regex','spath','stats','eventstats','streamstats','mvexpand','makemv','mvcombine','nomv','convert','replace'}
IDENTIFIER=re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}')

def pipeline(search):
    if not isinstance(search,str) or not 1<=len(search)<=8000 or '`' in search or any(ord(c)<32 and c not in '\n\r\t' for c in search):
        raise Error(400,'Enter up to 8000 characters of lookup SPL without macros or control characters.')
    parts=[]; current=[]; quoted=None; escaped=False
    for c in search:
        if escaped:
            current.append(c); escaped=False; continue
        if c=='\\' and quoted:
            current.append(c); escaped=True; continue
        if quoted:
            current.append(c)
            if c==quoted: quoted=None
        elif c in ['"',"'"]:
            quoted=c; current.append(c)
        elif c in '[]': raise Error(400,'Lookup subsearches are not supported.')
        elif c=='|':
            parts.append(''.join(current).strip()); current=[]
        else: current.append(c)
    if quoted or escaped: raise Error(400,'Close the quoted strings in the lookup search.')
    parts.append(''.join(current).strip())
    if parts and not parts[0]: parts=parts[1:]
    if not parts or any(not part for part in parts): raise Error(400,'Enter a complete lookup pipeline.')
    source=re.fullmatch(r'inputlookup\s+(?:strict=true\s+)?([A-Za-z0-9_][A-Za-z0-9_.-]{0,127})',parts[0],re.I)
    if not source: raise Error(400,'Start with | inputlookup lookup_name, then add read-only SPL transformations.')
    for part in parts[1:]:
        command=re.match(r'([a-zA-Z]+)(?:\s|$)',part)
        if not command or command[1].lower() not in READ_COMMANDS: raise Error(400,'Unsupported lookup command. Use read-only transformations such as eval, where, table, fields, rename or stats.')
    parts[0]='inputlookup strict=true '+source[1]
    return ' | '.join(parts)

def lookup_fields(config):
    # Older one-column forms keep their existing value/label mapping.
    legacy=SOURCE.fullmatch(config.get('search',''))
    value=config.get('value_field',legacy[2] if legacy else '')
    label=config.get('label_field',value)
    if not all(isinstance(v,str) and IDENTIFIER.fullmatch(v) for v in [value,label]): raise Error(400,'Choose the result field sent to SOAR and the field displayed as its label.')
    return value,label

def validate_source(config):
    required={'search','app','min_chars','debounce_ms'}
    if not isinstance(config,dict) or not required<=set(config) or set(config)-required-{'value_field','label_field'}: raise Error(400,'Configure the lookup search, result fields, app context, minimum characters and typing delay.')
    pipeline(config['search'])
    value,label=lookup_fields(config)
    if not isinstance(config['app'],str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]{0,99}',config['app']): raise Error(400,'Enter a valid Splunk app context for the lookup.')
    if type(config['min_chars']) is not int or not 3<=config['min_chars']<=10 or type(config['debounce_ms']) is not int or not 50<=config['debounce_ms']<=1000:
        raise Error(400,'Lookup fields need 3–10 characters and a 50–1000 ms typing delay.')
    return value,label

def lookup_spl(config,term,exact=False):
    column,label=validate_source(config)
    terms=term if isinstance(term,list) else [term]
    if isinstance(term,list) and (not exact or not 1<=len(term)<=25): raise Error(400,'Select 1–25 lookup values.')
    if any(not isinstance(t,str) or not 1<=len(t)<=200 or any(ord(c)<32 for c in t) or '`' in t for t in terms): raise Error(400,'Enter up to 200 characters without control characters or backticks.')
    if exact:
        comparison=' OR '.join(f"tostring('{column}') = {json.dumps(t,ensure_ascii=False)}" for t in terms)
    else:
        value=json.dumps(term.lower(),ensure_ascii=False)
        comparison=' OR '.join(f"substr(lower(tostring('{field}')),1,{len(term.lower())}) = {value}" for field in dict.fromkeys([column,label]))
    columns=' '.join(dict.fromkeys([column,label]))
    return f"| {pipeline(config['search'])} | where ({comparison}) | dedup {column} | head {len(terms) if exact else 26} | fields {columns}",column

def truth(value): return value is True or value==1 or value=='1'

class LookupSearch:
    def __init__(self,user_rest,username): self.rest,self.username=user_rest,username

    def search(self,config,term,exact=False):
        spl,column=lookup_spl(config,term,exact)
        base='/servicesNS/'+quote(self.username,safe='')+'/'+quote(config['app'],safe='')+'/search/jobs'
        sid=None
        try:
            job=self.rest.call('POST',base,form={'search':spl,'exec_mode':'normal','max_time':'5','auto_cancel':'30','auto_finalize_ec':'0','status_buckets':'0'})
            sid=job.get('sid') if isinstance(job,dict) else None
            if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',sid): raise Error(502,'Splunk did not return a lookup search ID.')
            path=base+'/'+quote(sid,safe=''); deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                state=self.rest.call('GET',path)
                entries=state.get('entry',[]) if isinstance(state,dict) else []
                if not isinstance(entries,list) or not entries or not isinstance(entries[0],dict) or not isinstance(entries[0].get('content'),dict): raise Error(502,'Lookup search status is unavailable.')
                c=entries[0]['content']
                if truth(c.get('isFailed')) or truth(c.get('isFinalized')) or c.get('dispatchState') in ['FAILED','BAD_INPUT_CANCEL','QUIT']:
                    raise Error(503,'Lookup search failed or exceeded its time limit. Check lookup access and refine the query.')
                if truth(c.get('isDone')) or c.get('dispatchState')=='DONE': break
                time.sleep(0.1)
            else: raise Error(504,'Lookup search timed out. Refine the query or use a smaller lookup.')
            result=self.rest.call('GET',path+'/results',params={'count':(len(term) if isinstance(term,list) else 1) if exact else 26,'output_mode':'json'})
            if not isinstance(result,dict) or not isinstance(result.get('results'),list) or not isinstance(result.get('messages',[]),list) or any(not isinstance(m,dict) or m.get('type') in ['WARN','ERROR','FATAL'] for m in result.get('messages',[])):
                raise Error(503,'Lookup results could not be confirmed. Check the lookup configuration and permissions.')
            _,label_column=lookup_fields(config)
            options=[]; seen=set()
            for row in result['results']:
                if not isinstance(row,dict): raise Error(502,'Invalid lookup result row.')
                if column not in row or label_column not in row: raise Error(400,'Lookup results are missing the configured value or label field. Keep both fields in the final SPL output.')
                value=row[column]; label=row[label_column]
                if not isinstance(value,str) or not value or len(value)>200 or any(ord(c)<32 for c in value): continue
                if not isinstance(label,str) or not label or len(label)>200: continue
                matches=(value in term if isinstance(term,list) else value==term) if exact else any(v.lower().startswith(term.lower()) for v in [value,label])
                if matches and value not in seen:
                    seen.add(value); options.append({'value':value,'label':label})
            return {'options':options[:25],'more':len(options)>25}
        except Error as exc:
            if exc.status==503 and 'storage' in exc.message.lower(): raise Error(503,'Lookup search is unavailable. The signed-in user needs search capability and read access to this lookup in its app context.')
            raise
        finally:
            if sid and re.fullmatch(r'[A-Za-z0-9_.-]+',sid):
                try: self.rest.call('DELETE',base+'/'+quote(sid,safe=''))
                except Error: pass  # Splunk's auto-cancel/TTL still bounds abandoned jobs.

"""Small, data-free projections of SOAR run and block status."""
import hashlib
import json
import re

STATUSES = ('success', 'failed', 'running', 'pending', 'cancelled', 'unknown')


def run_status(value):
    if value == 'failure': return 'failed'
    return value if isinstance(value, str) and value in STATUSES else 'unknown'


def counts(group):
    if group.get('error'): return None
    result = dict.fromkeys(STATUSES, 0)
    for item in group['items']: result[run_status(item.get('status'))] += 1
    return result


def block_rows(results, playbook_run, token=''):
    """Read datapath names/status only; never project saved block payloads."""
    rows = {}
    for path, value in list(results.items())[:1000]:
        if not isinstance(path, str): continue
        parts = path.split(':')
        if not parts[0] or len(parts[0]) > 180: continue
        filtered = parts[0] == 'filtered-data' and len(parts) > 2
        name = parts[1] if filtered else parts[0]
        tail = parts[2:] if filtered else parts[1:]
        kind = 'Filter' if filtered else 'Format' if 'formatted_data' in tail else 'Utility' if any('custom_function' in p for p in tail) else 'Decision / filter' if any(p.startswith('condition_') for p in tail) else 'Code / saved result'
        # Display condition rows separately; their statuses need not agree.
        condition = next((p for p in tail if p.startswith('condition_')), None)
        key = name + (':' + condition if condition else '')
        clean = re.sub(r'[\x00-\x1f\x7f]', ' ', key.replace(token, '[redacted]') if token else key)[:180]
        row = rows.setdefault(key, {'id':str(playbook_run)+':'+hashlib.sha256(key.encode()).hexdigest()[:16], 'name':clean, 'block_type':kind, 'status':'unknown', 'playbook_run_id':playbook_run, 'updated_at':None})
        # Output or a false condition is not a run success/failure signal.
        if tail and tail[-1] == 'status': row['status'] = run_status(value)
    return list(rows.values())[:100]


def utility_rows(message, playbook_run, token=''):
    # Some SOAR versions include custom-function run headers in the playbook
    # report. Use only those explicit headers, never the function definition.
    if isinstance(message, str):
        if len(message) > 512000: return []
        try: message = json.loads(message)
        except (ValueError, RecursionError): return []
    if not isinstance(message, dict) or message.get('playbook_run_id') != playbook_run: return []
    results = message.get('result')
    if not isinstance(results, list): return []
    rows = []
    for result in results[:100]:
        if not isinstance(result, dict) or type(result.get('custom_function_run_id')) is not int: continue
        name = result.get('name') or result.get('custom_function_name')
        if not isinstance(name, str): continue
        name = re.sub(r'[\x00-\x1f\x7f]', ' ', name.replace(token, '[redacted]') if token else name)[:180]
        rows.append({'id':str(playbook_run)+':utility:'+str(result['custom_function_run_id']), 'name':name, 'block_type':'Utility', 'status':run_status(result.get('status')), 'playbook_run_id':playbook_run, 'updated_at':None})
    return rows

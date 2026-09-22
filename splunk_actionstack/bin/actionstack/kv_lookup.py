"""Direct, user-authorized KV Store reads for projection-only lookup searches."""
import json
import re
from urllib.parse import quote
from .core import Error

NAME = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}')


def collection_rows(rest, username, app, search, fields, term, exact):
    # Only bypass search dispatch when every command preserves the selected
    # values. Scalar mvexpand is a no-op; array results use the SPL fallback.
    parts = search.split(' | ')
    source = parts[0].split()[-1]
    for part in parts[1:]:
        tokens = part.replace(',', ' ').split()
        if tokens[0].lower() in ['fields', 'table']:
            projected = tokens[1:]
            if projected and projected[0] == '+': projected = projected[1:]
            if not projected or any(not NAME.fullmatch(f) for f in projected) or not set(fields) <= set(projected): return None
        elif tokens[0].lower() != 'mvexpand' or len(tokens) != 2 or tokens[1] not in fields:
            return None
    context = '/servicesNS/' + quote(username, safe='') + '/' + quote(app, safe='')
    try:
        definition = rest.call('GET', context + '/data/transforms/lookups/' + quote(source, safe=''))
    except Error:
        # CSV lookups and identities without REST definition access can still
        # use the ordinary search permission path.
        return None
    entries = definition.get('entry', []) if isinstance(definition, dict) else []
    if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict): return None
    entry = entries[0]
    config = entry.get('content', {})
    if not isinstance(config, dict) or config.get('external_type') != 'kvstore' or config.get('filter') or config.get('time_field'): return None
    collection = config.get('collection')
    acl = entry.get('acl') or config.get('eai:acl', {})
    namespace = acl.get('app') if isinstance(acl, dict) else None
    declared = config.get('fields_list', '')
    if isinstance(declared, str): declared = re.split(r'[\s,]+', declared)
    if not isinstance(declared, list) or not set(fields) <= set(declared): return None
    if not all(isinstance(v, str) and NAME.fullmatch(v) for v in [collection, namespace]): return None
    # Search results stringify numeric/boolean fields. A regex against those
    # raw KV types is not equivalent, so accelerate declared string columns only.
    try:
        schema = rest.call('GET', '/servicesNS/nobody/' + quote(namespace, safe='') + '/storage/collections/config/' + quote(collection, safe=''))
    except Error: return None
    schema_entries = schema.get('entry', []) if isinstance(schema, dict) else []
    if not isinstance(schema_entries, list) or len(schema_entries) != 1 or not isinstance(schema_entries[0], dict): return None
    schema_fields = schema_entries[0].get('content', {})
    if not isinstance(schema_fields, dict) or any(f != '_key' and schema_fields.get('field.' + f) != 'string' for f in fields): return None
    terms = term if isinstance(term, list) else [term]
    clauses = [
        {field: {'$regex': '^' + re.escape(value) + ('$' if exact else ''), '$options': 'i'}}
        for field in (fields[:1] if exact else dict.fromkeys(fields)) for value in terms
    ]
    path = '/servicesNS/nobody/' + quote(namespace, safe='') + '/storage/collections/data/' + quote(collection, safe='')
    try:
        rows = rest.call('GET', path, params={
            'query': json.dumps({'$or': clauses}), 'limit': 251 if exact else 26,
            'fields': ','.join(dict.fromkeys(fields)),
        })
    except Error:
        return None  # A lookup search may be allowed when direct KV reads are not.
    if not isinstance(rows, list): raise Error(502, 'Unexpected KV Store lookup response.')
    if any(not isinstance(row, dict) or any(f in row and not isinstance(row[f], str) for f in fields) for row in rows): return None
    return rows

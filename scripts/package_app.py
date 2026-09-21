"""Build a deterministic, allowlisted Splunk bundle with no local settings or demo data."""
import configparser
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'splunk_actionstack'
version=json.loads((ROOT/'package.json').read_text())['version']
conf=configparser.ConfigParser(); conf.read(APP/'default'/'app.conf')
assert conf['launcher']['version']==version, 'Package versions differ'
assert conf.getboolean('install','is_configured',fallback=False) is False, 'Do not package completed setup state'
restmap=configparser.ConfigParser(); restmap.read(APP/'default'/'restmap.conf')
for stanza in restmap.sections():
    if stanza.startswith(('script:','admin_external:')):
        assert restmap[stanza].get('python.version') in {'python3','python3.7','python3.9'}, 'Declare an AppInspect-compatible python.version in '+stanza
for xml in (APP/'default'/'data'/'ui').rglob('*.xml'): ET.parse(xml)
for name in ['actionstack.js','actionstack.css']:
    assert (APP/'appserver'/'static'/name).stat().st_size>100, 'Build frontend first'

notices=['Third-party components bundled in ActionStack\n']
for name in ['react','react-dom','scheduler','lucide-react']:
    dep=ROOT/'node_modules'/name
    meta=json.loads((dep/'package.json').read_text())
    license_file=next((p for p in [dep/'LICENSE',dep/'LICENSE.txt'] if p.exists()),None)
    if license_file is None: raise RuntimeError('Missing license: '+name)
    notices.extend(['\n'+name+' '+meta['version']+'\n',license_file.read_text()])
(APP/'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(notices))
(APP/'LICENSE').write_bytes((ROOT/'LICENSE').read_bytes())
(APP/'README.txt').write_text('ActionStack '+version+'\n\nForm-based event submission from Splunk to Splunk SOAR.\nhttps://splunkbase.splunk.com/app/9812\n\nSee documentation/DEPLOYMENT.md for installation and configuration.\n')
docs=APP/'documentation'; docs.mkdir(exist_ok=True)
documentation={'README.md','CONTRIBUTING.md','LICENSE','DEPLOYMENT.md','SOAR_EVENT_CONTRACT.md','CHANGELOG.md'}
for name in sorted(documentation):
    (docs/name).write_bytes((ROOT/name).read_bytes())
examples=docs/'examples'; examples.mkdir(exist_ok=True)
for source in (ROOT/'examples').glob('*.json'):
    (examples/source.name).write_bytes(source.read_bytes())
    documentation.add('examples/'+source.name)

allowed_roots={'default','metadata','bin','appserver','documentation','static'}
allowed_suffixes={'.conf','.meta','.py','.xml','.js','.css','.md','.json','.png'}
files=[]
for p in sorted(APP.rglob('*')):
    rel=p.relative_to(APP)
    if not p.is_file() or p.is_symlink() or any(part in ['__pycache__','local'] or part.startswith('.') for part in rel.parts): continue
    if rel.parts[0]=='documentation' and rel.relative_to('documentation').as_posix() not in documentation: continue
    if p.name in ['README.txt','THIRD_PARTY_NOTICES.txt','LICENSE'] or (rel.parts[0] in allowed_roots and p.suffix in allowed_suffixes): files.append(p)
out=ROOT/'dist'; out.mkdir(exist_ok=True)
bundle=out/('splunk_actionstack-'+version+'.spl')
with bundle.open('wb') as raw:
    with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w',format=tarfile.USTAR_FORMAT) as archive:
            for p in files:
                data=p.read_bytes(); info=tarfile.TarInfo('splunk_actionstack/'+p.relative_to(APP).as_posix())
                info.size=len(data); info.mode=0o644; info.mtime=0; info.uid=info.gid=0; info.uname=info.gname=''
                archive.addfile(info,io.BytesIO(data))
sha=hashlib.sha256(bundle.read_bytes()).hexdigest()
bundle.with_suffix('.spl.sha256').write_text(sha+'  '+bundle.name+'\n')
print(str(bundle)+' ('+str(len(files))+' files, '+str(bundle.stat().st_size)+' bytes)')
print('SHA-256: '+sha)

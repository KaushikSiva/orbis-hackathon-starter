#!/usr/bin/env python3
"""Build three standalone, disclosed copies of the same canonical codebase.

Copies only reviewable source, dependencies manifests and public artifacts. Never
copies .env, runtime databases, uploaded rooms, node_modules or local CLI logs.
"""
from pathlib import Path
import hashlib
import json
import shutil
import re
import tempfile
import os
import subprocess
from urllib.parse import unquote
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'publication'
VARIANTS = ['live-video', 'ambiguous-coworker', 'qoder-neo4j']
EXCLUDE_DIRS = {'node_modules', '.venv', '.git', 'data', '__pycache__', '.pytest_cache', 'dist', 'raw', 'raw-capture', 'live-raw', 'live-cdp-raw', 'approved-save-raw', '.capture', '.ambi'}
EXCLUDE_SUFFIX = {'.log', '.pyc', '.webm', '.tsbuildinfo'}
SOURCE_DIRS = ['backend', 'frontend', 'scripts', 'tooling', 'docs', 'artifacts', 'deploy']
ROOT_FILES = ['README.md', '.env.example', '.gitignore', 'docker-compose.yml', 'compose.yaml', 'LICENSE', 'Dockerfile', '.dockerignore', 'render.yaml']

def include(path: Path):
    rel = path.relative_to(ROOT)
    if any(x in EXCLUDE_DIRS for x in rel.parts): return False
    if path.name.startswith('.env') and path.name != '.env.example': return False
    if rel.parts[:3] == ('frontend', 'public', 'reactor'): return False
    if path.suffix in EXCLUDE_SUFFIX or path.name == '.DS_Store': return False
    if path.is_file() and path.stat().st_size > 95_000_000: return False
    return True

def collect_snapshot():
    """Read each public file once so all three presentations share identical bytes."""
    snapshot={}
    for dirname in SOURCE_DIRS:
        for p in sorted((ROOT/dirname).rglob('*')):
            if p.is_symlink() and include(p): raise SystemExit(f'Refusing public symlink: {p.relative_to(ROOT)}')
            if p.is_file() and include(p): snapshot[str(p.relative_to(ROOT))]=p.read_bytes()
    for name in ROOT_FILES:
        if (ROOT/name).exists(): snapshot[name]=(ROOT/name).read_bytes()
    return snapshot

def digest_sources(snapshot):
    h=hashlib.sha256()
    files=[]
    for rel,data in sorted(snapshot.items()):
        if rel.startswith(('backend/','frontend/')):
            files.append(rel);h.update(rel.encode());h.update(data)
    return h.hexdigest(),files

def configured_secrets():
    secrets=[]
    envfile=ROOT/'.env'
    if envfile.exists():
        for line in envfile.read_text().splitlines():
            if '=' not in line or line.lstrip().startswith('#'): continue
            key,value=line.split('=',1);value=value.strip().strip('"').strip("'")
            if not any(word in key for word in ('TOKEN','SECRET','API_KEY','PASSWORD')) or not value: continue
            # This exact documented default is public and only used by local Docker.
            # Compose binds the development database to 127.0.0.1.
            if key=='NEO4J_PASSWORD' and value=='showroom-local-dev': continue
            secrets.append((key,value.encode()))
    cli_config=ROOT/'.ambi/config.json'
    if cli_config.exists():
        for key,value in json.loads(cli_config.read_text()).items():
            if isinstance(value,str) and value and re.search(r'token|secret|password|api.?key',key,re.I):
                secrets.append(('Ambiguous CLI credential',value.encode()))
    return secrets

def scan_secrets(dest):
    secrets=configured_secrets()
    for file in dest.rglob('*'):
        if not file.is_file(): continue
        data=file.read_bytes()
        for key,value in secrets:
            if value in data:
                raise SystemExit(f'Credential scan blocked package: {key} found in {file.relative_to(dest)} (value withheld)')
    return len(secrets)

def main():
    snapshot=collect_snapshot()
    digest, sources = digest_sources(snapshot)
    for variant in VARIANTS:
        OUT.mkdir(parents=True, exist_ok=True)
        final_dest=OUT/variant
        if final_dest.parent.resolve()!=OUT.resolve() or variant not in VARIANTS:
            raise SystemExit('Refusing an unexpected publication destination')
        dest=Path(tempfile.mkdtemp(prefix=f'.{variant}-stage-',dir=OUT))
        for rel,data in snapshot.items():
            target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            target.chmod((ROOT/rel).stat().st_mode & 0o777)
        readme_key=f'docs/readme-variants/{variant}.md'
        if readme_key not in snapshot: raise SystemExit(f'Missing {readme_key}')
        (dest/'README.md').write_text(snapshot[readme_key].decode().replace('../../README.md','QUICKSTART.md').replace('../../',''))
        (dest/'QUICKSTART.md').write_bytes(snapshot['README.md'])
        metadata=json.loads(snapshot[f'docs/readme-variants/{variant}.json'])
        metadata.update({'canonical_project':'SHOWROOM','same_codebase':True,'source_sha256':digest,'source_files':sources})
        metadata.setdefault('publication_status','prepared for approved public GitHub destination')
        if (ROOT/'.git').exists():
            metadata['canonical_local_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        (dest/'publication.json').write_text(json.dumps(metadata,indent=2)+'\n')
        missing=[]
        for markdown in dest.rglob('*.md'):
            for url in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',markdown.read_text()):
                if url.startswith(('https://','http://','mailto:','#')): continue
                target=unquote(url.split('#',1)[0].split('?',1)[0].strip('<>'))
                if target and not (markdown.parent/target).exists(): missing.append(f'{markdown.relative_to(dest)} -> {url}')
        if missing: raise SystemExit(f'Broken Markdown links in {variant}: {missing}')
        scanned=scan_secrets(dest)
        if final_dest.exists():
            marker=final_dest/'publication.json'
            if not marker.exists() or json.loads(marker.read_text()).get('canonical_project')!='SHOWROOM':
                raise SystemExit(f'Refusing to replace unrecognized destination {final_dest}')
            shutil.rmtree(final_dest)
        os.replace(dest,final_dest)
        dest=final_dest
        archive=OUT/f'showroom-{variant}.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(dest.rglob('*')):
                if p.is_file(): z.write(p,Path(f'showroom-{variant}')/p.relative_to(dest))
        print(f'{variant}: {archive.stat().st_size/1_000_000:.1f} MB, source {digest[:12]}, Markdown links valid, {scanned} configured secrets scanned')
    (OUT/'README.md').write_text('# SHOWROOM publication packages\n\nThree presentation packages share the same SHOWROOM backend and frontend source digest. Each directory is a standalone repository presentation; `publication.json` contains its approved repository URL, publication state, description, topics and shared-codebase disclosure. The zip files are portable copies. This script builds packages; it does not itself publish repositories.\n\nApproved destinations: [canonical live video](https://github.com/KaushikSiva/showroom), [Ambiguous coworker](https://github.com/KaushikSiva/showroom-coworker), and [Qoder / Neo4j](https://github.com/KaushikSiva/showroom-graph). Cross-event eligibility was confirmed by the participant on September 12, 2026. Review `docs/evidence/verification.md` in each package for integration status and `docs/publication.md` for publication status.\n')

if __name__=='__main__': main()

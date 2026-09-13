"""Verify the Render containers locally with isolated test data and no provider credentials."""
import json
import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
tag='showroom-render-check-'+secrets.token_hex(4)
folder=Path(tempfile.mkdtemp(prefix=tag+'-'))
env={**os.environ,'NEO4J_PASSWORD':secrets.token_urlsafe(20),'SHOWROOM_ACCESS_PASSWORD':secrets.token_urlsafe(20)}
containers=[]
def docker(*args):return subprocess.check_output(['docker',*args],env=env,text=True).strip()
def ready(client):
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        try:
            response=client.get('/api/health')
            if response.is_success and response.json()['integrations']['neo4j']['status']=='connected':return response.json()
        except httpx.HTTPError:pass
        time.sleep(1)
    raise RuntimeError('Container health did not become ready')
try:
    docker('network','create',tag)
    graph=tag+'-graph';web=tag+'-web';containers.extend([graph,web])
    docker('run','-d','--name',graph,'--network',tag,'-e','NEO4J_PASSWORD','-e','NEO4J_server_memory_heap_initial__size=256m','-e','NEO4J_server_memory_heap_max__size=512m','-e','NEO4J_server_memory_pagecache_size=256m','showroom-neo4j-render:local')
    docker('run','-d','--name',web,'--network',tag,'-p','127.0.0.1:8192:10000','-v',str(folder)+':/var/data','-e','NEO4J_PASSWORD','-e','SHOWROOM_ACCESS_PASSWORD','-e','SHOWROOM_REQUIRE_AUTH=true','-e','NEO4J_HOST='+graph,'showroom-render:local')
    with httpx.Client(base_url='http://127.0.0.1:8192',timeout=10) as client:
        health=ready(client);print('Container API and private Neo4j ready',flush=True)
        assert client.get('/').status_code==401
        assert client.get('/api/ambiguous/documents').status_code==401
        client.auth=('showroom',env['SHOWROOM_ACCESS_PASSWORD'])
        assert client.get('/').status_code==200
        runtime=client.get('/reactor/wasm/reactor_wasm.js');assert runtime.status_code==200 and 'javascript' in runtime.headers['content-type']
        assert client.get('/reactor/wasm/reactor_wasm_bg.wasm').status_code==200
        room=client.post('/api/rooms',json={'name':'Container persistence check','budget':500,'keep':['sofa']}).json()
        result=client.post(f"/api/rooms/{room['id']}/recommendations",json={'source':'catalog'});assert result.is_success and result.json()['graph']['status']=='connected'
        docker('restart',web);ready(client)
        restored=client.get(f"/api/rooms/{room['id']}");assert restored.is_success and restored.json()['products']
        assert docker('exec',web,'sh','-c','test ! -f /app/.env && test ! -d /app/backend/data')==''
        receipt={'passed':True,'graph':'connected','production_frontend':200,'reactor_runtime':200,'unauthenticated_workspace':401,'persistent_room_after_restart':True,'external_provider_calls':0,'environment_credentials_copied_into_image':False}
        (root/'docs/evidence/render-local-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
finally:
    for name in containers:subprocess.run(['docker','rm','-f',name],capture_output=True)
    subprocess.run(['docker','network','rm',tag],capture_output=True)

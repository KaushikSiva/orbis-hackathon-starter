"""Deploy the reviewed Docker services to Render; never prints environment values."""
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
REPO='https://github.com/KaushikSiva/orbis-hackathon-starter'
RECEIPT=ROOT/'backend/data/runtime/render-deployment.json'

def main():
    if '--deploy' not in sys.argv:
        raise SystemExit('Pass --deploy to create the reviewed paid Render services (about $32.50/month plus API usage).')
    values={**dotenv_values(ROOT/'.env'),**os.environ}
    if not values.get('RENDER_API_KEY'):raise SystemExit('Set RENDER_API_KEY in the ignored .env file.')
    for key in ['REACTOR_API_KEY','OPENAI_API_KEY','EXA_API_KEY','AMBIGUOUS_API_KEY']:
        if not values.get(key):raise SystemExit(f'Missing {key}; no service was created.')
    for key in ['RENDER_NEO4J_PASSWORD','RENDER_STUDIO_PASSWORD']:
        if not values.get(key):
            values[key]=secrets.token_urlsafe(32)
            with (ROOT/'.env').open('a') as f:f.write(f'\n{key}={values[key]}\n')
    (ROOT/'.env').chmod(0o600)
    with httpx.Client(base_url='https://api.render.com/v1',headers={'Authorization':'Bearer '+values['RENDER_API_KEY']},timeout=90) as client:
        def request(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            if not response.is_success:
                detail=response.text
                for key,value in values.items():
                    if value and any(s in key.upper() for s in ('KEY','PASSWORD','TOKEN','SECRET')):detail=detail.replace(value,'[redacted]')
                raise RuntimeError(f'Render {method} {path}: HTTP {response.status_code}: {detail[:800]}')
            return response.json() if response.content else {}
        owners=request('GET','/owners',params={'limit':100})
        owner=values.get('RENDER_OWNER_ID')
        if not owner:
            if len(owners)!=1:raise SystemExit('Set RENDER_OWNER_ID to select the intended Render workspace.')
            owner=owners[0]['owner']['id']
        existing=request('GET','/services',params={'ownerId':owner,'limit':100})
        by_name={row['service']['name']:row['service'] for row in existing}
        receipt=json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {'owner_id':owner,'repository':REPO,'services':{}}
        def persist():RECEIPT.parent.mkdir(parents=True,exist_ok=True);RECEIPT.write_text(json.dumps(receipt,indent=2)+'\n')
        def create(name,kind,plan,dockerfile,mount,env,health=None):
            if name in by_name:
                service=by_name[name]
                if service.get('repo','').removesuffix('.git')!=REPO or service['id']!=receipt['services'].get(name,{}).get('id'):
                    raise RuntimeError(f'{name} already exists without this deployment receipt; refusing to replace it.')
                return service
            details={'runtime':'docker','plan':plan,'region':'oregon','numInstances':1,'envSpecificDetails':{'dockerfilePath':dockerfile,'dockerContext':'.'},'disk':{'name':name+'-data','mountPath':mount,'sizeGB':1}}
            if health:details['healthCheckPath']=health
            data=request('POST','/services',json={'type':kind,'name':name,'ownerId':owner,'repo':REPO,'branch':'main','autoDeploy':'no','envVars':[{'key':k,'value':v} for k,v in env.items()],'serviceDetails':details})
            service=data['service'];receipt['services'][name]={'id':service['id'],'deploy_id':data.get('deployId'),'plan':plan,'url':service.get('serviceDetails',{}).get('url')};persist()
            print(json.dumps({'created':name,**receipt['services'][name]}),flush=True)
            return service
        graph=create('showroom-neo4j','private_service','1c-2g','./deploy/neo4j/Dockerfile','/data',{'NEO4J_PASSWORD':values['RENDER_NEO4J_PASSWORD'],'NEO4J_server_default__listen__address':'0.0.0.0','NEO4J_server_memory_heap_initial__size':'256m','NEO4J_server_memory_heap_max__size':'512m','NEO4J_server_memory_pagecache_size':'256m'})
        address=graph.get('serviceDetails',{}).get('url') or graph.get('slug')
        if not address:raise RuntimeError('Render did not return the private graph address; inspect the created service before continuing.')
        host=urlparse(address if '://' in address else '//'+address).hostname
        if not host:raise RuntimeError('Invalid private graph address')
        env={k:values[k] for k in ['REACTOR_API_KEY','OPENAI_API_KEY','EXA_API_KEY','AMBIGUOUS_API_KEY']}
        if values.get('SHOWROOM_SHARE_EMAIL'):env['SHOWROOM_SHARE_EMAIL']=values['SHOWROOM_SHARE_EMAIL']
        env.update(PORT='10000',SHOWROOM_DATA_DIR='/var/data/showroom',SHOWROOM_REQUIRE_AUTH='true',SHOWROOM_ACCESS_PASSWORD=values['RENDER_STUDIO_PASSWORD'],NEO4J_HOST=host,NEO4J_USER='neo4j',NEO4J_PASSWORD=values['RENDER_NEO4J_PASSWORD'])
        create('showroom','web_service','0.5c-512mb','./Dockerfile','/var/data',env,'/api/health')
        print('Deployment requests accepted. Poll the saved deploy IDs and verify the hosted application before claiming it is live.',flush=True)

if __name__=='__main__':main()

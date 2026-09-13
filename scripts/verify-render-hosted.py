"""Opt-in hosted verification using a prior recorded frame; no Orbis session or document writes."""
import json
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
import httpx
from dotenv import dotenv_values

root=Path(__file__).resolve().parents[1]
if '--live' not in sys.argv:raise SystemExit('Pass --live to verify the hosted app and call OpenAI, Exa and Ambiguous reads.')
values=dotenv_values(root/'.env')
private=json.loads((root/'backend/data/runtime/render-deployment.json').read_text())
url=private['services']['showroom']['url']
frame=(root/'backend/data/runtime/search-benchmark-frame.jpg').read_bytes()
receipt={'verified_at':datetime.now(timezone.utc).isoformat(),'url':url,'external_document_writes':0,'orbis_session_created':False}
with httpx.Client(base_url=url,timeout=140) as client:
    assert client.get('/').status_code==401
    assert client.get('/api/ambiguous/documents').status_code==401
    receipt['anonymous_workspace_status']=401
    client.auth=('showroom',values['RENDER_STUDIO_PASSWORD'])
    assert client.get('/').status_code==200
    assert client.get('/reactor/wasm/reactor_wasm_bg.wasm').status_code==200
    health=client.get('/api/health').json();assert health['integrations']['neo4j']['status']=='connected'
    receipt['static_runtime_status']=200;receipt['graph']='connected'
    docs=client.get('/api/ambiguous/documents');assert docs.is_success;receipt['ambiguous_read_status']=docs.status_code
    r=client.post('/api/rooms',json={'name':'Render verification','budget':2500,'keep':['sofa'],'preferences':['Warm minimal','Natural textures']});r.raise_for_status();room=r.json()
    catalog=client.post(f"/api/rooms/{room['id']}/recommendations",json={'source':'catalog'});catalog.raise_for_status();assert catalog.json()['graph']['status']=='connected'
    receipt['graph_relationship_count']=catalog.json()['graph']['relationship_count']
    receipt['search_runs']=[]
    for label in ('first','repeat'):
        started=time.perf_counter()
        r=client.post(f"/api/rooms/{room['id']}/visual-search",files={'file':('recorded-frame.jpg',frame,'image/jpeg')},data={'x':'.52','y':'.68'});r.raise_for_status();data=r.json()
        receipt['search_runs'].append({'run':label,'http_ms':round((time.perf_counter()-started)*1000,2),'performance':data['performance'],'selection':data['selection'],'product_count':len(data['products'])})
        assert data['graph']['status']=='connected'
        assert 0<len(data['products'])<=4
        assert all(p['source_url'].startswith('https://www.amazon.com/dp/') for p in data['products'])
    assert data['performance']['vision']['cache']['status']=='hit'
    assert data['performance']['search']['cache']['status']=='hit'
    assert client.get(f"/api/rooms/{room['id']}").json()['keep']==['sofa']
    receipt['passed']=True
(root/'docs/evidence/render-http-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),flush=True)

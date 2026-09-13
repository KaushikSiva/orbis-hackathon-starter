"""Opt-in real OpenAI/Exa cache benchmark against local HTTP. No Orbis or document writes."""
import json
import sys
import time
from pathlib import Path
from datetime import datetime,timezone
import httpx

if '--live' not in sys.argv:
    raise SystemExit('Pass --live to call OpenAI and Exa using the actual recorded test frame.')
root=Path(__file__).resolve().parents[1]
frame=(root/'backend/data/runtime/search-benchmark-frame.jpg').read_bytes()
with httpx.Client(base_url='http://127.0.0.1:8190',timeout=140) as client:
    response=client.post('/api/rooms',json={'name':'Search latency verification','budget':2500,'keep':['sofa'],'preferences':['Warm minimal','Natural textures']});response.raise_for_status();room=response.json()
    runs=[]
    for label in ['first_request','repeated_request']:
        started=time.perf_counter()
        response=client.post(f"/api/rooms/{room['id']}/visual-search",files={'file':('frame.jpg',frame,'image/jpeg')},data={'x':'.52','y':'.68'})
        assert response.is_success,(response.status_code,response.json())
        data=response.json();runs.append({'run':label,'http_ms':round((time.perf_counter()-started)*1000,2),'performance':data['performance'],'selection':data['selection'],'products':data['products']})
        print(json.dumps({k:v for k,v in runs[-1].items() if k!='products'}),flush=True)
    assert runs[1]['performance']['vision']['cache']['status']=='hit'
    assert runs[1]['performance']['search']['cache']['status']=='hit'
    assert 0<len(runs[1]['products'])<=4
    assert runs[0]['products']==runs[1]['products']
    report={'verified_at':datetime.now(timezone.utc).isoformat(),'providers':'actual OpenAI + Exa; same frame from prior actual Orbis recording','room_id':room['id'],'runs':runs,'external_document_writes':0}
    (root/'docs/evidence/search-latency-live.json').write_text(json.dumps(report,indent=2)+'\n')

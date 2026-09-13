"""Local contract tests. Mock provider responses are not live integration evidence."""
import io
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from backend import main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DATA', tmp_path)
    (tmp_path / 'uploads').mkdir()
    def no_graph(): raise RuntimeError('test graph offline')
    monkeypatch.setattr(main, 'graph_driver', no_graph)
    monkeypatch.setattr(main, 'setting', lambda key, default='': default if key.startswith('NEO4J') else '')
    return TestClient(main.app)


def room(client, **kwargs):
    data={'name':'Test room','budget':200,'preferences':['warm','natural'],'keep':['existing sofa']}
    data.update(kwargs)
    response=client.post('/api/rooms',json=data)
    assert response.status_code==201
    return response.json()


def products(client, rid):
    response=client.post(f'/api/rooms/{rid}/recommendations')
    assert response.status_code==200
    return response.json()


def test_budget_keep_and_persistence(client):
    r=room(client)
    r=products(client,r['id'])
    assert all(p['category']!='sofa' for p in r['products'])
    assert r['total']==sum(round(p['price']*100) for p in r['products'])/100
    assert r['total']<=r['budget']
    assert len({p['category'] for p in r['products']})==len(r['products'])
    assert r['graph']['status']=='fallback'
    assert client.get(f"/api/rooms/{r['id']}").json()==r
    changed=client.patch(f"/api/rooms/{r['id']}",json={'budget':30}).json()
    assert changed['keep']==['existing sofa'] and changed['products']==[]
    assert products(client,r['id'])['total']==29.99


def test_directives_preserve_constraints_and_only_accept_real_ack(client):
    r=room(client,budget=750)
    response=client.post(f"/api/rooms/{r['id']}/directives",json={'instruction':'Make the light warmer'})
    d=response.json()['directive']
    assert d['status']=='pending'
    assert '750.00' in d['prompt'] and 'existing sofa' in d['prompt']
    ack=client.post(f"/api/rooms/{r['id']}/directives/{d['id']}/ack",json={'status':'accepted'}).json()
    assert ack['directives'][0]['status']=='accepted'
    second=client.post(f"/api/rooms/{r['id']}/directives",json={'instruction':'Add natural texture'}).json()['directive']
    assert 'Make the light warmer' in second['prompt']


def test_upload_decode_and_token_missing_key(client):
    r=room(client)
    assert client.post('/api/reactor/token',json={'room_id':r['id']}).status_code==409
    url=f"/api/rooms/{r['id']}/image"
    assert client.post(url,files={'file':('x.jpg',b'not an image','image/jpeg')}).status_code==415
    data=io.BytesIO();Image.new('RGB',(64,64)).save(data,format='PNG')
    assert client.post(url,files={'file':('x.png',data.getvalue(),'image/png')}).status_code==200
    token=client.post('/api/reactor/token',json={'room_id':r['id']})
    assert token.status_code==503 and 'REACTOR_API_KEY' in token.json()['detail']
    assert 'jwt' not in client.get('/api/health').text


def test_export_requires_current_explicit_approval(client):
    r=products(client,room(client)['id'])
    preview=client.post(f"/api/rooms/{r['id']}/export-preview").json()
    assert 'Merchandise total' in preview['content']
    url=f"/api/rooms/{r['id']}/export"
    assert client.post(url,json={'approval_id':preview['approval_id']}).status_code==403
    client.patch(f"/api/rooms/{r['id']}",json={'budget':100})
    assert client.post(url,json={'approval_id':preview['approval_id'],'approved':True}).status_code==409


def test_export_retry_reads_same_returned_id(client,monkeypatch):
    r=products(client,room(client)['id'])
    preview=client.post(f"/api/rooms/{r['id']}/export-preview").json()
    calls=[]
    async def provider(provider, method,path,**kwargs):
        calls.append((method,path))
        if method=='POST':
            assert kwargs['json']['content']==preview['content']
            return {'id':'doc-contract-test','title':preview['title']}
        if len(calls)==2: raise HTTPException(502,'readback temporarily offline')
        return {'id':'doc-contract-test','title':preview['title'],'content':preview['content']}
    monkeypatch.setattr(main,'provider_request',provider)
    monkeypatch.setattr(main,'setting',lambda key,default='':'test-key')
    url=f"/api/rooms/{r['id']}/export";body={'approval_id':preview['approval_id'],'approved':True}
    assert client.post(url,json=body).status_code==502
    assert client.get(f"/api/rooms/{r['id']}").json()['exports'][0]['id']=='doc-contract-test'
    assert client.post(url,json=body).json()['exports'][0]['verified'] is True
    assert client.post(url,json=body).status_code==200
    assert sum(method=='POST' for method,path in calls)==1


def test_provider_failure_does_not_leak_key(client,monkeypatch):
    monkeypatch.setattr(main,'setting',lambda key,default='':'super-secret-contract-key')
    class Response:
        status_code=401
        def json(self): raise ValueError('Non-JSON provider error')
    class FakeClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def request(self,*args,**kwargs):return Response()
    monkeypatch.setattr(main.httpx,'AsyncClient',FakeClient)
    response=client.get('/api/ambiguous/documents')
    assert response.status_code==503
    assert 'super-secret' not in response.text


def test_invalid_budget(client):
    assert client.post('/api/rooms',json={'budget':-1}).status_code==422
    assert client.post('/api/rooms',json={'budget':1000001}).status_code==422


def test_uncertain_create_cannot_blindly_retry(client,monkeypatch):
    r=products(client,room(client)['id'])
    preview=client.post(f"/api/rooms/{r['id']}/export-preview").json()
    calls=[]
    async def provider(*args,**kwargs):
        calls.append(args)
        raise HTTPException(502,'Connection lost after request')
    monkeypatch.setattr(main,'provider_request',provider)
    monkeypatch.setattr(main,'setting',lambda key,default='':'test-key')
    url=f"/api/rooms/{r['id']}/export";body={'approval_id':preview['approval_id'],'approved':True}
    assert client.post(url,json=body).status_code==502
    response=client.post(url,json=body)
    assert response.status_code==409 and 'uncertain' in response.json()['detail']
    assert len(calls)==1


def test_content_mismatch_is_not_verified(client,monkeypatch):
    r=products(client,room(client)['id'])
    preview=client.post(f"/api/rooms/{r['id']}/export-preview").json()
    async def provider(provider,method,path,**kwargs):
        return {'id':'test-doc','title':preview['title'],'content':'Missing shopping list'}
    monkeypatch.setattr(main,'provider_request',provider)
    monkeypatch.setattr(main,'setting',lambda key,default='':'test-key')
    response=client.post(f"/api/rooms/{r['id']}/export",json={'approval_id':preview['approval_id'],'approved':True})
    assert response.status_code==200
    assert response.json()['exports'][0]['verified'] is False

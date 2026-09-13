"""Approval, recipient binding and invitation recovery tests; providers are mocked."""
import asyncio
import json
import httpx
from fastapi import HTTPException
from backend import main
from backend.test_main import client, products, room

EMAIL='owner@example.com'


def prepared(client, monkeypatch):
    current=products(client,room(client)['id'])
    monkeypatch.setattr(main,'setting',lambda name,default='': EMAIL if name=='SHOWROOM_SHARE_EMAIL' else 'test-key' if name=='AMBIGUOUS_API_KEY' else default)
    preview=client.post(f"/api/rooms/{current['id']}/export-preview").json()
    assert preview['share_recipient']==EMAIL
    return current,preview,{'approval_id':preview['approval_id'],'approved':True}


def provider_for(preview,calls,mode='pending'):
    invited=False
    async def provider(_provider,method,path,**kwargs):
        nonlocal invited
        calls.append((method,path,kwargs))
        if path.endswith('/permissions'):
            if not invited:return {'data':[],'pending':[]}
            return {'data':[{'user_id':'human-user','primary_email':EMAIL,'role':'viewer'}],'pending':[]} if mode=='direct' else {'data':[],'pending':[{'email':EMAIL,'role':'viewer','id':'pending-1'}]}
        if path.endswith('/share-invite'):
            assert kwargs['json']=={'email':EMAIL,'role':'viewer','invite_to_workspace':False}
            invited=True
            return {'granted':mode,'user_id':'human-user' if mode=='direct' else None,'pending_share_id':'pending-1'}
        return {'id':'shared-doc','title':preview['title'],'content':preview['content']}
    return provider


def test_share_after_approval_binds_recipient_and_creates_once(client,monkeypatch):
    current,preview,body=prepared(client,monkeypatch);calls=[]
    monkeypatch.setattr(main,'provider_request',provider_for(preview,calls))
    url=f"/api/rooms/{current['id']}/export"
    assert client.post(url,json={**body,'approved':False}).status_code==403
    assert calls==[]
    # Changing server configuration after review must not change the approved recipient.
    monkeypatch.setattr(main,'setting',lambda name,default='':'different@example.com' if name=='SHOWROOM_SHARE_EMAIL' else 'test-key')
    for _ in range(2):
        response=client.post(url,json=body);assert response.status_code==200
        item=response.json()['exports'][0];assert item['verified'] and item['sharing']['status']=='pending'
        assert item['sharing']['recipient']==EMAIL
    assert sum(method=='POST' and path=='/api/documents' for method,path,_ in calls)==1
    assert sum(method=='POST' and path.endswith('/share-invite') for method,path,_ in calls)==1


def test_direct_permission_verified_under_concurrent_approval(client,monkeypatch):
    current,preview,body=prepared(client,monkeypatch);calls=[]
    monkeypatch.setattr(main,'provider_request',provider_for(preview,calls,'direct'))
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://test') as api:
            return await asyncio.gather(*[api.post(f"/api/rooms/{current['id']}/export",json=body) for _ in range(3)])
    results=asyncio.run(run())
    assert all(r.json()['exports'][0]['sharing']['status']=='shared' for r in results)
    assert sum(method=='POST' for method,_,_ in calls)==2


def test_uncertain_invitation_checks_before_retry_and_never_duplicates(client,monkeypatch):
    current,preview,body=prepared(client,monkeypatch);calls=[];visible=False
    async def provider(_provider,method,path,**kwargs):
        calls.append((method,path))
        if path.endswith('/permissions'):return {'data':[],'pending':[{'email':EMAIL,'role':'viewer'}] if visible else []}
        if path.endswith('/share-invite'):
            with main.db() as con:stored=json.loads(con.execute('SELECT body FROM approvals WHERE id=?',(preview['approval_id'],)).fetchone()[0])
            assert stored['exports'][0]['sharing']['status']=='in_flight'
            raise HTTPException(502,'Connection lost after sending')
        return {'id':'shared-doc','title':preview['title'],'content':preview['content']}
    monkeypatch.setattr(main,'provider_request',provider)
    url=f"/api/rooms/{current['id']}/export"
    for _ in range(2):
        response=client.post(url,json=body);assert response.status_code==200
        assert response.json()['exports'][0]['verified']
        assert response.json()['exports'][0]['sharing']['status']=='uncertain'
    visible=True
    assert client.post(url,json=body).json()['exports'][0]['sharing']['status']=='pending'
    assert sum(method=='POST' for method,path in calls)==2


def test_sharing_rejection_can_retry_without_recreating_document(client,monkeypatch):
    current,preview,body=prepared(client,monkeypatch);calls=[];reject=True
    delegate=provider_for(preview,calls)
    async def provider(*args,**kwargs):
        if args[2].endswith('/share-invite') and reject:raise main.ProviderHTTPError(503,'Rejected',403,{})
        return await delegate(*args,**kwargs)
    monkeypatch.setattr(main,'provider_request',provider)
    url=f"/api/rooms/{current['id']}/export"
    assert client.post(url,json=body).json()['exports'][0]['sharing']['status']=='failed'
    reject=False
    assert client.post(url,json=body).json()['exports'][0]['sharing']['status']=='pending'
    assert sum(method=='POST' and path=='/api/documents' for method,path,_ in calls)==1


def test_unverified_content_does_not_send_invitation(client,monkeypatch):
    current,preview,body=prepared(client,monkeypatch);calls=[]
    async def provider(_provider,method,path,**kwargs):
        calls.append(path);return {'id':'wrong-content','title':preview['title'],'content':'Incomplete'}
    monkeypatch.setattr(main,'provider_request',provider)
    response=client.post(f"/api/rooms/{current['id']}/export",json=body)
    assert not response.json()['exports'][0]['verified']
    assert not any(path.endswith('/share-invite') for path in calls)


def test_invite_readback_failure_recovers_without_resending(client,monkeypatch):
    current,preview,body=prepared(client,monkeypatch);calls=[];fail_readback=True;invited=False
    delegate=provider_for(preview,calls)
    async def provider(*args,**kwargs):
        nonlocal invited
        if args[2].endswith('/permissions') and invited and fail_readback:raise HTTPException(502,'Readback offline')
        result=await delegate(*args,**kwargs)
        if args[2].endswith('/share-invite'):invited=True
        return result
    monkeypatch.setattr(main,'provider_request',provider)
    url=f"/api/rooms/{current['id']}/export"
    assert client.post(url,json=body).json()['exports'][0]['sharing']['status']=='unverified'
    fail_readback=False
    assert client.post(url,json=body).json()['exports'][0]['sharing']['status']=='pending'
    assert sum(method=='POST' for method,path,_ in calls)==2

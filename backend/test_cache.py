import asyncio
import pytest
from backend.cache import AsyncTTLCache
from backend import discovery, vision
from backend.test_discovery import listing


def test_cache_expiry_copy_isolation_and_bound():
    clock=[0];cache=AsyncTTLCache(ttl_seconds=10,max_entries=2,clock=lambda:clock[0]);calls=[]
    async def load():calls.append(1);return [{'price':49.99,'tags':[]}]
    async def run():
        first,status=await cache.get_or_load('a',load);assert status['status']=='miss'
        first[0]['tags'].append('changed')
        clock[0]=9;cached,status=await cache.get_or_load('a',load);assert status['status']=='hit' and cached[0]['tags']==[]
        clock[0]=10;await cache.get_or_load('a',load);assert len(calls)==2
        await cache.get_or_load('b',load);await cache.get_or_load('c',load);assert len(cache.entries)==2 and 'a' not in cache.entries
    asyncio.run(run())


def test_coalesced_requests_survive_one_waiter_cancelling():
    async def run():
        cache=AsyncTTLCache();ready=asyncio.Event();started=asyncio.Event();calls=[]
        async def load():calls.append(1);started.set();await ready.wait();return {'value':1}
        first=asyncio.create_task(cache.get_or_load('same',load));await started.wait()
        second=asyncio.create_task(cache.get_or_load('same',load));await asyncio.sleep(0);first.cancel()
        with pytest.raises(asyncio.CancelledError):await first
        ready.set();value,meta=await second
        assert value=={'value':1} and meta['status']=='shared' and len(calls)==1
        assert (await cache.get_or_load('same',load))[1]['status']=='hit'
    asyncio.run(run())


def test_failures_and_empty_results_are_not_cached():
    async def run():
        cache=AsyncTTLCache();calls=[]
        async def fail():calls.append(1);raise ValueError('retry')
        for _ in range(2):
            with pytest.raises(ValueError):await cache.get_or_load('a',fail)
        assert len(calls)==2 and not cache.pending
        async def empty():return []
        for _ in range(2):assert (await cache.get_or_load('empty',empty))[1]['status']=='miss'
    asyncio.run(run())


def test_search_cache_keys_and_timestamp_preservation(monkeypatch):
    import httpx
    calls=[];monkeypatch.setattr(discovery,'SEARCH_CACHE',AsyncTTLCache())
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):calls.append(kwargs);return httpx.Response(200,json={'results':[listing()]})
    monkeypatch.setattr(discovery.httpx,'AsyncClient',Client)
    async def run():
        room={'budget':500,'preferences':['warm','natural']};metrics={}
        first,_=await discovery.search_amazon('one','Oak table',room,metrics);assert metrics['cache']['status']=='miss'
        second,_=await discovery.search_amazon('one','  OAK   TABLE ',{**room,'preferences':['natural','warm']},metrics)
        assert metrics['cache']['status']=='hit' and first==second and len(calls)==1
        first[0]['price']=0
        assert (await discovery.search_amazon('one','oak table',room))[0][0]['price']==49.99
        for key,query,other in [('two','oak table',room),('one','white table',room),('one','oak table',{**room,'budget':100}),('one','oak table',{**room,'preferences':['minimal']})]:
            await discovery.search_amazon(key,query,other)
        assert len(calls)==5
    asyncio.run(run())


def test_visible_brand_and_colors_guide_visual_matches():
    raw={'label':'White lounge chair','item_type':'lounge chair','colors':['white'],'material':'wood','shape':'curved','brand':'IKEA','brand_evidence':'IKEA','brand_confidence':'readable'}
    identified=vision.selection_from_attributes(raw)
    assert identified['brand']=='IKEA' and 'IKEA white wood curved lounge chair'==identified['query']
    products=[{'name':'Black metal lounge chair'},{'name':'IKEA white wood curved lounge chair'}]
    ranked=vision.rank_visual_matches(products,identified)
    assert ranked[0]['name'].startswith('IKEA') and 'color: white' in ranked[0]['visual_match']['matched_attributes']
    for changes in [{'brand_confidence':'uncertain'},{'brand_evidence':''},{'brand_evidence':'unrelated logo'}]:
        selection=vision.selection_from_attributes({**raw,**changes})
        assert selection['brand'] is None and 'IKEA' not in selection['query']


def test_same_frame_reuses_identification_but_different_point_or_key_does_not(monkeypatch):
    from backend.test_vision import frame
    calls=[];monkeypatch.setattr(vision,'VISION_CACHE',AsyncTTLCache())
    async def identify(*args):calls.append(1);return {'label':'table','query':'oak table'}
    monkeypatch.setattr(vision,'identify_image',identify)
    async def run():
        metrics={};content=frame()
        await vision.identify_furniture('one',content,.5,.5,metrics);assert metrics['cache']['status']=='miss'
        await vision.identify_furniture('one',content,.5,.5,metrics);assert metrics['cache']['status']=='hit'
        await vision.identify_furniture('one',content,.8,.5)
        await vision.identify_furniture('two',content,.5,.5)
        assert len(calls)==3
    asyncio.run(run())

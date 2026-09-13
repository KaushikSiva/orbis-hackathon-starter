import asyncio
import io
import json
import httpx
import pytest
from PIL import Image
from fastapi import HTTPException
from backend import main, vision
from backend.test_main import client, room


@pytest.fixture(autouse=True)
def isolated_vision_cache(monkeypatch):
    monkeypatch.setattr(vision, 'VISION_CACHE', vision.AsyncTTLCache())


def frame():
    out=io.BytesIO();Image.new('RGB',(640,360),'tan').save(out,'JPEG');return out.getvalue()


def test_frame_validation_and_annotation():
    assert vision.prepare_frame(frame(),.2,.8).startswith('data:image/jpeg;base64,')
    for data,x,y,code in [(b'html',.5,.5,415),(frame(),2,.5,422),(b'',.5,.5,413)]:
        with pytest.raises(HTTPException) as error:vision.prepare_frame(data,x,y)
        assert error.value.status_code==code


def test_vision_contract_and_uncertain_selection(monkeypatch):
    observed={};found=True
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            observed.update(url=url,**kwargs)
            value={'found':found,'label':'Oak table','item_type':'side table' if found else '', 'colors':['brown'],'material':'oak','shape':'round','brand':'','brand_evidence':'','brand_confidence':'none'}
            return httpx.Response(200,json={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]})
    monkeypatch.setattr(vision.httpx,'AsyncClient',Client)
    result=asyncio.run(vision.identify_furniture('test-key',frame(),.5,.5))
    assert result['match_type']=='visually_similar'
    assert observed['url']=='https://api.openai.com/v1/responses'
    assert observed['json']['store'] is False and observed['json']['text']['format']['strict'] is True
    assert observed['json']['input'][0]['content'][1]['image_url'].startswith('data:image/jpeg;base64,')
    found=False
    vision.VISION_CACHE.clear()
    with pytest.raises(HTTPException) as error:asyncio.run(vision.identify_furniture('test-key',frame(),.5,.5))
    assert error.value.status_code==422


def test_visual_search_preserves_shopping_list_and_constraints(client,monkeypatch):
    current=room(client)
    async def identify(*args):return {'label':'Table','query':'oak table','match_type':'visually_similar'}
    async def search(*args):return [{'id':'amazon-test','name':'Oak table','category':'table','price':80,'source':'exa_amazon','source_url':'https://www.amazon.com/dp/B012345678'}], 'oak table'
    monkeypatch.setattr(main,'identify_furniture',identify);monkeypatch.setattr(main,'search_amazon',search)
    monkeypatch.setattr(main,'graph_driver',lambda: (_ for _ in ()).throw(RuntimeError('offline')))
    before=client.get(f"/api/rooms/{current['id']}").json()
    result=client.post(f"/api/rooms/{current['id']}/visual-search",files={'file':('frame.jpg',frame(),'image/jpeg')},data={'x':'.4','y':'.7'})
    assert result.status_code==200,result.text
    assert result.json()['products'][0]['price']==80
    assert client.get(f"/api/rooms/{current['id']}").json()==before
    client.patch(f"/api/rooms/{current['id']}",json={'keep':['existing table']})
    result=client.post(f"/api/rooms/{current['id']}/visual-search",files={'file':('frame.jpg',frame(),'image/jpeg')},data={'x':'.4','y':'.7'})
    assert result.status_code==404


def test_changed_brief_invalidates_visual_result(client,monkeypatch):
    current=room(client)
    async def identify(*args):
        changed=main.get_room(current['id']);changed['budget']=60;main.save_room(changed)
        return {'label':'Table','query':'oak table'}
    async def search(*args):return [],'oak table'
    monkeypatch.setattr(main,'identify_furniture',identify);monkeypatch.setattr(main,'search_amazon',search)
    result=client.post(f"/api/rooms/{current['id']}/visual-search",files={'file':('frame.jpg',frame(),'image/jpeg')},data={'x':'.4','y':'.7'})
    assert result.status_code==409

"""Provider contracts and untrusted listing validation; no external calls."""
import asyncio
import json
import httpx
import pytest
from fastapi import HTTPException
from backend import discovery, main
from backend.test_main import client, room


@pytest.fixture(autouse=True)
def isolated_search_cache(monkeypatch):
    monkeypatch.setattr(discovery, 'SEARCH_CACHE', discovery.AsyncTTLCache())


def listing(**changes):
    result={'url':'https://www.amazon.com/Table/dp/B012345678/ref=test','title':'Oak side table','text':'Current price $49.99. Dimensions: 20 x 20 x 18 inches.',
            'summary':json.dumps({'name':'Oak side table','category':'table','price':49.99,'currency':'USD','price_quote':'Current price $49.99.','dimensions':'20 x 20 x 18 inches'})}
    result.update(changes);return result


@pytest.mark.parametrize('url',['https://amazon.com.evil.test/dp/B012345678','http://www.amazon.com/dp/B012345678','https://www.amazon.com/s?k=table','javascript:alert(1)'])
def test_rejects_non_product_or_untrusted_urls(url):
    assert discovery.amazon_product(listing(url=url)) is None


def test_source_price_requires_verbatim_evidence():
    p=discovery.amazon_product(listing());assert p['price']==49.99 and p['source_url']=='https://www.amazon.com/dp/B012345678'
    p=discovery.amazon_product(listing(text='No price is available.'));assert p['price'] is None and p['price_quote'] is None and p['dimensions']=='Not provided by source'
    p=discovery.amazon_product(listing(summary='malformed'));assert p['price'] is None
    assert discovery.amazon_product(listing(image='https://fls-na.amazon.com/1/batch/tracking'))['image_url'] is None
    assert discovery.amazon_product(listing(image='https://m.media-amazon.com/images/I/product.jpg'))['image_url'].endswith('product.jpg')


def test_exa_contract_deduplicates_and_preserves_unknown_prices(monkeypatch):
    observed={}
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            observed.update(url=url,**kwargs)
            return httpx.Response(200,json={'results':[listing(),listing(),listing(url='https://www.amazon.com/dp/B987654321',text='No price.')]})
    monkeypatch.setattr(discovery.httpx,'AsyncClient',Client)
    products,query=asyncio.run(discovery.search_amazon('fake-key','side table',{'budget':500,'preferences':['warm']}))
    assert len(products)==2 and products[1]['price'] is None
    assert observed['json']['includeDomains']==['amazon.com'] and observed['json']['contents']['maxAgeHours']==6
    assert observed['json']['numResults']==4 and observed['json']['type']=='fast'
    assert observed['headers']=={'x-api-key':'fake-key'} and '500.00' in query
    limited,_=asyncio.run(discovery.search_amazon('fake-key','side table under $20',{'budget':500,'preferences':['warm']}))
    assert len(limited)==1 and limited[0]['price'] is None
    assert 'under $20.00 USD' in observed['json']['query']


def test_transcription_multipart_and_no_secret_in_errors(monkeypatch):
    observed={};status=200
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            observed.update(url=url,**kwargs);return httpx.Response(status,json={'text':'Find a warm lamp','error':'secret-value'})
    monkeypatch.setattr(discovery.httpx,'AsyncClient',Client)
    result=asyncio.run(discovery.transcribe_audio('secret-value',b'test-audio','audio/webm;codecs=opus'))
    assert result['text']=='Find a warm lamp' and observed['data']['model']=='gpt-4o-mini-transcribe'
    assert observed['files']['file']==('voice.webm',b'test-audio','audio/webm')
    assert observed['url']=='https://api.openai.com/v1/audio/transcriptions'
    status=401
    with pytest.raises(HTTPException) as error:asyncio.run(discovery.transcribe_audio('secret-value',b'test','audio/webm'))
    assert 'secret-value' not in error.value.detail


def test_missing_keys_and_invalid_audio_fail_honestly(client,monkeypatch):
    monkeypatch.setattr(main,'setting',lambda key,default='':default)
    current=room(client)
    result=client.post(f"/api/rooms/{current['id']}/recommendations",json={'source':'amazon','query':'lamp'})
    assert result.status_code==503 and 'EXA_API_KEY' in result.json()['detail']
    result=client.post('/api/transcriptions',files={'file':('audio.webm',b'test','audio/webm')})
    assert result.status_code==503 and 'OPENAI_API_KEY' in result.json()['detail']
    with pytest.raises(HTTPException) as error:asyncio.run(discovery.transcribe_audio('test',b'html','text/html'))
    assert error.value.status_code==415


def test_amazon_unknown_price_never_claims_zero_cost(client,monkeypatch):
    current=room(client)
    async def search(*args):return [discovery.amazon_product(listing(text='No quoted price'))], 'side table'
    monkeypatch.setattr(main,'search_amazon',search)
    # Force explicit graph fallback to test candidates without a live database.
    monkeypatch.setattr(main,'graph_driver',lambda: (_ for _ in ()).throw(RuntimeError('offline')))
    result=client.post(f"/api/rooms/{current['id']}/recommendations",json={'source':'amazon','query':'table'})
    assert result.status_code==200,result.text
    saved=result.json();assert saved['unpriced_count']==1 and saved['products'][0]['price'] is None
    assert 'Fits the available budget' not in saved['products'][0]['reason']
    preview=client.post(f"/api/rooms/{current['id']}/export-preview").json()
    assert 'Not quoted' in preview['content'] and 'Priced subtotal' in preview['content']
    assert 'IKEA US snapshot' not in preview['content']
    assert preview['shopping_rows'][-1][0] == 'Priced subtotal'
    changed=client.patch(f"/api/rooms/{current['id']}",json={'budget':600}).json()
    assert changed['unpriced_count']==0 and 'product_source' not in changed and 'search' not in changed


def test_search_intent_filters_unrelated_amazon_results():
    assert discovery.relevant_product({'name':'Solid oak side table'},'wood side table')
    assert not discovery.relevant_product({'name':'Govee TV Backlight 4 colors in 1 lamp bead'},'wood side table')
    assert not discovery.relevant_product({'name':'Starting from the middle Kindle edition'},'living room furniture')

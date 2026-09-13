"""Recovery tests use mocks. No provider writes occur in this test module."""
import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException

from backend import main
from backend.test_main import client, products, room


def uncertain_preview(client):
    current = products(client, room(client)['id'])
    preview = client.post(f"/api/rooms/{current['id']}/export-preview").json()
    with main.db() as con:
        approval = json.loads(con.execute('SELECT body FROM approvals WHERE id=?', (preview['approval_id'],)).fetchone()[0])
        approval['write_status'] = 'uncertain'
        con.execute('UPDATE approvals SET body=? WHERE id=?', (json.dumps(approval), preview['approval_id']))
    return current, preview


@pytest.mark.parametrize('listed', [
    {'data': [{'id': 'existing'}], 'has_more': False, 'total': 1},
    {'data': [], 'has_more': True, 'total': 0},
    {'data': [], 'total': 0},
])
def test_reconcile_refuses_existing_or_incomplete_lists(client, monkeypatch, listed):
    current, preview = uncertain_preview(client)
    calls = []
    async def provider(provider, method, path, **kwargs):
        calls.append(method)
        return listed
    monkeypatch.setattr(main, 'provider_request', provider)
    body = {'approval_id': preview['approval_id'], 'approved': True}
    response = client.post(f"/api/rooms/{current['id']}/export-reconcile", json=body)
    assert response.status_code == 409
    assert client.post(f"/api/rooms/{current['id']}/export", json=body).status_code == 409
    assert calls == ['GET']


def test_empty_reconciliation_does_not_write_then_reuses_exact_approval(client, monkeypatch):
    current, preview = uncertain_preview(client)
    calls = []
    async def provider(provider, method, path, **kwargs):
        calls.append((method, path))
        if path in ('/api/documents', '/api/activity') and method == 'GET':
            return {'data': [], 'has_more': False, 'total': 0}
        if method == 'POST':
            assert kwargs['json']['content'] == preview['content']
            assert kwargs['json']['visibility'] == 'restricted'
        return {'id': 'recovered-document', 'title': preview['title'], 'content': preview['content']}
    monkeypatch.setattr(main, 'provider_request', provider)
    monkeypatch.setattr(main, 'setting', lambda *args: 'test-only-key')
    body = {'approval_id': preview['approval_id'], 'approved': True}
    url = f"/api/rooms/{current['id']}"
    assert client.post(url + '/export', json=body).status_code == 409
    response = client.post(url + '/export-reconcile', json=body)
    assert response.status_code == 200
    assert response.json()['external_write_performed'] is False
    assert calls == [('GET', '/api/documents'), ('GET', '/api/activity')]
    assert client.post(url + '/export', json=body).json()['exports'][0]['verified']
    assert client.post(url + '/export', json=body).json()['exports'][0]['verified']
    assert [method for method, _ in calls] == ['GET', 'GET', 'POST', 'GET']


def test_provider_rejection_preserves_sanitized_status(client, monkeypatch):
    key = 'fake-secret-for-test'
    response = httpx.Response(422, json={'error': f'Invalid content; {key}', 'request_id': 'request-123'})
    class ProviderClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def request(self, *args, **kwargs): return response
    monkeypatch.setattr(main, 'setting', lambda name, default='': key if name=='AMBIGUOUS_API_KEY' else default)
    monkeypatch.setattr(main.httpx, 'AsyncClient', ProviderClient)
    with pytest.raises(main.ProviderHTTPError) as caught:
        asyncio.run(main.provider_request('ambiguous', 'POST', '/api/documents', json={}))
    assert caught.value.upstream_status == 422
    assert key not in str(caught.value.detail)
    assert caught.value.diagnostics['request_id'] == 'request-123'
    current = products(client, room(client)['id'])
    preview = client.post(f"/api/rooms/{current['id']}/export-preview").json()
    result = client.post(f"/api/rooms/{current['id']}/export", json={'approval_id': preview['approval_id'], 'approved': True})
    assert result.status_code == 502
    with main.db() as con:
        saved = json.loads(con.execute('SELECT body FROM approvals WHERE id=?', (preview['approval_id'],)).fetchone()[0])
    assert saved['write_status'] == 'rejected'
    assert saved['last_error']['upstream_status'] == 422
    assert key not in json.dumps(saved['last_error'])

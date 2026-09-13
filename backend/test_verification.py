"""Independent approval/concurrency checks. Providers are mocks, never live evidence."""
import asyncio

import httpx

from backend import main
from backend.test_main import client, products, room


def test_concurrent_approved_saves_create_once(client, monkeypatch):
    current = products(client, room(client)["id"])
    preview = client.post(f"/api/rooms/{current['id']}/export-preview").json()
    calls = []

    async def provider(provider, method, path, **kwargs):
        calls.append(method)
        await asyncio.sleep(0.025)
        return {"id": "concurrent-test-doc", "title": preview["title"], "content": preview["content"]}

    monkeypatch.setattr(main, "provider_request", provider)
    monkeypatch.setattr(main, "setting", lambda key, default="": "test-key")

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as api:
            return await asyncio.gather(*[
                api.post(f"/api/rooms/{current['id']}/export", json={"approval_id": preview["approval_id"], "approved": True})
                for _ in range(3)
            ])

    responses = asyncio.run(run())
    assert all(response.status_code == 200 for response in responses)
    assert calls == ["POST", "GET"]
    assert all(response.json()["exports"][0]["verified"] for response in responses)
    saved = client.get(f"/api/rooms/{current['id']}").json()
    assert len(saved["exports"]) == 1


def test_approval_cannot_export_another_room(client):
    original = products(client, room(client)["id"])
    other = products(client, room(client)["id"])
    preview = client.post(f"/api/rooms/{original['id']}/export-preview").json()
    response = client.post(f"/api/rooms/{other['id']}/export", json={"approval_id": preview["approval_id"], "approved": True})
    assert response.status_code == 404


def test_product_selection_change_invalidates_approval(client):
    current = products(client, room(client)["id"])
    preview = client.post(f"/api/rooms/{current['id']}/export-preview").json()
    client.patch(f"/api/rooms/{current['id']}", json={"keep": ["existing sofa", "existing rug"]})
    products(client, current["id"])
    response = client.post(f"/api/rooms/{current['id']}/export", json={"approval_id": preview["approval_id"], "approved": True})
    assert response.status_code == 409


def test_noop_patch_preserves_reviewable_products(client):
    current = products(client, room(client)["id"])
    same = {key: current[key] for key in ("name", "budget", "preferences", "keep")}
    response = client.patch(f"/api/rooms/{current['id']}", json=same)
    assert response.status_code == 200
    assert response.json() == current
    assert client.post(f"/api/rooms/{current['id']}/export-preview").status_code == 200

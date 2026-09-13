from backend.test_main import client


def test_hosted_studio_requires_signin_for_app_and_provider_routes(client,monkeypatch):
    monkeypatch.setenv('SHOWROOM_ACCESS_PASSWORD','test-private-password')
    for path in ['/','/api/ambiguous/documents','/api/reactor/token','/uploads/room.jpg']:
        response=client.get(path)
        assert response.status_code==401 and response.headers['www-authenticate'].startswith('Basic')
    assert client.get('/api/health').status_code==200
    assert client.get('/api/health',auth=('showroom','wrong')).status_code==200
    assert client.get('/api/ambiguous/documents',auth=('showroom','wrong')).status_code==401
    response=client.post('/api/rooms',auth=('showroom','test-private-password'),json={'name':'Private hosted room'})
    assert response.status_code==201


def test_required_hosting_auth_fails_closed_without_password(client,monkeypatch):
    monkeypatch.setenv('SHOWROOM_REQUIRE_AUTH','true');monkeypatch.delenv('SHOWROOM_ACCESS_PASSWORD',raising=False)
    assert client.get('/').status_code==503
    assert client.post('/api/rooms',json={'name':'not allowed'}).status_code==503


def test_malformed_authorization_does_not_crash(client,monkeypatch):
    monkeypatch.setenv('SHOWROOM_ACCESS_PASSWORD','test-private-password')
    for header in ['Basic !!!!','Basic Zm9v','Bearer token','Basic /w==']:
        assert client.get('/',headers={'Authorization':header}).status_code==401

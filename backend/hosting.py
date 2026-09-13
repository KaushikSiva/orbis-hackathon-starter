"""Password gate for the hosted studio; paid APIs and workspace documents stay private."""
import base64
import binascii
import hmac
import os
from starlette.responses import JSONResponse


def install_access_gate(app):
    @app.middleware('http')
    async def access_gate(request, call_next):
        password = os.environ.get('SHOWROOM_ACCESS_PASSWORD', '')
        required = os.environ.get('SHOWROOM_REQUIRE_AUTH', '').lower() == 'true'
        if request.url.path == '/api/health' and request.method == 'GET':
            return await call_next(request)
        if required and not password:
            return JSONResponse({'detail':'Hosted studio access is not configured.'},status_code=503)
        if password:
            try:
                kind, encoded = request.headers.get('authorization','').split(' ',1)
                user, supplied = base64.b64decode(encoded,validate=True).decode().split(':',1)
                allowed = kind.lower()=='basic' and hmac.compare_digest(user.encode(),b'showroom') and hmac.compare_digest(supplied.encode(),password.encode())
            except (ValueError,UnicodeDecodeError,binascii.Error):
                allowed = False
            if not allowed:
                return JSONResponse({'detail':'Sign in to the SHOWROOM studio.'},status_code=401,headers={'WWW-Authenticate':'Basic realm="SHOWROOM", charset="UTF-8"'})
        return await call_next(request)

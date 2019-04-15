from asgi_test_client import TestClient

import pytest


@pytest.fixture
def quart_app():
    from quart import Quart, jsonify

    app = Quart(__name__)

    @app.route("/")
    async def root():
        return b'full response'

    @app.route("/json")
    async def json():
        return jsonify({"hello": "world"})

    @app.route("/header")
    async def headers():
        return b"", 204, {'X-Header': 'Value'}

    yield app


@pytest.fixture
def starlette_app():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse, Response

    app = Starlette()

    @app.route('/')
    async def homepage(request):
        return Response('full response')

    @app.route("/json")
    async def json(request):
        return JSONResponse({'hello': 'world'})

    @app.route("/header")
    async def headers(request):
        return Response(status_code=204, headers={'X-Header': 'Value'})

    yield app


@pytest.mark.asyncio
async def test_test_client(quart_app, starlette_app):
    for app in (quart_app, starlette_app):
        tc = TestClient(app)
        status, _, resp = await tc.get("/")
        assert status == 200
        assert resp == b'full response'

        status, _, resp = await tc.get("/json")
        assert status == 200
        assert resp == {"hello": "world"}

        status, headers, resp = await tc.get("/header")
        assert status == 204
        assert headers['X-Header'] == 'Value'
        assert resp == b""

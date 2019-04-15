from asgi_test_client import TestClient

import pytest


@pytest.fixture
def quart_app():
    from quart import Quart, jsonify

    app = Quart(__name__)

    @app.before_serving
    async def open_database_connection_pool():
        app.custom_init_complete = True

    @app.route("/")
    async def root():
        return b"full response"

    @app.route("/json")
    async def json():
        return jsonify({"hello": "world"})

    @app.route("/header")
    async def headers():
        return b"", 204, {"X-Header": "Value"}

    @app.route("/before_serving_works")
    async def before_serving_works():
        if app.custom_init_complete:
            return b"yes"
        return b"no"

    yield app


@pytest.fixture
def starlette_app():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse, Response

    app = Starlette()

    @app.on_event("startup")
    async def open_database_connection_pool():
        app.custom_init_complete = True

    @app.route("/")
    async def homepage(request):
        return Response("full response")

    @app.route("/json")
    async def json(request):
        return JSONResponse({"hello": "world"})

    @app.route("/header")
    async def headers(request):
        return Response(status_code=204, headers={"X-Header": "Value"})

    @app.route("/before_serving_works")
    async def before_serving_works(request):
        if app.custom_init_complete:
            return Response("yes")
        return Response("no")

    yield app


@pytest.mark.asyncio
async def test_Quart_TestClient(quart_app):
    async with TestClient(quart_app) as client:
        status, _, resp = await client.get("/")
        assert status == 200
        assert resp == b"full response"

        status, _, resp = await client.get("/json")
        assert status == 200
        assert resp == {"hello": "world"}

        status, headers, resp = await client.get("/header")
        assert status == 204
        assert headers["X-Header"] == "Value"
        assert resp == b""

        status, _, resp = await client.get("/before_serving_works")
        assert status == 200
        assert resp == b"yes"


@pytest.mark.asyncio
async def test_Starlette_TestClient(starlette_app):
    async with TestClient(starlette_app) as client:
        status, _, resp = await client.get("/")
        assert status == 200
        assert resp == b"full response"

        status, _, resp = await client.get("/json")
        assert status == 200
        assert resp == {"hello": "world"}

        status, headers, resp = await client.get("/header")
        assert status == 204
        assert headers["X-Header"] == "Value"
        assert resp == b""

        status, _, resp = await client.get("/before_serving_works")
        assert status == 200
        assert resp == b"yes"

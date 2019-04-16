from asgi_test_client import TestClient

import pytest


@pytest.fixture
def quart_app():
    from quart import Quart, jsonify, request

    app = Quart(__name__)

    @app.before_serving
    async def startup():
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

    @app.route("/form", methods=["POST"])
    async def form():
        form = await request.form
        return jsonify(dict(form))

    @app.route("/check_startup_works")
    async def check_startup_works():
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
    async def startup():
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

    @app.route("/form", methods=["POST"])
    async def form(request):
        form = await request.form()
        return JSONResponse(form._dict)

    @app.route("/check_startup_works")
    async def check_startup_works(request):
        if app.custom_init_complete:
            return Response("yes")
        return Response("no")

    yield app


@pytest.mark.asyncio
async def test_Quart_TestClient(quart_app):
    async with TestClient(quart_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.text == "full response"

        resp = await client.get("/json")
        assert resp.status_code == 200
        assert resp.json() == {"hello": "world"}

        resp = await client.get("/header")
        assert resp.status_code == 204
        assert resp.headers["X-Header"] == "Value"
        assert resp.text == ""

        resp = await client.post("/form", form=[("user", "root"), ("pswd", 1234)])
        assert resp.json() == {"pswd": "1234", "user": "root"}

        resp = await client.get("/check_startup_works")
        assert resp.status_code == 200
        assert resp.text == "yes"


@pytest.mark.asyncio
async def test_Starlette_TestClient(starlette_app):
    async with TestClient(starlette_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.text == "full response"

        resp = await client.get("/json")
        assert resp.status_code == 200
        assert resp.json() == {"hello": "world"}

        resp = await client.get("/header")
        assert resp.status_code == 204
        assert resp.headers["X-Header"] == "Value"
        assert resp.text == ""

        # resp = await client.post("/form", form=[("user", "root"), ("pswd", 1234)])
        # assert resp.json() == {"pswd": "1234", "user": "root"}

        resp = await client.get("/check_startup_works")
        assert resp.status_code == 200
        assert resp.text == "yes"

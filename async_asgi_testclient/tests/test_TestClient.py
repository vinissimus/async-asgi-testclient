from async_asgi_testclient import TestClient

import pytest


@pytest.fixture
def quart_app():
    from quart import Quart, jsonify, request, Response

    app = Quart(__name__)

    @app.before_serving
    async def startup():
        app.custom_init_complete = True

    @app.route("/")
    async def root():
        return "full response"

    @app.route("/json")
    async def json():
        return jsonify({"hello": "world"})

    @app.route("/header")
    async def headers():
        return "", 204, {"X-Header": "Value"}

    @app.route("/form", methods=["POST"])
    async def form():
        form = await request.form
        return jsonify(dict(form))

    @app.route("/check_startup_works")
    async def check_startup_works():
        if app.custom_init_complete:
            return "yes"
        return "no"

    @app.route("/cookie", methods=["POST"])
    async def set_cookie():
        r = Response("")
        r.set_cookie(key="my-cookie", value="1234")
        return r

    @app.route("/cookie")
    async def get_cookie():
        cookies = request.cookies
        return jsonify(cookies)

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

    @app.route("/cookie", methods=["POST"])
    async def set_cookie(request):
        r = Response("")
        r.set_cookie("my-cookie", "1234")
        return r

    @app.route("/cookie")
    async def get_cookie(request):
        cookies = request.cookies
        return JSONResponse(cookies)

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

        resp = await client.post(
            "/cookie"
        )  # responds with 'set-cookie: my-cookie=1234'
        assert resp.status_code == 200
        assert resp.cookies == {"my-cookie": "1234"}

        resp = await client.get("/cookie")
        assert resp.status_code == 200
        assert resp.json() == {"my-cookie": "1234"}


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

        resp = await client.post("/form", form=[("user", "root"), ("pswd", 1234)])
        assert resp.json() == {"pswd": "1234", "user": "root"}

        resp = await client.get("/check_startup_works")
        assert resp.status_code == 200
        assert resp.text == "yes"

        resp = await client.post(
            "/cookie"
        )  # responds with 'set-cookie: my-cookie=1234'
        assert resp.status_code == 200

        resp = await client.get("/cookie")
        assert resp.status_code == 200
        assert resp.json() == {"my-cookie": "1234"}


@pytest.mark.asyncio
async def test_exception_capture(starlette_app):
    async def view_raiser(request):
        assert 1 == 0

    starlette_app.add_route("/raiser", view_raiser)

    async with TestClient(starlette_app) as client:
        resp = await client.get("/raiser")
        assert resp.status_code == 500


@pytest.mark.asyncio
async def test_exception_capture_release(starlette_app):
    async def view_raiser(request):
        assert 1 == 0

    starlette_app.add_route("/raiser", view_raiser)

    async with TestClient(starlette_app, raise_server_exceptions=True) as client:
        with pytest.raises(AssertionError):
            resp = await client.get("/raiser")

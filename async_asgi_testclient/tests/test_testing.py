from async_asgi_testclient import TestClient

import asyncio
import pytest


@pytest.fixture
def quart_app():
    from quart import Quart, jsonify, request, redirect, Response

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

    @app.route("/set_cookie", methods=["POST"])
    async def set_cookie():
        r = Response("")
        r.set_cookie(key="my-cookie", value="1234")
        return r

    @app.route("/cookie")
    async def get_cookie():
        cookies = request.cookies
        return jsonify(cookies)

    @app.route("/stuck")
    async def stuck():
        await asyncio.sleep(60)

    @app.route("/error")
    async def error():
        raise Exception("Error!")

    @app.route("/download_stream")
    async def down_stream():
        async def async_generator():
            chunk = b"X" * 1024
            for _ in range(3):
                yield chunk

        return async_generator()

    @app.route("/redir")
    async def redir():
        return redirect(request.args["path"])

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

    @app.route("/set_cookie", methods=["POST"])
    async def set_cookie(request):
        r = Response("")
        r.set_cookie("my-cookie", "1234")
        return r

    @app.route("/cookie")
    async def get_cookie(request):
        cookies = request.cookies
        return JSONResponse(cookies)

    @app.route("/stuck")
    async def stuck(request):
        await asyncio.sleep(60)

    yield app


@pytest.mark.asyncio
async def test_TestClient_Quart(quart_app):
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
            "/set_cookie"
        )  # responds with 'set-cookie: my-cookie=1234'
        assert resp.status_code == 200
        assert resp.cookies == {"my-cookie": "1234"}

        resp = await client.get("/cookie")
        assert resp.status_code == 200
        assert resp.json() == {"my-cookie": "1234"}


@pytest.mark.asyncio
async def test_TestClient_Starlette(starlette_app):
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
            "/set_cookie"
        )  # responds with 'set-cookie: my-cookie=1234'
        assert resp.status_code == 200

        resp = await client.get("/cookie")
        assert resp.status_code == 200
        assert resp.json() == {"my-cookie": "1234"}


@pytest.mark.asyncio
async def test_set_cookie_in_request(quart_app):
    async with TestClient(quart_app) as client:
        resp = await client.post(
            "/set_cookie"
        )  # responds with 'set-cookie: my-cookie=1234'
        assert resp.status_code == 200
        assert resp.cookies == {"my-cookie": "1234"}

        # Uses 'custom_cookie_jar' instead of 'client.cookie_jar'
        custom_cookie_jar = {"my-cookie": "6666"}
        resp = await client.get("/cookie", cookies=custom_cookie_jar)
        assert resp.status_code == 200
        assert resp.json() == custom_cookie_jar

        # Uses 'client.cookie_jar' again
        resp = await client.get("/cookie")
        assert resp.status_code == 200
        assert resp.json() == {"my-cookie": "1234"}


@pytest.mark.asyncio
async def test_disable_cookies_in_client(quart_app):
    async with TestClient(quart_app, use_cookies=False) as client:
        resp = await client.post(
            "/set_cookie"
        )  # responds with 'set-cookie: my-cookie=1234' but cookies are disabled
        assert resp.status_code == 200
        assert resp.cookies == {}


@pytest.mark.asyncio
async def test_exception_capture(starlette_app):
    async def view_raiser(request):
        assert 1 == 0

    starlette_app.add_route("/raiser", view_raiser)

    async with TestClient(starlette_app, raise_server_exceptions=False) as client:
        resp = await client.get("/raiser")
        assert resp.status_code == 500


@pytest.mark.asyncio
async def test_exception_capture_release(starlette_app):
    async def view_raiser(request):
        assert 1 == 0

    starlette_app.add_route("/raiser", view_raiser)

    async with TestClient(starlette_app) as client:
        with pytest.raises(AssertionError):
            await client.get("/raiser")


@pytest.mark.asyncio
async def test_quart_endpoint_not_responding(quart_app):
    async with TestClient(quart_app, timeout=0.1) as client:
        with pytest.raises(asyncio.TimeoutError):
            await client.get("/stuck")


@pytest.mark.asyncio
async def test_startlette_endpoint_not_responding(starlette_app):
    async with TestClient(starlette_app, timeout=0.1) as client:
        with pytest.raises(asyncio.TimeoutError):
            await client.get("/stuck")


@pytest.mark.asyncio
async def test_ensure_error_500(starlette_app):
    async def error(request):
        await asyncio.sleep(1)
        raise Exception("Error!")

    app = starlette_app
    app.add_route("/error", error)
    async with TestClient(app, raise_server_exceptions=False) as client:
        resp = await client.get("/error")
        assert resp.status_code == 500


@pytest.mark.asyncio
async def test_ensure_error_500_quart(quart_app):
    async with TestClient(quart_app) as client:
        resp = await client.get("/error")
        assert resp.status_code == 500


@pytest.mark.asyncio
async def test_response_stream(quart_app):
    async with TestClient(quart_app) as client:
        resp = await client.get("/download_stream", stream=True)
        assert resp.status_code == 200
        chunks = [c async for c in resp.iter_content(1024)]
        assert len(b"".join(chunks)) == 3 * 1024


@pytest.mark.asyncio
async def test_response_stream_crashes(starlette_app):
    from starlette.responses import StreamingResponse

    @starlette_app.route("/download_stream_crashes")
    async def stream_crashes(request):
        def gen():
            yield b'X' * 1024
            yield b'X' * 1024
            yield b'X' * 1024
            raise Exception("Stream crashed!")
        return StreamingResponse(gen())

    async with TestClient(starlette_app) as client:
        resp = await client.get("/download_stream_crashes", stream=True)
        assert resp.status_code == 200

        with pytest.raises(Exception):
            async for _ in resp.iter_content(1024):
                pass


@pytest.mark.asyncio
async def test_follow_redirects(quart_app):
    async with TestClient(quart_app) as client:
        resp = await client.get("/redir?path=/")
        assert resp.status_code == 200
        assert resp.text == "full response"

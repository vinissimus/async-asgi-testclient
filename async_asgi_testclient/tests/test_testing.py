from async_asgi_testclient import TestClient

import asyncio
import pytest
import sys

PY37 = sys.version_info >= (3, 7)


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

    @app.route("/set_cookies", methods=["POST"])
    async def set_cookie():
        r = Response("")
        r.set_cookie(key="my-cookie", value="1234")
        r.set_cookie(key="my-cookie-2", value="5678")
        return r

    @app.route("/clear_cookie", methods=["POST"])
    async def clear_cookie():
        r = Response("")
        r.delete_cookie(key="my-cookie")
        r.delete_cookie(key="my-cookie-2")
        return r

    @app.route("/cookies")
    async def get_cookie():
        cookies = request.cookies
        return jsonify(cookies)

    @app.route("/stuck")
    async def stuck():
        await asyncio.sleep(60)

    @app.route("/redir")
    async def redir():
        return redirect(request.args["path"])

    yield app


@pytest.fixture
def starlette_app():
    from starlette.applications import Starlette
    from starlette.endpoints import WebSocketEndpoint
    from starlette.responses import JSONResponse, Response

    app = Starlette()

    @app.on_event("startup")
    async def startup():
        app.custom_init_complete = True

    @app.websocket_route("/ws")
    class Echo(WebSocketEndpoint):

        encoding = "text"

        async def on_receive(self, websocket, data):
            await websocket.send_text(f"Message text was: {data}")

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

    @app.route("/set_cookies", methods=["POST"])
    async def set_cookie(request):
        r = Response("")
        r.set_cookie("my-cookie", "1234")
        r.set_cookie("my-cookie-2", "5678")
        return r

    @app.route("/clear_cookie", methods=["POST"])
    async def clear_cookie(request):
        r = Response("")
        r.delete_cookie("my-cookie")
        r.delete_cookie("my-cookie-2")
        return r

    @app.route("/cookies")
    async def get_cookie(request):
        cookies = request.cookies
        return JSONResponse(cookies)

    @app.route("/stuck")
    async def stuck(request):
        await asyncio.sleep(60)

    yield app


@pytest.mark.asyncio
@pytest.mark.skipif("PY37 != True")
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

        resp = await client.post("/set_cookies")
        assert resp.status_code == 200
        assert resp.cookies.get_dict() == {"my-cookie": "1234", "my-cookie-2": "5678"}

        resp = await client.get("/cookies")
        assert resp.status_code == 200
        assert resp.json() == {"my-cookie": "1234", "my-cookie-2": "5678"}

        resp = await client.post("/clear_cookie")
        assert resp.cookies.get_dict() == {"my-cookie": "", "my-cookie-2": ""}
        assert resp.status_code == 200


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

        resp = await client.post("/set_cookies")
        assert resp.status_code == 200
        assert resp.cookies.get_dict() == {"my-cookie": "1234", "my-cookie-2": "5678"}

        resp = await client.get("/cookies")
        assert resp.status_code == 200
        assert resp.json() == {"my-cookie": "1234", "my-cookie-2": "5678"}

        resp = await client.post("/clear_cookie")
        assert resp.cookies.get_dict() == {"my-cookie": "", "my-cookie-2": ""}
        assert resp.status_code == 200


@pytest.mark.asyncio
@pytest.mark.skipif("PY37 != True")
async def test_set_cookie_in_request(quart_app):
    async with TestClient(quart_app) as client:
        resp = await client.post("/set_cookies")
        assert resp.status_code == 200
        assert resp.cookies.get_dict() == {"my-cookie": "1234", "my-cookie-2": "5678"}

        # Uses 'custom_cookie_jar' instead of 'client.cookie_jar'
        custom_cookie_jar = {"my-cookie": "6666"}
        resp = await client.get("/cookies", cookies=custom_cookie_jar)
        assert resp.status_code == 200
        assert resp.json() == custom_cookie_jar

        # Uses 'client.cookie_jar' again
        resp = await client.get("/cookies")
        assert resp.status_code == 200
        assert resp.json() == {"my-cookie": "1234", "my-cookie-2": "5678"}


@pytest.mark.asyncio
@pytest.mark.skipif("PY37 != True")
async def test_disable_cookies_in_client(quart_app):
    async with TestClient(quart_app, use_cookies=False) as client:
        resp = await client.post(
            "/set_cookies"
        )  # responds with 'set-cookie: my-cookie=1234' but cookies are disabled
        assert resp.status_code == 200
        assert resp.cookies.get_dict() == {}


@pytest.mark.asyncio
async def test_exception_starlette(starlette_app):
    async def view_raiser(request):
        assert 1 == 0

    starlette_app.add_route("/raiser", view_raiser)

    async with TestClient(starlette_app) as client:
        with pytest.raises(AssertionError):
            await client.get("/raiser")


@pytest.mark.asyncio
@pytest.mark.skipif("PY37 != True")
async def test_exception_quart(quart_app):
    @quart_app.route("/raiser")
    async def error():
        assert 1 == 0

    async with TestClient(quart_app) as client:
        resp = await client.get("/raiser")
        # Quart suppresses all type of exceptions
        assert resp.status_code == 500


@pytest.mark.asyncio
@pytest.mark.skipif("PY37 != True")
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
async def test_ws_endpoint(starlette_app):
    async with TestClient(starlette_app, timeout=0.1) as client:
        async with client.websocket_connect("/ws") as ws:
            await ws.send_str("hi!")
            msg = await ws.receive_text()
            assert msg == "Message text was: hi!"


@pytest.mark.asyncio
async def test_request_stream(starlette_app):
    from starlette.responses import StreamingResponse

    async def up_stream(request):
        async def gen():
            async for chunk in request.stream():
                yield chunk

        return StreamingResponse(gen())

    starlette_app.add_route("/upload_stream", up_stream, methods=["POST"])

    async with TestClient(starlette_app) as client:

        async def stream_gen():
            chunk = b"X" * 1024
            for _ in range(3):
                yield chunk

        resp = await client.post("/upload_stream", data=stream_gen(), stream=True)
        assert resp.status_code == 200
        chunks = [c async for c in resp.iter_content(1024)]
        assert len(b"".join(chunks)) == 3 * 1024


@pytest.mark.asyncio
async def test_upload_stream_from_download_stream(starlette_app):
    from starlette.responses import StreamingResponse

    async def down_stream(request):
        def gen():
            for _ in range(3):
                yield b"X" * 1024

        return StreamingResponse(gen())

    async def up_stream(request):
        async def gen():
            async for chunk in request.stream():
                yield chunk

        return StreamingResponse(gen())

    starlette_app.add_route("/download_stream", down_stream, methods=["GET"])
    starlette_app.add_route("/upload_stream", up_stream, methods=["POST"])

    async with TestClient(starlette_app) as client:
        resp = await client.get("/download_stream", stream=True)
        assert resp.status_code == 200
        resp2 = await client.post(
            "/upload_stream", data=resp.iter_content(1024), stream=True
        )
        chunks = [c async for c in resp2.iter_content(1024)]
        assert len(b"".join(chunks)) == 3 * 1024


@pytest.mark.asyncio
@pytest.mark.skipif("PY37 != True")
async def test_response_stream(quart_app):
    @quart_app.route("/download_stream")
    async def down_stream():
        async def async_generator():
            chunk = b"X" * 1024
            for _ in range(3):
                yield chunk

        return async_generator()

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
            yield b"X" * 1024
            yield b"X" * 1024
            yield b"X" * 1024
            raise Exception("Stream crashed!")

        return StreamingResponse(gen())

    async with TestClient(starlette_app) as client:
        resp = await client.get("/download_stream_crashes", stream=True)
        assert resp.status_code == 200

        with pytest.raises(Exception):
            async for _ in resp.iter_content(1024):
                pass


@pytest.mark.asyncio
@pytest.mark.skipif("PY37 != True")
async def test_follow_redirects(quart_app):
    async with TestClient(quart_app) as client:
        resp = await client.get("/redir?path=/")
        assert resp.status_code == 200
        assert resp.text == "full response"


@pytest.mark.asyncio
@pytest.mark.skipif("PY37 != True")
async def test_no_follow_redirects(quart_app):
    async with TestClient(quart_app) as client:
        resp = await client.get("/redir?path=/", allow_redirects=False)
        assert resp.status_code == 302

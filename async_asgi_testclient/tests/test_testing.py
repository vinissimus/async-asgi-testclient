import ast
import asyncio
import io
from http.cookies import SimpleCookie
from json import dumps
from sys import version_info as PY_VER  # noqa

import pytest
import starlette.status
from quart import Quart, Response, jsonify, redirect, request, websocket
from starlette.responses import RedirectResponse, StreamingResponse

from async_asgi_testclient import TestClient


@pytest.fixture
def quart_app():  # noqa: C901

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

    @app.route("/cookies-raw")
    async def get_cookie_raw():
        return Response(request.headers["Cookie"])

    @app.route("/stuck")
    async def stuck():
        await asyncio.sleep(60)

    @app.route("/redir")
    async def redir():
        return redirect(request.args["path"])

    @app.route("/echoheaders")
    async def echoheaders():
        return "", 200, request.headers

    @app.route("/test_query")
    async def test_query():
        return Response(request.query_string)

    @app.websocket("/ws")
    async def websocket_endpoint():
        data = await websocket.receive()
        if data == "cookies":
            await websocket.send(dumps(websocket.cookies))
        elif data == "url":
            await websocket.send(str(websocket.url))
        else:
            await websocket.send(f"Message text was: {data}")

    @app.websocket("/ws-reject")
    async def websocket_reject():
        await websocket.close(
            code=starlette.status.WS_1003_UNSUPPORTED_DATA, reason="some reason"
        )

    yield app


@pytest.fixture
def starlette_app():  # noqa: C901
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
            if data == "cookies":
                await websocket.send_text(dumps(websocket.cookies))
            elif data == "url":
                await websocket.send_text(str(websocket.url))
            else:
                await websocket.send_text(f"Message text was: {data}")

    @app.websocket_route("/ws-reject")
    async def websocket_reject(websocket):
        # Send immediate close message to the client, using non default 100 code to test return of correct code
        await websocket.close(starlette.status.WS_1003_UNSUPPORTED_DATA)

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

    @app.route("/multipart", methods=["POST"])
    async def multipart(request):
        form = await request.form()
        return JSONResponse(form._dict)

    @app.route("/multipart_bin", methods=["POST"])
    async def multipart_bin(request):
        form = await request.form()
        assert form["a"] == "\x89\x01\x02\x03\x04"

        file_b = form["b"]
        assert file_b.filename == "b.bin"
        assert await file_b.read() == b"\x89\x01\x02\x03\x04"

        file_c = form["c"]
        assert file_c.filename == "c.txt"
        assert file_c.content_type == "text/plain"
        assert await file_c.read() == b"01234"

        return Response(status_code=200)

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

    @app.route("/cookies-raw")
    async def get_cookie_raw(request):
        return Response(request.headers["Cookie"])

    @app.route("/stuck")
    async def stuck(request):
        await asyncio.sleep(60)

    @app.route("/echoheaders")
    async def echoheaders(request):
        return Response(headers=request.headers)

    @app.route("/test_query")
    async def test_query(request):
        return Response(str(request.query_params))

    @app.route("/redir")
    async def redir(request):
        return RedirectResponse(request.query_params["path"], status_code=302)

    yield app


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
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

        resp = await client.get("/cookies-raw")
        assert resp.status_code == 200
        assert resp.text == "my-cookie=1234; my-cookie-2=5678"

        resp = await client.post("/clear_cookie")
        assert resp.cookies.get_dict() == {"my-cookie": "", "my-cookie-2": ""}
        assert resp.status_code == 200

        client.headers = {"Authorization": "mytoken"}
        resp = await client.get("/echoheaders", headers={"this should be": "merged"})
        assert resp.status_code == 200
        assert resp.headers.get("authorization") == "mytoken"
        assert resp.headers.get("this should be") == "merged"
        # Reset client headers for next tests
        client.headers = {}

        resp = await client.get("/echoheaders")
        assert resp.status_code == 200
        assert "Authorization" not in resp.headers

        resp = await client.get("/test_query", query_string={"a": 1, "b": "ç"})
        assert resp.status_code == 200
        assert resp.text == "a=1&b=%C3%A7"

        resp = await client.get("/test_query?a=1&b=ç")
        assert resp.status_code == 200
        assert resp.text == "a=1&b=%C3%A7"


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

        file_like = io.StringIO("abcd")
        resp = await client.post("/multipart", files={"a": "abcd", "b": (file_like,)})
        assert resp.json() == {"a": "abcd", "b": "abcd"}

        file_like_1 = io.BytesIO(bytes([0x89, 1, 2, 3, 4]))
        file_like_2 = io.BytesIO(bytes([0x89, 1, 2, 3, 4]))
        file_like_3 = io.BytesIO(bytes("01234", "ascii"))
        resp = await client.post(
            "/multipart_bin",
            files={
                "a": (file_like_1,),
                "b": ("b.bin", file_like_2),
                "c": ("c.txt", file_like_3, "text/plain"),
            },
        )
        assert resp.status_code == 200

        resp = await client.get("/check_startup_works")
        assert resp.status_code == 200
        assert resp.text == "yes"

        resp = await client.post("/set_cookies")
        assert resp.status_code == 200
        assert resp.cookies.get_dict() == {"my-cookie": "1234", "my-cookie-2": "5678"}

        resp = await client.get("/cookies")
        assert resp.status_code == 200
        assert resp.json() == {"my-cookie": "1234", "my-cookie-2": "5678"}

        resp = await client.get("/cookies-raw")
        assert resp.status_code == 200
        assert resp.text == "my-cookie=1234; my-cookie-2=5678"

        resp = await client.post("/clear_cookie")
        assert resp.cookies.get_dict() == {"my-cookie": "", "my-cookie-2": ""}
        assert resp.status_code == 200

        client.headers = {"Authorization": "mytoken"}
        resp = await client.get("/echoheaders", headers={"this should be": "merged"})
        assert resp.status_code == 200
        assert resp.headers.get("authorization") == "mytoken"
        assert resp.headers.get("this should be") == "merged"
        # Reset client headers for next tests
        client.headers = {}

        resp = await client.get("/echoheaders")
        assert resp.status_code == 200
        assert "authorization" not in resp.headers

        resp = await client.get("/test_query", query_string={"a": 1, "b": "ç"})
        assert resp.status_code == 200
        assert resp.text == "a=1&b=%C3%A7"

        resp = await client.get("/test_query?a=1&b=ç")
        assert resp.status_code == 200
        assert resp.text == "a=1&b=%C3%A7"


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
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

        resp = await client.get("/cookies-raw")
        assert resp.status_code == 200
        assert resp.text == "my-cookie=1234; my-cookie-2=5678"


@pytest.mark.asyncio
async def test_set_cookie_in_request_starlette(starlette_app):
    async with TestClient(starlette_app) as client:
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

        resp = await client.get("/cookies-raw")
        assert resp.status_code == 200
        assert resp.text == "my-cookie=1234; my-cookie-2=5678"


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
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
@pytest.mark.skipif("PY_VER < (3,7)")
async def test_exception_quart(quart_app):
    @quart_app.route("/raiser")
    async def error():
        assert 1 == 0

    async with TestClient(quart_app) as client:
        resp = await client.get("/raiser")
        # Quart suppresses all type of exceptions
        assert resp.status_code == 500


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
async def test_quart_endpoint_not_responding(quart_app):
    async with TestClient(quart_app, timeout=0.1) as client:
        with pytest.raises(asyncio.TimeoutError):
            await client.get("/stuck")


@pytest.mark.asyncio
async def test_starlette_endpoint_not_responding(starlette_app):
    async with TestClient(starlette_app, timeout=0.1) as client:
        with pytest.raises(asyncio.TimeoutError):
            await client.get("/stuck")


@pytest.mark.asyncio
async def test_ws_endpoint(starlette_app):
    async with TestClient(starlette_app, timeout=0.1) as client:
        async with client.websocket_connect("/ws") as ws:
            await ws.send_text("hi!")
            msg = await ws.receive_text()
            assert msg == "Message text was: hi!"


@pytest.mark.asyncio
async def test_ws_endpoint_cookies(starlette_app):
    async with TestClient(starlette_app, timeout=0.1) as client:
        async with client.websocket_connect("/ws", cookies={"session": "abc"}) as ws:
            await ws.send_text("cookies")
            msg = await ws.receive_json()
            assert msg == {"session": "abc"}


@pytest.mark.asyncio
async def test_ws_connect_inherits_test_client_cookies(starlette_app):
    client = TestClient(starlette_app, use_cookies=True, timeout=0.1)
    client.cookie_jar = SimpleCookie({"session": "abc"})
    async with client:
        async with client.websocket_connect("/ws") as ws:
            await ws.send_text("cookies")
            msg = await ws.receive_text()
            assert msg == '{"session": "abc"}'


@pytest.mark.asyncio
async def test_ws_connect_default_scheme(starlette_app):
    async with TestClient(starlette_app, timeout=0.1) as client:
        async with client.websocket_connect("/ws") as ws:
            await ws.send_text("url")
            msg = await ws.receive_text()
            assert msg.startswith("ws://")


@pytest.mark.asyncio
async def test_ws_connect_custom_scheme(starlette_app):
    async with TestClient(starlette_app, timeout=0.1) as client:
        async with client.websocket_connect("/ws", scheme="wss") as ws:
            await ws.send_text("url")
            msg = await ws.receive_text()
            assert msg.startswith("wss://")


@pytest.mark.asyncio
async def test_ws_endpoint_with_immediate_rejection(starlette_app):
    async with TestClient(starlette_app, timeout=0.1) as client:
        try:
            async with client.websocket_connect("/ws-reject"):
                pass
        except Exception as e:
            thrown_exception = e

        assert ast.literal_eval(str(thrown_exception)) == {
            "type": "websocket.close",
            "code": starlette.status.WS_1003_UNSUPPORTED_DATA,
            "reason": ""
        }


@pytest.mark.asyncio
async def test_invalid_ws_endpoint(starlette_app):
    async with TestClient(starlette_app, timeout=0.1) as client:
        try:
            async with client.websocket_connect("/invalid"):
                pass
        except Exception as e:
            thrown_exception = e

        assert ast.literal_eval(str(thrown_exception)) == {
            "type": "websocket.close",
            "code": starlette.status.WS_1000_NORMAL_CLOSURE,
            "reason": ""
        }


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
async def test_quart_ws_endpoint(quart_app):
    async with TestClient(quart_app, timeout=0.1) as client:
        async with client.websocket_connect("/ws") as ws:
            await ws.send_text("hi!")
            msg = await ws.receive_text()
            assert msg == "Message text was: hi!"


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
async def test_quart_ws_endpoint_cookies(quart_app):
    async with TestClient(quart_app, timeout=0.1) as client:
        async with client.websocket_connect("/ws", cookies={"session": "abc"}) as ws:
            await ws.send_text("cookies")
            msg = await ws.receive_json()
            assert msg == {"session": "abc"}


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
async def test_quart_ws_connect_inherits_test_client_cookies(quart_app):
    client = TestClient(quart_app, use_cookies=True, timeout=0.1)
    client.cookie_jar = SimpleCookie({"session": "abc"})
    async with client:
        async with client.websocket_connect("/ws") as ws:
            await ws.send_text("cookies")
            msg = await ws.receive_text()
            assert msg == '{"session": "abc"}'


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
async def test_quart_ws_connect_default_scheme(quart_app):
    async with TestClient(quart_app, timeout=0.1) as client:
        async with client.websocket_connect("/ws") as ws:
            await ws.send_text("url")
            msg = await ws.receive_text()
            assert msg.startswith("ws://")


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
async def test_quart_ws_connect_custom_scheme(quart_app):
    async with TestClient(quart_app, timeout=0.1) as client:
        async with client.websocket_connect("/ws", scheme="wss") as ws:
            await ws.send_text("url")
            msg = await ws.receive_text()
            assert msg.startswith("wss://")


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
async def test_quart_ws_endpoint_with_immediate_rejection(quart_app):
    async with TestClient(quart_app, timeout=0.1) as client:
        try:
            async with client.websocket_connect("/ws-reject"):
                pass
        except Exception as e:
            thrown_exception = e

        assert ast.literal_eval(str(thrown_exception)) == {
            "type": "websocket.close",
            "code": starlette.status.WS_1003_UNSUPPORTED_DATA,
        }


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
async def test_quart_invalid_ws_endpoint(quart_app):
    async with TestClient(quart_app, timeout=0.1) as client:
        try:
            async with client.websocket_connect("/invalid"):
                pass
        except Exception as e:
            thrown_exception = e

        assert ast.literal_eval(str(thrown_exception)) == {
            "type": "websocket.close",
            "code": starlette.status.WS_1000_NORMAL_CLOSURE,
        }


# @pytest.mark.asyncio
# async def test_request_stream(starlette_app):
#     print('coucou')

#     async def up_stream(request):
#         from starlette.responses import StreamingResponse

#         async def gen():
#             print('gen')
#             async for chunk in request.stream():
#                 print('resprespresp')
#                 yield chunk

#         return StreamingResponse(gen())

#     print('upload_stream_rout')
#     starlette_app.add_route("/upload_stream", up_stream, methods=["POST"])

#     async with TestClient(starlette_app) as client:
#         async def stream_gen():
#             print('here')
#             chunk = b"X" * 1024
#             for _ in range(3):
#                 print('one two three')
#                 yield chunk

#         print('coucou1')
#         resp = await client.post("/upload_stream", data=stream_gen(), stream=True)
#         print('coucou2')
#         assert resp.status_code == 200
#         chunks = [c async for c in resp.iter_content(1024)]
#         assert len(b"".join(chunks)) == 3 * 1024


# @pytest.mark.asyncio
# async def test_upload_stream_from_download_stream(starlette_app):
#     from starlette.responses import StreamingResponse

#     async def down_stream(request):
#         def gen():
#             for _ in range(3):
#                 yield b"X" * 1024

#         return StreamingResponse(gen())

#     async def up_stream(request):
#         async def gen():
#             async for chunk in request.stream():
#                 yield chunk

#         return StreamingResponse(gen())

#     starlette_app.add_route("/download_stream", down_stream, methods=["GET"])
#     starlette_app.add_route("/upload_stream", up_stream, methods=["POST"])

#     async with TestClient(starlette_app) as client:
#         resp = await client.get("/download_stream", stream=True)
#         assert resp.status_code == 200
#         resp2 = await client.post(
#             "/upload_stream", data=resp.iter_content(1024), stream=True
#         )
#         chunks = [c async for c in resp2.iter_content(1024)]
#         assert len(b"".join(chunks)) == 3 * 1024


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
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
async def test_response_stream_starlette(starlette_app):
    @starlette_app.route("/download_stream")
    async def down_stream(_):
        async def async_generator():
            chunk = b"X" * 1024
            for _ in range(3):
                yield chunk

        return StreamingResponse(async_generator())

    async with TestClient(starlette_app) as client:
        resp = await client.get("/download_stream", stream=False)
        assert resp.status_code == 200
        assert len(resp.content) == 3 * 1024


@pytest.mark.asyncio
async def test_response_stream_crashes_starlette(starlette_app):
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

        with pytest.raises(Exception):  # noqa: B017
            async for _ in resp.iter_content(1024):
                pass


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
async def test_follow_redirects(quart_app):
    async with TestClient(quart_app) as client:
        resp = await client.get("/redir?path=/")
        assert resp.status_code == 200
        assert resp.text == "full response"


@pytest.mark.asyncio
@pytest.mark.skipif("PY_VER < (3,7)")
async def test_no_follow_redirects(quart_app):
    async with TestClient(quart_app) as client:
        resp = await client.get("/redir?path=/", allow_redirects=False)
        assert resp.status_code == 302


@pytest.mark.asyncio
async def test_follow_redirects_starlette(starlette_app):
    async with TestClient(starlette_app) as client:
        resp = await client.get("/redir?path=/")
        assert resp.status_code == 200
        assert resp.text == "full response"


@pytest.mark.asyncio
async def test_no_follow_redirects_starlette(starlette_app):
    async with TestClient(starlette_app) as client:
        resp = await client.get("/redir?path=/", allow_redirects=False)
        assert resp.status_code == 302

"""ASGI spec websocket tests

Tests to verify conformance with the ASGI specification. This module tests
the websocket protocol.

These tests attempt to make sure that TestClient conforms to
the ASGI specification documented at
https://asgi.readthedocs.io/en/latest/specs/main.html
"""

from async_asgi_testclient import TestClient
from multidict import CIMultiDict
from urllib.parse import quote

import pytest


@pytest.mark.asyncio
async def test_asgi_version_is_present_in_websocket_scope(mock_app):
    """
    The key scope["asgi"] will also be present as a dictionary containing a scope["asgi"]["version"] key
    that corresponds to the ASGI version the server implements.
    https://asgi.readthedocs.io/en/latest/specs/main.html#applications

    We expect this to be version 3.0, as that is the current spec version.
    """

    async def handle_all(scope, receive, send):
        if scope["type"] == "websocket":
            assert "asgi" in scope
            assert scope["asgi"]["version"] == "3.0"

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        async with client.websocket_connect("/ws") as ws:
            await ws.send_text("hello there")
            await ws.close(code=1000)


@pytest.mark.asyncio
async def test_websocket_spec_version_is_missing_or_correct(mock_app):
    """
    asgi["spec_version"] (Unicode string) – Version of the ASGI HTTP spec this server
     understands; one of "2.0" or "2.1". Optional; if missing assume 2.0
    https://asgi.readthedocs.io/en/latest/specs/www.html#websocket-connection-scope

    TestClient doesn't specify spec_version at the moment, which is also okay.
    Note that if newer features are added (eg websocket headers in Accept, reason
     parameter to websocket.close) then the spec_version needs to be passed correctly.
    """

    async def handle_all(scope, receive, send):
        if scope["type"] == "websocket":
            assert (
                "spec_version" not in scope["asgi"]
                or scope["asgi"]["spec_version"] == "2.0"
            )

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        async with client.websocket_connect("/ws") as ws:
            await ws.send_text("hello there")
            await ws.close(code=1000)


@pytest.mark.asyncio
async def test_http_version_is_1_1_or_missing(mock_app):
    """
    http_version (Unicode string) – One of "1.1" or "2".
     Optional; if missing default is "1.1".
    https://asgi.readthedocs.io/en/latest/specs/www.html#websocket-connection-scope
    Interestingly, the ASGI spec does not require http_version for websocket
    (but does require it for http)
    """

    async def handle_all(scope, receive, send):
        if scope["type"] == "websocket":
            assert "http_version" not in scope or scope["http_version"] == "1.1"

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        async with client.websocket_connect("/ws") as ws:
            await ws.send_text("hello there")
            await ws.close(code=1000)


# Ok, this one I'm not sure about...
# The grey area here is TestClient doesn't currently decode an encoded URL; but should it?
# ASGI servers do, but then they're receiving the encoded URL from the web browser, and it is
# encoded because the HTTP protocol requires it...on the other hand, the query string is
# encoded from raw, and passed in encoded form...
# For now, mark this as xfail, but possibly we rewrite the test to say current behaviour is correct. TBD.
@pytest.mark.xfail(
    AssertionError,
    reason="TBD - this might be the correct behaviour, and the test is wrong",
)
@pytest.mark.asyncio
async def test_http_path_is_not_escaped(mock_app):
    """
    path (Unicode string) – HTTP request target excluding any query string, with percent-encoded
     sequences and UTF-8 byte sequences decoded into characters.
    https://asgi.readthedocs.io/en/latest/specs/www.html#websocket-connection-scope
    Path is decoded in the scope, with UTF-8 byte sequences properly decoded as well.
    """

    crazy_path = "/crazy.request with spaces and,!%/\xef/"
    encoded_path = quote(crazy_path, encoding="utf-8")

    async def handle_all(scope, receive, send):
        if scope["type"] == "websocket":
            assert scope["path"] == crazy_path

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        async with client.websocket_connect(encoded_path) as ws:
            await ws.send_text("hello there")
            await ws.close(code=1000)


@pytest.mark.xfail(KeyError, reason="The raw_path is not supported by TestClient")
@pytest.mark.asyncio
async def test_http_raw_path_is_escaped(mock_app):
    """
    raw_path (byte string) – The original HTTP path component unmodified from the bytes
     that were received by the web server. Some web server implementations may be unable
     to provide this. Optional; if missing defaults to None.
    https://asgi.readthedocs.io/en/latest/specs/www.html#websocket-connection-scope
    """

    crazy_path = "/crazy.request with spaces and,!%/\xef/"
    encoded_path = quote(crazy_path, encoding="utf-8").encode("utf-8")

    async def handle_all(scope, receive, send):
        if scope["type"] == "websocket":
            assert scope["raw_path"] == encoded_path

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        async with client.websocket_connect(crazy_path) as ws:
            await ws.send_text("hello there")
            await ws.close(code=1000)


@pytest.mark.asyncio
async def test_http_querystring_is_escaped(mock_app):
    """
    query_string (byte string) – URL portion after the ?, percent-encoded.
    https://asgi.readthedocs.io/en/latest/specs/www.html#websocket-connection-scope
    Query string is percent-encoded in the scope.
    """

    crazy_querystring = "q=crazy.request with spaces and?,!%&p=foobar"
    encoded_querystring = quote(crazy_querystring, safe="&=", encoding="utf-8").encode(
        "utf-8"
    )

    async def handle_all(scope, receive, send):
        if scope["type"] == "websocket":
            assert scope["query_string"] == encoded_querystring

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        async with client.websocket_connect("/ws?" + crazy_querystring) as ws:
            await ws.send_text("hello there")
            await ws.close(code=1000)


@pytest.mark.asyncio
async def test_testclient_preserves_headers_order_of_values(mock_app):
    """
    headers (Iterable[[byte string, byte string]]) – An iterable of [name, value]
     two-item iterables, where name is the header name, and value is the header value.
     Order of header values must be preserved from the original HTTP request; order of header names is not important.
     Duplicates are possible and must be preserved in the message as received.
     Header names should be lowercased, but it is not required; servers should preserve header case on a best-effort
     basis. Pseudo headers (present in HTTP/2 and HTTP/3) must be removed; if :authority is present its value must be
     added to the start of the iterable with host as the header name or replace any existing host header already present.
    https://asgi.readthedocs.io/en/latest/specs/www.html#http-connection-scope
    """

    # The spec isn't very clearly written on this; I *think* what it is saying, is if a header has multiple values with
    # the same header name, the order of those values must be preserved...but that the overall order of headers with
    # different names can change. This would match with implementations in eg Daphne.

    headers = [
        (b"x-test-1", b"2"),
        (b"x-test-1", b"1"),
        (b"x-test-9", b"4"),
        (b"x-test-3", b"3"),
        (b"x-test-1", b"3"),
    ]
    headers_dict = CIMultiDict(
        [(k.decode("utf-8"), v.decode("utf-8")) for k, v in headers]
    )

    original_ws_request = mock_app.websocket_connect

    async def custom_ws_request(scope, receive, send, msg, msg_history):
        # Check that the headers with the same name are still in the same order
        request_headers = [(k, v) for k, v in scope["headers"] if k == b"x-test-1"]
        matches_headers = [(k, v) for k, v in headers if k == b"x-test-1"]
        assert request_headers == matches_headers
        await original_ws_request(scope, receive, send, msg, msg_history)

    mock_app.websocket_connect = custom_ws_request

    async with TestClient(mock_app) as client:
        async with client.websocket_connect("/ws", headers=headers_dict) as ws:
            await ws.send_text("hello there")
            await ws.close(code=1000)


@pytest.mark.asyncio
async def test_testclient_lowercases_header_names(mock_app):
    """
    headers (Iterable[[byte string, byte string]]) – An iterable of [name, value]
     Header names should be lowercased, but it is not required; servers should preserve header case on a best-effort
     basis.
    https://asgi.readthedocs.io/en/latest/specs/www.html#http-connection-scope
    """

    # The spec isn't very clearly written on this; I *think* what it is saying, is if a header has multiple values with
    # the same header name, the order of those values must be preserved...but that the overall order of headers with
    # different names can change. This would match with implementations in eg Daphne.

    headers = [
        (b"X-TEST-1", b"2"),
    ]
    headers_dict = CIMultiDict(
        [(k.decode("utf-8"), v.decode("utf-8")) for k, v in headers]
    )

    original_ws_request = mock_app.websocket_connect

    async def custom_ws_request(scope, receive, send, msg, msg_history):
        # Check that the headers with the same name are still in the same order
        request_header_keys = [k for k, v in scope["headers"]]
        assert b"x-test-1" in request_header_keys
        await original_ws_request(scope, receive, send, msg, msg_history)

    mock_app.websocket_connect = custom_ws_request

    async with TestClient(mock_app) as client:
        async with client.websocket_connect("/ws", headers=headers_dict) as ws:
            await ws.send_text("hello there")
            await ws.close(code=1000)


@pytest.mark.xfail(
    AssertionError,
    reason="websocket session does not support receiving a close instead of accept",
)
@pytest.mark.asyncio
async def test_close_on_connect(mock_app):
    """
    This message must be responded to with either an Accept message or a Close message
    before the socket will pass websocket.receive messages. The protocol server must send
    this message during the handshake phase of the WebSocket and not complete the handshake
    until it gets a reply, returning HTTP status code 403 if the connection is denied.
    https://asgi.readthedocs.io/en/latest/specs/www.html#connect-receive-event
    """

    async def custom_ws_connect(scope, receive, send, msg, msg_history):
        await send({"type": "websocket.close"})
        return False

    mock_app.websocket_connect = custom_ws_connect

    async with TestClient(mock_app) as client:
        async with client.websocket_connect("/ws") as ws:
            # There should be a way to assert that the websocket session was closed
            # In fact, what will actually happen is an AssertionError in websocket.py:132
            # because it asserts that the message type will always be websocket.accept,
            # so it doesn't support receiving a websocket.close
            await ws.send_text("we never reach this")


# - Subprotocols - proper support for subprotocols doesn't exist so we can test for it yet.
#  (e.g. websocket_connect() might specify a list of allowed subprotocols, or a callback to check...)

# - Test sending and receiving text/binary data in websockets


@pytest.mark.asyncio
async def test_sending_event_after_disconnect_is_ignored(mock_app):
    """
    Note that messages received by a server after the connection has been closed are not
     considered errors. In this case the send awaitable callable should act as a no-op.
    https://asgi.readthedocs.io/en/latest/specs/main.html#error-handling
    """

    async with TestClient(mock_app) as client:
        async with client.websocket_connect("/ws") as ws:
            await ws.send_text("hello there")
            await ws.close(code=1000)
            await ws.send_text("this should be ignored")

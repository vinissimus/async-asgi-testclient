"""ASGI spec http tests

Tests to verify conformance with the ASGI specification. This module tests
the http protocol.

These tests attempt to make sure that TestClient conforms to
the ASGI specification documented at
https://asgi.readthedocs.io/en/latest/specs/main.html
"""
from async_asgi_testclient import TestClient
from multidict import CIMultiDict
from urllib.parse import quote

import pytest


@pytest.mark.asyncio
async def test_asgi_version_is_present_in_http_scope(mock_app):
    """
    The key scope["asgi"] will also be present as a dictionary containing a scope["asgi"]["version"] key
    that corresponds to the ASGI version the server implements.
    https://asgi.readthedocs.io/en/latest/specs/main.html#applications

    We expect this to be version 3.0, as that is the current spec version.
    """

    async def handle_all(scope, receive, send):
        if scope["type"] == "http":
            assert "asgi" in scope
            assert scope["asgi"]["version"] == "3.0"

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        await client.get("/")


@pytest.mark.asyncio
async def test_http_spec_version_is_missing_or_correct(mock_app):
    """
    asgi["spec_version"] (Unicode string) – Version of the ASGI HTTP spec this server
     understands; one of "2.0" or "2.1". Optional; if missing assume 2.0
    https://asgi.readthedocs.io/en/latest/specs/www.html#http-connection-scope

    TestClient doesn't specify spec_version at the moment, which is also okay.
    Note that if newer features are added (specifically allowing None in 'server' scope value)
    then the spec_version needs to be passed correctly.
    """

    async def handle_all(scope, receive, send):
        if scope["type"] == "http":
            assert (
                "spec_version" not in scope["asgi"]
                or scope["asgi"]["spec_version"] == "2.0"
            )

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_http_version_is_1_1(mock_app):
    """
    http_version (Unicode string) – One of "1.0", "1.1" or "2".
    https://asgi.readthedocs.io/en/latest/specs/www.html#http-connection-scope
    TestClient currently only supports http/1.1, so test that it is set correctly.
    """

    async def handle_all(scope, receive, send):
        if scope["type"] == "http":
            assert scope["http_version"] == "1.1"

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_http_method_is_uppercased(mock_app):
    """
    method (Unicode string) – The HTTP method name, uppercased.
    https://asgi.readthedocs.io/en/latest/specs/www.html#http-connection-scope
    Method is uppercased.
    """

    async def handle_all(scope, receive, send):
        if scope["type"] == "http":
            assert scope["method"] == "GET"

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        resp = await client.open("/", method="get")
        assert resp.status_code == 200


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
    https://asgi.readthedocs.io/en/latest/specs/www.html#http-connection-scope
    Path is decoded in the scope, with UTF-8 byte sequences properly decoded as well.
    """

    crazy_path = "/crazy.request with spaces and,!%/\xef/"
    encoded_path = quote(crazy_path, encoding="utf-8")

    async def handle_all(scope, receive, send):
        if scope["type"] == "http":
            assert scope["path"] == crazy_path

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        resp = await client.get(encoded_path)
        assert resp.status_code == 200


@pytest.mark.xfail(KeyError, reason="The raw_path is not supported by TestClient")
@pytest.mark.asyncio
async def test_http_raw_path_is_escaped(mock_app):
    """
    raw_path (byte string) – The original HTTP path component unmodified from the bytes
     that were received by the web server. Some web server implementations may be unable
     to provide this. Optional; if missing defaults to None.
    https://asgi.readthedocs.io/en/latest/specs/www.html#http-connection-scope
    """

    crazy_path = "/crazy.request with spaces and,!%/\xef/"
    encoded_path = quote(crazy_path, encoding="utf-8").encode("utf-8")

    async def handle_all(scope, receive, send):
        if scope["type"] == "http":
            assert scope["raw_path"] == encoded_path

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        resp = await client.get(crazy_path)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_http_querystring_is_escaped(mock_app):
    """
    query_string (byte string) – URL portion after the ?, percent-encoded.
    https://asgi.readthedocs.io/en/latest/specs/www.html#http-connection-scope
    Query string is percent-encoded in the scope.
    """

    crazy_querystring = "q=crazy.request with spaces and?,!%&p=foobar"
    encoded_querystring = quote(crazy_querystring, safe="&=", encoding="utf-8").encode(
        "utf-8"
    )

    async def handle_all(scope, receive, send):
        if scope["type"] == "http":
            assert scope["query_string"] == encoded_querystring

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        resp = await client.get("/?" + crazy_querystring)
        assert resp.status_code == 200


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

    original_http_request = mock_app.http_request

    async def custom_http_request(scope, receive, send, msg):
        # Check that the headers with the same name are still in the same order
        request_headers = [(k, v) for k, v in scope["headers"] if k == b"x-test-1"]
        matches_headers = [(k, v) for k, v in headers if k == b"x-test-1"]
        assert request_headers == matches_headers
        await original_http_request(scope, receive, send, msg)

    mock_app.http_request = custom_http_request

    async with TestClient(mock_app, headers=headers_dict) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


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

    original_http_request = mock_app.http_request

    async def custom_http_request(scope, receive, send, msg):
        # Check that the headers with the same name are still in the same order
        request_header_keys = [k for k, v in scope["headers"]]
        assert b"x-test-1" in request_header_keys
        await original_http_request(scope, receive, send, msg)

    mock_app.http_request = custom_http_request

    async with TestClient(mock_app, headers=headers_dict) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_response_headers_can_be_missing(mock_app):
    """
    headers (Iterable[[byte string, byte string]]) – An iterable of [name, value]
     two-item iterables, where name is the header name, and value is the header value.
     Order must be preserved in the HTTP response. Header names must be lowercased.
     Optional; if missing defaults to an empty list.
     Pseudo headers (present in HTTP/2 and HTTP/3) must not be present.
    https://asgi.readthedocs.io/en/latest/specs/www.html#response-start-send-event
    """

    async def custom_http_request(scope, receive, send, msg):
        # A http.response.start is NOT required to have a headers key; if missing, defaults to [].
        await send({"type": "http.response.start", "status": 200})
        await send({"type": "http.response.body", "body": b"OK", "more_body": False})

    mock_app.http_request = custom_http_request

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_response_status_is_required(mock_app):
    """
    status (int) – HTTP status code.
    https://asgi.readthedocs.io/en/latest/specs/www.html#response-start-send-event
    """

    async def custom_http_request(scope, receive, send, msg):
        # A http.response.start is NOT required to have a headers key; if missing, defaults to [].
        await send({"type": "http.response.start", "headers": []})
        await send({"type": "http.response.body", "body": b"OK", "more_body": False})

    mock_app.http_request = custom_http_request

    with pytest.raises(KeyError):
        async with TestClient(mock_app) as client:
            resp = await client.get("/")
            assert resp.status_code == 200


@pytest.mark.xfail(
    AssertionError, reason="TestClient currently accepts incorrectly typed status code"
)
@pytest.mark.asyncio
async def test_response_status_must_be_int(mock_app):
    """
    status (int) – HTTP status code.
    https://asgi.readthedocs.io/en/latest/specs/www.html#response-start-send-event
    """

    async def custom_http_request(scope, receive, send, msg):
        # A http.response.start is NOT required to have a headers key; if missing, defaults to [].
        await send({"type": "http.response.start", "status": "200", "headers": []})
        await send({"type": "http.response.body", "body": b"OK", "more_body": False})

    mock_app.http_request = custom_http_request

    with pytest.raises(TypeError):
        async with TestClient(mock_app) as client:
            await client.get("/")


@pytest.mark.asyncio
async def test_response_body_can_be_missing(mock_app):
    """
    The TestClient should allow for a response with no headers in the message
    https://asgi.readthedocs.io/en/latest/specs/www.html#response-body-send-event
    """

    async def custom_http_request(scope, receive, send, msg):
        await send({"type": "http.response.start", "headers": [], "status": 200})
        # A http.response.body is NOT required to have a body key; if missing, defaults to b"".
        await send({"type": "http.response.body", "more_body": False})

    mock_app.http_request = custom_http_request

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_response_more_body_can_be_missing(mock_app):
    """
    The TestClient should allow for a response with no headers in the message
    https://asgi.readthedocs.io/en/latest/specs/www.html#response-body-send-event
    """

    async def custom_http_request(scope, receive, send, msg):
        await send({"type": "http.response.start", "headers": [], "status": 200})
        # A http.response.body is NOT required to have a more_body key; if missing, defaults to False.
        await send({"type": "http.response.body", "body": b"OK"})

    mock_app.http_request = custom_http_request

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.xfail(
    raises=AttributeError,
    reason="TestClient is not currently compliant with this part of the spec",
)
@pytest.mark.asyncio
async def test_sending_event_after_disconnect_is_ignored(mock_app):
    """
    Note that messages received by a server after the connection has been closed are not
     considered errors. In this case the send awaitable callable should act as a no-op.
    https://asgi.readthedocs.io/en/latest/specs/main.html#error-handling
    """

    async def http_request(scope, receive, send, msg):
        # Send an invalid response - expect an exception to be raised
        await send({"type": "http.response.start", "headers": [], "status": 200})
        await send({"type": "http.response.body", "body": b"OK", "more_body": False})
        # This should be ignored:
        await send({"type": "http.response.start", "headers": [], "status": 404})

    mock_app.http_request = http_request

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200

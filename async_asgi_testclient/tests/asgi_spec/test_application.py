"""ASGI spec application tests

Tests to verify conformance with the ASGI specification. This module tests
application-level tests.

These tests attempt to make sure that TestClient conforms to
the ASGI specification documented at
https://asgi.readthedocs.io/en/latest/specs/main.html
"""

from async_asgi_testclient import TestClient

import pytest


@pytest.mark.asyncio
async def test_legacy_asgi_application(legacy_mock_app):
    """
    Legacy (v2.0) ASGI applications are defined as a callable [...] which returns
    another, awaitable callable [...]

    https://asgi.readthedocs.io/en/latest/specs/main.html#legacy-applications

    We expect a legacy app to be handled correctly and be callable as usual
    """

    async with TestClient(legacy_mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_asgi_version_is_present_in_scope(mock_app):
    """
    The key scope["asgi"] will also be present as a dictionary containing a scope["asgi"]["version"] key
    that corresponds to the ASGI version the server implements.
    https://asgi.readthedocs.io/en/latest/specs/main.html#applications

    We expect this to be version 3.0, as that is the current spec version.
    """

    async def handle_all(scope, receive, send):
        assert "asgi" in scope
        assert scope["asgi"]["version"] == "3.0"

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        await client.get("/")


@pytest.mark.asyncio
async def test_sending_invalid_event_raises_exception(mock_app):
    """
    If a server receives an invalid event dictionary - for example, having an unknown
    type, missing keys an event type should have, or with wrong Python types for objects
    (e.g. Unicode strings for HTTP headers) - it should raise an exception out of the
    send awaitable back to the application.
    https://asgi.readthedocs.io/en/latest/specs/main.html#error-handling
    """

    async def http_request(scope, receive, send, msg):
        # Send an invalid response - expect an exception to be raised
        await send(
            {"type": "http.invalid.response.start", "headers": [], "status": 200}
        )
        await send({"type": "http.response.body", "body": b"OK"})

    mock_app.http_request = http_request

    async with TestClient(mock_app) as client:
        with pytest.raises(
            Exception, match=r"^Excpected message type 'http.response.start'. .*$"
        ):
            await client.get("/")


@pytest.mark.asyncio
async def test_sending_extra_keys_does_not_raise_error(mock_app):
    """
    In both cases [of send and receive events], the presence of additional keys in the
    event dictionary should not raise an exception. This allows non-breaking upgrades to
    protocol specifications over time.
    https://asgi.readthedocs.io/en/latest/specs/main.html#error-handling
    """

    async def http_request(scope, receive, send, msg):
        # Send an invalid response - expect an exception to be raised
        await send(
            {
                "type": "http.response.start",
                "headers": [],
                "status": 200,
                "extra_unknown_key": "unnecessary data",
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"OK",
                "more_body": False,
                "extra_unknown_data": "also unnecessary",
            }
        )

    mock_app.http_request = http_request

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_scope_is_isolated_between_calls(mock_app):
    """
    When middleware is modifying the scope, it should make a copy of the scope object
    before mutating it and passing it to the inner application, as changes may leak
    upstream otherwise.
    https://asgi.readthedocs.io/en/latest/specs/main.html#middleware

    The spec doesn't explicitly state this in general, but it is implied in the
    middleware section (and by common sense) that the scope dictionary should be
    isolated within a call. So if we launch two http requests, one should not pollute
    the other's scope dict.
    """

    async def handle_all(scope, receive, send):
        assert "persisted" not in scope["asgi"]
        scope["asgi"]["persisted"] = "this value should not persist across calls"

    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.xfail(
    raises=AssertionError, reason="Custom scopes can pollute between calls"
)
@pytest.mark.asyncio
async def test_custom_scope_is_isolated_between_calls(mock_app):
    """
    When middleware is modifying the scope, it should make a copy of the scope object
    before mutating it and passing it to the inner application, as changes may leak
    upstream otherwise.
    https://asgi.readthedocs.io/en/latest/specs/main.html#middleware

    The spec doesn't explicitly state this in general, but it is implied in the
    middleware section (and by common sense) that the scope dictionary should be
    isolated within a call. So if we launch two http requests, one should not pollute
    the other's scope dict.
    """

    async def handle_all(scope, receive, send):
        # lifespan protocol currently ignores the custom scope :-(
        if scope["type"] == "lifespan":
            return
        assert "persisted" not in scope["custom"]
        scope["custom"]["persisted"] = "this value should not persist across calls"

    mock_app.handle_all = handle_all

    async with TestClient(mock_app, scope={"custom": {"key": "value"}}) as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        resp = await client.get("/")
        assert resp.status_code == 200

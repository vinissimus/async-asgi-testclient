"""ASGI spec lifespan tests

Tests to verify conformance with the ASGI specification. This module tests
the lifespan protocol.

These tests attempt to make sure that TestClient conforms to
the ASGI specification documented at
https://asgi.readthedocs.io/en/latest/specs/main.html
"""
import logging

from async_asgi_testclient import TestClient

import pytest


@pytest.mark.asyncio
async def test_lifespan_spec_version_is_missing_or_correct(mock_app):
    """
    asgi["spec_version"] (Unicode string) – The version of this spec being used.
     Optional; if missing defaults to "1.0".
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#scope

    TestClient doesn't specify spec_version at the moment, which is also okay.
    """

    async def handle_all(scope, receive, send):
        if scope["type"] == "lifespan":
            assert (
                "spec_version" not in scope["asgi"]
                or scope["asgi"]["spec_version"] == "1.0"
            )

    mock_app.use_lifespan = True
    mock_app.handle_all = handle_all

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_lifespan_not_supported_is_allowed(mock_app):
    """
    If an exception is raised when calling the application callable with a lifespan.startup
    message or a scope with type lifespan, the server must continue but not send any lifespan
    events.
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#scope
    """

    mock_app.use_lifespan = False

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_lifespan_not_supported_logs_the_exception(mock_app, caplog):
    """
    If an exception is raised when calling the application callable with a lifespan.startup
    message or a scope with type lifespan, the server must continue but not send any lifespan
    events.
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#scope

    Test that the exception raised is logged by the TestClient.
    """

    mock_app.use_lifespan = False

    with caplog.at_level(level=logging.DEBUG, logger="async_asgi_testclient.testing"):
        async with TestClient(mock_app) as client:
            resp = await client.get("/")
    records = [record for record in caplog.records if record.message == "Lifespan protocol raised an exception"]
    assert len(records) == 1
    assert str(records[0].exc_info[1]) == "Type 'lifespan' is not supported."


@pytest.mark.asyncio
async def test_lifespan_startup_failed(mock_app):
    """
    If the application returns lifespan.startup.failed, the client should not attempt to continue, and should raise
    an exception that can be caught and asserted when using the TestClient.
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-complete-send-event
    """

    mock_app.use_lifespan = True
    mock_app.lifespan_startup_message = {
        "type": "lifespan.startup.failed",
    }

    with pytest.raises(Exception, match=r"^{'type': 'lifespan.startup.failed'}"):
        async with TestClient(mock_app) as client:
            await client.get("/")


@pytest.mark.asyncio
async def test_lifespan_startup_failed_with_message(mock_app):
    """
    If the application returns lifespan.startup.failed, the client should not attempt to continue, and should raise
    an exception that can be caught and asserted when using the TestClient.
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-complete-send-event
    """

    mock_app.use_lifespan = True
    mock_app.lifespan_startup_message = {
        "type": "lifespan.startup.failed",
        "message": "Cowardly failing",
    }

    with pytest.raises(
        Exception,
        match=r"{'type': 'lifespan.startup.failed', 'message': 'Cowardly failing'}",
    ):
        async with TestClient(mock_app) as client:
            await client.get("/")


@pytest.mark.asyncio
async def test_lifespan_startup_completed(mock_app):
    """
    If the application returns lifespan.startup.complete, the client should continue with its request
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-complete-send-event
    """

    mock_app.use_lifespan = True
    mock_app.lifespan_startup_message = {"type": "lifespan.startup.complete"}

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_lifespan_startup_completed_with_message(mock_app):
    """
    If the application returns lifespan.startup.complete, the client should continue with its request
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-complete-send-event
    """

    mock_app.use_lifespan = True
    mock_app.lifespan_startup_message = {
        "type": "lifespan.startup.complete",
        "message": "OK",
    }

    async with TestClient(mock_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_lifespan_shutdown_failed_raises_error(mock_app):
    """
    If the application returns lifespan.shutdown.failed, the server should raise an error
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#shutdown-failed-send-event
    """

    mock_app.lifespan_shutdown_message = {
        "type": "lifespan.shutdown.failed",
    }
    mock_app.use_lifespan = True

    with pytest.raises(Exception, match=r"{'type': 'lifespan.shutdown.failed'}"):
        async with TestClient(mock_app) as client:
            resp = await client.get("/")
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_lifespan_shutdown_failed_with_message_raises_error(mock_app):
    """
    If the application returns lifespan.shutdown.failed, the server should raise an error
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#shutdown-failed-send-event
    """

    mock_app.lifespan_shutdown_message = {
        "type": "lifespan.shutdown.failed",
        "message": "We failed to shut down",
    }
    mock_app.use_lifespan = True

    with pytest.raises(
        Exception,
        match=r"{'type': 'lifespan.shutdown.failed', 'message': 'We failed to shut down'}",
    ):
        async with TestClient(mock_app) as client:
            resp = await client.get("/")
            assert resp.status_code == 200

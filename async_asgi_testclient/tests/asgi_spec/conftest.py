"""Test setup for ASGI spec tests

Mock application used for testing ASGI standard compliance.
"""
from enum import Enum
from functools import partial
from sys import version_info as PY_VER  # noqa

import pytest


class AppState(Enum):
    PREINIT = 0
    INIT = 1
    READY = 2
    SHUTDOWN = 3


class BaseMockApp(object):
    """A mock application object passed to TestClient for the tests"""

    # Make it easy to override these for lifespan related test scenarios
    lifespan_startup_message = {"type": "lifespan.startup.complete", "message": "OK"}
    lifespan_shutdown_message = {"type": "lifespan.shutdown.complete", "message": "OK"}
    use_lifespan = True

    def __init__(self, **kwargs):
        for k, v in kwargs:
            setattr(self, k, v)
        self.state = AppState.PREINIT

    async def lifespan_startup(self, scope, receive, send, msg):
        if self.state == AppState.READY:
            # Technically, this isn't explicitly forbidden in the spec.
            # But I think it should not happen.
            raise RuntimeError("Received more than one lifespan.startup")
        self.state = AppState.READY
        return await send(self.lifespan_startup_message)

    async def lifespan_shutdown(self, scope, receive, send, msg):
        if self.state == AppState.SHUTDOWN:
            # Technically, this isn't explicitly forbidden in the spec.
            # But I think it should not happen.
            raise RuntimeError("Received more than one lifespan.shutdown")
        self.state = AppState.SHUTDOWN
        return await send(self.lifespan_shutdown_message)

    async def lifespan(self, scope, receive, send):
        if not self.use_lifespan:
            raise RuntimeError(f"Type '{scope['type']}' is not supported.")
        while True:
            try:
                msg = await receive()
            except RuntimeError as e:
                if e.args == ("Event loop is closed",):
                    return
                else:
                    raise

            if msg["type"] == "lifespan.startup":
                await self.lifespan_startup(scope, receive, send, msg)
            elif msg["type"] == "lifespan.shutdown":
                await self.lifespan_shutdown(scope, receive, send, msg)
            else:
                raise RuntimeError(f"Received unknown message type '{msg['type']}")
            if self.state == AppState.SHUTDOWN:
                return

    async def http_request(self, scope, receive, send, msg):
        # Default behaviour, just send a minimal response with OK to any request
        await send({"type": "http.response.start", "headers": [], "status": 200})
        await send({"type": "http.response.body", "body": b"OK"})

    async def http_disconnect(self, scope, receive, send, msg):
        raise RuntimeError(f"Received http.disconnect message {msg}")

    async def http(self, scope, receive, send):
        msg = []
        # Receive http.requests until http.disconnect or more_body = False
        while True:
            msg.append(await receive())
            if msg[-1]["type"] == "http.disconnect" or not msg[-1].get(
                "more_body", False
            ):
                break
        if msg[0]["type"] == "http.disconnect":
            # Honestly this shouldn't really happen, but it's allowed in spec, so check.
            return await self.http_disconnect(scope, receive, send, msg)
        else:
            return await self.http_request(scope, receive, send, msg)

    async def websocket_connect(self, scope, receive, send, msg, msg_history):
        await send({"type": "websocket.accept"})
        return True

    async def websocket_receive(self, scope, receive, send, msg, msg_history):
        return True

    async def websocket_disconnect(self, scope, receive, send, msg, msg_history):
        return False

    async def websocket(self, scope, receive, send):
        msg_history = []
        while True:
            msg = await receive()

            # Send websocket events to a handler
            func = getattr(
                self, msg["type"].replace(".", "_").replace("-", "__"), "handle_unknown"
            )
            res = await func(scope, receive, send, msg, msg_history)
            msg_history.append(msg)

            # If the event handler returns false, assume we closed the socket.
            if msg["type"] == "websocket.disconnect" or not res:
                return

    async def handle_unknown(self, scope, receive, send):
        if self.state != AppState.READY:
            raise RuntimeError(
                "Received another request before lifespan.startup.complete sent"
            )
        raise RuntimeError(f"Type '{scope['type']}' is not supported.")

    async def handle_all(self, scope, receive, send):
        # Do nothing unless something monkeypatches us
        pass

    async def asgi_call(self, scope, receive, send):
        # Initial catch-all, for testing things like scope type itself
        await self.handle_all(scope, receive, send)

        if self.state == AppState.PREINIT:
            if self.use_lifespan:
                self.state = AppState.INIT
            else:
                self.state = AppState.READY
        if self.state == AppState.SHUTDOWN:
            raise RuntimeError(f"Got message after shutting down: {scope}")

        # call hooks based on scope type, so we can monkeypatch them in tests
        # the lifespan, http, and websocket protocol types all have simple methods already
        # implemented.
        func = getattr(
            self, scope["type"].replace(".", "_").replace("-", "__"), "handle_unknown"
        )
        return await func(scope, receive, send)


class MockApp(BaseMockApp):
    """Modern ASGI single-callable app"""

    async def __call__(self, scope, receive, send):
        return await super().asgi_call(scope, receive, send)


class LegacyMockApp(BaseMockApp):
    """Legacy ASGI 'two-callable' app"""

    def __call__(self, scope):
        return partial(super().asgi_call, scope)


@pytest.fixture(scope="function")
def mock_app():
    """Create a mock ASGI App to test the TestClient against"""

    return MockApp()


@pytest.fixture(scope="function")
def legacy_mock_app():
    """Create a mock legacy ASGI App to test the TestClient against"""

    return LegacyMockApp()

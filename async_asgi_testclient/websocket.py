from async_asgi_testclient.utils import create_monitored_task
from async_asgi_testclient.utils import flatten_headers
from async_asgi_testclient.utils import make_test_headers_path_and_query_string
from async_asgi_testclient.utils import Message
from async_asgi_testclient.utils import receive
from http.cookies import SimpleCookie
from typing import Dict
from typing import Optional

import asyncio
import json


class WebSocketSession:
    def __init__(
        self,
        testclient,
        path,
        headers: Optional[Dict] = None,
        cookies: Optional[Dict] = None,
    ):
        self.testclient = testclient
        self.path = path
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.input_queue: asyncio.Queue[dict] = asyncio.Queue()
        self.output_queue: asyncio.Queue[dict] = asyncio.Queue()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def close(self, code: int = 1000):
        await self._send({"type": "websocket.disconnect", "code": code})

    async def send_str(self, data: str) -> None:
        await self.send_text(data)

    async def send_text(self, data: str) -> None:
        await self._send({"type": "websocket.receive", "text": data})

    async def send_bytes(self, data: bytes) -> None:
        await self._send({"type": "websocket.receive", "bytes": data})

    async def send_json(self, data, mode: str = "text") -> None:
        assert mode in ["text", "binary"]
        text = json.dumps(data)
        if mode == "text":
            await self._send({"type": "websocket.receive", "text": text})
        else:
            await self._send(
                {"type": "websocket.receive", "bytes": text.encode("utf-8")}
            )

    async def _send(self, data):
        self.input_queue.put_nowait(data)

    async def receive_text(self) -> str:
        message = await self._receive()
        if message["type"] != "websocket.send":
            raise Exception(message)
        return message["text"]

    async def receive_bytes(self) -> bytes:
        message = await self._receive()
        if message["type"] != "websocket.send":
            raise Exception(message)
        return message["bytes"]

    async def receive_json(self, mode: str = "text"):
        assert mode in ["text", "binary"]
        message = await self._receive()
        if message["type"] != "websocket.send":
            raise Exception(message)
        if mode == "text":
            text = message["text"]
        else:
            text = message["bytes"].decode("utf-8")
        return json.loads(text)

    async def _receive(self):
        return await receive(self.output_queue)

    def __aiter__(self):
        return self

    async def __anext__(self):
        msg = await self._receive()
        if isinstance(msg, Message):
            if msg.event == "exit":
                raise StopAsyncIteration(msg)
        return msg

    async def connect(self):
        tc = self.testclient
        app = tc.application
        headers, path, query_string_bytes = make_test_headers_path_and_query_string(
            app, self.path, self.headers
        )

        if self.cookies is None:  # use TestClient.cookie_jar
            cookie_jar = tc.cookie_jar
        else:
            cookie_jar = SimpleCookie(self.cookies)

        if cookie_jar and cookie_jar.output(header=""):
            headers.add("Cookie", cookie_jar.output(header=""))

        scope = {
            "type": "websocket",
            "headers": flatten_headers(headers),
            "path": path,
            "query_string": query_string_bytes,
            "root_path": "",
            "scheme": "http",
            "subprotocols": [],
        }

        create_monitored_task(
            app(scope, self.input_queue.get, self.output_queue.put),
            self.output_queue.put_nowait,
        )

        await self._send({"type": "websocket.connect"})
        msg = await self._receive()
        assert msg["type"] == "websocket.accept"

from async_asgi_testclient.utils import create_monitored_task
from async_asgi_testclient.utils import Message
from async_asgi_testclient.utils import receive
from functools import partial

import asyncio
import json


class WebSocketSession:
    def __init__(self, app, path, extra_headers):
        self.path = path
        self.headers = extra_headers or {}
        self.app = app
        self.input_queue: asyncio.Queue[dict] = asyncio.Queue()
        self.output_queue: asyncio.Queue[dict] = asyncio.Queue()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def close(self, code: int = 1000):
        await self.send({"type": "websocket.disconnect", "code": code})

    async def send(self, data):
        self.input_queue.put_nowait(data)

    async def send_str(self, data: str) -> None:
        await self.send({"type": "websocket.receive", "text": data})

    async def send_bytes(self, data: bytes) -> None:
        await self.send({"type": "websocket.receive", "bytes": data})

    async def send_json(self, data, mode: str = "text") -> None:
        assert mode in ["text", "binary"]
        text = json.dumps(data)
        if mode == "text":
            await self.send({"type": "websocket.receive", "text": text})
        else:
            await self.send(
                {"type": "websocket.receive", "bytes": text.encode("utf-8")}
            )

    async def receive(self):
        receive_or_fail = partial(receive, self.output_queue)
        return await self.wait_response(receive_or_fail)

    async def receive_text(self) -> str:
        message = await self.receive()
        return message["text"]

    async def receive_bytes(self) -> bytes:
        message = await self.receive()
        return message["bytes"]

    async def receive_json(self, mode: str = "text"):
        assert mode in ["text", "binary"]
        message = await self.receive()
        if mode == "text":
            text = message["text"]
        else:
            text = message["bytes"].decode("utf-8")
        return json.loads(text)

    def __aiter__(self):
        return self

    async def __anext__(self):
        msg = await self.receive()
        if isinstance(msg, Message):
            if msg.event == "exit":
                raise StopAsyncIteration(msg)
        return msg

    async def connect(self):
        self.headers.update({"host": "localhost"})
        flat_headers = [
            (bytes(k.lower(), "utf8"), bytes(v, "utf8"))
            for k, v in self.headers.items()
        ]
        scope = {
            "type": "websocket",
            "headers": flat_headers,
            "path": self.path,
            "query_string": "",
            "root_path": "",
            "scheme": "ws",
            "subprotocols": [],
        }

        create_monitored_task(
            self.app(scope, self.input_queue.get, self.output_queue.put),
            self.output_queue.put_nowait,
        )

        await self.send({"type": "websocket.connect"})
        msg = await self.receive()
        assert msg["type"] == "websocket.accept"

    async def wait_response(self, receive_or_fail):
        message = await receive_or_fail()
        return message

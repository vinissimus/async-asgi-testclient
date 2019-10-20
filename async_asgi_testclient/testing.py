"""
Copyright P G Jones 2017.

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
"""
from async_asgi_testclient.compatibility import guarantee_single_callable
from async_asgi_testclient.response import BytesRW
from async_asgi_testclient.response import Response
from async_asgi_testclient.utils import create_monitored_task
from async_asgi_testclient.utils import is_last_one
from async_asgi_testclient.utils import Message
from async_asgi_testclient.utils import receive
from async_asgi_testclient.websocket import WebSocketSession
from functools import partial
from http.cookies import SimpleCookie
from json import dumps
from multidict import CIMultiDict
from typing import Any
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union
from urllib.parse import urlencode

import asyncio
import inspect
import requests

sentinel = object()


class TestClient:
    """A Client bound to an app for testing.

    This should be used to make requests and receive responses from
    the app for testing purposes.
    """

    __test__ = False  # prevent pytest.PytestCollectionWarning

    def __init__(
        self, application, use_cookies: bool = True, timeout: Optional[int] = None
    ):
        self.application = guarantee_single_callable(application)
        self.cookie_jar = SimpleCookie() if use_cookies else None
        self._lifespan_input_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._lifespan_output_queue: asyncio.Queue[dict] = asyncio.Queue()
        self.timeout = timeout

    async def __aenter__(self):
        create_monitored_task(
            self.application(
                {"type": "lifespan", "asgi": {"version": "3.0"}},
                self._lifespan_input_queue.get,
                self._lifespan_output_queue.put,
            ),
            self._lifespan_output_queue.put_nowait,
        )

        await self.send_lifespan("startup")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.send_lifespan("shutdown")

    async def send_lifespan(self, action):
        await self._lifespan_input_queue.put({"type": f"lifespan.{action}"})
        message = await receive(self._lifespan_output_queue, timeout=self.timeout)

        if isinstance(message, Message):
            raise Exception(f"{message.event} - {message.reason} - {message.task}")

        if message["type"] == f"lifespan.{action}.complete":
            pass
        elif message["type"] == f"lifespan.{action}.failed":
            raise Exception(message)

    def websocket_connect(self, path, extra_headers=None):
        return WebSocketSession(self.application, path, extra_headers)

    async def open(
        self,
        path: str,
        *,
        method: str = "GET",
        headers: Optional[Union[dict, CIMultiDict]] = None,
        data: Any = None,
        form: Optional[dict] = None,
        query_string: Optional[dict] = None,
        json: Any = sentinel,
        scheme: str = "http",
        cookies: Optional[dict] = None,
        stream: bool = False,
        allow_redirects: bool = True,
    ):
        """Open a request to the app associated with this client.

        Arguments:
            path
                The path to request. If the query_string argument is not
                defined this argument will be partitioned on a '?' with the
                following part being considered the query_string.

            method
                The method to make the request with, defaults to 'GET'.

            headers
                Headers to include in the request.

            data
                Raw data to send in the request body or async generator

            form
                Data to send form encoded in the request body.

            query_string
                To send as a dictionary, alternatively the query_string can be
                determined from the path.

            json
                Data to send json encoded in the request body.

            scheme
                The scheme to use in the request, default http.

            cookies
                Cookies to send in the request instead of cookies in
                TestClient.cookie_jar

            stream
                Return the response in streaming instead of buffering

            allow_redirects
                If set to True follows redirects

        Returns:
            The response from the app handling the request.
        """
        input_queue: asyncio.Queue[dict] = asyncio.Queue()
        output_queue: asyncio.Queue[dict] = asyncio.Queue()

        headers, path, query_string_bytes = make_test_headers_path_and_query_string(
            self.application, path, headers, query_string
        )

        if [json is not sentinel, form is not None, data is not None].count(True) > 1:
            raise ValueError(
                "Test args 'json', 'form', and 'data' are mutually exclusive"
            )

        request_data = b""

        if isinstance(data, str):
            request_data = data.encode("utf-8")
        elif isinstance(data, bytes):
            request_data = data

        if json is not sentinel:
            request_data = dumps(json).encode("utf-8")
            headers["Content-Type"] = "application/json"

        if form is not None:
            request_data = urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        if cookies is None:  # use TestClient.cookie_jar
            cookie_jar = self.cookie_jar
        else:
            cookie_jar = SimpleCookie(cookies)

        if cookie_jar and cookie_jar.output(header=""):
            headers.add("Cookie", cookie_jar.output(header=""))

        flat_headers: List[Tuple] = [
            (bytes(k.lower(), "utf8"), bytes(v, "utf8")) for k, v in headers.items()
        ]

        scope = {
            "type": "http",
            "http_version": "1.1",
            "asgi": {"version": "3.0"},
            "method": method,
            "scheme": scheme,
            "path": path,
            "query_string": query_string_bytes,
            "root_path": "",
            "headers": flat_headers,
        }

        create_monitored_task(
            self.application(scope, input_queue.get, output_queue.put),
            output_queue.put_nowait,
        )

        send = input_queue.put_nowait
        receive_or_fail = partial(receive, output_queue, timeout=self.timeout)

        # Send request
        if inspect.isasyncgen(data):
            async for is_last, body in is_last_one(data):
                send({"type": "http.request", "body": body, "more_body": not is_last})
        else:
            send({"type": "http.request", "body": request_data})

        response = Response(stream, receive_or_fail, send)

        # Receive response start
        message = await self.wait_response(receive_or_fail, "http.response.start")
        response.status_code = message["status"]
        response.headers = CIMultiDict(
            [(k.decode("utf8"), v.decode("utf8")) for k, v in message["headers"]]
        )

        # Receive initial response body
        message = await self.wait_response(receive_or_fail, "http.response.body")
        response.raw.write(message["body"])
        response._more_body = message.get("more_body", False)

        # Consume the remaining response if not in stream
        if not stream:
            bytes_io = BytesRW()
            bytes_io.write(response.raw.read())
            async for chunk in response:
                bytes_io.write(chunk)
            response.raw = bytes_io
            response._content = bytes_io.read()
            response._content_consumed = True

        if cookie_jar is not None:
            cookies = SimpleCookie()
            for c in response.headers.getall("Set-Cookie", ""):
                cookies.load(c)
            response.cookies = requests.cookies.RequestsCookieJar()
            response.cookies.update(cookies)
            cookie_jar.update(cookies)

        if allow_redirects and response.is_redirect:
            path = response.headers["location"]
            return await self.get(path)
        else:
            return response

    async def wait_response(self, receive_or_fail, type_):
        message = await receive_or_fail()
        if not isinstance(message, dict):
            raise Exception(f"Unexpected message {message}")
        if message["type"] != type_:
            raise Exception(f"Excpected message type '{type_}'. " f"Found {message}")
        return message

    async def delete(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a DELETE request.
        """
        return await self.open(*args, method="DELETE", **kwargs)

    async def get(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a GET request.
        """
        return await self.open(*args, method="GET", **kwargs)

    async def head(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a HEAD request.
        """
        return await self.open(*args, method="HEAD", **kwargs)

    async def options(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a OPTIONS request.
        """
        return await self.open(*args, method="OPTIONS", **kwargs)

    async def patch(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a PATCH request.
        """
        return await self.open(*args, method="PATCH", **kwargs)

    async def post(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a POST request.
        """
        return await self.open(*args, method="POST", **kwargs)

    async def put(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a PUT request.
        """
        return await self.open(*args, method="PUT", **kwargs)

    async def trace(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a TRACE request.
        """
        return await self.open(*args, method="TRACE", **kwargs)


def make_test_headers_path_and_query_string(
    app: Any,
    path: str,
    headers: Optional[Union[dict, CIMultiDict]] = None,
    query_string: Optional[dict] = None,
) -> Tuple[CIMultiDict, str, bytes]:
    """Make the headers and path with defaults for testing.

    Arguments:
        app: The application to test against.
        path: The path to request. If the query_string argument is not
            defined this argument will be partitioned on a '?' with
            the following part being considered the query_string.
        headers: Initial headers to send.
        query_string: To send as a dictionary, alternatively the
            query_string can be determined from the path.
    """
    if headers is None:
        headers = CIMultiDict()
    elif isinstance(headers, CIMultiDict):
        headers = headers
    elif headers is not None:
        headers = CIMultiDict(headers)
    headers.setdefault("Remote-Addr", "127.0.0.1")
    headers.setdefault("User-Agent", "ASGI-Test-Client")
    headers.setdefault("host", "localhost")

    if "?" in path and query_string is not None:
        raise ValueError("Query string is defined in the path and as an argument")
    if query_string is None:
        path, _, query_string_raw = path.partition("?")
    else:
        query_string_raw = urlencode(query_string, doseq=True)
    query_string_bytes = query_string_raw.encode("ascii")
    return headers, path, query_string_bytes

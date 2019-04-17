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

import asyncio
import async_timeout
import io
import time
import requests
import traceback

from .compatibility import guarantee_single_callable
from json import dumps
from typing import Any, AnyStr, Optional, Tuple, Union
from urllib.parse import urlencode
from http.cookies import SimpleCookie
from multidict import CIMultiDict
from requests.models import Response
from concurrent.futures import CancelledError

sentinel = object()


class TestClient:
    """A Client bound to an app for testing.

    This should be used to make requests and receive responses from
    the app for testing purposes.
    """

    def __init__(self, application, raise_server_exceptions=True):
        self.application = guarantee_single_callable(application)
        self.cookie_jar = SimpleCookie()
        self.lifespan_input_queue = asyncio.Queue()
        self.lifespan_output_queue = asyncio.Queue()
        self.raise_server_exceptions = raise_server_exceptions

    async def __aenter__(self):
        asyncio.ensure_future(
            self.application(
                {"type": "lifespan", "asgi": {"version": "3.0"}},
                self.lifespan_input_queue.get,
                self.lifespan_output_queue.put,
            )
        )
        await self.send_lifespan("startup")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.send_lifespan("shutdown")

    async def send_lifespan(self, action):
        await self.lifespan_input_queue.put({"type": f"lifespan.{action}"})
        message = await self.lifespan_output_queue.get()

        if message["type"] == f"lifespan.{action}.complete":
            pass
        elif message["type"] == f"lifespan.{action}.failed":
            raise Exception(message)

    async def open(
        self,
        path: str,
        *,
        method: str = "GET",
        headers: Optional[Union[dict, CIMultiDict]] = None,
        data: AnyStr = None,
        form: Optional[dict] = None,
        query_string: Optional[dict] = None,
        json: Any = sentinel,
        scheme: str = "http",
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
                Raw data to send in the request body.

            form
                Data to send form encoded in the request body.

            query_string
                To send as a dictionary, alternatively the query_string can be
                determined from the path.

            json
                Data to send json encoded in the request body.

            scheme
                The scheme to use in the request, default http.

        Returns:
            The response from the app handling the request.
        """
        input_queue = asyncio.Queue()
        output_queue = asyncio.Queue()

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

        if self.cookie_jar.output():
            headers.add("Cookie", self.cookie_jar.output(header=""))

        # Convert dict to list of tuples
        headers = [
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
            "headers": headers,
        }

        future = asyncio.ensure_future(
            self.application(scope, input_queue.get, output_queue.put)
        )

        await input_queue.put({"type": "http.request", "body": request_data})

        response = Response()
        response.raw = io.BytesIO()

        while await self._receive_nothing(output_queue) is False:
            try:
                message = await self._receive_output(future, output_queue)
            except Exception as exc:
                if not self.raise_server_exceptions:
                    response.status_code = 500
                    response.raw.write(bytes(
                        "".join(traceback.format_tb(exc.__traceback__)),
                        encoding='utf-8'
                    ))
                    await input_queue.put({"type": "http.disconnect"})
                    break
                raise exc from None

            if message["type"] == "http.response.start":
                response.status_code = message["status"]
                response.headers = CIMultiDict(
                    [
                        (k.decode("utf8"), v.decode("utf8"))
                        for k, v in message["headers"]
                    ]
                )
            elif message["type"] == "http.response.body":
                response.raw.write(bytes(message["body"]))
                if not message.get("more_body", False):
                    await input_queue.put({"type": "http.disconnect"})
                    break
            else:
                raise Exception(message)

        self.cookie_jar.load(response.headers.get("Set-Cookie", ""))
        response.cookies = requests.cookies.RequestsCookieJar()
        response.cookies.update(self.cookie_jar)

        response.raw.seek(0)
        return response

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

    async def _receive_output(self, future, output_queue, timeout=1):
        """
        Receives a single message from the application, with optional timeout.
        """
        # Make sure there's not an exception to raise from the task
        if future.done():
            future.result()
        # Wait and receive the message
        try:
            async with async_timeout.timeout(timeout):
                return await output_queue.get()
        except asyncio.TimeoutError as e:
            # See if we have another error to raise inside
            if future.done():
                future.result()
            else:
                future.cancel()
                try:
                    await future
                except CancelledError:
                    pass
            raise e

    async def _receive_nothing(self, output_queue, timeout=0.1, interval=0.01):
        """
        Checks that there is no message to receive in the given time.
        """
        # `interval` has precedence over `timeout`
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if not output_queue.empty():
                return False
            await asyncio.sleep(interval)
        return output_queue.empty()


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

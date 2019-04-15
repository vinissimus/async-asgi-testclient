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
import time

from .compatibility import guarantee_single_callable
from contextlib import asynccontextmanager
from json import dumps, loads
from typing import Any, AnyStr, AsyncGenerator, List, Optional, Tuple, TYPE_CHECKING, Union
from urllib.parse import urlencode
from multidict import CIMultiDict
from concurrent.futures import CancelledError


sentinel = object()


class TestClient:
    """A Client bound to an app for testing.

    This should be used to make requests and receive responses from
    the app for testing purposes.
    """

    def __init__(self, application):
        self.application = guarantee_single_callable(application)

    async def open(
            self,
            path: str,
            *,
            method: str='GET',
            headers: Optional[Union[dict, CIMultiDict]]=None,
            data: AnyStr=None,
            form: Optional[dict]=None,
            query_string: Optional[dict]=None,
            json: Any=sentinel,
            scheme: str='http',
            follow_redirects: bool=False,
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

            follow_redirects
                Whether or not a redirect response should be followed, defaults
                to False.

        Returns:
            The response from the app handling the request.
        """
        input_queue = asyncio.Queue()
        output_queue = asyncio.Queue()

        headers, path, query_string_bytes = make_test_headers_path_and_query_string(
            self.application, path, headers, query_string,
        )

        if [json is not sentinel, form is not None, data is not None].count(True) > 1:
            raise ValueError("Quart test args 'json', 'form', and 'data' are mutually exclusive")

        request_data = b''

        if isinstance(data, str):
            request_data = data.encode('utf-8')
        elif isinstance(data, bytes):
            request_data = data

        if json is not sentinel:
            request_data = dumps(json).encode('utf-8')
            headers['Content-Type'] = 'application/json'

        if form is not None:
            request_data = urlencode(form).encode('utf-8')
            headers['Content-Type'] = 'application/x-www-form-urlencoded'

        scope = {
            "type": "http",
            "http_version": "1.1",
            "asgi": {"version": "3.0"},
            "method": method,
            "scheme": scheme,
            "path": path,
            "query_string": query_string_bytes,
            "root_path": "",  # TODO
            "headers": headers,
            "client": (None, None),  # TODO
            "server": (None, None),  # TODO
        }

        future = asyncio.ensure_future(
            self.application(scope, input_queue.get, output_queue.put)
        )

        await input_queue.put({"type": "http.request", "body": request_data})

        status = 0
        raw_headers = []
        resp = b''

        while await self._receive_nothing(output_queue) is False:
            message = await self._receive_output(future, output_queue)
            if message["type"] == "http.response.start":
                status = message["status"]
                raw_headers = message["headers"]
            elif message["type"] == "http.response.body":
                resp += bytes(message["body"])
                if not message.get("more_body", False):
                    await input_queue.put({"type": "http.disconnect"})
                    break
            else:
                raise Exception(message)

        headers = CIMultiDict(
            [(k.decode("utf8"), v.decode("utf8")) for k, v in raw_headers]
        )

        if headers.get('Content-Type', '') == 'application/json':
            resp = loads(resp)

        return status, headers, resp

    async def delete(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a DELETE request.
        """
        return await self.open(*args, method='DELETE', **kwargs)

    async def get(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a GET request.
        """
        return await self.open(*args, method='GET', **kwargs)

    async def head(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a HEAD request.
        """
        return await self.open(*args, method='HEAD', **kwargs)

    async def options(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a OPTIONS request.
        """
        return await self.open(*args, method='OPTIONS', **kwargs)

    async def patch(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a PATCH request.
        """
        return await self.open(*args, method='PATCH', **kwargs)

    async def post(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a POST request.
        """
        return await self.open(*args, method='POST', **kwargs)

    async def put(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a PUT request.
        """
        return await self.open(*args, method='PUT', **kwargs)

    async def trace(self, *args: Any, **kwargs: Any) -> bytes:
        """Make a TRACE request.
        """
        return await self.open(*args, method='TRACE', **kwargs)

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
        app: 'Quart',
        path: str,
        headers: Optional[Union[dict, CIMultiDict]]=None,
        query_string: Optional[dict]=None,
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
    headers.setdefault('Remote-Addr', '127.0.0.1')
    headers.setdefault('User-Agent', 'Quart')
    headers.setdefault('host', 'localhost')
    headers = [
        (bytes(k, 'utf8'), bytes(v, 'utf8'))
        for k, v in headers.items()
    ]

    if '?' in path and query_string is not None:
        raise ValueError('Query string is defined in the path and as an argument')
    if query_string is None:
        path, _, query_string_raw = path.partition('?')
    else:
        query_string_raw = urlencode(query_string, doseq=True)
    query_string_bytes = query_string_raw.encode('ascii')
    return headers, path, query_string_bytes

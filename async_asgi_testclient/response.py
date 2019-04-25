import io
from aioerl import receive_or_fail
from aioerl import send

from requests.exceptions import StreamConsumedError
from requests.models import Response as _Response
from requests.utils import iter_slices
from requests.utils import stream_decode_response_unicode


class BytesRW(object):
    def __init__(self):
        self._stream = io.BytesIO()
        self._rpos = 0
        self._wpos = 0

    def read(self, size=-1):
        if self._stream is None:
            raise Exception("Stream is closed")
        self._stream.seek(self._rpos)
        bytes_ = self._stream.read(size)
        self._rpos += len(bytes_)
        return bytes_

    def write(self, b):
        if self._stream is None:
            raise Exception("Stream is closed")
        self._stream.seek(self._wpos)
        n = self._stream.write(b)
        self._wpos += n
        return n

    def close(self):
        self._stream = None


class Response(_Response):
    def __init__(self, stream: bool, timeout, process):
        super().__init__()

        self.stream = stream
        self.timeout = timeout
        self.process = process
        self._more_body = False
        self.raw = BytesRW()

    async def __aiter__(self):
        """Allows you to use a response as an iterator."""
        async for c in self.iter_content(128):
            yield c

    async def generate(self, n):
        while True:
            val = self.raw.read(n)
            if val == b"":  # EOF
                break
            yield val

        while self._more_body:
            message = await receive_or_fail("ok", timeout=self.timeout)
            if message.body["type"] != "http.response.body":
                raise Exception(
                    f"Excpected message type 'http.response.body'. " f"Found {message}"
                )

            message = message.body
            yield message["body"]
            self._more_body = message.get("more_body", False)

        # Send disconnect
        await send(self.process, {"type": "http.disconnect"})
        await receive_or_fail("exit")

    async def iter_content(self, chunk_size=1, decode_unicode=False):
        """Iterates over the response data.  When stream=True is set on the
        request, this avoids reading the content at once into memory for
        large responses.  The chunk size is the number of bytes it should
        read into memory.  This is not necessarily the length of each item
        returned as decoding can take place.

        chunk_size must be of type int or None. A value of None will
        function differently depending on the value of `stream`.
        stream=True will read data as it arrives in whatever size the
        chunks are received. If stream=False, data is returned as
        a single chunk.

        If decode_unicode is True, content will be decoded using the best
        available encoding based on the response.
        """
        if self._content_consumed and isinstance(self._content, bool):
            raise StreamConsumedError()
        elif chunk_size is not None and not isinstance(chunk_size, int):
            raise TypeError(
                "chunk_size must be an int, it is instead a %s." % type(chunk_size)
            )
        # simulate reading small chunks of the content
        reused_chunks = iter_slices(self._content, chunk_size)

        stream_chunks = self.generate(chunk_size)

        chunks = reused_chunks if self._content_consumed else stream_chunks

        if decode_unicode:
            chunks = stream_decode_response_unicode(chunks, self)

        async for c in chunks:
            yield c

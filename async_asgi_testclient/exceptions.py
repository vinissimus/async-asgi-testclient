"""Exceptions for TestClient

Base Exception class and sub-classed exceptions to make it easy
(and in some cases, possible at all) to handle errors in different
ways.
"""
from async_asgi_testclient.utils import Message
from typing import Optional


class TestClientError(Exception):
    """An error in async_asgi_testclient"""

    def __init__(self, *args, message: Optional[Message] = None):
        super().__init__(*args)
        self.message = message

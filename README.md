# async-asgi-testclient

[![Build Status](https://travis-ci.com/vinissimus/async-asgi-testclient.svg?branch=master)](https://travis-ci.com/vinissimus/async-asgi-testclient) [![PyPI version](https://badge.fury.io/py/async-asgi-testclient.svg)](https://badge.fury.io/py/async-asgi-testclient) ![](https://img.shields.io/pypi/pyversions/async-asgi-testclient.svg)

Async ASGI TestClient is a library for testing web applications that implements ASGI specification (version 2 and 3).

The motivation behind this project is building a common testing library that doesn't depend on the web framework ([Quart](https://gitlab.com/pgjones/quart), [Startlette](https://github.com/encode/starlette), ...), the same way people are doing ASGI servers like [uvicorn](https://www.uvicorn.org/) or [hypercorn](https://gitlab.com/pgjones/quart) that doesn't depend on the framework.

This library is based on the testing module provided in [Quart](https://gitlab.com/pgjones/quart).

## Quickstart

Requirements: Python 3.6+

Installation:

```bash
pip install async-asgi-testclient
```

## Usage

`my_api.py`:
```python
from quart import Quart, jsonify

app = Quart(__name__)

@app.route("/")
async def root():
    return "plain response"

@app.route("/json")
async def json():
    return jsonify({"hello": "world"})

if __name__ == '__main__':
    app.run()
```

`test_app.py`:
```python
from async_asgi_testclient import TestClient

import pytest

@pytest.mark.asyncio
async def test_quart_app():
    from .my_api import app

    async with TestClient(app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.text == "plain response"

        resp = await client.get("/json")
        assert resp.status_code == 200
        assert resp.json() == {"hello": "world"}
```

## Supports

 - [X] cookies
 - [X] follow redirects
 - [X] response streams
 - [X] request streams
 - [X] websocket support

# async-asgi-testclient

Async ASGI TestClient is a library for testing web applications that implements ASGI specification (version 2 and 3).

The motivation behind this project is building a common testing library that doesn't deppend on the web framework ([Quart](https://gitlab.com/pgjones/quart), [Startlette](https://github.com/encode/starlette), ...), the same way people are doing ASGI servers like [uvicorn](https://www.uvicorn.org/) or [hypercorn](https://gitlab.com/pgjones/quart) that doesn't deppend on the framework.

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
from asgi_testclient import TestClient
from .my_api import app

import pytest

@pytest.mark.asyncio
async def test_quart_app():
    async with TestClient() as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.text == "plain response"

        resp = await client.get("/json")
        assert resp.status_code == 200
        assert resp.json() == {"hello": "world"}
```

1.4.10
------
 - Fix cookie header rendering in WS requests
   [masipcat]

1.4.9
-----
 - Fix websocket scope scheme
   [yanyongyu]

1.4.8
-----
 - fix Cookie header rendering in requests
   [druid8] [Paweł Pecio]

1.4.7
-----
 - Add support for Python 3.10

1.4.6
-----
 - Maintain hard references to tasks to prevent garbage collection
   [MatthewScholefield]

1.4.5
-----
 - Add support for Python 3.9
   [kleschenko]

1.4.4
-----
 - Fix WebSocketSession.receive_json() doesn't support bytes
   [masipcat]

1.4.3
-----
 - Send header Content-Length
   [masipcat]

1.4.2
-----
 - Fixed mypy annotation
   [masipcat]
 - Remove default dict for self.cookies attr
   [otsuka]

1.4.1
-----
 - Don't decode bytes to string to build multipart
   [masipcat]

1.4.0
-----
 - Added argument 'cookies' to `websocket_connect()`
   [masipcat]
 - Renamed `ws.send_str()` to `ws.send_text()`
   [masipcat]
 - Fix return type annotation of the methods invoking open()
   [otsuka]

1.3.0
-----
 - Add support for multipart/form-data
   [masipcat]

1.2.2
-----
 - Quote query_string by default
   [masipcat]

1.2.1
-----
 - Add client (remote peer) to scope
   [aviramha]

1.2.0
-----
 - Added support for Python 3.8
   [masipcat]
 - Updated test dependencies
   [masipcat]

1.1.3
-----
 - added default client headers
   [logileifs]

1.1.2
-----
 - Prevent PytestCollectionWarning
   [podhmo]

1.1.1
-----
 - fast work-around to make websocket query params works
   [grubberr]

1.1.0
-----
 - Relicensed library to MIT License
   [masipcat]

1.0.4
-----
 - ws: added safeguards to validate received ASGI message has expected type and fixed query_string default value
   [masipcat]

1.0.3
-----
 - Fix response with multime cookies
   [masipcat]

1.0.2
-----
 - Fix warning on Py37 and added 'timeout' in 'send_lifespan()'
   [masipcat]

1.0.1
-----
 - Unpinned dependencies
   [masipcat]

1.0.0
-----
 - Websocket client
   [dmanchon]

0.2.2
-----
 - Add 'allow_redirects' to TestClient.open(). Defaults to True
   [masipcat]

0.2.1
-----
 - Support Python 3.6 and small improvements
   [masipcat]

0.2.0
-----
 - Streams and redirects
   [masipcat]

0.1.3
-----
 - Improved cookies support
   [masipcat]

0.1.2
-----
 - flag on the testclient to catch unhandle server exceptions
   [jordic]

0.1
---
 - Initial version
   [masipcat]

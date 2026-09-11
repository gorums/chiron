"""One HTTP request against a `BaseHTTPRequestHandler`, without a socket.

Both servers in this repo - Studio and the tutor bridge - are one handler class over the
standard library's HTTP machinery, and the interesting part is what a route does, not what
the kernel does. So a request here is the handler instance with a `BytesIO` where its
socket would be: everything from the dispatch down runs exactly as it does in the server,
and the tests still open no port (`test_studio.py`: "nothing here opens a socket").

    reply = call(server.Handler, "GET", "/api/state")
    reply.status, reply.json()["courses"]
"""

from __future__ import annotations

import email.parser
import io
import json
from typing import Any, Dict, Optional


class Reply:
    """What the handler wrote back, parsed the way a browser would read it."""

    def __init__(self, raw: bytes):
        self.raw = raw
        head, _, self.body = raw.partition(b"\r\n\r\n")
        first, _, rest = head.partition(b"\r\n")
        parts = first.decode("latin-1").split(" ", 2)
        self.status = int(parts[1]) if len(parts) > 1 else 0
        self.headers = email.parser.Parser().parsestr(rest.decode("latin-1"))

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    @property
    def error(self) -> str:
        """The `error` field of a JSON failure, or "" when the reply is not one."""
        try:
            return self.json().get("error", "")
        except (ValueError, AttributeError):
            return ""

    def __repr__(self):
        return "<Reply %s %s>" % (self.status, self.body[:120])


def call(handler_cls, method: str, path: str, body: Any = None, *,
         raw_body: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None,
         quiet: bool = False) -> Reply:
    """Drive one request through `handler_cls` and return what it wrote.

    `body` is sent as JSON; `raw_body` sends bytes as they are, which is how a malformed or
    oversized request is tested.
    """
    if raw_body is None:
        raw_body = b"" if body is None else json.dumps(body).encode("utf-8")

    handler = handler_cls.__new__(handler_cls)
    handler.rfile = io.BytesIO(raw_body)
    handler.wfile = io.BytesIO()
    handler.command = method
    handler.path = path
    handler.requestline = "%s %s HTTP/1.1" % (method, path)
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 0)
    handler.close_connection = True
    handler.server = None
    lines = ["Content-Length: %d" % len(raw_body), "Host: 127.0.0.1"]
    lines += ["%s: %s" % (k, v) for k, v in (headers or {}).items()]
    handler.headers = email.parser.Parser().parsestr("\r\n".join(lines))
    if quiet:
        handler.log_message = lambda *a, **k: None

    getattr(handler, "do_" + method)()
    return Reply(handler.wfile.getvalue())

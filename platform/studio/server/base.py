"""The HTTP plumbing every route sits on: the registry, the dispatch, the replies.

Nothing here knows what any route does. A route is registered with `@route(METHOD, pattern)`
on one of the groups in this package, and the dispatch below calls the function that was
registered
- so splitting the routes across files is only about being readable, and the server sees
one flat table either way.

The plumbing is what every route shares: reading the body exactly once, sending JSON,
refusing a bad course id, refusing to start a second job on one course, and naming the
provider that could not answer.
"""

from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import re
from http.server import BaseHTTPRequestHandler
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from coursekit.errors import CourseError
from coursekit.settings import SETTINGS

from .. import catalog, modelcall
from ..store import jobs
from ..store.runtime import PREFS, REGISTRY
from ..support.ids import is_course_id, is_module_id
from ..support.log import log

# `studio.port` / `studio.host` in settings.json; STUDIO_PORT and STUDIO_HOST override them.
# The host is loopback unless told otherwise. A container sets 0.0.0.0 to be reachable
# through its published port, and compose publishes that port to loopback on the host so
# the boundary is preserved.
DEFAULT_PORT = int(SETTINGS.get("studio.port"))
DEFAULT_HOST = str(SETTINGS.get("studio.host"))
MAX_BODY = int(SETTINGS.get("studio.maxBodyBytes"))

# What a guard says when the provider a job would run on cannot answer. "%s" is that
# provider, named, because telling someone to install a command-line tool is wrong advice
# for a missing API key - and the reverse.
NOTHING_TO_ASK = "%s cannot answer, so nothing can be %s."
JOB_RUNNING = "That course already has a job running."


# --------------------------------------------------------------------------- routing

Route = Tuple[str, "re.Pattern[str]", Callable]
ROUTES: List[Route] = []


def route(method: str, pattern: str):
    """Register a Handler method for `METHOD <pattern>`. Named groups become arguments."""
    def register(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn))
        return fn
    return register


COURSE = r"/api/courses/(?P<course_id>[^/]+)"
MODULE = COURSE + r"/modules/(?P<mid>[^/]+)"


class Base(BaseHTTPRequestHandler):
    server_version = "CourseStudio/1.2"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):      # access lines go to the log at DEBUG, not the console
        log.debug("%s %s", self.command, fmt % args)

    def log_error(self, fmt, *args):
        log.warning("http: " + (fmt % args))

    # ---- dispatch ----

    def do_GET(self):
        self._dispatch("GET")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        url = urlparse(self.path)
        self.query = parse_qs(url.query)
        self._raw = None
        try:
            self._raw_body()                 # drain first, whatever the route does; see _raw_body
            for verb, pattern, fn in ROUTES:
                found = pattern.match(url.path) if verb == method else None
                if not found:
                    continue
                args = found.groupdict()
                if "course_id" in args and not self._course_exists(args["course_id"]):
                    return
                if "mid" in args and not is_module_id(args["mid"]):
                    return self._fail("Bad module id.")
                return fn(self, **args)
            self._fail("Not found", 404)
        except BrokenPipeError:
            pass
        except CourseError as exc:
            log.warning("%s %s: %s", method, url.path, exc)
            self._fail(str(exc))
        except Exception as exc:  # noqa: BLE001
            log.exception("%s %s failed", method, url.path)
            self._fail(str(exc), 500)

    # ---- plumbing ----

    def _send(self, code: int, body: bytes, ctype: str, extra: Optional[Dict] = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def _json(self, obj: Any, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _fail(self, message: str, code: int = 400, **extra) -> None:
        """`extra` is for what the browser has to branch on rather than print - `why`, the
        kind of failure, which decides whether the page offers Try again."""
        self._json(dict(extra, error=message), code)

    def _raw_body(self) -> bytes:
        """The request body, read exactly once.

        Every request must consume it, even a route that ignores it: the server speaks
        HTTP/1.1 with keep-alive, so bytes left unread sit on the connection and become the
        first bytes of the *next* request - which then fails with "Bad request syntax ('{}')"
        and the browser sees an HTML error page where it expected JSON.
        """
        # One handler instance serves a whole keep-alive connection, so the cache is per
        # request: _dispatch resets it before anything else runs.
        if getattr(self, "_raw", None) is not None:
            return self._raw
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._raw = b""
        elif length > MAX_BODY:
            self.rfile.read(length)
            raise ValueError("Request body too large.")
        else:
            self._raw = self.rfile.read(length)
        return self._raw

    def _body(self) -> Dict[str, Any]:
        raw = self._raw_body()
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _param(self, name: str, default: str = "") -> str:
        return (self.query.get(name) or [default])[0]

    def _course_exists(self, course_id: str) -> bool:
        if not is_course_id(course_id):
            self._fail("Bad course id.")
            return False
        if not os.path.isfile(os.path.join(catalog.course_root(course_id), "course.json")):
            self._fail("No such course.", 404)
            return False
        return True

    def _idle(self, course_id: str, message: str = JOB_RUNNING) -> bool:
        """False, with the reply sent, when a job already runs on the course."""
        if REGISTRY.active_for(course_id):
            self._fail(message)
            return False
        return True

    def _provider(self, doing: str = "written") -> bool:
        """False, with the reply sent, when the provider a job would run on cannot answer."""
        if not modelcall.available():
            message = NOTHING_TO_ASK % (catalog.llm_view()["providerLabel"], doing)
            self._fail(message)
            return False
        return True

    def _model(self, brief: Dict[str, Any]) -> str:
        """The model a job should use: the request's, else Studio's default. Every writing
        form offers the list from settings.json; an unknown name falls back to the default."""
        asked = str(brief.get("model") or "").strip()
        return asked if asked in modelcall.model_aliases() else PREFS.model

    def _start_job(self, job: jobs.Job, work: Callable[[jobs.Job], Any]) -> None:
        REGISTRY.add(job).start(work)
        self._json({"job": job.summary()})

    # ---- static files ----

    @staticmethod
    def _under(base: str, relative: str) -> str:
        """Resolve inside `base` or refuse - the UI path is user-supplied."""
        clean = posixpath.normpath("/" + relative.lstrip("/")).lstrip("/")
        full = os.path.normpath(os.path.join(base, clean))
        if os.path.commonpath([os.path.abspath(base), os.path.abspath(full)]) != os.path.abspath(base):
            raise ValueError("path outside the served directory")
        return full

    def _static(self, path: str) -> None:
        if not os.path.isfile(path):
            return self._fail("Not found", 404)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        with open(path, "rb") as fh:
            self._send(200, fh.read(), ctype)

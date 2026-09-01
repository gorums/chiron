"""The Course Studio server.

A small local app: it serves the Studio UI, lists and builds courses, and runs generation
jobs. Bound to 127.0.0.1 so nothing outside this machine can reach it — it can write files
and spawn processes, so that binding is a security boundary, not a default.

    GET  /                      the UI
    GET  /api/state             courses, Claude availability, running jobs
    POST /api/generate          start a generation job  -> {job}
    POST /api/jobs/<id>/answer  supply the approved curriculum
    POST /api/jobs/<id>/cancel  stop a job
    GET  /api/jobs/<id>/events  Server-Sent Events, replayed from ?from=<n>
    POST /api/courses/<id>/check
    POST /api/courses/<id>/build
    GET  /course/<id>/<file>    serve a built course so it can be opened from the UI
"""

from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import re
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from coursekit import config as ck_config
from coursekit.errors import CourseError

from . import claude_cli, generator, jobs

HERE = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(HERE, "ui")
PLATFORM_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(PLATFORM_DIR)
COURSES_DIR = os.path.join(REPO_ROOT, "courses")
DIST_DIR = os.path.join(REPO_ROOT, "dist")

DEFAULT_PORT = int(os.environ.get("STUDIO_PORT", "8790"))
# Loopback unless told otherwise. Studio writes files and spawns processes, so the default
# must stay local. A container sets 0.0.0.0 to be reachable through its published port, and
# compose publishes that port to 127.0.0.1 on the host so the boundary is preserved.
DEFAULT_HOST = os.environ.get("STUDIO_HOST", "127.0.0.1")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}$")

REGISTRY = jobs.Registry()


# --------------------------------------------------------------------------- course listing


def course_summary(course_id: str) -> Dict[str, Any]:
    root = os.path.join(COURSES_DIR, course_id)
    info: Dict[str, Any] = {"id": course_id, "ok": False, "title": course_id,
                            "modules": 0, "hours": 0, "built": False, "error": ""}
    try:
        cfg = ck_config.load(root)
        info.update(ok=True, title=cfg.title, hours=cfg.hours, tagline=cfg.tagline,
                    subject=cfg.subject, parts=len(cfg.parts))
        count = 0
        for part in cfg.parts:
            directory = os.path.join(cfg.modules_dir, part.dir)
            if os.path.isdir(directory):
                count += len([f for f in os.listdir(directory) if f.endswith(".md")])
        info["modules"] = count
        built = os.path.join(DIST_DIR, cfg.id, cfg.local_file)
        if os.path.isfile(built):
            info.update(built=True, builtAt=os.path.getmtime(built),
                        localFile=cfg.local_file, webFile=cfg.web_file)
    except CourseError as exc:
        info["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)
    job = REGISTRY.active_for(course_id)
    if job:
        info["job"] = job.summary()
    return info


def list_courses() -> list:
    if not os.path.isdir(COURSES_DIR):
        return []
    ids = sorted(d for d in os.listdir(COURSES_DIR)
                 if os.path.isfile(os.path.join(COURSES_DIR, d, "course.json")))
    return [course_summary(cid) for cid in ids]


def state() -> Dict[str, Any]:
    return {
        "courses": list_courses(),
        "claude": {"available": claude_cli.available(), "path": claude_cli.find_cli() or ""},
        "jobs": [j.summary() for j in REGISTRY.all()[:12]],
        "root": REPO_ROOT,
    }


# --------------------------------------------------------------------------- handler


class Handler(BaseHTTPRequestHandler):
    server_version = "CourseStudio/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):      # keep the console for progress, not access logs
        pass

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

    def _fail(self, message: str, code: int = 400) -> None:
        self._json({"error": message}, code)

    def _body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return {}

    # ---- GET ----

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        try:
            if path in ("/", "/index.html"):
                return self._static(os.path.join(UI_DIR, "index.html"))
            if path.startswith("/ui/"):
                return self._static(self._under(UI_DIR, path[4:]))
            if path == "/api/state":
                return self._json(state())
            if path.startswith("/api/jobs/") and path.endswith("/events"):
                return self._events(path.split("/")[3], url)
            if path.startswith("/course/"):
                return self._built_file(path)
            return self._fail("Not found", 404)
        except BrokenPipeError:
            pass
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc), 500)

    def _under(self, base: str, relative: str) -> str:
        """Resolve inside `base` or refuse — the UI path is user-supplied."""
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

    def _built_file(self, path: str) -> None:
        bits = path.split("/", 3)
        if len(bits) < 4 or not SAFE_ID.match(bits[2]):
            return self._fail("Not found", 404)
        return self._static(self._under(os.path.join(DIST_DIR, bits[2]), bits[3]))

    def _events(self, job_id: str, url) -> None:
        """Server-Sent Events, replayed from the client's last index so a refresh loses nothing."""
        job = REGISTRY.get(job_id)
        if not job:
            return self._fail("No such job", 404)
        cursor = int((parse_qs(url.query).get("from") or ["0"])[0])

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        last_beat = time.time()
        try:
            while True:
                for event in job.since(cursor):
                    cursor = event["i"] + 1
                    self.wfile.write(
                        ("data: %s\n\n" % json.dumps(event, ensure_ascii=False)).encode("utf-8")
                    )
                    self.wfile.flush()
                if job.finished and cursor >= len(job.events):
                    return
                if time.time() - last_beat > 15:      # keep proxies and the browser awake
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    last_beat = time.time()
                time.sleep(0.25)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    # ---- POST ----

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/generate":
                return self._generate()
            if path.startswith("/api/jobs/"):
                bits = path.split("/")
                if len(bits) == 5 and bits[4] in ("answer", "cancel"):
                    return self._job_action(bits[3], bits[4])
            if path.startswith("/api/courses/"):
                bits = path.split("/")
                if len(bits) == 5 and bits[4] in ("check", "build"):
                    return self._course_action(bits[3], bits[4])
            return self._fail("Not found", 404)
        except CourseError as exc:
            self._fail(str(exc))
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc), 500)

    def _generate(self) -> None:
        brief = self._body()
        theme = (brief.get("theme") or "").strip()
        if not theme:
            return self._fail("Give the course a theme.")
        try:
            hours = float(brief.get("hours") or 0)
        except (TypeError, ValueError):
            return self._fail("Hours must be a number.")
        if hours < 3:
            return self._fail("Three hours is the shortest course worth structuring.")
        if hours > 200:
            return self._fail("Two hundred hours is beyond what one course should hold.")
        if not claude_cli.available():
            return self._fail("Claude Code is not on this PATH, so nothing can be written.")

        brief["theme"], brief["hours"] = theme, hours
        course_id = (brief.get("id") or "").strip().lower()
        if course_id and not SAFE_ID.match(course_id):
            return self._fail("A course id may hold lowercase letters, digits and hyphens only.")
        brief["id"] = course_id or None
        if brief["id"] and REGISTRY.active_for(brief["id"]):
            return self._fail("That course already has a job running.")

        job = REGISTRY.add(jobs.Job("generate", {"theme": theme, "hours": hours}))
        job.start(lambda j: generator.generate(j, COURSES_DIR, DIST_DIR, brief))
        self._json({"job": job.summary()})

    def _job_action(self, job_id: str, action: str) -> None:
        job = REGISTRY.get(job_id)
        if not job:
            return self._fail("No such job", 404)
        if action == "cancel":
            job.cancel()
            return self._json({"ok": True})
        if not job.provide(self._body()):
            return self._fail("That job is not waiting for an answer.")
        self._json({"ok": True})

    def _course_action(self, course_id: str, action: str) -> None:
        if not SAFE_ID.match(course_id):
            return self._fail("Bad course id.")
        root = os.path.join(COURSES_DIR, course_id)
        if not os.path.isfile(os.path.join(root, "course.json")):
            return self._fail("No such course.", 404)
        if action == "check":
            return self._json({"problems": generator.check_course(root)})
        problems = generator.check_course(root)
        if problems:
            return self._json({"problems": problems, "built": False})
        self._json({"problems": [], "built": True,
                    "result": generator.build_course(root, DIST_DIR)})


# --------------------------------------------------------------------------- entry point


def serve(port: int = DEFAULT_PORT, open_browser: bool = True,
          host: str = "") -> int:
    host = host or DEFAULT_HOST
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    url = "http://%s:%d/" % ("127.0.0.1" if host in ("0.0.0.0", "") else host, port)

    print("  Course Studio")
    print("  %s" % url)
    print("  Claude Code: %s" % (claude_cli.find_cli() or "NOT FOUND — generation disabled"))
    print("  Courses: %s" % COURSES_DIR)
    print("\n  Leave this window open. Ctrl+C to stop.\n")

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
    finally:
        httpd.server_close()
    return 0

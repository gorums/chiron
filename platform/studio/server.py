"""The Course Studio server.

A small local app: it serves the Studio UI, lists and builds courses, runs generation jobs,
keeps the platform-side copy of the reader's progress, and answers the tutor inside a served
course. Bound to 127.0.0.1 so nothing outside this machine can reach it — it writes files
and spawns processes, so that binding is a security boundary, not a default.

    GET  /                                  the UI
    GET  /api/state                         courses (with progress), Claude availability, jobs
    GET  /api/settings                      Studio-wide preferences (model), paths, log file
    POST /api/settings                      change them  {model}
    GET  /api/logs?limit=&level=&q=         the newest log lines, for the Settings page
    POST /api/logs/clear                    empty the in-memory buffer (the file is kept)
    GET  /api/courses/<id>                  one course in detail: parts, modules, files, progress
    GET  /api/courses/<id>/progress         the stored reader state for a course
    PUT  /api/courses/<id>/progress         store it (the served course page syncs here)
    GET  /api/courses/<id>/files?path=<rel> read one markdown/JSON file of the course
    PUT  /api/courses/<id>/files?path=<rel> write it  {text}
    POST /api/courses/<id>/check
    POST /api/courses/<id>/build
    GET  /api/courses/<id>/settings         the editable subset of course.json
    POST /api/courses/<id>/settings         change it (id is locked)
    POST /api/courses/<id>/delete           move the course and its build to state/trash/
    POST /api/courses/<id>/resume           finish a generation run that died  -> {job}
    POST /api/courses/<id>/extend           add a module  {topic, part, minutes, notes} -> {job}
    POST /api/courses/<id>/modules/<mid>/rewrite   rewrite one module  {notes} -> {job}
    POST /api/courses/<id>/modules/<mid>/remove    take one module out (file to state/trash/)
    POST /api/generate                      start a generation job  -> {job}
    POST /api/jobs/<id>/answer              supply the approved curriculum
    POST /api/jobs/<id>/cancel              stop a job
    GET  /api/jobs/<id>/events              Server-Sent Events, replayed from ?from=<n>
    POST /api/ask                           the tutor: {system, messages, model} -> {text}
    GET  /course/<id>/<file>                serve a built course so it can be opened from the UI
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
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from coursekit import config as ck_config
from coursekit import loader as ck_loader
from coursekit.errors import CourseError
from coursekit.paths import COURSES_DIR, DIST_DIR, REPO_ROOT
from coursekit import settings as ck_settings
from coursekit.settings import SETTINGS

from . import claude_cli, generator, jobs, manage, prefs, progress
from .log import log
from . import log as logmod

HERE = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(HERE, "ui")
PLATFORM_DIR = os.path.dirname(HERE)
# COURSES_DIR and DIST_DIR come from coursekit.paths: courses are separate repositories
# and live wherever `.env` or the environment says, not inside this one.
# Reader progress, kept apart from both the course (which is content) and dist/ (which is
# regenerated). `paths.state` / `paths.progress` in settings.json; STUDIO_STATE_ROOT and
# STUDIO_STATE_DIR override them so a container can point at a volume of its own.
STATE_ROOT = SETTINGS.state_dir
STATE_DIR = SETTINGS.progress_dir
JOBS_DIR = os.path.join(STATE_ROOT, "jobs")       # finished jobs, replayable after a restart
TRASH_DIR = os.path.join(STATE_ROOT, "trash")     # removed modules and courses, never deleted
LOGS_DIR = os.path.join(STATE_ROOT, "logs")       # studio.log, rotating
PREFS_PATH = os.path.join(STATE_ROOT, "studio.json")

# `studio.port` / `studio.host` in settings.json; STUDIO_PORT and STUDIO_HOST override them.
# The host is loopback unless told otherwise. Studio writes files and spawns processes, so
# the default must stay local. A container sets 0.0.0.0 to be reachable through its
# published port, and compose publishes that port to loopback on the host so the boundary
# is preserved.
DEFAULT_PORT = int(SETTINGS.get("studio.port"))
DEFAULT_HOST = str(SETTINGS.get("studio.host"))
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}$")
SAFE_MID = re.compile(r"^M\d{2,3}$")
EDITABLE = (".md", ".json")
MAX_BODY = int(SETTINGS.get("studio.maxBodyBytes"))
ASK_TIMEOUT = int(SETTINGS.get("studio.askTimeout"))
RECENT_JOBS = int(SETTINGS.get("studio.recentJobs"))
MIN_HOURS = float(SETTINGS.get("generation.minHours"))
MAX_HOURS = float(SETTINGS.get("generation.maxHours"))

REGISTRY = jobs.Registry(JOBS_DIR)
PROGRESS = progress.Store(STATE_DIR)
PREFS = prefs.Prefs(PREFS_PATH)
LOG_FILE = logmod.configure(LOGS_DIR)


# --------------------------------------------------------------------------- course listing


def _module_ids(cfg) -> List[str]:
    """Module ids in course order, from filenames alone - cheap enough for every listing."""
    ids = []
    for part in cfg.parts:
        directory = os.path.join(cfg.modules_dir, part.dir)
        if not os.path.isdir(directory):
            continue
        for name in sorted(f for f in os.listdir(directory) if f.endswith(".md")):
            ids.append(name.split("-", 1)[0])
    return ids


def course_summary(course_id: str) -> Dict[str, Any]:
    root = os.path.join(COURSES_DIR, course_id)
    info: Dict[str, Any] = {"id": course_id, "ok": False, "title": course_id,
                            "modules": 0, "hours": 0, "built": False, "error": ""}
    try:
        cfg = ck_config.load(root)
        ids = _module_ids(cfg)
        info.update(ok=True, title=cfg.title, hours=cfg.hours, tagline=cfg.tagline,
                    subject=cfg.subject, parts=len(cfg.parts), modules=len(ids),
                    localFile=cfg.local_file, webFile=cfg.web_file,
                    progress=PROGRESS.summary(course_id, ids))
        built = os.path.join(DIST_DIR, cfg.id, cfg.local_file)
        if os.path.isfile(built):
            info.update(built=True, builtAt=os.path.getmtime(built))
        info["resumable"] = can_resume(course_id)
    except CourseError as exc:
        info["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)
    job = REGISTRY.active_for(course_id)
    if job:
        info["job"] = job.summary()
    return info


def course_detail(course_id: str) -> Dict[str, Any]:
    """Everything the course page in Studio shows. Parses the modules, so not for listings."""
    info = course_summary(course_id)
    if not info["ok"]:
        return info
    root = os.path.join(COURSES_DIR, course_id)
    cfg = ck_config.load(root)
    info["parts"] = [dict(p.public(), dir=p.dir) for p in cfg.parts]
    info["audience"] = cfg.audience
    info["practitioner"] = cfg.practitioner
    info["moduleList"] = []
    try:
        for m in ck_loader.load_modules(cfg):
            info["moduleList"].append({
                "id": m.id, "num": m.num, "part": m.part, "title": m.title, "short": m.short,
                "minutes": m.minutes, "sections": len(m.sections),
                "path": os.path.relpath(m.source, root).replace(os.sep, "/"),
            })
    except CourseError as exc:
        info["error"] = str(exc)
    info["files"] = course_files(root)
    record = PROGRESS.load(course_id)
    state_obj = record["state"] if record else {}
    info["moduleProgress"] = _module_progress(state_obj)
    info["questions"] = open_questions(state_obj, info["moduleList"])
    info["settings"] = manage.settings(root)
    return info


def open_questions(state: Dict[str, Any], module_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The passages the reader marked with a question, newest first.

    These are the reader's own record of where the course stopped short - the best brief an
    Add-a-module form can be given.
    """
    titles = {m["id"]: m["title"] for m in module_list}
    out = []
    marks = state.get("marks") if isinstance(state.get("marks"), dict) else {}
    for mid, rows in marks.items():
        for m in rows if isinstance(rows, list) else []:
            if not isinstance(m, dict) or m.get("status") not in ("open", "answered"):
                continue
            out.append({
                "mid": mid, "title": titles.get(mid, mid), "id": m.get("id", ""),
                "sec": m.get("sec"), "text": str(m.get("text") or "")[:400],
                "q": str(m.get("q") or "")[:400], "note": str(m.get("note") or "")[:400],
                "status": m.get("status"), "ts": m.get("ts") or 0,
            })
    return sorted(out, key=lambda q: q["ts"], reverse=True)


def _module_progress(state: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for mid, entry in (state.get("progress") or {}).items():
        if not isinstance(entry, dict):
            continue
        secs = entry.get("secs") or {}
        out[mid] = {
            "done": bool(entry.get("done")),
            "minutes": int(progress._number(entry.get("time")) // 60),
            "read": sum(1 for v in secs.values() if v) if isinstance(secs, dict) else 0,
            "quiz": bool((entry.get("quiz") or {}).get("finished")) if isinstance(entry.get("quiz"), dict) else False,
        }
    return out


def course_files(root: str) -> List[str]:
    """Every markdown and JSON file in the course, as repo-relative posix paths."""
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if name.endswith(EDITABLE):
                out.append(os.path.relpath(os.path.join(base, name), root).replace(os.sep, "/"))
    return out


def list_courses() -> list:
    if not os.path.isdir(COURSES_DIR):
        return []
    ids = sorted(d for d in os.listdir(COURSES_DIR)
                 if os.path.isfile(os.path.join(COURSES_DIR, d, "course.json")))
    return [course_summary(cid) for cid in ids]


def state() -> Dict[str, Any]:
    return {
        "courses": list_courses(),
        "claude": {"available": claude_cli.available(), "path": claude_cli.find_cli() or "",
                   "model": PREFS.model},
        "jobs": [j.summary() for j in REGISTRY.all()[:RECENT_JOBS]],
        "root": REPO_ROOT,
    }


def settings_view() -> Dict[str, Any]:
    return {
        "model": PREFS.model,
        "models": [{"id": m[0], "name": m[1], "note": m[2]} for m in prefs.MODELS],
        "claude": {"available": claude_cli.available(), "path": claude_cli.find_cli() or ""},
        "paths": {"root": REPO_ROOT, "courses": COURSES_DIR, "dist": DIST_DIR,
                  "state": STATE_ROOT, "log": LOG_FILE, "settings": SETTINGS.path,
                  "overlay": SETTINGS.overlay},
        "platform": SETTINGS.describe(),
        "overrides": dict(SETTINGS.overrides),
        "envKeys": dict(ck_settings.ENV_KEYS),
        "logs": {"maxBytes": logmod.MAX_BYTES, "backups": logmod.BACKUPS},
    }


def can_resume(course_id: str) -> bool:
    """A course that does not build clean but still has a curriculum to finish from -
    saved in plan/plan.json, or reconstructible from course.json."""
    root = os.path.join(COURSES_DIR, course_id)
    try:
        generator._load_plan(root)
    except (CourseError, generator.GenerationError, ValueError, OSError):
        return False
    try:
        return bool(generator.check_course(root))
    except CourseError:
        return True


def resolve_course_file(course_id: str, relative: str) -> str:
    """A path inside the course folder, or a ValueError. Only markdown and JSON qualify."""
    root = os.path.join(COURSES_DIR, course_id)
    clean = posixpath.normpath("/" + (relative or "").replace("\\", "/").lstrip("/")).lstrip("/")
    if not clean or clean == "." or not clean.endswith(EDITABLE):
        raise ValueError("Only .md and .json files inside the course can be edited.")
    full = os.path.normpath(os.path.join(root, clean))
    if os.path.commonpath([os.path.abspath(root), os.path.abspath(full)]) != os.path.abspath(root):
        raise ValueError("That path is outside the course.")
    return full


# --------------------------------------------------------------------------- handler


class Handler(BaseHTTPRequestHandler):
    server_version = "CourseStudio/1.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):      # access lines go to the log at DEBUG, not the console
        log.debug("%s %s", self.command, fmt % args)

    def log_error(self, fmt, *args):
        log.warning("http: " + (fmt % args))

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

    def _raw_body(self) -> bytes:
        """The request body, read exactly once.

        Every handler must consume it, even one that ignores it: the server speaks
        HTTP/1.1 with keep-alive, so bytes left unread sit on the connection and become the
        first bytes of the *next* request - which then fails with "Bad request syntax ('{}')"
        and the browser sees an HTML error page where it expected JSON.
        """
        # One handler instance serves a whole keep-alive connection, so the cache is per
        # request: do_GET/do_POST/do_PUT reset it before anything else runs.
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

    def _course_root(self, course_id: str) -> Optional[str]:
        if not SAFE_ID.match(course_id):
            self._fail("Bad course id.")
            return None
        root = os.path.join(COURSES_DIR, course_id)
        if not os.path.isfile(os.path.join(root, "course.json")):
            self._fail("No such course.", 404)
            return None
        return root

    # ---- GET ----

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        self._raw = None
        try:
            self._raw_body()                     # a GET with a body is odd but must not poison the next request
            if path in ("/", "/index.html"):
                return self._static(os.path.join(UI_DIR, "index.html"))
            if path.startswith("/ui/"):
                return self._static(self._under(UI_DIR, path[4:]))
            if path == "/api/state":
                return self._json(state())
            if path.startswith("/api/jobs/") and path.endswith("/events"):
                return self._events(path.split("/")[3], url)
            if path.startswith("/api/courses/"):
                bits = path.split("/")
                if len(bits) == 4:
                    return self._course_get(bits[3])
                if len(bits) == 5 and bits[4] == "progress":
                    return self._progress_get(bits[3])
                if len(bits) == 5 and bits[4] == "files":
                    return self._file_get(bits[3], url)
                if len(bits) == 5 and bits[4] == "settings":
                    return self._settings_get(bits[3])
            if path == "/api/settings":
                return self._json(settings_view())
            if path == "/api/logs":
                q = parse_qs(url.query)
                return self._json({"lines": logmod.recent(
                    limit=int((q.get("limit") or ["400"])[0]),
                    level=(q.get("level") or [""])[0], contains=(q.get("q") or [""])[0]),
                    "file": LOG_FILE})
            if path.startswith("/course/"):
                return self._built_file(path)
            return self._fail("Not found", 404)
        except BrokenPipeError:
            pass
        except CourseError as exc:
            log.warning("GET %s: %s", path, exc)
            self._fail(str(exc))
        except Exception as exc:  # noqa: BLE001
            log.exception("GET %s failed", path)
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

    def _course_get(self, course_id: str) -> None:
        if not self._course_root(course_id):
            return
        self._json(course_detail(course_id))

    def _settings_get(self, course_id: str) -> None:
        root = self._course_root(course_id)
        if not root:
            return
        self._json(manage.settings(root))

    def _progress_get(self, course_id: str) -> None:
        if not self._course_root(course_id):
            return
        record = PROGRESS.load(course_id)
        self._json({"state": record["state"] if record else None,
                    "updatedAt": record["updatedAt"] if record else None})

    def _file_get(self, course_id: str, url) -> None:
        root = self._course_root(course_id)
        if not root:
            return
        relative = (parse_qs(url.query).get("path") or [""])[0]
        try:
            full = resolve_course_file(course_id, relative)
        except ValueError as exc:
            return self._fail(str(exc))
        if not os.path.isfile(full):
            return self._fail("No such file.", 404)
        with open(full, encoding="utf-8") as fh:
            self._json({"path": relative, "text": fh.read()})

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

    # ---- PUT ----

    def do_PUT(self):
        url = urlparse(self.path)
        path = url.path
        self._raw = None
        try:
            self._raw_body()                     # drain first; see _raw_body
            if path.startswith("/api/courses/"):
                bits = path.split("/")
                if len(bits) == 5 and bits[4] == "progress":
                    return self._progress_put(bits[3])
                if len(bits) == 5 and bits[4] == "files":
                    return self._file_put(bits[3], url)
            return self._fail("Not found", 404)
        except CourseError as exc:
            log.warning("PUT %s: %s", path, exc)
            self._fail(str(exc))
        except Exception as exc:  # noqa: BLE001
            log.exception("PUT %s failed", path)
            self._fail(str(exc), 500)

    def _progress_put(self, course_id: str) -> None:
        if not self._course_root(course_id):
            return
        body = self._body()
        state_obj = body.get("state") if "state" in body else body
        if not isinstance(state_obj, dict) or not state_obj:
            return self._fail("Send the page state as a JSON object.")
        record = PROGRESS.save(course_id, state_obj)
        self._json({"ok": True, "updatedAt": record["updatedAt"]})

    def _file_put(self, course_id: str, url) -> None:
        if not self._course_root(course_id):
            return
        relative = (parse_qs(url.query).get("path") or [""])[0]
        try:
            full = resolve_course_file(course_id, relative)
        except ValueError as exc:
            return self._fail(str(exc))
        body = self._body()
        text = body.get("text")
        if not isinstance(text, str):
            return self._fail("Send {text: ...}.")
        if full.endswith(".json"):
            try:
                json.loads(text)
            except ValueError as exc:
                return self._fail("That is not valid JSON: %s" % exc)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text if text.endswith("\n") else text + "\n")
        self._json({"ok": True, "path": relative})

    # ---- POST ----

    def do_POST(self):
        path = urlparse(self.path).path
        self._raw = None
        try:
            self._raw_body()                     # drain first; see _raw_body
            if path == "/api/generate":
                return self._generate()
            if path == "/api/ask":
                return self._ask()
            if path == "/api/settings":
                try:
                    saved = PREFS.save(self._body())
                except ValueError as exc:
                    return self._fail(str(exc))
                log.info("settings: model -> %s", saved["model"])
                return self._json({"ok": True, "settings": settings_view()})
            if path == "/api/logs/clear":
                logmod.clear()
                return self._json({"ok": True})
            if path.startswith("/api/jobs/"):
                bits = path.split("/")
                if len(bits) == 5 and bits[4] in ("answer", "cancel"):
                    return self._job_action(bits[3], bits[4])
            if path.startswith("/api/courses/"):
                bits = path.split("/")
                if len(bits) == 5 and bits[4] in ("check", "build"):
                    return self._course_action(bits[3], bits[4])
                if len(bits) == 5 and bits[4] == "progress":   # sendBeacon can only POST
                    return self._progress_put(bits[3])
                if len(bits) == 5 and bits[4] == "extend":
                    return self._extend(bits[3])
                if len(bits) == 5 and bits[4] == "resume":
                    return self._resume(bits[3])
                if len(bits) == 5 and bits[4] == "settings":
                    return self._settings_post(bits[3])
                if len(bits) == 5 and bits[4] == "delete":
                    return self._delete_course(bits[3])
                if len(bits) == 7 and bits[4] == "modules" and bits[6] == "rewrite":
                    return self._rewrite(bits[3], bits[5])
                if len(bits) == 7 and bits[4] == "modules" and bits[6] == "remove":
                    return self._remove_module(bits[3], bits[5])
            return self._fail("Not found", 404)
        except CourseError as exc:
            log.warning("POST %s: %s", path, exc)
            self._fail(str(exc))
        except Exception as exc:  # noqa: BLE001
            log.exception("POST %s failed", path)
            self._fail(str(exc), 500)

    def _model(self, brief: Dict[str, Any]) -> str:
        """The model a job should use: the request's, else Studio's default."""
        asked = str(brief.get("model") or "").strip()
        return asked if asked in claude_cli.MODEL_ALIASES else PREFS.model

    def _generate(self) -> None:
        brief = self._body()
        theme = (brief.get("theme") or "").strip()
        if not theme:
            return self._fail("Give the course a theme.")
        try:
            hours = float(brief.get("hours") or 0)
        except (TypeError, ValueError):
            return self._fail("Hours must be a number.")
        if hours < MIN_HOURS:
            return self._fail("%g hours is the shortest course worth structuring." % MIN_HOURS)
        if hours > MAX_HOURS:
            return self._fail("%g hours is beyond what one course should hold." % MAX_HOURS)
        if not claude_cli.available():
            return self._fail("Claude Code is not on this PATH, so nothing can be written.")

        brief["theme"], brief["hours"] = theme, hours
        course_id = (brief.get("id") or "").strip().lower()
        if course_id and not SAFE_ID.match(course_id):
            return self._fail("A course id may hold lowercase letters, digits and hyphens only.")
        brief["id"] = course_id or None
        if brief["id"] and REGISTRY.active_for(brief["id"]):
            return self._fail("That course already has a job running.")

        brief["model"] = self._model(brief)
        brief["resume"] = False
        log.info("generate: theme=%r hours=%s model=%s", theme, hours, brief["model"])
        job = REGISTRY.add(jobs.Job("generate", {"theme": theme, "hours": hours, "model": brief["model"]}))
        job.start(lambda j: generator.generate(j, COURSES_DIR, DIST_DIR, brief))
        self._json({"job": job.summary()})

    def _resume(self, course_id: str) -> None:
        root = self._course_root(course_id)
        if not root:
            return
        try:
            generator._load_plan(root)
        except (generator.GenerationError, ValueError) as exc:
            return self._fail("Cannot resume: %s" % exc)
        if not can_resume(course_id):
            return self._fail("Nothing to resume: this course is complete and consistent. Use Build.")
        if not claude_cli.available():
            return self._fail("Claude Code is not on this PATH, so nothing can be written.")
        if REGISTRY.active_for(course_id):
            return self._fail("That course already has a job running.")
        body = self._body()
        cfg = ck_config.load(root)
        brief = {"id": course_id, "theme": cfg.subject, "hours": cfg.hours, "resume": True,
                 "model": self._model(body)}
        log.info("resume: course=%s model=%s", course_id, brief["model"])
        job = REGISTRY.add(jobs.Job("generate", {"theme": cfg.subject, "hours": cfg.hours,
                                                 "course": course_id, "resume": True,
                                                 "model": brief["model"]}))
        job.start(lambda j: generator.generate(j, COURSES_DIR, DIST_DIR, brief))
        self._json({"job": job.summary()})

    def _extend(self, course_id: str) -> None:
        if not self._course_root(course_id):
            return
        brief = self._body()
        if not (brief.get("topic") or "").strip():
            return self._fail("Say what the new module should cover.")
        if not claude_cli.available():
            return self._fail("Claude Code is not on this PATH, so nothing can be written.")
        if REGISTRY.active_for(course_id):
            return self._fail("That course already has a job running.")
        brief["model"] = self._model(brief)
        log.info("extend: course=%s topic=%r model=%s", course_id, brief["topic"], brief["model"])
        job = REGISTRY.add(jobs.Job("extend", {"course": course_id, "topic": brief["topic"]}))
        job.start(lambda j: generator.extend(j, COURSES_DIR, DIST_DIR, course_id, brief))
        self._json({"job": job.summary()})

    def _rewrite(self, course_id: str, mid: str) -> None:
        if not self._course_root(course_id):
            return
        if not SAFE_MID.match(mid):
            return self._fail("Bad module id.")
        brief = self._body()
        if not claude_cli.available():
            return self._fail("Claude Code is not on this PATH, so nothing can be written.")
        if REGISTRY.active_for(course_id):
            return self._fail("That course already has a job running.")
        brief["model"] = self._model(brief)
        log.info("rewrite: course=%s module=%s model=%s", course_id, mid, brief["model"])
        job = REGISTRY.add(jobs.Job("rewrite", {"course": course_id, "module": mid}))
        job.start(lambda j: generator.rewrite(j, COURSES_DIR, DIST_DIR, course_id, mid, brief))
        self._json({"job": job.summary()})

    def _settings_post(self, course_id: str) -> None:
        root = self._course_root(course_id)
        if not root:
            return
        if REGISTRY.active_for(course_id):
            return self._fail("That course has a job running; wait for it to finish.")
        self._json({"ok": True, "settings": manage.update_settings(root, self._body())})

    def _delete_course(self, course_id: str) -> None:
        if not self._course_root(course_id):
            return
        if REGISTRY.active_for(course_id):
            return self._fail("That course has a job running; stop it first.")
        if (self._body().get("confirm") or "") != course_id:
            return self._fail("Type the course id to confirm.")
        PROGRESS.delete(course_id)
        self._json(dict(manage.trash_course(COURSES_DIR, DIST_DIR, TRASH_DIR, course_id), ok=True))

    def _remove_module(self, course_id: str, mid: str) -> None:
        root = self._course_root(course_id)
        if not root:
            return
        if REGISTRY.active_for(course_id):
            return self._fail("That course has a job running; wait for it to finish.")
        removed = manage.remove_module(root, mid, TRASH_DIR)
        self._json(dict(removed, ok=True, problems=generator.check_course(root)))

    def _ask(self) -> None:
        """The tutor, for a course served from here: same origin, no key, no bridge."""
        body = self._body()
        messages = body.get("messages") or []
        if not isinstance(messages, list) or not messages:
            return self._fail("No messages to send.")
        if not claude_cli.available():
            return self._fail("Claude Code is not on this PATH.", 503)
        prompt = claude_cli.chat_prompt(str(body.get("system") or ""), messages)
        try:
            text = claude_cli.ask(prompt, model=self._model(body), timeout=ASK_TIMEOUT)
        except claude_cli.ClaudeFailed as exc:
            log.warning("ask: %s", exc)
            return self._fail(str(exc), 502)
        self._json({"text": text, "mode": "studio"})

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
        root = self._course_root(course_id)
        if not root:
            return
        problems = generator.check_course(root)
        if action == "check":
            log.info("check %s: %s", course_id, "consistent" if not problems else
                     "%d problem(s): %s" % (len(problems), "; ".join(problems)[:600]))
            return self._json({"problems": problems})
        if problems:
            log.warning("build %s refused: %d problem(s): %s", course_id, len(problems),
                        "; ".join(problems)[:600])
            return self._json({"problems": problems, "built": False})
        result = generator.build_course(root, DIST_DIR)
        log.info("build %s: %d modules, %d sections, %s KB", course_id,
                 result["modules"], result["sections"], result["kb"])
        self._json({"problems": [], "built": True, "result": result})


# --------------------------------------------------------------------------- entry point


def serve(port: int = DEFAULT_PORT, open_browser: bool = True,
          host: str = "") -> int:
    host = host or DEFAULT_HOST
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    url = SETTINGS.local_url(host, port) + "/"

    print("  Course Studio")
    print("  %s" % url)
    print("  Claude Code: %s" % (claude_cli.find_cli() or "NOT FOUND — generation disabled"))
    print("  Courses: %s" % COURSES_DIR)
    print("  State: %s" % STATE_ROOT)
    print("  Model: %s   Log: %s" % (PREFS.model, LOG_FILE or "console only"))
    log.info("studio started on %s, model %s, claude %s", url, PREFS.model,
             claude_cli.find_cli() or "NOT FOUND")
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

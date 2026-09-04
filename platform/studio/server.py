"""The Course Studio server: HTTP in, JSON out.

A small local app: it serves the Studio UI, lists and builds courses, runs generation jobs,
keeps the platform-side copy of the reader's progress, and answers the tutor inside a served
course. Bound to 127.0.0.1 so nothing outside this machine can reach it - it writes files
and spawns processes, so that binding is a security boundary, not a default.

Every route is one method on `Handler`, registered with `@route(METHOD, pattern)`. The
pattern is a regex over the URL path; its named groups become the method's keyword
arguments. A `course_id` group is checked and resolved before the method runs (400 for a
bad id, 404 for a missing course) and a `mid` group is checked for shape, so a handler can
trust both. The table at the bottom of the class lists every route in one place.

    GET  /                                  the UI
    GET  /api/state                         courses (with progress), Claude availability, jobs,
                                            the active profile, the study calendar
    GET  /api/search?q=                     every course: modules, sections, passages, glossary terms
    GET  /api/profile                       the active reader profile (a served page asks on boot)
    GET  /api/profiles                      every profile, and which is active
    POST /api/profiles                      {action: switch|add|remove, name}
    POST /api/import                        a course zip  {name, data: base64}  -> {course}
    POST /api/import/git                    clone a course repository  {url}    -> {course}
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
    GET  /api/courses/<id>/export           the course folder as a zip (without .git)
    GET  /api/courses/<id>/reviews          every stored "review this module" result
    POST /api/courses/<id>/settings         change it (id is locked)
    POST /api/courses/<id>/delete           move the course and its build to state/trash/
    POST /api/courses/<id>/resume           finish a generation run that died  -> {job}
    POST /api/courses/<id>/extend           add a module  {topic, part, minutes, notes} -> {job}
    POST /api/courses/<id>/modules/<mid>/rewrite   rewrite one module  {notes} -> {job}
    POST /api/courses/<id>/modules/<mid>/remove    take one module out (file to state/trash/)
    POST /api/courses/<id>/modules/<mid>/move      reorder, or move to another part  {part, index}
    POST /api/courses/<id>/modules/<mid>/review    have Claude read it critically  -> {job}
    POST /api/courses/<id>/modules/<mid>/accept    the owner's own verdict  {accepted: bool}
    POST /api/generate                      start a generation job  -> {job}
    POST /api/jobs/<id>/answer              supply the approved curriculum
    POST /api/jobs/<id>/cancel              stop a job
    GET  /api/jobs/<id>/events              Server-Sent Events, replayed from ?from=<n>
    POST /api/ask                           the tutor: {system, messages, model} -> {text}
    GET  /course/<id>/<file>                serve a built course so it can be opened from the UI
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import posixpath
import re
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from coursekit import config as ck_config
from coursekit import loader as ck_loader
from coursekit.errors import CourseError
from coursekit.paths import COURSES_DIR, DIST_DIR
from coursekit.settings import SETTINGS

from . import catalog, claude_cli, curriculum, editing, generator, jobs, manage, progress, reviews, search, transfer
from . import log as logmod
from .errors import GenerationError
from .files import write_text
from .ids import DEFAULT_PROFILE, is_course_id, is_module_id, is_profile
from .log import log
from .runtime import LOG_FILE, PREFS, PROGRESS_DIR, REGISTRY, STATE_ROOT, TRASH_DIR, store

HERE = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(HERE, "ui")

# `studio.port` / `studio.host` in settings.json; STUDIO_PORT and STUDIO_HOST override them.
# The host is loopback unless told otherwise. A container sets 0.0.0.0 to be reachable
# through its published port, and compose publishes that port to loopback on the host so
# the boundary is preserved.
DEFAULT_PORT = int(SETTINGS.get("studio.port"))
DEFAULT_HOST = str(SETTINGS.get("studio.host"))
MAX_BODY = int(SETTINGS.get("studio.maxBodyBytes"))
ASK_TIMEOUT = int(SETTINGS.get("studio.askTimeout"))
GIT_TIMEOUT = int(SETTINGS.get("studio.gitTimeout"))
SEARCH_LIMIT = int(SETTINGS.get("studio.searchLimit"))
MIN_HOURS = float(SETTINGS.get("generation.minHours"))
MAX_HOURS = float(SETTINGS.get("generation.maxHours"))

NO_CLAUDE = "Claude Code is not on this PATH, so nothing can be written."
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


class Handler(BaseHTTPRequestHandler):
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

    def _fail(self, message: str, code: int = 400) -> None:
        self._json({"error": message}, code)

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

    def _claude(self, message: str = NO_CLAUDE) -> bool:
        """False, with the reply sent, when Claude Code cannot be found."""
        if not claude_cli.available():
            self._fail(message)
            return False
        return True

    def _model(self, brief: Dict[str, Any]) -> str:
        """The model a job should use: the request's, else Studio's default."""
        asked = str(brief.get("model") or "").strip()
        return asked if asked in claude_cli.MODEL_ALIASES else PREFS.model

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

    @route("GET", r"/(index\.html)?")
    def ui_index(self):
        self._static(os.path.join(UI_DIR, "index.html"))

    @route("GET", r"/ui/(?P<path>.+)")
    def ui_file(self, path: str):
        self._static(self._under(UI_DIR, path))

    @route("GET", r"/course/(?P<course_id>[^/]+)/(?P<path>.+)")
    def built_file(self, course_id: str, path: str):
        self._static(self._under(os.path.join(DIST_DIR, course_id), path))

    # ---- the library ----

    @route("GET", r"/api/state")
    def state(self):
        self._json(catalog.state())

    @route("GET", r"/api/search")
    def search(self):
        self._json(search.search(COURSES_DIR, self._param("q"), SEARCH_LIMIT))

    @route("GET", r"/api/settings")
    def settings_get(self):
        self._json(catalog.settings_view())

    @route("POST", r"/api/settings")
    def settings_post(self):
        try:
            saved = PREFS.save(self._body())
        except ValueError as exc:
            return self._fail(str(exc))
        log.info("settings: model -> %s", saved["model"])
        self._json({"ok": True, "settings": catalog.settings_view()})

    @route("GET", r"/api/logs")
    def logs(self):
        lines = logmod.recent(limit=int(self._param("limit", "400")),
                              level=self._param("level"), contains=self._param("q"))
        self._json({"lines": lines, "file": LOG_FILE})

    @route("POST", r"/api/logs/clear")
    def logs_clear(self):
        logmod.clear()
        self._json({"ok": True})

    # ---- reader profiles ----

    @route("GET", r"/api/profile")
    def profile(self):
        self._json({"profile": PREFS.profile})

    @route("GET", r"/api/profiles")
    def profiles_get(self):
        self._json(catalog.profiles_view())

    @route("POST", r"/api/profiles")
    def profiles_post(self):
        body = self._body()
        action = str(body.get("action") or "switch")
        name = str(body.get("name") or "").strip().lower()
        if action in ("switch", "add"):
            try:
                PREFS.save({"profile": name})
            except ValueError as exc:
                return self._fail(str(exc))
            if action == "add":
                os.makedirs(progress.Store(PROGRESS_DIR, name).directory, exist_ok=True)
            log.info("profile -> %s", name)
        elif action == "remove":
            if name == DEFAULT_PROFILE:
                return self._fail("The default profile cannot be removed.")
            if not is_profile(name):
                return self._fail("Bad profile name.")
            directory = progress.Store(PROGRESS_DIR, name).directory
            if os.path.isdir(directory):
                dest = os.path.join(TRASH_DIR, "profile-%s-%s" % (name, time.strftime("%Y%m%d-%H%M%S")))
                os.makedirs(TRASH_DIR, exist_ok=True)
                os.replace(directory, dest)
            if PREFS.profile == name:
                PREFS.save({"profile": DEFAULT_PROFILE})
            log.info("profile %s removed (to trash)", name)
        else:
            return self._fail("Unknown action.")
        self._json(dict(catalog.profiles_view(), ok=True))

    # ---- moving courses in and out ----

    @route("POST", r"/api/import")
    def import_zip(self):
        body = self._body()
        raw = str(body.get("data") or "")
        if "," in raw[:80] and raw.lstrip().startswith("data:"):
            raw = raw.split(",", 1)[1]
        try:
            data = base64.b64decode(raw, validate=True)
        except (ValueError, TypeError):
            return self._fail("Send the zip as base64 in {data}.")
        if not data:
            return self._fail("The upload is empty.")
        course = transfer.import_zip(COURSES_DIR, data)
        log.info("import zip: %s (%d modules) from %s", course["id"], course["modules"],
                 body.get("name") or "upload")
        self._json(dict(course, ok=True, build=self._try_build(course["id"])))

    @route("POST", r"/api/import/git")
    def import_git(self):
        body = self._body()
        course = transfer.import_git(COURSES_DIR, str(body.get("url") or ""), timeout=GIT_TIMEOUT)
        log.info("import git: %s from %s", course["id"], course["url"])
        self._json(dict(course, ok=True, build=self._try_build(course["id"])))

    def _try_build(self, course_id: str) -> Dict[str, Any]:
        """Build a freshly imported course if it is consistent; report why not otherwise."""
        root = catalog.course_root(course_id)
        try:
            problems = generator.check_course(root)
            if problems:
                return {"built": False, "problems": problems}
            return {"built": True, "result": generator.build_course(root, DIST_DIR)}
        except CourseError as exc:
            return {"built": False, "problems": [str(exc)]}

    @route("GET", COURSE + r"/export")
    def export(self, course_id: str):
        data = transfer.export_zip(catalog.course_root(course_id))
        log.info("export %s: %d KB", course_id, len(data) // 1024)
        self._send(200, data, "application/zip",
                   {"Content-Disposition": 'attachment; filename="%s.zip"' % course_id})

    # ---- one course ----

    @route("GET", COURSE)
    def course_get(self, course_id: str):
        self._json(catalog.course_detail(course_id))

    @route("GET", COURSE + r"/settings")
    def course_settings_get(self, course_id: str):
        self._json(manage.settings(catalog.course_root(course_id)))

    @route("POST", COURSE + r"/settings")
    def course_settings_post(self, course_id: str):
        if not self._idle(course_id, "That course has a job running; wait for it to finish."):
            return
        self._json({"ok": True, "settings": manage.update_settings(catalog.course_root(course_id), self._body())})

    @route("GET", COURSE + r"/reviews")
    def reviews_get(self, course_id: str):
        self._json({"reviews": reviews.load_reviews(STATE_ROOT, course_id)})

    @route("POST", COURSE + r"/(?P<action>check|build)")
    def check_or_build(self, course_id: str, action: str):
        root = catalog.course_root(course_id)
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

    @route("POST", COURSE + r"/delete")
    def delete_course(self, course_id: str):
        if not self._idle(course_id, "That course has a job running; stop it first."):
            return
        if (self._body().get("confirm") or "") != course_id:
            return self._fail("Type the course id to confirm.")
        store().delete_everywhere(course_id)
        self._json(dict(manage.trash_course(COURSES_DIR, DIST_DIR, TRASH_DIR, course_id), ok=True))

    # ---- files of a course ----

    @route("GET", COURSE + r"/files")
    def file_get(self, course_id: str):
        relative = self._param("path")
        try:
            full = catalog.resolve_course_file(catalog.course_root(course_id), relative)
        except ValueError as exc:
            return self._fail(str(exc))
        if not os.path.isfile(full):
            return self._fail("No such file.", 404)
        with open(full, encoding="utf-8") as fh:
            self._json({"path": relative, "text": fh.read()})

    @route("PUT", COURSE + r"/files")
    def file_put(self, course_id: str):
        relative = self._param("path")
        try:
            full = catalog.resolve_course_file(catalog.course_root(course_id), relative)
        except ValueError as exc:
            return self._fail(str(exc))
        text = self._body().get("text")
        if not isinstance(text, str):
            return self._fail("Send {text: ...}.")
        if full.endswith(".json"):
            try:
                json.loads(text)
            except ValueError as exc:
                return self._fail("That is not valid JSON: %s" % exc)
        write_text(full, text)
        self._json({"ok": True, "path": relative})

    # ---- reader progress ----

    @route("GET", COURSE + r"/progress")
    def progress_get(self, course_id: str):
        record = store().load(course_id)
        self._json({"state": record["state"] if record else None,
                    "updatedAt": record["updatedAt"] if record else None,
                    "profile": PREFS.profile})

    @route("PUT", COURSE + r"/progress")
    @route("POST", COURSE + r"/progress")      # sendBeacon can only POST
    def progress_put(self, course_id: str):
        # A page names the profile it loaded under. If Studio has since switched to another
        # reader, its state must not land in that reader's file.
        asked = self._param("profile")
        if asked and asked != PREFS.profile:
            return self._fail("Studio is now reading as '%s'; this page belongs to '%s'. Reload it."
                              % (PREFS.profile, asked), 409)
        body = self._body()
        state_obj = body.get("state") if "state" in body else body
        if not isinstance(state_obj, dict) or not state_obj:
            return self._fail("Send the page state as a JSON object.")
        record = store().save(course_id, state_obj)
        self._json({"ok": True, "updatedAt": record["updatedAt"], "profile": PREFS.profile})

    # ---- modules of a course, without a model ----

    @route("POST", MODULE + r"/remove")
    def remove_module(self, course_id: str, mid: str):
        if not self._idle(course_id, "That course has a job running; wait for it to finish."):
            return
        root = catalog.course_root(course_id)
        removed = manage.remove_module(root, mid, TRASH_DIR)
        self._json(dict(removed, ok=True, problems=generator.check_course(root)))

    @route("POST", MODULE + r"/move")
    def move_module(self, course_id: str, mid: str):
        if not self._idle(course_id, "That course has a job running; wait for it to finish."):
            return
        root = catalog.course_root(course_id)
        body = self._body()
        try:
            index = int(body.get("index")) if body.get("index") is not None else -1
        except (TypeError, ValueError):
            index = -1
        moved = manage.move_module(root, mid, str(body.get("part") or ""), index)
        log.info("move %s/%s -> part %s index %s", course_id, mid, moved["part"], index)
        self._json(dict(moved, ok=True, problems=generator.check_course(root)))

    @route("POST", MODULE + r"/accept")
    def accept_module(self, course_id: str, mid: str):
        """"This is good": the owner's verdict, which the review pill then shows."""
        accepted = bool(self._body().get("accepted", True))
        cfg = ck_config.load(catalog.course_root(course_id))
        sources = {m.id: m.source for m in ck_loader.load_modules(cfg)}
        if mid not in sources:
            return self._fail("No module '%s' in this course." % mid, 404)
        reviews.accept_module(STATE_ROOT, course_id, mid, accepted)
        log.info("accept: course=%s module=%s accepted=%s", course_id, mid, accepted)
        self._json({"ok": True, "accepted": accepted,
                    "review": reviews.load_reviews(STATE_ROOT, course_id, sources).get(mid)})

    # ---- jobs: generation and editing with a model ----

    @route("POST", r"/api/generate")
    def generate(self):
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
        if not self._claude():
            return
        course_id = (brief.get("id") or "").strip().lower()
        if course_id and not is_course_id(course_id):
            return self._fail("A course id may hold lowercase letters, digits and hyphens only.")
        if course_id and not self._idle(course_id):
            return

        brief.update(theme=theme, hours=hours, id=course_id or None, model=self._model(brief),
                     resume=False)
        log.info("generate: theme=%r hours=%s model=%s", theme, hours, brief["model"])
        job = jobs.Job("generate", {"theme": theme, "hours": hours, "model": brief["model"]})
        self._start_job(job, lambda j: generator.generate(j, COURSES_DIR, DIST_DIR, brief))

    @route("POST", COURSE + r"/resume")
    def resume(self, course_id: str):
        root = catalog.course_root(course_id)
        try:
            curriculum.load_plan(root)
        except (GenerationError, ValueError) as exc:
            return self._fail("Cannot resume: %s" % exc)
        if not catalog.can_resume(course_id):
            return self._fail("Nothing to resume: this course is complete and consistent. Use Build.")
        if not self._claude() or not self._idle(course_id):
            return
        cfg = ck_config.load(root)
        brief = {"id": course_id, "theme": cfg.subject, "hours": cfg.hours, "resume": True,
                 "model": self._model(self._body())}
        log.info("resume: course=%s model=%s", course_id, brief["model"])
        job = jobs.Job("generate", {"theme": cfg.subject, "hours": cfg.hours, "course": course_id,
                                    "resume": True, "model": brief["model"]})
        self._start_job(job, lambda j: generator.generate(j, COURSES_DIR, DIST_DIR, brief))

    @route("POST", COURSE + r"/extend")
    def extend(self, course_id: str):
        brief = self._body()
        if not (brief.get("topic") or "").strip():
            return self._fail("Say what the new module should cover.")
        if not self._claude() or not self._idle(course_id):
            return
        brief["model"] = self._model(brief)
        log.info("extend: course=%s topic=%r model=%s", course_id, brief["topic"], brief["model"])
        job = jobs.Job("extend", {"course": course_id, "topic": brief["topic"]})
        self._start_job(job, lambda j: editing.extend(j, COURSES_DIR, DIST_DIR, course_id, brief))

    @route("POST", MODULE + r"/rewrite")
    def rewrite(self, course_id: str, mid: str):
        brief = self._body()
        if not self._claude() or not self._idle(course_id):
            return
        brief["model"] = self._model(brief)
        mode = "patch" if brief.get("mode") == "patch" else "rewrite"
        log.info("rewrite: course=%s module=%s mode=%s model=%s", course_id, mid, mode, brief["model"])
        job = jobs.Job("rewrite", {"course": course_id, "module": mid, "mode": mode})
        self._start_job(job, lambda j: editing.rewrite(j, COURSES_DIR, DIST_DIR, course_id, mid, brief))

    @route("POST", MODULE + r"/review")
    def review(self, course_id: str, mid: str):
        if not self._claude("Claude Code is not on this PATH, so nothing can be reviewed."):
            return
        if not self._idle(course_id):
            return
        brief = self._body()
        brief["model"] = self._model(brief)
        log.info("review: course=%s module=%s model=%s", course_id, mid, brief["model"])
        job = jobs.Job("review", {"course": course_id, "module": mid})
        self._start_job(job, lambda j: reviews.review(j, COURSES_DIR, STATE_ROOT, course_id, mid, brief))

    @route("POST", r"/api/jobs/(?P<job_id>[^/]+)/(?P<action>answer|cancel)")
    def job_action(self, job_id: str, action: str):
        job = REGISTRY.get(job_id)
        if not job:
            return self._fail("No such job", 404)
        if action == "cancel":
            job.cancel()
            return self._json({"ok": True})
        if not job.provide(self._body()):
            return self._fail("That job is not waiting for an answer.")
        self._json({"ok": True})

    @route("GET", r"/api/jobs/(?P<job_id>[^/]+)/events")
    def job_events(self, job_id: str):
        """Server-Sent Events, replayed from the client's last index so a refresh loses nothing."""
        job = REGISTRY.get(job_id)
        if not job:
            return self._fail("No such job", 404)
        cursor = int(self._param("from", "0"))

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
                    self.wfile.write(("data: %s\n\n" % json.dumps(event, ensure_ascii=False)).encode("utf-8"))
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

    # ---- the tutor ----

    @route("POST", r"/api/ask")
    def ask(self):
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


# --------------------------------------------------------------------------- entry point


def serve(port: int = DEFAULT_PORT, open_browser: bool = True, host: str = "") -> int:
    host = host or DEFAULT_HOST
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    url = SETTINGS.local_url(host, port) + "/"

    print("  Course Studio")
    print("  %s" % url)
    print("  Claude Code: %s" % (claude_cli.find_cli() or "NOT FOUND — generation disabled"))
    print("  Courses: %s" % COURSES_DIR)
    print("  State: %s" % STATE_ROOT)
    print("  Model: %s   Profile: %s   Log: %s" % (PREFS.model, PREFS.profile, LOG_FILE or "console only"))
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

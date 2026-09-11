"""The Course Studio server: HTTP in, JSON out.

A small local app: it serves the Studio UI, lists and builds courses, runs generation jobs,
keeps the platform-side copy of the reader's progress, and answers the tutor inside a served
course. Bound to 127.0.0.1 so nothing outside this machine can reach it - it writes files
and spawns processes, so that binding is a security boundary, not a default.

Every route is one method, registered with `@route(METHOD, pattern)` on the group it
belongs to - `pages`, `state`, `settings`, `courses`, `modules`, `writing`, `jobs`,
`tutor` - and `Handler` below is those groups over the plumbing in `base`. The
pattern is a regex over the URL path; its named groups become the method's keyword
arguments. A `course_id` group is checked and resolved before the method runs (400 for a
bad id, 404 for a missing course) and a `mid` group is checked for shape, so a handler can
trust both. The table below lists every route in one place, and a test checks it against
what is actually registered.

    GET  /                                  the UI
    GET  /ui/shared/<file>                  the design system both surfaces are built from
                                            (platform/web: tokens.css, base.css, core/dom.js)
    GET  /api/state                         courses (with progress), providers and models, jobs,
                                            the active profile, the study calendar, Jupyter
    GET  /api/jupyter                       the Jupyter server: reachable?, its address, the token a served page uses
    GET  /api/search?q=                     every course: modules, sections, passages, glossary terms
    GET  /api/profile                       the active reader profile (a served page asks on boot)
    GET  /api/profiles                      every profile, and which is active
    POST /api/profiles                      {action: switch|add|remove, name}
    POST /api/import                        a course zip  {name, data: base64}  -> {course}
    POST /api/import/git                    clone a course repository  {url}    -> {course}
    GET  /api/settings                      Studio-wide preferences (model), paths, log file
    POST /api/settings                      change them  {model}
    GET  /api/models                        the model list in use, and whether it is Studio's own
    PUT  /api/models                        replace it  {list: [{id, alias, label, note}]}
    POST /api/models/reset                  forget Studio's list; the platform's applies again
    POST /api/models/test                   ask once, this model only, on the provider that reaches it  {model, provider} -> {ok, seconds, error}
    POST /api/models/discover               look for new or retired models now (every provider, asked what it knows)
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
    POST /api/courses/<id>/settings         change it (id is locked)
    POST /api/courses/<id>/delete           move the course and its build to state/trash/
    POST /api/courses/<id>/resume           finish a generation run that died  {figures, notebooks, model} -> {job}
    POST /api/courses/<id>/extend           add a module  {topic, part, minutes, notes, model} -> {job}
    POST /api/courses/<id>/figures          draw figures for every module without any  {all} -> {job}
    POST /api/courses/<id>/notebooks        write notebooks for every module without any  {all} -> {job}
    POST /api/courses/<id>/modules/<mid>/rewrite   rewrite one module  {notes, mode, model} -> {job}
    POST /api/courses/<id>/modules/<mid>/remove    take one module out (file to state/trash/)
    POST /api/courses/<id>/modules/<mid>/move      reorder, or move to another part  {part, index}
    POST /api/courses/<id>/modules/<mid>/review    have the model read it critically  -> {job}
    POST /api/courses/<id>/modules/<mid>/figures   draw (or redraw) its figures  -> {job}
    POST /api/courses/<id>/modules/<mid>/notebooks write (or replace) its notebooks  -> {job}
    POST /api/courses/<id>/modules/<mid>/accept    the owner's own verdict  {accepted: bool}
    GET  /api/courses/<id>/modules/<mid>/prompts   every prompt this module is written from -> {stages}
    PUT  /api/courses/<id>/modules/<mid>/prompts   replace one, or take the override away  {stage, text}
    POST /api/plan/prompt                   the prompts one module of a plan would be written from  {plan, mid} -> {stages}
    POST /api/generate                      start a generation job  {theme, hours, ..., model} -> {job}
    POST /api/jobs/<id>/answer              supply the approved curriculum
    POST /api/jobs/<id>/cancel              stop a job
    GET  /api/jobs/<id>/events              Server-Sent Events, replayed from ?from=<n>
    POST /api/ask                           the tutor: {system, messages, model} -> {text}
    GET  /course/<id>/<file>                serve a built course so it can be opened from the UI
"""

from __future__ import annotations

import threading
import webbrowser
from http.server import ThreadingHTTPServer

from coursekit.paths import COURSES_DIR
from coursekit.settings import SETTINGS

from .. import catalog, discover
from ..store.runtime import LOG_FILE, PREFS, STATE_ROOT
from ..support.log import log
from .base import DEFAULT_HOST, DEFAULT_PORT, ROUTES, Base, route  # noqa: F401  (re-exported)
from .courses import CourseRoutes
from .jobs import JobRoutes
from .modules import ModuleRoutes
from .pages import SHARED_UI, Pages  # noqa: F401  (SHARED_UI is re-exported)
from .settings import SettingsRoutes
from .state import StateRoutes
from .tutor import TutorRoutes
from .writing import WritingRoutes


class Handler(Pages, StateRoutes, SettingsRoutes, CourseRoutes, ModuleRoutes,
              WritingRoutes, JobRoutes, TutorRoutes, Base):
    """Every route group, over the plumbing they share.

    The groups carry no state and override nothing, so the order here is the reading order
    of the route table above and not a resolution order. Dispatch does not go through this
    class at all - the dispatch in `base` calls the function `@route` registered - so a group
    is a file boundary and nothing more.
    """


# --------------------------------------------------------------------------- entry point


def _writer_line() -> str:
    """What a generation run would go through, and whether it can answer right now. A path to
    a binary was the honest answer when one tool was the only way in; now it is a provider."""
    view = catalog.llm_view()
    if view["available"]:
        return "%s · model %s" % (view["providerLabel"], view["model"])
    return "%s — NOT READY, %s" % (view["providerLabel"], view["hint"] or "nothing can be written")


def serve(port: int = DEFAULT_PORT, open_browser: bool = True, host: str = "") -> int:
    host = host or DEFAULT_HOST
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    url = SETTINGS.local_url(host, port) + "/"

    print("  Course Studio")
    print("  %s" % url)
    print("  Writes with: %s" % _writer_line())
    print("  Courses: %s" % COURSES_DIR)
    print("  State: %s" % STATE_ROOT)
    print("  Model: %s   Profile: %s   Log: %s" % (PREFS.model, PREFS.profile, LOG_FILE or "console only"))
    log.info("studio started on %s, model %s, provider %s", url, PREFS.model, _writer_line())
    print("\n  Leave this window open. Ctrl+C to stop.\n")

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    discover.schedule()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
    finally:
        httpd.server_close()
    return 0

"""A course as a whole: in, out, checked, built, deleted - and the reader's progress in it.

Everything here works without a model. `_try_build` is the shared tail: whatever just changed
the course is followed by a rebuild, and a build that fails is reported rather than raised,
because by then the thing the user asked for has already happened.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict

from coursekit.course import figures as ck_figures
from coursekit.course import notebooks as ck_notebooks
from coursekit.errors import CourseError
from coursekit.paths import COURSES_DIR, DIST_DIR
from coursekit.settings import SETTINGS

from .. import catalog, manage, transfer
from ..authoring import generator
from ..store.runtime import PREFS, TRASH_DIR, store
from ..support.files import write_text
from ..support.log import log
from .base import COURSE, route

GIT_TIMEOUT = int(SETTINGS.get("studio.gitTimeout"))


class CourseRoutes:
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
        if full.endswith(".svg"):
            problem = ck_figures.first_problem(text)
            if problem:
                return self._fail("That figure %s." % problem)
            text = ck_figures.sanitize(text)
        if full.endswith(".ipynb"):
            problem = ck_notebooks.first_problem(text)
            if problem:
                return self._fail("That notebook %s." % problem)
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

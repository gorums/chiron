"""Self-tests for Studio's HTTP layer.

    python platform/tests/test_server.py

`test_studio.py` covers what Studio does; this covers how a browser asks for it. Every test
drives a real request through the real `Handler` - the dispatch, the guards, the body, the
status code - with a `BytesIO` where the socket would be (`fakehttp.py`), so nothing here
opens a port and nothing calls a model.

The library, `dist/` and the whole state directory are redirected into a temporary folder
for the duration of each test by `redirect_paths`, because these routes write files.
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = os.path.dirname(HERE)
sys.path.insert(0, PLATFORM)
sys.path.insert(0, HERE)

from coursekit.settings import SETTINGS  # noqa: E402

# The tests describe the platform's list, not what this machine's Studio last saved over it.
SETTINGS.studio_file = ""
SETTINGS.reload()

from fakehttp import call  # noqa: E402
from test_build import CourseFixture  # noqa: E402

from studio import catalog, modelcall, transfer  # noqa: E402
from studio.authoring import editing, generator, reviews  # noqa: E402
from studio.server import Handler  # noqa: E402
from studio.store import jobs, prefs  # noqa: E402


def patch_global(test, name, value):
    """Set a module-level name to `value` everywhere in the platform that holds one.

    Studio resolves `COURSES_DIR`, `STATE_ROOT`, `REGISTRY` and `PREFS` once at import, into
    whichever modules need them - that is what keeps a route from re-deriving a path. A test
    therefore has to redirect the name in every module that took a copy, which is this.
    """
    for module in list(sys.modules.values()):
        if not getattr(module, "__name__", "").split(".")[0] in ("coursekit", "studio"):
            continue
        if name in vars(module):
            test.addCleanup(setattr, module, name, vars(module)[name])
            setattr(module, name, value)


def redirect_paths(test):
    """A whole platform in a temporary folder: courses/, dist/ and state/."""
    tmp = tempfile.mkdtemp(prefix="studio-http-")
    test.addCleanup(shutil.rmtree, tmp, True)
    state = os.path.join(tmp, "state")
    where = {"COURSES_DIR": os.path.join(tmp, "courses"),
             "DIST_DIR": os.path.join(tmp, "dist"),
             "STATE_ROOT": state,
             "PROGRESS_DIR": os.path.join(state, "progress"),
             "JOBS_DIR": os.path.join(state, "jobs"),
             "TRASH_DIR": os.path.join(state, "trash")}
    for name, value in where.items():
        os.makedirs(value, exist_ok=True)
        patch_global(test, name, value)
    patch_global(test, "REGISTRY", jobs.Registry(where["JOBS_DIR"]))
    patch_global(test, "PREFS", prefs.Prefs(os.path.join(state, "studio.json")))
    return tmp, where


class ServerTest(unittest.TestCase):
    """One temporary library, and a fixture course in it called `fixture`."""

    def setUp(self):
        self.tmp, self.where = redirect_paths(self)
        self.courses = self.where["COURSES_DIR"]
        self.dist = self.where["DIST_DIR"]
        # `/api/state` asks whether Jupyter is up, which is the one route that would open a
        # socket. It is stubbed for every test; `TestStateRoutes` says what the page is told.
        from studio import jupyter
        self.addCleanup(setattr, jupyter, "probe", jupyter.probe)
        jupyter.probe = lambda force=False: None

    def fixture(self, course_id="fixture"):
        self.course = CourseFixture(self.courses, course_id=course_id)
        return self.course

    def get(self, path, **kw):
        return call(Handler, "GET", path, **kw)

    def post(self, path, body=None, **kw):
        return call(Handler, "POST", path, body, **kw)

    def put(self, path, body=None, **kw):
        return call(Handler, "PUT", path, body, **kw)

    def no_model(self):
        """A provider that cannot answer: what every writing route is guarded against."""
        self.addCleanup(setattr, modelcall, "available", modelcall.available)
        modelcall.available = lambda: False

    def a_model(self, alias="opus"):
        self.addCleanup(setattr, modelcall, "available", modelcall.available)
        self.addCleanup(setattr, modelcall, "model_aliases", modelcall.model_aliases)
        modelcall.available = lambda: True
        modelcall.model_aliases = lambda: {alias: alias}

    def no_work(self):
        """Every job body replaced by one that parks until the test is over, so a started
        job is a running job - which is what the one-job-per-course guard is about."""
        self.done = threading.Event()
        self.addCleanup(self.done.set)
        for module, name in ((generator, "generate"), (editing, "extend"), (editing, "rewrite"),
                             (editing, "draw"), (editing, "notebooks_job"), (reviews, "review")):
            self.addCleanup(setattr, module, name, getattr(module, name))
            setattr(module, name, lambda *a, **kw: self.done.wait(10) and {"ok": True})


# --------------------------------------------------------------------------- the plumbing


class TestDispatch(ServerTest):
    """`server/base.py`: what every route sits on."""

    def test_an_unknown_path_is_a_404_in_json(self):
        reply = self.get("/api/nothing-here")
        self.assertEqual(reply.status, 404)
        self.assertEqual(reply.error, "Not found")

    def test_a_route_is_matched_by_method_too(self):
        self.assertEqual(self.post("/api/state").status, 404)

    def test_a_bad_course_id_never_reaches_the_disk(self):
        reply = self.get("/api/courses/..%2Fetc/files?path=course.json")
        self.assertEqual(reply.status, 400)
        self.assertEqual(reply.error, "Bad course id.")

    def test_a_missing_course_is_a_404_before_the_handler_runs(self):
        reply = self.get("/api/courses/absent")
        self.assertEqual(reply.status, 404)
        self.assertEqual(reply.error, "No such course.")

    def test_a_bad_module_id_is_refused_by_shape(self):
        self.fixture()
        reply = self.post("/api/courses/fixture/modules/nope/accept", {"accepted": True})
        self.assertEqual(reply.status, 400)
        self.assertEqual(reply.error, "Bad module id.")

    def test_the_body_is_read_even_by_a_route_that_ignores_it(self):
        """Bytes left unread become the first bytes of the next request on the connection
        (CONVENTIONS.md "Gotchas")."""
        payload = json.dumps({"ignored": "x" * 200}).encode("utf-8")
        handler = Handler.__new__(Handler)
        reply = self.post("/api/logs/clear", {"ignored": "x" * 200})
        self.assertEqual(reply.status, 200)
        del handler, payload

    def test_an_oversized_body_is_refused_rather_than_buffered(self):
        from studio.server import base
        patch_global(self, "MAX_BODY", 32)
        base.MAX_BODY = 32
        self.addCleanup(setattr, base, "MAX_BODY", int(SETTINGS.get("studio.maxBodyBytes")))
        reply = self.post("/api/settings", {"model": "x" * 200})
        self.assertEqual(reply.status, 500)
        self.assertIn("too large", reply.error)

    def test_a_body_that_is_not_json_is_read_as_nothing(self):
        reply = self.post("/api/profiles", raw_body=b"<html>")
        self.assertEqual(reply.status, 400)
        self.assertIn("profile name", reply.error)

    def test_a_course_error_is_the_user_s_problem_and_a_400(self):
        self.fixture()
        broken = os.path.join(self.courses, "fixture", "course.json")
        with open(broken, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        reply = self.post("/api/courses/fixture/check")
        self.assertEqual(reply.status, 400)
        self.assertTrue(reply.error)

    def test_an_unexpected_error_is_a_500_and_still_json(self):
        old = catalog.state
        catalog.state = lambda: 1 / 0
        self.addCleanup(setattr, catalog, "state", old)
        reply = self.get("/api/state")
        self.assertEqual(reply.status, 500)
        self.assertIn("division", reply.error)

    def test_every_reply_says_not_to_cache_it(self):
        self.assertEqual(self.get("/api/state").headers.get("Cache-Control"), "no-store")


class TestStaticRoutes(ServerTest):
    """`server/pages.py`: the UI, the design system both surfaces share, a built course."""

    def test_the_root_serves_the_studio_ui(self):
        reply = self.get("/")
        self.assertEqual(reply.status, 200)
        self.assertIn("<script", reply.text())

    def test_the_design_system_is_linked_not_copied(self):
        """Studio links `platform/web/`'s three files rather than keeping its own
        (CONVENTIONS.md "The design system")."""
        for name in ("tokens.css", "base.css", "dom.js"):
            reply = self.get("/ui/shared/" + name)
            self.assertEqual(reply.status, 200, name)
            self.assertTrue(reply.body)

    def test_only_the_three_shared_files_are_served(self):
        self.assertEqual(self.get("/ui/shared/studio.css").status, 404)

    def test_a_ui_file_outside_the_ui_directory_is_refused(self):
        reply = self.get("/ui/../../settings.json")
        self.assertIn(reply.status, (400, 404))
        self.assertNotIn("providers", reply.text())

    def test_a_built_course_is_served_from_dist(self):
        course = self.fixture()
        course.build(os.path.join(self.dist, "fixture"))
        reply = self.get("/course/fixture/fixture-course-local.html")
        self.assertEqual(reply.status, 200)
        self.assertIn("text/html", reply.headers.get("Content-Type", ""))

    def test_a_course_that_was_never_built_is_a_404(self):
        self.fixture()
        self.assertEqual(self.get("/course/fixture/fixture-course.html").status, 404)


# --------------------------------------------------------------------------- one course


class TestCourseRoutes(ServerTest):
    def test_the_detail_carries_the_parts_and_the_modules(self):
        self.fixture()
        detail = self.get("/api/courses/fixture").json()
        self.assertEqual(detail["id"], "fixture")
        self.assertEqual(detail["modules"], 6)
        self.assertEqual([m["id"] for m in detail["moduleList"]][:2], ["M01", "M02"])
        self.assertEqual(detail["profile"], "default")

    def test_check_reports_every_problem_without_building(self):
        course = self.fixture()
        course.write_suggestions({mid: [["one?"]] for mid in course.ids})
        reply = self.post("/api/courses/fixture/check")
        self.assertEqual(reply.status, 200)
        self.assertGreater(len(reply.json()["problems"]), 1)
        self.assertFalse(os.path.isdir(os.path.join(self.dist, "fixture")))

    def test_build_writes_dist_and_says_what_it_wrote(self):
        self.fixture()
        result = self.post("/api/courses/fixture/build").json()
        self.assertTrue(result["built"])
        self.assertEqual(result["result"]["modules"], 6)
        self.assertTrue(os.path.isfile(os.path.join(self.dist, "fixture", "fixture-course-local.html")))

    def test_a_broken_course_is_not_built(self):
        course = self.fixture()
        course.write_assessments({})
        result = self.post("/api/courses/fixture/build").json()
        self.assertFalse(result["built"])
        self.assertTrue(result["problems"])

    def test_the_settings_form_is_the_editable_subset_of_the_manifest(self):
        self.fixture()
        form = self.get("/api/courses/fixture/settings").json()
        for key in ("title", "tagline", "audience", "parts", "anchor", "milestones"):
            self.assertIn(key, form)

    def test_the_id_is_shown_and_locked(self):
        """It is the reader's storage key: changing it orphans every existing save."""
        self.fixture()
        reply = self.post("/api/courses/fixture/settings", {"id": "something-else"})
        self.assertEqual(reply.status, 400)
        self.assertTrue(os.path.isdir(os.path.join(self.courses, "fixture")))

    def test_settings_can_be_changed(self):
        self.fixture()
        reply = self.post("/api/courses/fixture/settings", {"title": "A better title"})
        self.assertEqual(reply.status, 200)
        self.assertEqual(reply.json()["settings"]["title"], "A better title")

    def test_a_course_with_a_job_running_will_not_take_settings(self):
        self.fixture()
        from studio.server import base
        base.REGISTRY.add(jobs.Job("generate", {"course": "fixture"}))
        base.REGISTRY.active_for = lambda course_id: True
        reply = self.post("/api/courses/fixture/settings", {"title": "x"})
        self.assertEqual(reply.status, 400)
        self.assertIn("job running", reply.error)

    def test_deleting_needs_the_id_typed_back(self):
        self.fixture()
        self.assertEqual(self.post("/api/courses/fixture/delete", {}).status, 400)
        self.assertEqual(self.post("/api/courses/fixture/delete", {"confirm": "wrong"}).status, 400)
        reply = self.post("/api/courses/fixture/delete", {"confirm": "fixture"})
        self.assertEqual(reply.status, 200)
        self.assertFalse(os.path.isdir(os.path.join(self.courses, "fixture")))
        self.assertTrue(os.listdir(self.where["TRASH_DIR"]), "moved, never erased")


class TestCourseFiles(ServerTest):
    """`GET/PUT /api/courses/<id>/files`: raw editing, confined to the course."""

    def setUp(self):
        super().setUp()
        self.fixture()

    def test_a_file_comes_back_as_text(self):
        reply = self.get("/api/courses/fixture/files?path=course.json")
        self.assertEqual(reply.status, 200)
        self.assertIn("fixture", reply.json()["text"])

    def test_a_path_climbing_out_of_the_course_lands_back_inside_it(self):
        reply = self.get("/api/courses/fixture/files?path=../../settings.json")
        self.assertEqual(reply.status, 404, "normalised to settings.json inside the course")
        self.assertNotIn("providers", reply.text())

    def test_only_the_four_editable_kinds_of_file(self):
        reply = self.get("/api/courses/fixture/files?path=README.txt")
        self.assertEqual(reply.status, 400)
        self.assertIn(".ipynb", reply.error)

    def test_a_file_that_is_not_there_is_a_404(self):
        self.assertEqual(self.get("/api/courses/fixture/files?path=modules/M99.md").status, 404)

    def test_markdown_is_written_through(self):
        path = "modules/01-foundations/M01-lesson.md"
        reply = self.put("/api/courses/fixture/files?path=" + path, {"text": "# M01 — new\n"})
        self.assertEqual(reply.status, 200)
        with open(os.path.join(self.courses, "fixture", path), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "# M01 — new\n")

    def test_the_body_has_to_carry_text(self):
        reply = self.put("/api/courses/fixture/files?path=course.json", {"text": 12})
        self.assertEqual(reply.status, 400)

    def test_json_is_parsed_before_it_is_written(self):
        reply = self.put("/api/courses/fixture/files?path=course.json", {"text": "{nope"})
        self.assertEqual(reply.status, 400)
        self.assertIn("not valid JSON", reply.error)

    def test_a_figure_is_checked_and_sanitised(self):
        good = '<svg viewBox="0 0 10 10"><script>alert(1)</script><rect width="3"/></svg>'
        reply = self.put("/api/courses/fixture/files?path=figures/M01-1.svg", {"text": good})
        self.assertEqual(reply.status, 200)
        with open(os.path.join(self.courses, "fixture", "figures", "M01-1.svg"), encoding="utf-8") as fh:
            self.assertNotIn("<script", fh.read(), "a <style> or a <script> would reach the page")

    def test_a_figure_without_a_viewbox_is_refused(self):
        reply = self.put("/api/courses/fixture/files?path=figures/M01-2.svg",
                         {"text": "<svg><rect/></svg>"})
        self.assertEqual(reply.status, 400)
        self.assertIn("figure", reply.error)

    def test_a_notebook_is_checked(self):
        reply = self.put("/api/courses/fixture/files?path=notebooks/M01-1.ipynb",
                         {"text": json.dumps({"nbformat": 3, "cells": []})})
        self.assertEqual(reply.status, 400)
        self.assertIn("notebook", reply.error)


class TestProgressRoutes(ServerTest):
    """The platform's copy of a reader's state, and the profile it belongs to."""

    def setUp(self):
        super().setUp()
        self.fixture()

    def test_nothing_stored_yet_is_not_an_error(self):
        body = self.get("/api/courses/fixture/progress").json()
        self.assertIsNone(body["state"])
        self.assertEqual(body["profile"], "default")

    def test_a_page_syncs_and_reads_back_what_it_sent(self):
        self.put("/api/courses/fixture/progress", {"state": {"mods": {"M01": {"read": 1}}}})
        body = self.get("/api/courses/fixture/progress").json()
        self.assertEqual(body["state"]["mods"]["M01"]["read"], 1)
        self.assertTrue(body["updatedAt"])

    def test_sendbeacon_posts_the_same_shape(self):
        self.assertEqual(self.post("/api/courses/fixture/progress", {"mods": {}, "v": 1}).status, 200)

    def test_an_empty_state_is_refused_rather_than_stored(self):
        reply = self.put("/api/courses/fixture/progress", {"state": {}})
        self.assertEqual(reply.status, 400)

    def test_a_page_belonging_to_another_reader_is_told_to_reload(self):
        """One reader's state must never land in another's file."""
        reply = self.put("/api/courses/fixture/progress?profile=someone-else", {"mods": {"M01": {}}})
        self.assertEqual(reply.status, 409)
        self.assertIn("default", reply.error)

    def test_device_settings_are_stripped_on_the_way_in(self):
        self.put("/api/courses/fixture/progress",
                 {"state": {"mods": {}, "bridge": {"keys": {"anthropic": "sk-ant-secret"}}}})
        stored = self.get("/api/courses/fixture/progress").json()["state"]
        self.assertNotIn("bridge", stored, "a key never leaves the browser")


class TestImportAndExport(ServerTest):
    def test_a_course_exported_and_imported_again_is_the_same_course(self):
        self.fixture()
        exported = self.get("/api/courses/fixture/export")
        self.assertEqual(exported.status, 200)
        self.assertIn("fixture.zip", exported.headers.get("Content-Disposition", ""))
        shutil.rmtree(os.path.join(self.courses, "fixture"))

        reply = self.post("/api/import", {"name": "fixture.zip",
                                          "data": base64.b64encode(exported.body).decode()})
        self.assertEqual(reply.status, 200)
        self.assertEqual(reply.json()["id"], "fixture")
        self.assertTrue(reply.json()["build"]["built"], "a consistent import is built at once")

    def test_a_data_url_from_the_drop_zone_is_accepted(self):
        self.fixture("other")
        data = transfer.export_zip(os.path.join(self.courses, "other"))
        shutil.rmtree(os.path.join(self.courses, "other"))
        payload = "data:application/zip;base64," + base64.b64encode(data).decode()
        self.assertEqual(self.post("/api/import", {"data": payload}).status, 200)

    def test_an_import_over_a_course_that_exists_is_refused_not_merged(self):
        self.fixture()
        data = transfer.export_zip(os.path.join(self.courses, "fixture"))
        reply = self.post("/api/import", {"data": base64.b64encode(data).decode()})
        self.assertEqual(reply.status, 400)

    def test_something_that_is_not_base64_is_named_as_such(self):
        reply = self.post("/api/import", {"data": "not base 64 at all!!"})
        self.assertEqual(reply.status, 400)
        self.assertIn("base64", reply.error)

    def test_an_empty_upload_is_refused(self):
        self.assertEqual(self.post("/api/import", {"data": ""}).status, 400)

    def test_a_zip_that_is_no_course_is_refused(self):
        import io as _io
        import zipfile
        buf = _io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("notes/readme.txt", "hello")
        reply = self.post("/api/import", {"data": base64.b64encode(buf.getvalue()).decode()})
        self.assertEqual(reply.status, 400)
        self.assertIn("course.json", reply.error)

    def test_an_import_that_does_not_validate_says_why_instead_of_building(self):
        course = self.fixture()
        course.write_assessments({})
        data = transfer.export_zip(os.path.join(self.courses, "fixture"))
        shutil.rmtree(os.path.join(self.courses, "fixture"))
        reply = self.post("/api/import", {"data": base64.b64encode(data).decode()})
        self.assertEqual(reply.status, 200)
        self.assertFalse(reply.json()["build"]["built"])
        self.assertTrue(reply.json()["build"]["problems"])

    def test_only_a_git_url_becomes_a_subprocess_argument(self):
        reply = self.post("/api/import/git", {"url": "; rm -rf /"})
        self.assertEqual(reply.status, 400)


# --------------------------------------------------------------------------- one module


class TestModuleRoutes(ServerTest):
    def setUp(self):
        super().setUp()
        self.fixture()

    def test_a_module_is_removed_to_the_trash_with_its_data(self):
        reply = self.post("/api/courses/fixture/modules/M02/remove")
        self.assertEqual(reply.status, 200)
        self.assertEqual(reply.json()["problems"], [], "the course still validates")
        self.assertTrue(any("M02" in n for n in os.listdir(self.where["TRASH_DIR"])))

    def test_a_module_moves_to_another_part(self):
        parts = self.get("/api/courses/fixture").json()["parts"]
        target = parts[1]["id"]
        reply = self.post("/api/courses/fixture/modules/M01/move", {"part": target, "index": 0})
        self.assertEqual(reply.status, 200)
        self.assertEqual(reply.json()["part"], target)
        self.assertEqual(reply.json()["problems"], [])

    def test_an_index_that_is_not_a_number_is_taken_as_the_end(self):
        reply = self.post("/api/courses/fixture/modules/M01/move", {"index": "last"})
        self.assertEqual(reply.status, 200)

    def test_every_stage_a_module_is_written_from_is_shown(self):
        body = self.get("/api/courses/fixture/modules/M01/prompts").json()
        stages = {row["stage"] for row in body["stages"]}
        self.assertLessEqual({"module", "assessment", "suggestions", "review"}, stages)
        self.assertIn("module_text", json.dumps(body["tokens"]))

    def test_a_module_that_is_not_in_the_course_is_a_404(self):
        self.assertEqual(self.get("/api/courses/fixture/modules/M99/prompts").status, 404)

    def test_a_prompt_override_is_stored_and_taken_away_again(self):
        put = self.put("/api/courses/fixture/modules/M01/prompts",
                       {"stage": "module", "text": "Write it my way."})
        self.assertEqual(put.status, 200)
        self.assertEqual(put.json()["overridden"], ["module"])
        rows = {r["stage"]: r for r in self.get("/api/courses/fixture/modules/M01/prompts").json()["stages"]}
        self.assertTrue(rows["module"]["overridden"])
        self.assertIn("my way", rows["module"]["prompt"])

        back = self.put("/api/courses/fixture/modules/M01/prompts", {"stage": "module", "text": ""})
        self.assertEqual(back.json()["overridden"], [])

    def test_there_is_no_stage_by_that_name(self):
        reply = self.put("/api/courses/fixture/modules/M01/prompts", {"stage": "vibes", "text": "x"})
        self.assertEqual(reply.status, 400)

    def test_a_prompt_is_text(self):
        reply = self.put("/api/courses/fixture/modules/M01/prompts", {"stage": "module", "text": []})
        self.assertEqual(reply.status, 400)

    def test_the_owner_s_own_verdict_is_stored_beside_the_review(self):
        reply = self.post("/api/courses/fixture/modules/M01/accept", {"accepted": True})
        self.assertEqual(reply.status, 200)
        self.assertTrue(reply.json()["review"]["accepted"])
        self.assertTrue(reply.json()["review"]["ownerOnly"], "there was no review to overrule")
        again = self.post("/api/courses/fixture/modules/M01/accept", {"accepted": False})
        self.assertFalse(again.json()["accepted"])

    def test_accepting_a_module_that_is_not_there_is_a_404(self):
        self.assertEqual(self.post("/api/courses/fixture/modules/M99/accept", {}).status, 404)


# --------------------------------------------------------------------------- writing


class TestWritingGuards(ServerTest):
    """`server/writing.py`: every route that sets a model writing is the same shape -
    refuse if the provider cannot answer, refuse if the course is busy, settle the model."""

    def setUp(self):
        super().setUp()
        self.fixture()
        self.no_work()

    def test_a_course_needs_a_theme(self):
        self.a_model()
        self.assertEqual(self.post("/api/generate", {"hours": 10}).status, 400)

    def test_hours_are_a_number_between_two_bounds(self):
        self.a_model()
        self.assertIn("number", self.post("/api/generate", {"theme": "x", "hours": "lots"}).error)
        self.assertIn("shortest", self.post("/api/generate", {"theme": "x", "hours": 0.5}).error)
        self.assertIn("one course", self.post("/api/generate", {"theme": "x", "hours": 9000}).error)

    def test_nothing_is_started_when_nothing_can_answer(self):
        self.no_model()
        reply = self.post("/api/generate", {"theme": "bread", "hours": 10})
        self.assertEqual(reply.status, 400)
        self.assertIn("cannot answer", reply.error)

    def test_an_id_that_could_not_be_a_folder_is_refused(self):
        self.a_model()
        reply = self.post("/api/generate", {"theme": "x", "hours": 10, "id": "Not A Folder"})
        self.assertEqual(reply.status, 400)
        self.assertIn("lowercase", reply.error)

    def test_a_started_job_answers_with_its_summary(self):
        self.a_model()
        reply = self.post("/api/generate", {"theme": "bread", "hours": 10, "model": "opus"})
        self.assertEqual(reply.status, 200)
        summary = reply.json()["job"]
        self.assertEqual(summary["kind"], "generate")
        self.assertEqual(summary["meta"]["model"], "opus")

    def test_an_unknown_model_falls_back_to_the_default_rather_than_failing(self):
        self.a_model()
        reply = self.post("/api/generate", {"theme": "bread", "hours": 10, "model": "no-such"})
        self.assertEqual(reply.status, 200)
        self.assertNotEqual(reply.json()["job"]["meta"]["model"], "no-such")

    def test_extending_needs_a_topic(self):
        self.a_model()
        self.assertEqual(self.post("/api/courses/fixture/extend", {}).status, 400)

    def test_one_job_per_course(self):
        self.a_model()
        self.assertEqual(self.post("/api/courses/fixture/extend", {"topic": "pricing"}).status, 200)
        second = self.post("/api/courses/fixture/extend", {"topic": "more pricing"})
        self.assertEqual(second.status, 400)
        self.assertIn("already has a job", second.error)

    def test_a_rewrite_is_a_patch_only_when_it_says_so(self):
        self.a_model()
        job = self.post("/api/courses/fixture/modules/M01/rewrite", {"mode": "patch"}).json()["job"]
        self.assertEqual(job["meta"]["mode"], "patch")

    def test_figures_and_notebooks_name_the_module_they_are_for(self):
        self.a_model()
        job = self.post("/api/courses/fixture/modules/M01/figures").json()["job"]
        self.assertEqual(job["meta"], {"course": "fixture", "module": "M01"})

    def test_a_review_is_a_job_of_its_own(self):
        self.a_model()
        job = self.post("/api/courses/fixture/modules/M03/review").json()["job"]
        self.assertEqual(job["kind"], "review")

    def test_the_guard_names_what_could_not_be_done(self):
        """"drawn" and "reviewed", not "written": the sentence has to be true."""
        self.no_model()
        self.assertIn("drawn", self.post("/api/courses/fixture/figures").error)
        self.assertIn("reviewed", self.post("/api/courses/fixture/modules/M01/review").error)

    def test_a_course_that_is_already_complete_has_nothing_to_resume(self):
        self.a_model()
        reply = self.post("/api/courses/fixture/resume")
        self.assertEqual(reply.status, 400)
        self.assertIn("Nothing to resume", reply.error)


class TestPlanPromptRoute(ServerTest):
    """`POST /api/plan/prompt`: the approval gate shows what the run will send."""

    def test_a_body_without_a_plan_is_refused(self):
        self.assertEqual(self.post("/api/plan/prompt", {"mid": "M01"}).status, 400)

    def test_a_module_the_plan_does_not_hold_is_a_404(self):
        plan = {"title": "T", "subject": "bread", "hours": 6, "parts": [],
                "modules": [{"id": "M01", "title": "One", "sections": ["A"]}]}
        reply = self.post("/api/plan/prompt", {"plan": plan, "mid": "M09"})
        self.assertEqual(reply.status, 404)

    def test_the_stages_come_back_with_the_prompt_each_would_send(self):
        plan = {"title": "T", "subject": "bread", "hours": 6,
                "parts": [{"id": "p1", "name": "Part one", "dir": "01-part-one", "hours": 6}],
                "modules": [{"id": "M01", "part": "p1", "title": "One", "minutes": 45,
                             "summary": "s", "sections": ["Why this matters", "Core concepts"]}]}
        body = self.post("/api/plan/prompt", {"plan": plan, "mid": "M01"}).json()
        rows = {r["stage"]: r for r in body["stages"]}
        self.assertIn("Why this matters", rows["module"]["prompt"])
        self.assertFalse(rows["module"]["overridden"])

    def test_an_override_carried_in_the_plan_is_shown_as_the_owner_s(self):
        plan = {"title": "T", "subject": "bread", "hours": 6,
                "parts": [{"id": "p1", "name": "P", "dir": "01-p", "hours": 6}],
                "modules": [{"id": "M01", "part": "p1", "title": "One", "minutes": 45,
                             "summary": "s", "sections": ["A", "B"]}],
                "prompts": {"M01": {"module": "Write it my way."}}}
        rows = {r["stage"]: r for r in
                self.post("/api/plan/prompt", {"plan": plan, "mid": "M01"}).json()["stages"]}
        self.assertTrue(rows["module"]["overridden"])
        self.assertIn("my way", rows["module"]["prompt"])


# --------------------------------------------------------------------------- jobs


class TestJobRoutes(ServerTest):
    def _job(self):
        from studio.server import base
        job = jobs.Job("generate", {"theme": "bread"})
        base.REGISTRY.add(job)
        return job

    def test_a_job_that_does_not_exist_is_a_404(self):
        self.assertEqual(self.post("/api/jobs/nope/cancel").status, 404)
        self.assertEqual(self.get("/api/jobs/nope/events").status, 404)

    def test_a_job_can_be_cancelled(self):
        job = self._job()
        self.assertEqual(self.post("/api/jobs/%s/cancel" % job.id).status, 200)
        with self.assertRaises(jobs.Cancelled):
            job.check_cancelled()

    def test_answering_a_job_that_is_not_waiting_is_refused(self):
        job = self._job()
        reply = self.post("/api/jobs/%s/answer" % job.id, {"ok": True})
        self.assertEqual(reply.status, 400)
        self.assertIn("not waiting", reply.error)

    def test_the_approval_gate_takes_its_answer(self):
        job = self._job()
        answered = {}

        def work(j):
            answered["plan"] = j.await_input("plan", {})

        job.start(work)
        for _ in range(500):
            if job.status == jobs.WAITING:
                break
            time.sleep(0.01)
        self.assertEqual(self.post("/api/jobs/%s/answer" % job.id, {"hours": 8}).status, 200)
        for _ in range(500):
            if job.finished:
                break
            time.sleep(0.01)
        self.assertEqual(answered["plan"]["hours"], 8)

    def test_the_event_stream_replays_from_where_the_browser_left_off(self):
        job = self._job()
        job.progress(1, 2, "step one")
        job.progress(2, 2, "step two")
        job.status = jobs.DONE
        reply = self.get("/api/jobs/%s/events?from=1" % job.id)
        self.assertEqual(reply.status, 200)
        self.assertIn("text/event-stream", reply.headers.get("Content-Type", ""))
        self.assertNotIn("step one", reply.text())
        self.assertIn("step two", reply.text())


# --------------------------------------------------------------------------- the rest


class TestStateRoutes(ServerTest):
    def test_the_state_every_screen_polls(self):
        self.fixture()
        state = self.get("/api/state").json()
        self.assertEqual([c["id"] for c in state["courses"]], ["fixture"])
        self.assertIn("llm", state)
        self.assertIn("claude", state, "a page loaded before the rename still looks for it")
        self.assertIn("calendar", state)

    def test_the_listing_counts_module_files_rather_than_parsing_them(self):
        self.fixture()
        self.assertEqual(self.get("/api/state").json()["courses"][0]["modules"], 6)

    def test_search_reaches_into_every_course(self):
        self.fixture()
        found = self.get("/api/search?q=lesson").json()
        self.assertTrue(found["hits"])
        self.assertEqual(self.get("/api/search?q=").json()["hits"], [])

    def test_a_served_page_asks_which_reader_it_is(self):
        self.assertEqual(self.get("/api/profile").json()["profile"], "default")

    def test_a_profile_is_added_switched_to_and_removed(self):
        added = self.post("/api/profiles", {"action": "add", "name": "sam"})
        self.assertEqual(added.status, 200)
        self.assertEqual(added.json()["active"], "sam")
        self.assertIn("sam", added.json()["profiles"])

        removed = self.post("/api/profiles", {"action": "remove", "name": "sam"})
        self.assertEqual(removed.status, 200)
        self.assertEqual(removed.json()["active"], "default")
        self.assertTrue(any(n.startswith("profile-sam") for n in os.listdir(self.where["TRASH_DIR"])))

    def test_the_default_profile_cannot_be_removed(self):
        reply = self.post("/api/profiles", {"action": "remove", "name": "default"})
        self.assertEqual(reply.status, 400)

    def test_a_name_that_could_not_be_a_folder_is_refused(self):
        self.assertEqual(self.post("/api/profiles", {"name": "../escape"}).status, 400)

    def test_an_action_nobody_offers_is_refused(self):
        self.assertEqual(self.post("/api/profiles", {"action": "merge", "name": "sam"}).status, 400)

    def test_the_page_is_told_where_jupyter_is(self):
        view = self.get("/api/jupyter").json()
        self.assertFalse(view["available"])
        self.assertIn("url", view)
        self.assertIn("token", view, "the token reaches the page on Studio's own origin")


class TestSettingsRoutes(ServerTest):
    def test_the_settings_page_gets_every_resolved_value_with_its_source(self):
        view = self.get("/api/settings").json()
        self.assertIn("courses", view["paths"])
        rows = {row["key"]: row for row in view["platform"]}
        self.assertEqual(rows["studio.port"]["source"], "settings.json")
        self.assertIn(rows["providers.anthropic.apiKey"]["value"], ("", "(set)"),
                      "every provider key is masked by rule, never printed")

    def test_the_model_is_what_the_ui_edits(self):
        alias = SETTINGS.models[0]["alias"]
        reply = self.post("/api/settings", {"model": alias})
        self.assertEqual(reply.status, 200)
        self.assertEqual(reply.json()["settings"]["model"], alias)

    def test_a_model_nobody_offers_is_refused_here_rather_than_at_module_eight(self):
        reply = self.post("/api/settings", {"model": "gpt-hypothetical"})
        self.assertEqual(reply.status, 400)
        self.assertIn("Unknown model", reply.error)

    def test_the_list_in_use_is_reported_with_where_it_came_from(self):
        body = self.get("/api/models").json()
        self.assertTrue(body["list"])
        self.assertIn("custom", body)

    def test_a_studio_with_no_settings_file_cannot_save_a_list(self):
        reply = self.put("/api/models", {"list": [{"id": "x", "alias": "x", "label": "X"}]})
        self.assertEqual(reply.status, 400)

    def test_the_list_is_saved_validated_and_reset_again(self):
        settings_file = os.path.join(self.where["STATE_ROOT"], "settings.json")
        self.addCleanup(setattr, SETTINGS, "studio_file", SETTINGS.studio_file)
        self.addCleanup(SETTINGS.reload)
        SETTINGS.studio_file = settings_file

        saved = self.put("/api/models", {"list": [
            {"id": "some-model-1", "alias": "one", "label": "One"},
            {"id": "some-model-2", "alias": "two", "label": "Two"}]})
        self.assertEqual(saved.status, 200)
        self.assertEqual([m["alias"] for m in saved.json()["models"]["list"]], ["one", "two"])
        self.assertTrue(saved.json()["models"]["custom"])

        self.assertEqual(self.put("/api/models", {"list": []}).status, 400)
        self.assertEqual(self.put("/api/models", {"list": [
            {"id": "a", "alias": "same", "label": "A"},
            {"id": "b", "alias": "same", "label": "B"}]}).status, 400)

        back = self.post("/api/models/reset")
        self.assertEqual(back.status, 200)
        self.assertFalse(back.json()["models"]["custom"])

    def test_a_row_is_tested_on_its_own_provider_with_no_fallback_chain(self):
        asked = {}
        old = modelcall.probe
        modelcall.probe = lambda model, provider="": asked.update(
            model=model, provider=provider) or {"ok": True, "seconds": 0.1}
        self.addCleanup(setattr, modelcall, "probe", old)
        reply = self.post("/api/models/test", {"model": "some-model-1", "provider": "openai"})
        self.assertEqual(reply.status, 200)
        self.assertTrue(reply.json()["ok"])
        self.assertEqual(asked, {"model": "some-model-1", "provider": "openai"})

    def test_testing_needs_a_model_id(self):
        self.assertEqual(self.post("/api/models/test", {"model": " "}).status, 400)

    def test_discovery_can_be_run_now(self):
        from studio import discover
        old = discover.run
        discover.run = lambda: {"providers": [], "added": [], "removed": []}
        self.addCleanup(setattr, discover, "run", old)
        reply = self.post("/api/models/discover")
        self.assertEqual(reply.status, 200)
        self.assertIn("report", reply.json())

    def test_the_log_is_readable_and_clearable_from_the_settings_page(self):
        from studio.support.log import log
        log.info("a line only this test writes: kumquat")
        body = self.get("/api/logs?q=kumquat").json()
        self.assertTrue(any("kumquat" in line["msg"] for line in body["lines"]))
        self.assertEqual(self.post("/api/logs/clear").status, 200)
        self.assertEqual(self.get("/api/logs?q=kumquat").json()["lines"], [])

    def test_the_log_can_be_filtered_by_level(self):
        from studio.support.log import log
        log.info("ordinary")
        log.warning("worth reading")
        lines = self.get("/api/logs?level=WARNING").json()["lines"]
        self.assertTrue(lines)
        self.assertTrue(all(line["level"] in ("WARNING", "ERROR", "CRITICAL") for line in lines))


class TestTutorRoute(ServerTest):
    """`/api/ask`: the tutor for a course served from here. The failure kind is what the
    page branches on, so it travels with the error."""

    def test_a_question_with_no_messages_is_refused(self):
        self.assertEqual(self.post("/api/ask", {"messages": []}).status, 400)

    def test_the_tutor_says_it_is_unavailable_rather_than_failing_silently(self):
        self.no_model()
        reply = self.post("/api/ask", {"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(reply.status, 503)
        self.assertIn("unavailable", reply.error)

    def test_an_answer_carries_the_mode_the_page_shows(self):
        self.a_model()
        old = modelcall.ask
        modelcall.ask = lambda prompt, **kw: "the answer"
        self.addCleanup(setattr, modelcall, "ask", old)
        body = self.post("/api/ask", {"system": "s", "messages": [{"role": "user", "content": "q"}]}).json()
        self.assertEqual(body, {"text": "the answer", "mode": "studio"})

    def test_a_timeout_is_a_504_kind_the_page_can_retry(self):
        self.a_model()
        old = modelcall.ask

        def fail(prompt, **kw):
            raise modelcall.LLMFailed("took too long", kind="timeout", detail="")

        modelcall.ask = fail
        self.addCleanup(setattr, modelcall, "ask", old)
        reply = self.post("/api/ask", {"messages": [{"role": "user", "content": "q"}]})
        self.assertEqual(reply.status, 502)
        self.assertEqual(reply.json()["why"], "timeout")



class TestServing(ServerTest):
    """`serve()` binds loopback and says what it is before it blocks. The binding is a
    security boundary, not a default: Studio writes files and spawns processes."""

    def test_it_binds_what_it_was_given_and_starts_the_discovery_schedule(self):
        import studio.server as server
        started, scheduled = {}, []

        class Stub:
            daemon_threads = False

            def __init__(self, address, handler):
                started["address"], started["handler"] = address, handler

            def serve_forever(self):
                raise KeyboardInterrupt

            def server_close(self):
                started["closed"] = True

        self.addCleanup(setattr, server, "ThreadingHTTPServer", server.ThreadingHTTPServer)
        self.addCleanup(setattr, server.discover, "schedule", server.discover.schedule)
        server.ThreadingHTTPServer = Stub
        server.discover.schedule = lambda: scheduled.append(True)

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(server.serve(port=8791, open_browser=False), 0)
        self.assertEqual(started["address"], ("127.0.0.1", 8791))
        self.assertIs(started["handler"], server.Handler)
        self.assertTrue(started["closed"])
        self.assertEqual(scheduled, [True])

    def test_the_line_it_prints_names_the_provider_not_a_vendor(self):
        """A path to a binary was the honest answer when one tool was the only way in."""
        import studio.server as server
        self.addCleanup(setattr, server.catalog, "llm_view", server.catalog.llm_view)
        server.catalog.llm_view = lambda: {"available": True, "providerLabel": "A tool",
                                           "model": "opus", "hint": ""}
        self.assertEqual(server._writer_line(), "A tool · model opus")
        server.catalog.llm_view = lambda: {"available": False, "providerLabel": "A tool",
                                           "model": "", "hint": "sign in first"}
        self.assertIn("NOT READY, sign in first", server._writer_line())


class TestWritingForAWholeCourse(ServerTest):
    """The course-wide twins of the per-module media routes, and resuming a dead run. Each
    test starts one job, because a course takes one at a time."""

    def setUp(self):
        super().setUp()
        self.fixture()
        self.no_work()
        self.a_model()

    def job_for(self, path, body=None):
        reply = self.post(path, body)
        self.assertEqual(reply.status, 200, reply.error)
        return reply.json()["job"]

    def test_figures_for_every_module_without_any(self):
        job = self.job_for("/api/courses/fixture/figures", {"all": False, "module": "M01"})
        self.assertEqual(job["kind"], "figures")
        self.assertEqual(job["meta"], {"course": "fixture", "all": False},
                         "a course-wide run is not about one module")

    def test_redrawing_them_all_says_so(self):
        self.assertTrue(self.job_for("/api/courses/fixture/figures", {"all": True})["meta"]["all"])

    def test_notebooks_for_every_module_without_any(self):
        job = self.job_for("/api/courses/fixture/notebooks", {})
        self.assertEqual(job["kind"], "notebooks")
        self.assertEqual(job["meta"], {"course": "fixture", "all": False})

    def test_notebooks_for_one_module(self):
        job = self.job_for("/api/courses/fixture/modules/M02/notebooks")
        self.assertEqual(job["meta"], {"course": "fixture", "module": "M02"})

    def test_a_run_that_died_is_finished_from_the_curriculum_it_saved(self):
        """`brief["resume"]` keeps every module already on disk and writes only what is
        missing."""
        self.course.write_assessments({})       # a course that no longer builds clean
        job = self.job_for("/api/courses/fixture/resume", {"figures": False, "notebooks": False})
        self.assertTrue(job["meta"]["resume"])
        self.assertEqual(job["meta"]["course"], "fixture")

    def test_a_curriculum_that_cannot_be_read_is_said_to_be(self):
        self.course.write_assessments({})
        import studio.authoring.curriculum as ck_curriculum
        plan = os.path.join(self.courses, "fixture", ck_curriculum.PLAN_FILE)
        os.makedirs(os.path.dirname(plan), exist_ok=True)
        with open(plan, "w", encoding="utf-8") as fh:
            json.dump({"modules": []}, fh)
        reply = self.post("/api/courses/fixture/resume")
        self.assertEqual(reply.status, 400)
        self.assertIn("Cannot resume", reply.error)


class TestJobListing(ServerTest):
    """A finished job is written to `state/jobs/` and can be replayed after a restart."""

    def test_a_job_outlives_the_registry_that_ran_it(self):
        from studio.server import base
        job = jobs.Job("generate", {"theme": "bread"})
        base.REGISTRY.add(job)
        job.start(lambda j: {"ok": True})
        for _ in range(500):
            if job.finished:
                break
            time.sleep(0.01)

        patch_global(self, "REGISTRY", jobs.Registry(self.where["JOBS_DIR"]))
        replayed = self.get("/api/jobs/%s/events" % job.id)
        self.assertEqual(replayed.status, 200)
        self.assertIn("started", replayed.text())
        self.assertEqual(self.post("/api/jobs/%s/cancel" % job.id).status, 200,
                         "cancelling one that is already over is not an error")

    def test_the_state_every_screen_polls_lists_the_recent_runs(self):
        from studio.server import base
        base.REGISTRY.add(jobs.Job("review", {"course": "fixture", "module": "M01"}))
        listed = self.get("/api/state").json()["jobs"]
        self.assertEqual(listed[0]["kind"], "review")

if __name__ == "__main__":
    unittest.main(verbosity=2)

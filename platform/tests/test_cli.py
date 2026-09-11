"""Self-tests for the command line.

    python platform/tests/test_cli.py

`build.py` is how the platform is driven from a terminal, and every subcommand here writes
or refuses to write real files. Nothing calls a model: `studio` and `jupyter` are only
checked for handing over to the right place, because both are servers.
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = os.path.dirname(HERE)
sys.path.insert(0, PLATFORM)
sys.path.insert(0, HERE)

from coursekit import cli  # noqa: E402
from test_build import CourseFixture  # noqa: E402


def run(*argv):
    """One `build.py` invocation. Returns (exit code, everything it printed)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue() + err.getvalue()


class CliTest(unittest.TestCase):
    """Every test gets its own courses/ and dist/, so nothing here can touch the library."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cli-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.courses = os.path.join(self.tmp, "courses")
        self.dist = os.path.join(self.tmp, "dist")
        os.makedirs(self.courses)
        for name, value in (("COURSES_DIR", self.courses), ("DIST_DIR", self.dist)):
            old = getattr(cli, name)
            setattr(cli, name, value)
            self.addCleanup(setattr, cli, name, old)

    def fixture(self):
        return CourseFixture(self.courses)


class TestList(CliTest):
    def test_an_empty_library_says_how_to_start_one(self):
        code, text = run("list")
        self.assertEqual(code, 0)
        self.assertIn("No courses yet", text)

    def test_a_missing_directory_is_not_an_error(self):
        cli.COURSES_DIR = os.path.join(self.tmp, "nowhere")
        code, text = run("list")
        self.assertEqual(code, 0)
        self.assertIn("No courses directory yet", text)

    def test_a_course_is_listed_with_its_title_and_shape(self):
        self.fixture()
        code, text = run("list")
        self.assertEqual(code, 0)
        self.assertIn("fixture", text)
        self.assertIn("hours", text)

    def test_a_broken_manifest_is_named_rather_than_ending_the_listing(self):
        """One unreadable course must not hide the others."""
        broken = self.fixture()
        with open(broken.cfg_path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        code, text = run("list")
        self.assertEqual(code, 0)
        self.assertIn("[broken manifest]", text)

    def test_a_folder_without_a_manifest_is_not_a_course(self):
        os.makedirs(os.path.join(self.courses, "notes"))
        code, text = run("list")
        self.assertEqual(code, 0)
        self.assertNotIn("notes", text)


class TestNew(CliTest):
    def test_it_scaffolds_a_course_that_already_validates(self):
        code, text = run("new", "--theme", "negotiation", "--hours", "12")
        self.assertEqual(code, 0)
        root = os.path.join(self.courses, "negotiation")
        self.assertTrue(os.path.isfile(os.path.join(root, "course.json")))
        self.assertIn("Scaffolded", text)
        self.assertIn("own repository", text, "a course is a repository of its own")

    def test_the_id_can_be_given_outright(self):
        self.assertEqual(run("new", "--theme", "sourdough", "--hours", "8", "--id", "bread")[0], 0)
        self.assertTrue(os.path.isdir(os.path.join(self.courses, "bread")))

    def test_writing_into_a_taken_folder_needs_force(self):
        run("new", "--theme", "negotiation", "--hours", "12")
        code, text = run("new", "--theme", "negotiation", "--hours", "12")
        self.assertEqual(code, 1)
        self.assertIn("error:", text)
        self.assertEqual(run("new", "--theme", "negotiation", "--hours", "12", "--force")[0], 0)


class TestCheck(CliTest):
    def test_a_consistent_course_passes(self):
        self.fixture()
        code, text = run("check", "fixture")
        self.assertEqual(code, 0)
        self.assertIn("is consistent", text)

    def test_every_problem_is_reported_at_once_and_the_exit_code_says_so(self):
        course = self.fixture()
        course.write_suggestions({mid: [["only one section?"]] for mid in course.ids})
        code, text = run("check", "fixture")
        self.assertEqual(code, 1)
        self.assertIn("problem(s)", text)
        self.assertGreater(text.count("  - "), 1)

    def test_a_course_can_be_named_by_its_path(self):
        course = self.fixture()
        self.assertEqual(run("check", course.root)[0], 0)

    def test_a_name_that_is_no_course_says_where_to_look(self):
        code, text = run("check", "nothing-like-this")
        self.assertEqual(code, 1)
        self.assertIn("build.py list", text)


class TestBuild(CliTest):
    def test_it_writes_both_copies_and_names_the_local_one(self):
        self.fixture()
        code, text = run("build", "fixture")
        self.assertEqual(code, 0)
        out = os.path.join(self.dist, "fixture")
        self.assertTrue(os.path.isfile(os.path.join(out, "fixture-course.html")))
        self.assertTrue(os.path.isfile(os.path.join(out, "fixture-course-local.html")))
        self.assertIn("local copy", text)

    def test_out_overrides_the_dist_directory(self):
        self.fixture()
        elsewhere = os.path.join(self.tmp, "elsewhere")
        self.assertEqual(run("build", "fixture", "--out", elsewhere)[0], 0)
        self.assertTrue(os.path.isfile(os.path.join(elsewhere, "fixture-course-local.html")))
        self.assertFalse(os.path.isdir(self.dist), "--out means nothing lands in dist/")

    def test_a_broken_course_is_refused_before_anything_is_written(self):
        course = self.fixture()
        course.write_assessments({})
        code, text = run("build", "fixture")
        self.assertEqual(code, 1)
        self.assertIn("error:", text)
        self.assertFalse(os.path.isdir(os.path.join(self.dist, "fixture")))


class TestWhere(CliTest):
    def test_it_prints_what_was_resolved(self):
        code, text = run("where")
        self.assertEqual(code, 0)
        for line in ("platform", "courses", "dist", "settings", "config"):
            self.assertIn(line, text)

    def test_every_overridden_setting_is_named_with_its_layer(self):
        from coursekit.settings import SETTINGS
        old = SETTINGS.overrides
        SETTINGS.overrides = dict(old, **{"studio.port": "an environment variable"})
        self.addCleanup(setattr, SETTINGS, "overrides", old)
        self.assertIn("an environment variable", run("where")[1])


class TestServersAreHandedOver(CliTest):
    """Both are lazy imports: the build path must not depend on the server or a provider."""

    def _stub_serve(self):
        import studio.server as server
        seen = {}
        old = server.serve
        server.serve = lambda **kw: seen.update(kw) or 0
        self.addCleanup(setattr, server, "serve", old)
        return seen

    def test_studio_gets_the_port_host_and_browser_choice(self):
        seen = self._stub_serve()
        self.assertEqual(run("studio", "--port", "8123", "--no-open", "--host", "0.0.0.0")[0], 0)
        self.assertEqual(seen, {"port": 8123, "open_browser": False, "host": "0.0.0.0"})

    def test_studio_without_a_port_takes_the_setting(self):
        from coursekit.settings import SETTINGS
        seen = self._stub_serve()
        run("studio")
        self.assertEqual(seen["port"], int(SETTINGS.get("studio.port")))
        self.assertTrue(seen["open_browser"])

    def test_jupyter_is_handed_to_its_own_module(self):
        from studio import jupyter
        old = jupyter.run
        jupyter.run = lambda: 7
        self.addCleanup(setattr, jupyter, "run", old)
        self.assertEqual(run("jupyter")[0], 7)


class TestParser(unittest.TestCase):
    def test_a_subcommand_is_required(self):
        with self.assertRaises(SystemExit):
            run()

    def test_hours_must_be_a_number(self):
        with self.assertRaises(SystemExit):
            run("new", "--theme", "x", "--hours", "many")

    def test_every_documented_subcommand_exists(self):
        """The docstring at the top of `cli.py` is the help a person reads first."""
        parser = cli.build_parser()
        sub = [a for a in parser._actions if a.choices and "list" in a.choices][0]
        for name in ("list", "where", "new", "check", "build", "studio", "jupyter"):
            self.assertIn(name, sub.choices)



class TestTheEntryPoint(unittest.TestCase):
    """`build.py` is the shim in front of `coursekit.cli`: it forces UTF-8 on the way out,
    because courses are written in real typography and the Windows console is cp1252."""

    def test_it_runs_as_a_program_and_prints_typography_without_dying(self):
        import subprocess
        script = os.path.join(PLATFORM, "build.py")
        proc = subprocess.run([sys.executable, script, "where"], capture_output=True,
                              timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertIn(b"platform", proc.stdout)

    def test_help_names_every_subcommand(self):
        import subprocess
        proc = subprocess.run([sys.executable, os.path.join(PLATFORM, "build.py"), "--help"],
                              capture_output=True, timeout=120)
        self.assertEqual(proc.returncode, 0)
        for name in (b"list", b"where", b"new", b"check", b"build", b"studio", b"jupyter"):
            self.assertIn(name, proc.stdout)

if __name__ == "__main__":
    unittest.main(verbosity=2)

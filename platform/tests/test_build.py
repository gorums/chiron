"""Self-tests for the course platform.

    python platform/tests/test_build.py

These build throwaway courses in a temp directory. They cover the two things most likely to
break quietly: the validator letting an inconsistent course through, and a subject-specific
string creeping back into the engine.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = os.path.dirname(HERE)
REPO = os.path.dirname(PLATFORM)
sys.path.insert(0, PLATFORM)

from coursekit import assessments, bundler, config, library, loader, paths, renderer, scaffold, validate  # noqa: E402
from coursekit.errors import CourseError, DataError, ManifestError  # noqa: E402

MODULE_MD = """# M{n:02d} — Lesson {n}

**Time:** 45 minutes (20 read · 25 practice)

---

## Why this matters

Something true and specific about lesson {n}.

---

## Core concepts

The idea, stated plainly.

---

## Exercise

Do the thing. Write down what happened.
"""

SECTIONS_PER_MODULE = 3


def _assessment(mid):
    return {
        "id": mid,
        "predict": "Guess before reading.",
        "quiz": [{"q": "Which?", "options": ["a", "b", "c", "d"], "answer": 2, "why": "Because c."}],
        "cards": [{"front": "Q", "back": "A"}],
        "elaborate": ["Explain it to a friend."],
        "transfer": {"scenario": "A situation.", "prompt": "Diagnose it.", "model": "The answer."},
    }


class CourseFixture:
    """A complete, valid, throwaway course. Tests break it deliberately."""

    def __init__(self, root_dir, hours=6, theme="bread baking", course_id="fixture"):
        self.courses_dir = root_dir
        self.root = scaffold.create(root_dir, theme, hours, course_id=course_id)
        self.cfg_path = os.path.join(self.root, "course.json")
        with open(self.cfg_path, encoding="utf-8") as fh:
            manifest = json.load(fh)

        self.ids = []
        for part in manifest["parts"]:
            for _ in range(2):
                n = len(self.ids) + 1
                self.ids.append("M%02d" % n)
                path = os.path.join(self.root, "modules", part["dir"], "M%02d-lesson.md" % n)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(MODULE_MD.format(n=n))

        manifest["shortTitles"] = {mid: "Lesson " + mid for mid in self.ids}
        manifest["milestones"] = [{"after": 0, "text": "Not started."},
                                  {"after": len(self.ids), "text": "Done."}]
        self._write_manifest(manifest)
        self.write_assessments({mid: _assessment(mid) for mid in self.ids})
        self.write_suggestions({mid: [["a?", "b?", "c?"]] * SECTIONS_PER_MODULE for mid in self.ids})

    def _write_manifest(self, manifest):
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)

    def edit_manifest(self, **changes):
        with open(self.cfg_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        manifest.update(changes)
        self._write_manifest(manifest)

    def write_assessments(self, by_id):
        path = os.path.join(self.root, "data/assessments/part1.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(list(by_id.values()), fh, ensure_ascii=False)

    def write_suggestions(self, by_id):
        path = os.path.join(self.root, "data/suggestions/part1.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(by_id, fh, ensure_ascii=False)

    def problems(self):
        cfg = config.load(self.root)
        mods = loader.load_modules(cfg)
        return validate.check(mods, assessments.load_assessments(cfg), assessments.load_suggestions(cfg))

    def build(self, out_dir):
        cfg = config.load(self.root)
        mods = loader.load_modules(cfg)
        assess = assessments.load_assessments(cfg)
        sugg = assessments.load_suggestions(cfg)
        validate.raise_if_broken(validate.check(mods, assess, sugg))
        assessments.attach(mods, assess, sugg)
        return cfg, renderer.write(cfg, mods, library.build(cfg), out_dir)


class TempCourseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="coursekit-test-")
        self.course = CourseFixture(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestScaffold(unittest.TestCase):
    def test_part_hours_sum_to_the_budget(self):
        for hours in (6, 10, 20, 30, 45, 100):
            parts = scaffold.plan_parts(hours)
            self.assertEqual(sum(p["hours"] for p in parts), hours, "budget lost at %gh" % hours)

    def test_whole_hours_stay_ints(self):
        for p in scaffold.plan_parts(30):
            self.assertIsInstance(p["hours"], int)

    def test_rejects_an_unstructurable_budget(self):
        with self.assertRaises(CourseError):
            scaffold.plan_parts(1)

    def test_slugify(self):
        self.assertEqual(scaffold.slugify("Bread Baking!"), "bread-baking")
        with self.assertRaises(CourseError):
            scaffold.slugify("!!!")


class TestManifest(TempCourseTest):
    def test_loads(self):
        cfg = config.load(self.course.root)
        self.assertEqual(cfg.id, "fixture")
        self.assertEqual(len(cfg.parts), 3)

    def test_missing_manifest(self):
        with self.assertRaises(ManifestError):
            config.load(self.tmp)

    def test_missing_required_field(self):
        with open(self.course.cfg_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        del manifest["subject"]
        with open(self.course.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        with self.assertRaises(ManifestError):
            config.load(self.course.root)

    def test_runtime_config_carries_no_content(self):
        runtime = config.load(self.course.root).runtime()
        self.assertEqual(runtime["storageKey"], "course_fixture_v1")
        self.assertEqual(runtime["localFile"], "fixture-course-local.html")
        self.assertNotIn("parts", runtime)
        self.assertNotIn("modules", runtime)


class TestLoader(TempCourseTest):
    def test_module_shape(self):
        cfg = config.load(self.course.root)
        mods = loader.load_modules(cfg)
        self.assertEqual(len(mods), 6)
        self.assertEqual([m.id for m in mods], self.course.ids)
        self.assertEqual([m.num for m in mods], [1, 2, 3, 4, 5, 6])
        self.assertTrue(all(len(m.sections) == SECTIONS_PER_MODULE for m in mods))
        self.assertEqual(mods[0].minutes, 45)
        self.assertEqual(mods[0].title, "Lesson 1")

    def test_empty_section_is_dropped(self):
        """The subtle one: an empty heading vanishes, so suggestion counts stop matching."""
        path = os.path.join(self.course.root, "modules/01-foundations/M01-lesson.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n---\n\n## An empty section\n\n")
        mods = loader.load_modules(config.load(self.course.root))
        self.assertEqual(len(mods[0].sections), SECTIONS_PER_MODULE)


class TestValidation(TempCourseTest):
    def test_a_good_course_is_clean(self):
        self.assertEqual(self.course.problems(), [])

    def test_catches_suggestion_count_mismatch(self):
        sugg = {mid: [["a?", "b?", "c?"]] * SECTIONS_PER_MODULE for mid in self.course.ids}
        sugg["M02"] = sugg["M02"][:-1]
        self.course.write_suggestions(sugg)
        problems = self.course.problems()
        self.assertTrue(any("M02" in p and "sections" in p for p in problems), problems)

    def test_catches_out_of_range_quiz_answer(self):
        by_id = {mid: _assessment(mid) for mid in self.course.ids}
        by_id["M03"]["quiz"][0]["answer"] = 9
        self.course.write_assessments(by_id)
        self.assertTrue(any("M03" in p and "index" in p for p in self.course.problems()))

    def test_catches_missing_why(self):
        by_id = {mid: _assessment(mid) for mid in self.course.ids}
        by_id["M01"]["quiz"][0]["why"] = ""
        self.course.write_assessments(by_id)
        self.assertTrue(any("why" in p for p in self.course.problems()))

    def test_catches_incomplete_flashcard(self):
        by_id = {mid: _assessment(mid) for mid in self.course.ids}
        by_id["M01"]["cards"][0]["back"] = ""
        self.course.write_assessments(by_id)
        self.assertTrue(any("front" in p and "back" in p for p in self.course.problems()))

    def test_catches_missing_and_orphaned_assessments(self):
        by_id = {mid: _assessment(mid) for mid in self.course.ids if mid != "M04"}
        by_id["M99"] = _assessment("M99")
        self.course.write_assessments(by_id)
        problems = self.course.problems()
        self.assertTrue(any("M04" in p for p in problems), problems)
        self.assertTrue(any("M99" in p for p in problems), problems)

    def test_build_refuses_an_inconsistent_course(self):
        by_id = {mid: _assessment(mid) for mid in self.course.ids}
        by_id["M01"]["quiz"][0]["answer"] = -1
        self.course.write_assessments(by_id)
        with self.assertRaises(DataError):
            self.course.build(os.path.join(self.tmp, "out"))


class TestRender(TempCourseTest):
    def setUp(self):
        super().setUp()
        self.out = os.path.join(self.tmp, "out")
        self.cfg, self.result = self.course.build(self.out)
        with open(self.result.web_path, encoding="utf-8") as fh:
            self.html = fh.read()

    def test_counts(self):
        self.assertEqual(self.result.modules, 6)
        self.assertEqual(self.result.sections, 6 * SECTIONS_PER_MODULE)
        self.assertEqual(self.result.quiz_items, 6)

    def test_writes_both_copies(self):
        self.assertTrue(os.path.isfile(self.result.web_path))
        self.assertTrue(os.path.isfile(self.result.local_path))
        with open(self.result.local_path, encoding="utf-8") as fh:
            local = fh.read()
        self.assertTrue(local.startswith("<!doctype html>"))
        self.assertFalse(self.html.startswith("<!doctype html>"))

    def test_placeholders_are_all_filled(self):
        for marker in ("/*__CSS__*/", "/*__JS__*/", "/*__CONFIG__*/", "/*__DATA__*/", "{{TITLE}}"):
            self.assertNotIn(marker, self.html, "%s left unreplaced" % marker)

    def test_embedded_json_cannot_close_the_script_tag(self):
        start = self.html.index("const DATA =")
        self.assertNotIn("</script>", self.html[start:self.html.index("\n</script>", start)])

    def test_data_round_trips(self):
        start = self.html.index("const DATA =") + len("const DATA =")
        blob = self.html[start:self.html.index("\n</script>", start)].strip().rstrip(";")
        data = json.loads(blob.replace("<" + chr(92) + "/", "</"))
        self.assertEqual(len(data["modules"]), 6)
        self.assertEqual(len(data["parts"]), 3)

    def test_library_degrades_when_reference_files_are_absent(self):
        """A course with no glossary or worksheets must still build."""
        shutil.rmtree(os.path.join(self.course.root, "reference"))
        _, result = self.course.build(os.path.join(self.tmp, "out2"))
        self.assertEqual(result.glossary, 0)
        self.assertEqual(result.models, 0)


class TestEngineIsSubjectAgnostic(unittest.TestCase):
    """The load-bearing rule: no course may leak into platform/web/."""

    FORBIDDEN = ("marketing", "marketer", "mm_course")

    def test_no_subject_strings_in_the_front_end(self):
        offenders = []
        for path in bundler.source_files():
            with open(path, encoding="utf-8") as fh:
                text = fh.read().lower()
            for word in self.FORBIDDEN:
                if word in text:
                    offenders.append("%s contains %r" % (os.path.basename(path), word))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_boot_runs_last(self):
        names = [os.path.basename(p) for p in bundler.source_files() if p.endswith(".js")]
        self.assertTrue(names[-1].endswith("-boot.js"), "boot must sort last, got %s" % names[-1])

    def test_bundles_are_non_empty(self):
        self.assertGreater(len(bundler.js()), 10000)
        self.assertGreater(len(bundler.css()), 1000)


class TestPaths(unittest.TestCase):
    """Courses are separate repositories: the platform finds them through one setting."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="paths-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _dotenv(self, text):
        path = os.path.join(self.tmp, ".env")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_dotenv_parsing(self):
        got = paths.read_env_file(self._dotenv(
            "# comment\n\nCLAUDE_HOME=C:/Users/x/.claude\nCOURSES_DIR = \"../courses\" \n"
            "export DIST_DIR='out'\nBROKEN\n"))
        self.assertEqual(got, {"CLAUDE_HOME": "C:/Users/x/.claude", "COURSES_DIR": "../courses",
                               "DIST_DIR": "out"})
        self.assertEqual(paths.read_env_file(os.path.join(self.tmp, "missing")), {})

    def test_environment_beats_dotenv_beats_default(self):
        base = os.path.join(self.tmp, "platform")
        default = os.path.join(base, "courses")
        self.assertEqual(paths.resolve("COURSES_DIR", default, env={}, dotenv={}, base=base),
                         os.path.normpath(default))
        self.assertEqual(paths.resolve("COURSES_DIR", default, env={},
                                       dotenv={"COURSES_DIR": "../courses"}, base=base),
                         os.path.normpath(os.path.join(self.tmp, "courses")))
        self.assertEqual(paths.resolve("COURSES_DIR", default, env={"COURSES_DIR": self.tmp},
                                       dotenv={"COURSES_DIR": "../courses"}, base=base),
                         os.path.normpath(self.tmp))

    def test_container_setting_is_absolute_and_ignores_dotenv(self):
        absolute = os.path.abspath(os.sep + "work" + os.sep + "courses")
        got = paths.resolve("COURSES_DIR", "x", env={"COURSES_DIR": absolute},
                            dotenv={"COURSES_DIR": "D:/Courses"}, base=self.tmp)
        self.assertEqual(got, absolute)

    def test_scaffold_writes_a_readme_and_keeps_an_existing_one(self):
        root = scaffold.create(self.tmp, "knot tying", 4)
        readme = os.path.join(root, "README.md")
        with open(readme, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("build.py build knot-tying", text)
        with open(readme, "w", encoding="utf-8") as fh:
            fh.write("mine\n")
        scaffold.write_readme(root, "knot-tying", "Knots")
        with open(readme, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "mine\n")
        cfg = config.load(root)
        self.assertEqual(cfg.folder_label, "knot-tying")


class TestShippedMarketingCourse(unittest.TestCase):
    """The reference course must stay buildable, wherever the courses directory is."""

    ROOT = os.path.join(paths.COURSES_DIR, "marketing")

    @unittest.skipUnless(os.path.isdir(ROOT), "marketing course not present")
    def test_it_validates(self):
        cfg = config.load(self.ROOT)
        mods = loader.load_modules(cfg)
        problems = validate.check(
            mods, assessments.load_assessments(cfg), assessments.load_suggestions(cfg)
        )
        self.assertEqual(problems, [], "\n".join(problems))
        self.assertEqual(len(mods), 19)
        self.assertEqual(sum(len(m.sections) for m in mods), 152)


if __name__ == "__main__":
    unittest.main(verbosity=2)

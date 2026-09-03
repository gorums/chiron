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

from coursekit import assessments, bundler, config, library, loader, paths, renderer, scaffold, settings, validate  # noqa: E402
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
        # the reader's own case is named by the course, never by the engine
        self.assertEqual(set(runtime["anchor"]), {"label", "prompt", "placeholder", "noun"})
        self.assertEqual(runtime["anchor"]["label"], "Your own case")

    def test_anchor_overrides_merge_over_defaults(self):
        path = os.path.join(self.course.root, "course.json")
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        raw["anchor"] = {"label": "Your kitchen", "bogus": "ignored"}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(raw, fh)
        anchor = config.load(self.course.root).runtime()["anchor"]
        self.assertEqual(anchor["label"], "Your kitchen")
        self.assertEqual(anchor["noun"], "my own case")
        self.assertNotIn("bogus", anchor)


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


class TestQuestionTypes(TempCourseTest):
    """Every type the page can render has a validator rule; `single` stays the default."""

    def with_item(self, item):
        by_id = {mid: _assessment(mid) for mid in self.course.ids}
        by_id["M01"]["quiz"].append(dict(item, why="w"))
        self.course.write_assessments(by_id)
        return self.course.problems()

    def test_good_items_of_every_type_are_clean(self):
        good = [
            {"type": "multi", "q": "Q", "options": ["a", "b", "c"], "answer": [0, 2]},
            {"type": "tf", "q": "Q", "answer": False, "feedback": ["x", "y"]},
            {"type": "numeric", "q": "Q", "answer": 12.5, "tolerance": 0.5, "unit": "%"},
            {"type": "order", "q": "Q", "options": ["first", "second", "third"]},
            {"type": "match", "q": "Q", "pairs": [["a", "1"], ["b", "2"]]},
            {"type": "cloze", "q": "The ___ is", "answer": ["x", "y"]},
            {"type": "short", "q": "Q", "model": "A good answer."},
            {"q": "Q", "options": ["a", "b"], "answer": 1, "feedback": ["no", "yes"], "hints": ["h"]},
        ]
        for item in good:
            self.assertEqual(self.with_item(item), [], item)

    def test_bad_items_are_named(self):
        bad = [
            ({"type": "bogus", "q": "Q"}, "unknown type"),
            ({"type": "multi", "q": "Q", "options": ["a", "b"], "answer": []}, "non-empty list"),
            ({"type": "multi", "q": "Q", "options": ["a", "b"], "answer": [5]}, "non-empty list"),
            ({"type": "tf", "q": "Q", "answer": "true"}, "true or false"),
            ({"type": "numeric", "q": "Q", "answer": "12"}, "number"),
            ({"type": "order", "q": "Q", "options": ["only"]}, "at least 2"),
            ({"type": "match", "q": "Q", "pairs": [["a"]]}, "pairs"),
            ({"type": "cloze", "q": "no blank here", "answer": "x"}, "___"),
            ({"type": "short", "q": "Q"}, "model"),
            ({"q": "Q", "options": ["a", "b"], "answer": 0, "feedback": ["only one"]}, "one entry per option"),
            ({"q": "Q", "options": ["a", "b"], "answer": 0, "hints": "not a list"}, "hints"),
            ({"q": "", "options": ["a", "b"], "answer": 0}, "question text"),
        ]
        for item, needle in bad:
            problems = self.with_item(item)
            self.assertTrue(any(needle in p for p in problems), (item, problems))

    def test_roleplay_is_optional_but_checked_when_present(self):
        by_id = {mid: _assessment(mid) for mid in self.course.ids}
        by_id["M01"]["roleplay"] = {"persona": "You are", "situation": "s", "goal": "g", "rubric": ["r"]}
        self.course.write_assessments(by_id)
        self.assertEqual(self.course.problems(), [])
        by_id["M01"]["roleplay"] = {"persona": "You are", "rubric": []}
        self.course.write_assessments(by_id)
        problems = self.course.problems()
        self.assertTrue(any("situation" in p for p in problems), problems)
        self.assertTrue(any("rubric" in p for p in problems), problems)

    def test_roleplay_reaches_the_page(self):
        by_id = {mid: _assessment(mid) for mid in self.course.ids}
        by_id["M01"]["roleplay"] = {"persona": "You are", "situation": "s", "goal": "g", "rubric": ["r"]}
        self.course.write_assessments(by_id)
        cfg, result = self.course.build(os.path.join(self.tmp, "out"))
        with open(result.web_path, encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn('"roleplay"', html)
        self.assertIn('"rubric"', html)


class TestRequires(TempCourseTest):
    def _set_head(self, mid, line):
        path = os.path.join(self.course.root, "modules/01-foundations/%s-lesson.md" % mid)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        text = text.replace("**Time:** 45 minutes (20 read · 25 practice)",
                            "**Time:** 45 minutes (20 read · 25 practice)\n" + line)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_requires_line_is_parsed_and_self_reference_dropped(self):
        self._set_head("M02", "**Requires:** M01, M02 and M01 again")
        mods = loader.load_modules(config.load(self.course.root))
        self.assertEqual(mods[1].requires, ["M01"])
        self.assertEqual(mods[0].requires, [])
        self.assertIn("requires", mods[1].public())

    def test_unknown_prerequisite_is_a_problem(self):
        self._set_head("M02", "**Requires:** M77")
        problems = self.course.problems()
        self.assertTrue(any("M77" in p for p in problems), problems)


class TestFillableWorksheets(unittest.TestCase):
    def test_blanks_cells_checks_and_answer_blocks_become_inputs(self):
        import re
        from coursekit.markdown_render import to_html
        md = ("# Sheet\n\nName: ______\n\n| Field | Value |\n|---|---|\n| Owner | |\n| Date | filled |\n\n"
              "- [ ] first\n- [ ] second\n\n```answer\nWrite here\n```\n\n```\nkeep ____ these\n```\n")
        html, n = library.fillable(to_html(md))
        self.assertEqual(n, 5)
        self.assertEqual(html.count('class="wsin"'), 2)
        self.assertEqual(html.count('class="wscb"'), 2)
        self.assertEqual(html.count('class="wsta"'), 1)
        self.assertIn("keep ____ these", html)          # fenced code is left alone
        self.assertEqual(sorted(int(x) for x in re.findall(r'data-f="(\d+)"', html)), [0, 1, 2, 3, 4])

    def test_use_with_line_links_the_worksheet_to_modules(self):
        tmp = tempfile.mkdtemp(prefix="coursekit-ws-")
        try:
            with open(os.path.join(tmp, "plan.md"), "w", encoding="utf-8") as fh:
                fh.write("# Plan\n\n**Use with:** M03 — Something, and M07\n\nA sentence.\n\nGoal: ____\n")
            out = library._templates(tmp)
            self.assertEqual(out[0]["uses"], ["M03", "M07"])
            self.assertEqual(out[0]["fields"], 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


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

    @unittest.skipUnless(shutil.which("node"), "node not on PATH")
    def test_page_boots_under_node(self):
        """`node --check` only parses. Booting the built page in a stub DOM catches a name the
        bundle uses but never declares - the class of bug a rename leaves behind."""
        import subprocess
        harness = os.path.join(HERE, "page_smoke.js")
        proc = subprocess.run(["node", harness, self.result.local_path],
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("booted", proc.stdout)

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

    # Addresses, endpoints, model names and ports reach the page through CFG.platform,
    # built from platform/settings.json. A literal here would be a second source of truth.
    HARDCODED = ("api.anthropic.com/", "claude-sonnet", "claude-opus", "claude-haiku",
                 "127.0.0.1", "localhost:", ":8787", ":8790", "anthropic-version\": \"20")

    def test_no_hardcoded_endpoints_or_models_in_the_front_end(self):
        offenders = []
        for path in bundler.source_files():
            if not path.endswith(".js"):
                continue
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    code = line.split("//")[0] if not line.lstrip().startswith(("/*", "*")) else ""
                    for word in self.HARDCODED:
                        if word in code:
                            offenders.append("%s:%d has %r" % (os.path.basename(path), n, word))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_page_receives_platform_settings(self):
        cfg = config.load(scaffold.create(tempfile.mkdtemp(prefix="cfg-"), "knots", 4))
        got = renderer.runtime_config(cfg)
        self.assertEqual(got["id"], cfg.id)
        platform = got["platform"]
        for key in ("bridgeUrl", "apiUrl", "apiVersion", "defaultModel", "models",
                    "tutor", "sync", "study", "ui"):
            self.assertIn(key, platform)
        self.assertIn(platform["defaultModel"], [m["id"] for m in platform["models"]])
        self.assertEqual(platform, settings.SETTINGS.page())


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


class TestSettings(unittest.TestCase):
    """One file holds every default; .env and the environment override the scalar knobs."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="settings-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _file(self, name, obj):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return path

    def test_shipped_file_is_complete(self):
        s = settings.SETTINGS
        for key in ("studio.host", "studio.port", "bridge.host", "bridge.port", "anthropic.apiUrl",
                    "anthropic.apiVersion", "models.default", "claude.timeout", "logs.maxBytes",
                    "generation.timeouts.module", "build.excerptChars", "page.tutor.maxTokens",
                    "page.study.maxFreezes", "page.ui.railDefault"):
            self.assertIsNotNone(s.get(key), key)
        self.assertIn(s.default_model, s.model_aliases)
        self.assertTrue(s.model_id(s.default_model).startswith("claude-"))
        self.assertEqual(s.model_id("nonsense"), s.model_id(s.default_model))
        self.assertEqual(s.bridge_url, "http://%s:%d" % (s.get("bridge.host"), s.get("bridge.port")))

    def test_environment_beats_dotenv_beats_file_and_is_typed(self):
        s = settings.load(env={"STUDIO_PORT": "9000", "STUDIO_MODEL": "claude-opus-5"},
                          dotenv={"STUDIO_PORT": "9500", "BRIDGE_PORT": "9001", "BRIDGE_HOST": "0.0.0.0"},
                          overlay="")
        self.assertEqual(s.get("studio.port"), 9000)
        self.assertIsInstance(s.get("studio.port"), int)
        self.assertEqual(s.default_model, "opus")
        self.assertEqual(s.bridge_url, "http://127.0.0.1:9001", "a page must never be told 0.0.0.0")
        self.assertEqual(s.overrides["studio.port"], "environment")
        self.assertEqual(s.overrides["bridge.port"], ".env")
        self.assertNotIn("studio.host", s.overrides)
        with self.assertRaises(settings.SettingsError):
            settings.load(env={"STUDIO_PORT": "eighty"}, dotenv={}, overlay="")

    def test_explicit_bridge_url_wins(self):
        s = settings.load(env={"BRIDGE_URL": "http://tutor.local:1234/"}, dotenv={}, overlay="")
        self.assertEqual(s.bridge_url, "http://tutor.local:1234")
        self.assertEqual(s.page()["bridgeUrl"], "http://tutor.local:1234")

    def test_overlay_file_deep_merges(self):
        overlay = self._file("over.json", {
            "studio": {"port": 8100},
            "models": {"default": "mini", "list": [{"id": "claude-mini-9", "alias": "mini", "label": "Mini"}]},
        })
        s = settings.load(env={}, dotenv={}, overlay=overlay)
        self.assertEqual(s.get("studio.port"), 8100)
        self.assertEqual(s.get("studio.host"), settings.SETTINGS.get("studio.host"), "untouched keys survive")
        self.assertEqual(s.default_model, "mini")
        self.assertEqual(s.page()["models"], [{"id": "claude-mini-9", "label": "Mini"}])
        self.assertEqual(s.overrides["studio.port"], overlay)
        self.assertIn({"key": "studio.port", "value": 8100, "source": overlay}, s.describe())

    def test_paths_resolve_relative_to_the_repo(self):
        s = settings.load(env={"COURSES_DIR": "../elsewhere", "STUDIO_STATE_ROOT": self.tmp},
                          dotenv={}, overlay="")
        self.assertEqual(s.courses_dir, os.path.normpath(os.path.join(settings.REPO_ROOT, "..", "elsewhere")))
        self.assertEqual(s.state_dir, os.path.normpath(self.tmp))
        self.assertEqual(s.progress_dir, os.path.join(os.path.normpath(self.tmp), "progress"))

    def test_missing_or_broken_file_is_loud(self):
        with self.assertRaises(settings.SettingsError):
            settings.load(os.path.join(self.tmp, "absent.json"), env={}, dotenv={}, overlay="")
        broken = os.path.join(self.tmp, "broken.json")
        with open(broken, "w", encoding="utf-8") as fh:
            fh.write("{")
        with self.assertRaises(settings.SettingsError):
            settings.load(broken, env={}, dotenv={}, overlay="")


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

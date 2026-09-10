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

from coursekit import assessments, bundler, config, failures, library, loader, paths, renderer, scaffold, settings, validate  # noqa: E402
from coursekit import llm  # noqa: E402
from coursekit.llm import base as llm_base  # noqa: E402
from coursekit.llm import chain as llm_chain  # noqa: E402
from coursekit.llm import cli as llm_cli  # noqa: E402
from coursekit.llm import shape as llm_shape  # noqa: E402
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


GOOD_SVG = """<svg viewBox='0 0 800 450'><title>A flow</title>
<rect x='10' y='10' width='200' height='80' class='fig-soft'/>
<g data-step='1'><text x='20' y='50' fill='currentColor'>First</text></g>
<g data-step='2'><text x='20' y='90' class='fig-muted'>Second</text></g>
</svg>"""

DIRTY_SVG = """<?xml version='1.0'?><svg viewBox='0 0 10 10' width='400' height='300'>
<style>body{display:none}</style><script>alert(1)</script>
<a href='https://evil.example/x'><rect onclick='alert(2)' x='1' y='1' width='2' height='2'/></a>
<image href='https://evil.example/pic.png'/><use href='#ok'/>
</svg>"""


class TestFigures(TempCourseTest):
    """A figure is an SVG under figures/, referenced as `![caption](figures/<name>.svg)` and
    inlined by the build; it is sanitised on the way in and checked like any other file
    (CLAUDE.md "Figures")."""

    def _with_figure(self, name, svg, mid="M01", caption="What to notice"):
        fig_dir = os.path.join(self.course.root, "figures")
        os.makedirs(fig_dir, exist_ok=True)
        if svg is not None:
            with open(os.path.join(fig_dir, name), "w", encoding="utf-8") as fh:
                fh.write(svg)
        cfg = config.load(self.course.root)
        path = next(m.source for m in loader.load_modules(cfg) if m.id == mid)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        text = text.replace("The idea, stated plainly.",
                            "The idea, stated plainly.\n\n![%s](figures/%s)" % (caption, name))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_a_figure_is_inlined_with_its_caption_and_steps(self):
        self._with_figure("M01-1.svg", GOOD_SVG)
        self.assertEqual(self.course.problems(), [])
        mods = loader.load_modules(config.load(self.course.root))
        sec = mods[0].sections[1]
        self.assertIn('<figure class="figure" data-fig="M01-1.svg" data-steps="2">', sec.html)
        self.assertIn("<figcaption>What to notice</figcaption>", sec.html)
        self.assertNotIn("<img", sec.html)
        self.assertNotIn("<svg", sec.text, "the excerpt is words, not drawing")
        self.assertEqual(mods[0].figures, [{"name": "M01-1.svg", "steps": 2, "problem": ""}])
        _, result = self.course.build(os.path.join(self.tmp, "dist"))
        self.assertEqual(result.figures, 1)
        self.assertIn("figures 1", result.summary())

    def test_a_figure_is_sanitised_before_it_reaches_the_page(self):
        from coursekit import figures
        clean = figures.sanitize(DIRTY_SVG)
        for gone in ("<?xml", "<style", "<script", "onclick", "https://evil.example", "<image",
                     "width='400'", "height='300'"):
            self.assertNotIn(gone, clean, gone)
        self.assertIn("<use href='#ok'/>", clean, "fragment references stay")
        self.assertIn("<rect", clean)
        self.assertEqual(figures.problems(clean), [])

    def test_a_missing_or_broken_figure_is_a_check_problem(self):
        self._with_figure("M01-1.svg", None)
        problems = self.course.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn("M01: figure M01-1.svg is missing", problems[0])

        self._with_figure("M02-1.svg", "<svg viewBox='0 0 1 1'><g></svg>", mid="M02")
        problems = self.course.problems()
        self.assertTrue(any("M02: figure M02-1.svg is not well-formed" in p for p in problems), problems)

        self._with_figure("M03-1.svg", "<svg><rect/></svg>", mid="M03")
        problems = self.course.problems()
        self.assertTrue(any("M03: figure M03-1.svg has no viewBox" in p for p in problems), problems)

    def test_any_other_image_is_refused(self):
        """A one-file site cannot load an image; only a figures/*.svg reference is allowed."""
        path = os.path.join(self.course.root, "modules", "01-foundations", "M01-lesson.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n![a photo](images/photo.png)\n")
        problems = self.course.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn("M01: figure images/photo.png is not a figures/<name>.svg reference", problems[0])

    def test_names_for_lists_a_modules_figures_in_order(self):
        from coursekit import figures
        fig_dir = os.path.join(self.course.root, "figures")
        os.makedirs(fig_dir)
        for name in ("M01-10.svg", "M01-2.svg", "M01-1.svg", "M010-1.svg", "M01-x.svg", "notes.md"):
            with open(os.path.join(fig_dir, name), "w", encoding="utf-8") as fh:
                fh.write("x")
        self.assertEqual(figures.names_for(fig_dir, "M01"), ["M01-1.svg", "M01-2.svg", "M01-10.svg"])
        self.assertEqual(figures.names_for(os.path.join(fig_dir, "nowhere"), "M01"), [])


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

    def test_learner_memory_behaves(self):
        """The learner memory (17c-learner.js): evidence, chips, the tutor context, a checked
        model reply, and a closed gap that stays closed through a refresh and a merge."""
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        harness = os.path.join(HERE, "page_smoke.js")
        checks = os.path.join(HERE, "learner_checks.js")
        proc = subprocess.run([node, harness, self.result.local_path, "--checks", checks],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, (proc.stdout + proc.stderr).strip())
        self.assertIn("learner checks passed", proc.stdout)

    def test_chat_rail_follows_the_place(self):
        """The chat rail (17-convos.js, 17a-place.js, 17-rail.js): the conversation shown is
        the one at the place the reader is looking at - step, and section on the Read step -
        a hand-picked one stays only until they move, a pin fixes the place, and the tutor is
        told what the step asks and what the reader wrote."""
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        harness = os.path.join(HERE, "page_smoke.js")
        checks = os.path.join(HERE, "rail_checks.js")
        proc = subprocess.run([node, harness, self.result.local_path, "--checks", checks],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, (proc.stdout + proc.stderr).strip())
        self.assertIn("rail checks passed", proc.stdout)

    def test_reading_aloud_behaves(self):
        """Reading aloud (07d-audio.js): what a section says, block by block; a section read
        to its end is ticked and the next one follows; leaving the Read step stops it."""
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        harness = os.path.join(HERE, "page_smoke.js")
        checks = os.path.join(HERE, "audio_checks.js")
        proc = subprocess.run([node, harness, self.result.local_path, "--checks", checks],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, (proc.stdout + proc.stderr).strip())
        self.assertIn("audio checks passed", proc.stdout)

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
                 "claude-fable", "127.0.0.1", "localhost:", ":8787", ":8790", "anthropic-version\": \"20")

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

    def test_figure_colours_are_defined_for_both_themes(self):
        """A figure's colour classes come from the page (`fig-1` ... `fig-muted`), so every
        token has a light and a dark value and every class a rule."""
        from coursekit import figures
        css = bundler.css()
        for token in ("--fig-1", "--fig-2", "--fig-3", "--fig-4", "--fig-soft", "--fig-line"):
            self.assertGreaterEqual(css.count(token + ":"), 3, "%s in :root, the media block and the explicit dark block" % token)
        for cls in figures.COLOUR_CLASSES:
            self.assertIn(".figure .%s {" % cls, css)

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
                    "page.study.maxFreezes", "page.ui.railDefault", "page.learner.maxGaps",
                    "page.audio.rate"):
            self.assertIsNotNone(s.get(key), key)
        self.assertIn(s.default_model, s.model_aliases)
        self.assertTrue(s.model_id(s.default_model).startswith("claude-"))
        self.assertEqual(s.model_id("nonsense"), s.model_id(s.default_model))
        self.assertEqual(s.bridge_url, "http://%s:%d" % (s.get("bridge.host"), s.get("bridge.port")))

    def test_environment_beats_dotenv_beats_file_and_is_typed(self):
        s = settings.load(env={"STUDIO_PORT": "9000", "STUDIO_MODEL": "claude-opus-5"},
                          dotenv={"STUDIO_PORT": "9500", "BRIDGE_PORT": "9001", "BRIDGE_HOST": "0.0.0.0"},
                          overlay="", studio_file="")
        self.assertEqual(s.get("studio.port"), 9000)
        self.assertIsInstance(s.get("studio.port"), int)
        self.assertEqual(s.default_model, "opus")
        self.assertEqual(s.bridge_url, "http://127.0.0.1:9001", "a page must never be told 0.0.0.0")
        self.assertEqual(s.overrides["studio.port"], "environment")
        self.assertEqual(s.overrides["bridge.port"], ".env")
        self.assertNotIn("studio.host", s.overrides)
        with self.assertRaises(settings.SettingsError):
            settings.load(env={"STUDIO_PORT": "eighty"}, dotenv={}, overlay="", studio_file="")

    def test_explicit_bridge_url_wins(self):
        s = settings.load(env={"BRIDGE_URL": "http://tutor.local:1234/"}, dotenv={}, overlay="", studio_file="")
        self.assertEqual(s.bridge_url, "http://tutor.local:1234")
        self.assertEqual(s.page()["bridgeUrl"], "http://tutor.local:1234")

    def test_overlay_file_deep_merges(self):
        overlay = self._file("over.json", {
            "studio": {"port": 8100},
            "models": {"default": "mini", "list": [{"id": "claude-mini-9", "alias": "mini", "label": "Mini"}]},
        })
        s = settings.load(env={}, dotenv={}, overlay=overlay, studio_file="")
        self.assertEqual(s.get("studio.port"), 8100)
        self.assertEqual(s.get("studio.host"), settings.SETTINGS.get("studio.host"), "untouched keys survive")
        self.assertEqual(s.default_model, "mini")
        self.assertEqual(s.page()["models"], [{"id": "claude-mini-9", "label": "Mini"}])
        self.assertEqual(s.overrides["studio.port"], overlay)
        self.assertIn({"key": "studio.port", "value": 8100, "source": overlay}, s.describe())

    def test_secrets_are_masked_and_stay_off_the_page(self):
        """`SECRET_KEYS` (the API key, the Jupyter token) show as set or empty on the settings
        page and never reach `page()`."""
        s = settings.load(env={"ANTHROPIC_API_KEY": "sk-ant-test-secret"}, dotenv={}, overlay="",
                          studio_file="")
        self.assertEqual(s.get("anthropic.apiKey"), "sk-ant-test-secret")
        rows = {r["key"]: r["value"] for r in s.describe()}
        self.assertEqual(rows["anthropic.apiKey"], "(set)")
        self.assertEqual(rows["jupyter.token"], "(set)")
        self.assertNotIn("sk-ant-test-secret", json.dumps(s.describe()))
        self.assertNotIn("sk-ant-test-secret", json.dumps(s.page()))
        self.assertNotIn("apiKey", json.dumps(s.page()))
        blank = settings.load(env={}, dotenv={}, overlay="", studio_file="")
        self.assertEqual({r["key"]: r["value"] for r in blank.describe()}["anthropic.apiKey"], "")

    def test_studio_layer_sits_between_overlay_and_environment(self):
        """The list Studio's settings page saves lives in <state>/settings.json, read over
        the platform defaults and the overlay, under .env and the environment; reload()
        picks up a change without a restart."""
        studio = self._file("studio-settings.json", {
            "models": {"list": [{"id": "claude-new-1", "alias": "new", "label": "New"}]},
            "studio": {"port": 8200},
        })
        s = settings.load(env={"STUDIO_PORT": "9300"}, dotenv={}, overlay="", studio_file=studio)
        self.assertEqual([m["id"] for m in s.models], ["claude-new-1"])
        self.assertEqual(s.overrides["models.list"], settings.STUDIO_SOURCE)
        self.assertEqual(s.default_model, "new", "an unknown default falls back to the first")
        self.assertEqual(s.get("studio.port"), 9300, "the environment still wins over Studio")
        self.assertEqual(s.studio_file, studio)

        with open(studio, "w", encoding="utf-8") as fh:
            json.dump({"models": {"list": [{"id": "claude-newer-2", "alias": "newer"}]}}, fh)
        s.reload()
        self.assertEqual([m["id"] for m in s.models], ["claude-newer-2"])
        self.assertEqual(s.get("studio.port"), 9300)

        off = settings.load(env={}, dotenv={}, overlay="", studio_file="")
        self.assertEqual(off.studio_file, "")
        self.assertNotIn("models.list", off.overrides)
        missing = settings.load(env={}, dotenv={}, overlay="",
                                studio_file=os.path.join(self.tmp, "absent.json"))
        self.assertEqual([m["id"] for m in missing.models], [m["id"] for m in off.models],
                         "no file, no layer")

    def test_paths_resolve_relative_to_the_repo(self):
        s = settings.load(env={"COURSES_DIR": "../elsewhere", "STUDIO_STATE_ROOT": self.tmp},
                          dotenv={}, overlay="", studio_file="")
        self.assertEqual(s.courses_dir, os.path.normpath(os.path.join(settings.REPO_ROOT, "..", "elsewhere")))
        self.assertEqual(s.state_dir, os.path.normpath(self.tmp))
        self.assertEqual(s.progress_dir, os.path.join(os.path.normpath(self.tmp), "progress"))

    def test_missing_or_broken_file_is_loud(self):
        with self.assertRaises(settings.SettingsError):
            settings.load(os.path.join(self.tmp, "absent.json"), env={}, dotenv={}, overlay="", studio_file="")
        broken = os.path.join(self.tmp, "broken.json")
        with open(broken, "w", encoding="utf-8") as fh:
            fh.write("{")
        with self.assertRaises(settings.SettingsError):
            settings.load(broken, env={}, dotenv={}, overlay="", studio_file="")


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



class TestFailureKinds(unittest.TestCase):
    """`coursekit.failures` is the one place that says what a Claude failure was, because
    the answer differs per kind: wait out weather, swap a model that was refused, and stop
    at once when the account itself is the problem."""

    def test_the_wordings_the_cli_really_uses_are_recognised(self):
        cases = {
            "Claude usage limit reached. Your limit will reset at 3pm.": failures.QUOTA,
            "API Error: 429 rate_limit_error": failures.QUOTA,
            "Your credit balance is too low to access the Anthropic API": failures.QUOTA,
            "Invalid API key - please run /login": failures.AUTH,
            "API Error: 401 authentication_error": failures.AUTH,
            "unrecognized_model: claude-x[1m]": failures.MODEL,
            '"claude-x" isn\'t described by this version\'s model catalog': failures.MODEL,
            "API Error: 529 overloaded_error": failures.TRANSIENT,
            "fetch failed: ECONNRESET": failures.TRANSIENT,
            "API Error: 500 Internal server error": failures.TRANSIENT,
        }
        for text, kind in cases.items():
            self.assertEqual(failures.classify(text), kind, text)

    def test_a_failure_nobody_planned_for_is_permanent(self):
        """Unknown is not retried: trying something we cannot name again is how a run burns
        an hour to arrive at the same error."""
        self.assertEqual(failures.classify("exit code 1 with no output"), failures.UNKNOWN)
        self.assertEqual(failures.classify(""), failures.UNKNOWN)

    def test_the_reset_time_is_repeated_back_without_its_timezone(self):
        line = "Claude usage limit reached. Your limit will reset at 3pm (America/New_York)."
        self.assertEqual(failures.resets_at(line), "3pm")
        self.assertIn("3pm", failures.explain(failures.QUOTA, line, failures.resets_at(line)))
        self.assertEqual(failures.resets_at("API Error: 429"), "")

    def test_every_kind_has_a_sentence_and_none_of_them_is_stderr(self):
        for kind in (failures.QUOTA, failures.AUTH, failures.MODEL, failures.TRANSIENT):
            said = failures.explain(kind, "raw stderr nobody should read")
            self.assertTrue(said.endswith("."), said)
            self.assertNotIn("raw stderr", said)

    def test_describe_is_the_whole_classification_in_one_call(self):
        said, kind, when = failures.describe("usage limit reached, resets at 9:00 AM.")
        self.assertEqual((kind, when), (failures.QUOTA, "9:00 AM"))
        self.assertIn("9:00 AM", said)

    def test_an_http_status_says_the_same_things_in_numbers(self):
        self.assertEqual(failures.from_status(429), failures.QUOTA)
        self.assertEqual(failures.from_status(401), failures.AUTH)
        self.assertEqual(failures.from_status(404), failures.MODEL)
        self.assertEqual(failures.from_status(529), failures.TRANSIENT)
        self.assertEqual(failures.from_status(418), failures.UNKNOWN)


class Answers(llm_base.Provider):
    """A provider that says whatever the test tells it to, so the retry policy can be
    exercised without a subprocess. Each entry of `script` is either the text of a reply or
    an exception to raise."""

    kind = "test"
    name = "test"
    label = "The test provider"

    def __init__(self, *script):
        self.script = list(script)
        self.seen = []                  # the model each attempt asked for

    def available(self):
        return True

    def complete(self, req):
        self.seen.append(req.model)
        answer = self.script.pop(0) if self.script else "ok"
        if isinstance(answer, Exception):
            raise answer
        return llm_base.Reply(text=answer, model=req.model, provider=self.name)


def refused(detail, kind=""):
    return llm_base.failed(detail, kind, provider="test")


class TestProviderLayer(unittest.TestCase):
    """`coursekit.llm` is the one place a wire format or a command line appears. What is
    tested here is the part that is the platform, not any provider: which model is tried
    next, what is waited out, and what ends a run at once."""

    def setUp(self):
        self.backoff = llm_chain.BACKOFF
        llm_chain.BACKOFF = 0           # the waiting is the point, not the wall clock

    def tearDown(self):
        llm_chain.BACKOFF = self.backoff

    def _ask(self, provider, model="", prompt="hi"):
        return llm_chain.complete(
            provider, llm_base.Request(prompt=prompt, model=model, timeout=5)).text

    # ---- the chain

    def test_the_asked_for_model_is_tried_first_then_the_default_then_none(self):
        """The last resort names no model at all, which is what the default of the provider
        itself means. Without it a run dies when every listed model is refused."""
        provider = Answers(refused("unrecognized_model"), refused("unrecognized_model"), "ok")
        self.assertEqual(self._ask(provider, model="sonnet"), "ok")
        self.assertEqual(provider.seen, ["sonnet", llm_chain.default_model(), ""])

    def test_weather_is_waited_out_on_the_same_model(self):
        provider = Answers(refused("529 overloaded_error"), "ok")
        self.assertEqual(self._ask(provider, model="sonnet"), "ok")
        self.assertEqual(provider.seen, ["sonnet", "sonnet"], "the same model, not the next")

    def test_weather_that_never_clears_gives_up_after_the_settings_say_so(self):
        provider = Answers(*[refused("529 overloaded_error")] * 99)
        with self.assertRaises(llm_base.LLMFailed) as caught:
            self._ask(provider, model="sonnet")
        self.assertEqual(caught.exception.kind, failures.TRANSIENT)
        tried = len(set(provider.seen)) * (llm_chain.RETRIES + 1)
        self.assertEqual(len(provider.seen), tried)

    def test_an_exhausted_account_stops_at_the_first_model(self):
        """Every model on the chain draws on the same account, so trying the next one wastes
        a minute and then tells the reader the wrong story."""
        for detail, kind in (("Claude usage limit reached.", failures.QUOTA),
                             ("Invalid API key - please run /login", failures.AUTH)):
            provider = Answers(*[refused(detail)] * 9)
            with self.assertRaises(llm_base.LLMFailed) as caught:
                self._ask(provider, model="sonnet")
            self.assertEqual(caught.exception.kind, kind)
            self.assertEqual(len(provider.seen), 1, detail)

    def test_a_spent_timeout_is_not_paid_for_twice(self):
        provider = Answers(*[refused("no answer within 5s", failures.TIMEOUT)] * 9)
        with self.assertRaises(llm_base.LLMFailed):
            self._ask(provider, model="sonnet")
        self.assertEqual(len(provider.seen), 1)

    def test_a_provider_that_is_not_there_is_not_called(self):
        class Missing(Answers):
            def available(self):
                return False

        with self.assertRaises(llm_base.ProviderUnavailable):
            self._ask(Missing())

    def test_progress_is_reported_and_the_default_reporter_is_a_noop(self):
        """The tutor route calls this on a request thread, where nothing is watching."""
        seen = []

        class Watching(llm_chain.Reporter):
            def event(self, kind, **fields):
                seen.append((kind, fields.get("phase"), fields.get("ok")))

        original = llm_chain.REPORTER
        llm_chain.set_reporter(Watching())
        try:
            self._ask(Answers("ok"), model="sonnet")
        finally:
            llm_chain.set_reporter(original)
        self.assertEqual(seen, [("call", "start", None), ("call", "end", True)])
        llm_chain.REPORTER.event("call", phase="start")      # nothing listens; nothing breaks
        llm_chain.REPORTER.say("nor to this")

    # ---- shaping

    def test_a_prompt_is_sent_verbatim_and_never_wrapped_in_a_transcript(self):
        """A module prompt is a document, not a conversation. Wrapping it in "User:" would
        change what the model is asked."""
        provider, sent = Answers("ok"), []
        provider.complete = lambda r: sent.append(r) or llm_base.Reply(text="ok")
        llm_chain.complete(provider, llm_base.Request(prompt="Write M03.", timeout=5))
        self.assertEqual(sent[0].prompt, "Write M03.")

    def test_a_conversation_is_flattened_only_when_there_is_no_prompt(self):
        flat = llm_shape.chat_prompt("SYSTEM", [{"role": "user", "content": "why?"}])
        self.assertEqual(flat, "SYSTEM\n\nUser: why?\n\nAssistant:")

    def test_json_is_dug_out_of_prose_and_fences(self):
        self.assertEqual(llm_shape.strip_fence("```markdown\n# T\n```"), "# T")
        self.assertEqual(json.loads(llm_shape.slice_json('Here:\n{"a": [1, 2]}\nEnjoy.')),
                         {"a": [1, 2]})

    def test_ask_json_asks_again_with_the_parse_error(self):
        replies = iter(["not json at all", '```json\n{"a": 1}\n```'])
        asked = []

        def asker(prompt, **kw):
            asked.append(prompt)
            return next(replies)

        self.assertEqual(llm_chain.ask_json("q", asker=asker), {"a": 1})
        self.assertIn("could not be parsed as JSON", asked[1])

    # ---- the CLI provider

    def test_the_cli_argv_is_what_it_always_was(self):
        provider = llm_cli.CliProvider()
        self.assertEqual(provider._args_for("opus"),
                         ["-p", "--output-format", "text", "--model", "opus"])
        self.assertEqual(provider._args_for(""), ["-p", "--output-format", "text"],
                         "no model named means the default of the binary itself")

    def test_a_shim_on_windows_is_run_through_cmd(self):
        """A .cmd or .bat cannot be executed directly, and every Windows install is one."""
        if os.name != "nt":
            self.skipTest("the shim only exists on Windows")
        self.assertEqual(llm_cli.argv("C:/x/claude.cmd", ["-p"]),
                         ["cmd", "/c", "C:/x/claude.cmd", "-p"])
        self.assertEqual(llm_cli.argv("C:/x/claude.exe", ["-p"]), ["C:/x/claude.exe", "-p"])

    def test_the_registry_offers_the_cli_provider(self):
        self.assertEqual(llm.provider_for().kind, "cli")
        self.assertEqual(llm.provider_for("nothing-by-that-name").kind, "cli")
        self.assertIn("available", llm.describe()[0])


class TestCodeConventions(unittest.TestCase):
    """The rules in CLAUDE.md "Code conventions" that a test can hold."""

    PLATFORM = os.path.dirname(HERE)
    REPO = os.path.dirname(PLATFORM)

    def _python_files(self):
        out = []
        for sub in ("coursekit", "studio"):
            base = os.path.join(self.PLATFORM, sub)
            out += [os.path.join(base, n) for n in sorted(os.listdir(base)) if n.endswith(".py")]
        return out

    def test_every_module_starts_with_a_docstring(self):
        """A module says what it is for before it says anything else."""
        import ast
        missing = []
        for path in self._python_files():
            if os.path.basename(path) == "__init__.py":
                continue
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            if not ast.get_docstring(tree):
                missing.append(os.path.relpath(path, self.PLATFORM))
        self.assertEqual(missing, [], "modules without a docstring: %s" % missing)

    def test_no_module_reaches_into_another_modules_privates(self):
        """`_name` is private to its module. Something two modules need is public and lives
        in one place (files.py, ids.py, ...)."""
        import re
        offenders = []
        pattern = re.compile(r"\b(?!self\b|cls\b)([a-z_][a-z0-9_]*)\._[a-z][a-zA-Z0-9_]*\b")
        for path in self._python_files():
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    code = line.split("#")[0]
                    for m in pattern.finditer(code):
                        if m.group(1) in ("self", "cls", "os", "sys", "re", "json"):
                            continue
                        offenders.append("%s:%d %s" % (os.path.relpath(path, self.PLATFORM), n, m.group(0)))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def _prettier(self):
        """The formatter, when it is installed: `npm install` at the repo root, or on PATH."""
        local = os.path.join(self.REPO, "node_modules", ".bin",
                             "prettier.cmd" if os.name == "nt" else "prettier")
        if os.path.isfile(local):
            return local
        return shutil.which("prettier")

    def test_front_end_source_is_prettier_formatted(self):
        """One statement per line, one style everywhere: `npm run format` before a commit."""
        prettier = self._prettier()
        if not prettier:
            self.skipTest("prettier not installed (npm install)")
        import subprocess
        proc = subprocess.run([prettier, "--check", "platform/web/js/*.js", "platform/web/css/*.css",
                               "platform/studio/ui/js/*.js", "platform/studio/ui/*.css",
                               "platform/tests/page_smoke.js"],
                              cwd=self.REPO, capture_output=True, text=True, encoding="utf-8",
                              shell=(os.name == "nt"))
        self.assertEqual(proc.returncode, 0, (proc.stdout + proc.stderr).strip())

    def test_page_javascript_files_stay_small(self):
        """A file is one concern. Past this size it is two, and should be split (17-rail.js
        became 17-convos.js + 17-rail.js at 800 lines)."""
        big = []
        for path in bundler.source_files():
            if path.endswith(".js"):
                with open(path, encoding="utf-8") as fh:
                    n = sum(1 for _ in fh)
                if n > 700:
                    big.append("%s: %d lines" % (os.path.basename(path), n))
        self.assertEqual(big, [], "\n".join(big))

    # ---- the design system: one place for colour, one scale for type ----

    CSS_DIRS = ("platform/web/css", "platform/studio/ui")
    JS_DIRS = ("platform/web/js", "platform/studio/ui/js")
    # The scale: the tokens, the display sizes the two surfaces use for headings, and the
    # three relative sizes inside prose. A number outside this set is a new rung.
    FONT_SIZES = {"9px", "10px", "10.5px", "11.5px", "12.5px", "13px", "13.5px", "14px",
                  "14.5px", "15px", "15.5px", "16px", "16.5px", "17px", "18px", "19px",
                  "20px", "21px", "22px", "23px", "24px", "25px", "26px", "27px", "28px",
                  "30px", "32px", "52px", "0.87em", "1em", "1.17em", "inherit"}
    BTN_VARIANTS = {"primary", "ghost", "warm", "danger", "sm", "iconbtn", "disabled", "rm"}

    def _css_files(self):
        out = []
        for rel in self.CSS_DIRS:
            base = os.path.join(self.REPO, rel)
            out += [os.path.join(base, n) for n in sorted(os.listdir(base)) if n.endswith(".css")]
        return out

    def _js_files(self):
        out = []
        for rel in self.JS_DIRS:
            base = os.path.join(self.REPO, rel)
            out += [os.path.join(base, n) for n in sorted(os.listdir(base)) if n.endswith(".js")]
        return out

    def test_only_the_token_file_carries_a_colour(self):
        """Every colour the platform has is in web/css/00-tokens.css. A hex or an rgba()
        anywhere else is a second palette starting (CLAUDE.md "The design system")."""
        import re
        colour = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(")
        offenders = []
        for path in self._css_files():
            if os.path.basename(path) == "00-tokens.css":
                continue
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    if colour.search(line):
                        offenders.append("%s:%d %s" % (os.path.basename(path), n, line.strip()))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_font_sizes_come_from_the_scale(self):
        """A size is a token (--fs-*) or one of the display sizes already in use. A new
        number here means the type scale has quietly grown a rung."""
        import re
        rule = re.compile(r"font-size:\s*([^;}\n]+)")
        offenders = []
        for path in self._css_files():
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    for m in rule.finditer(line):
                        value = m.group(1).strip()
                        if value.startswith("var(") or value in self.FONT_SIZES:
                            continue
                        offenders.append("%s:%d %s" % (os.path.basename(path), n, value))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_no_button_variant_outside_the_family(self):
        """`.btn` has one family. A variant defined nowhere is a button that looks like a
        mistake on one screen and nothing at all on another."""
        import re
        found = set()
        for path in self._css_files():
            with open(path, encoding="utf-8") as fh:
                for m in re.finditer(r"\.btn((?:\.[a-z-]+)+)", fh.read()):
                    found.update(m.group(1).strip(".").split("."))
        self.assertEqual(found - self.BTN_VARIANTS, set(),
                         "button variants with no rule: %s" % (found - self.BTN_VARIANTS))

    def test_every_class_the_front_end_uses_exists_in_the_css(self):
        """A class in a template with no rule behind it renders as nothing — which is how
        `.card.tight` and `.disabled` came to be used in Studio and defined nowhere."""
        import re
        defined = set()
        for path in self._css_files():
            with open(path, encoding="utf-8") as fh:
                defined.update(re.findall(r"\.([A-Za-z][A-Za-z0-9_-]*)", fh.read()))
        used, offenders = set(), []
        for path in self._js_files():
            with open(path, encoding="utf-8") as fh:
                for m in re.finditer(r'class="([^"${}]+)"', fh.read()):
                    used.update(m.group(1).split())
        for name in sorted(used - defined):
            offenders.append(name)
        self.assertEqual(offenders, [], "classes used with no CSS rule: %s" % offenders)

    # The pairs the design system leans on at 13.5px and below, where AA asks for 4.5:1.
    # Read out of 00-tokens.css so the check moves when the palette does.
    CONTRAST_PAIRS = [("--muted", "--bg"), ("--muted", "--surface"), ("--text-2", "--bg"),
                      ("--text-2", "--surface"), ("--accent-ink", "--accent-soft"),
                      ("--ok", "--ok-soft"), ("--warm", "--warm-soft"), ("--bad", "--bad-soft"),
                      ("--on-accent", "--accent")]

    @staticmethod
    def _luminance(hex_colour):
        raw = hex_colour.lstrip("#")
        if len(raw) == 3:
            raw = "".join(c * 2 for c in raw)
        channels = []
        for i in (0, 2, 4):
            v = int(raw[i:i + 2], 16) / 255
            channels.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    def _themes(self):
        """The light palette and the dark one, as name -> hex, from the token file."""
        import re
        path = os.path.join(self.REPO, "platform", "web", "css", "00-tokens.css")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        light, dark = {}, {}
        # Each `:root...{ ... }` block, with enough of what comes before it to tell whether
        # it is the dark one (`[data-theme="dark"]`, or inside a prefers-color-scheme query).
        for m in re.finditer(r":root([^{]*)\{([^}]*)\}", text):
            found = dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,6})\s*;", m.group(2)))
            context = text[max(0, m.start() - 120):m.end()]
            is_dark = 'data-theme="dark"' in m.group(1) or "prefers-color-scheme: dark" in context
            (dark if is_dark else light).update(found)
        if not light or not dark:
            raise AssertionError("could not read both palettes out of 00-tokens.css")
        merged_dark = dict(light)
        merged_dark.update(dark)
        return {"light": light, "dark": merged_dark}

    def test_small_text_meets_AA_in_both_themes(self):
        """Every colour pair the platform prints small text in clears 4.5:1. `--muted` on
        `--bg` used to sit at about 4.0 (CLAUDE.md "The design system")."""
        bad = []
        for theme, palette in self._themes().items():
            for fg, bg in self.CONTRAST_PAIRS:
                if fg not in palette or bg not in palette:
                    bad.append("%s: %s or %s is not defined" % (theme, fg, bg))
                    continue
                a, b = self._luminance(palette[fg]), self._luminance(palette[bg])
                ratio = (max(a, b) + 0.05) / (min(a, b) + 0.05)
                if ratio < 4.5:
                    bad.append("%s: %s on %s is %.2f:1" % (theme, fg, bg, ratio))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_inline_styles_stay_rare(self):
        """An inline style is for a value only the code knows — a bar's width, a colour
        from a score. Anything else belongs in a stylesheet."""
        import re
        counts = {}
        for path in self._js_files():
            with open(path, encoding="utf-8") as fh:
                counts[path] = len(re.findall(r'style="', fh.read()))
        reader = sum(v for k, v in counts.items() if "web" in k)
        studio = sum(v for k, v in counts.items() if "studio" in k)
        self.assertLessEqual(reader, 60, "inline styles in web/js: %d" % reader)
        self.assertLessEqual(studio, 30, "inline styles in studio/ui/js: %d" % studio)



GOOD_NB = json.dumps({
    "nbformat": 4, "nbformat_minor": 5, "metadata": {"kernelspec": {"name": "python3"}},
    "cells": [
        {"id": "a", "cell_type": "markdown", "metadata": {}, "source": "Change **n** and rerun."},
        {"id": "b", "cell_type": "code", "metadata": {}, "execution_count": 2,
         "source": ["n = 3\n", "print(n * 2)  # your turn"],
         "outputs": [
             {"output_type": "stream", "name": "stdout", "text": ["6\n"]},
             {"output_type": "display_data",
              "data": {"image/png": "iVBORw0KGgo=\n", "text/plain": "<Figure>"}},
             {"output_type": "execute_result", "execution_count": 2,
              "data": {"text/html": "<script>alert(1)</script>", "text/plain": "7"}},
             {"output_type": "error", "ename": "ZeroDivisionError", "evalue": "division by zero",
              "traceback": []}]},
        {"id": "c", "cell_type": "raw", "metadata": {}, "source": "ignored"},
    ],
})


class TestNotebooks(TempCourseTest):
    """A notebook is an .ipynb under notebooks/, referenced as `[caption](notebooks/<name>.ipynb)`
    and rendered read-only by the build; only a course whose manifest declares `notebooks`
    may carry one (CLAUDE.md "Notebooks")."""

    def _with_notebook(self, name, text, mid="M01", caption="Try it: double a number", declare=True):
        nb_dir = os.path.join(self.course.root, "notebooks")
        os.makedirs(nb_dir, exist_ok=True)
        if text is not None:
            with open(os.path.join(nb_dir, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        if declare:
            self.course.edit_manifest(notebooks={"kernel": "python3", "packages": ["numpy"]})
        cfg = config.load(self.course.root)
        path = next(m.source for m in loader.load_modules(cfg) if m.id == mid)
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        body = body.replace("The idea, stated plainly.",
                            "The idea, stated plainly.\n\n[%s](notebooks/%s)" % (caption, name))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)

    def test_a_notebook_is_rendered_read_only_with_its_cells_and_outputs(self):
        self._with_notebook("M01-1.ipynb", GOOD_NB)
        cfg = config.load(self.course.root)
        self.assertEqual(cfg.notebooks, {"kernel": "python3", "packages": ["numpy"]})
        self.assertEqual(cfg.runtime()["notebooks"], cfg.notebooks)
        mods = loader.load_modules(cfg)
        sec = mods[0].sections[1]
        self.assertIn('<div class="notebook" data-nb="M01-1.ipynb" data-cells="2">', sec.html)
        self.assertIn('<span class="nb-title">Try it: double a number</span>', sec.html)
        self.assertIn("Change <strong>n</strong> and rerun.", sec.html)
        self.assertIn("print(n * 2)  # your turn", sec.html)
        self.assertIn('<pre class="nb-out">6\n</pre>', sec.html)
        self.assertIn('src="data:image/png;base64,iVBORw0KGgo="', sec.html)
        self.assertIn("ZeroDivisionError: division by zero", sec.html)
        self.assertNotIn("<script>", sec.html, "an HTML output never reaches the page")
        self.assertNotIn("ignored", sec.html, "an unknown cell type is skipped")
        self.assertIn("Try it: double a number", sec.text, "the caption is words for search")
        ref = mods[0].notebooks[0]
        self.assertEqual((ref["name"], ref["cells"], ref["problem"]), ("M01-1.ipynb", 2, ""))
        self.assertIn("n = 3", ref["code"])
        self.assertEqual(sec.public()["notebooks"], [{"name": "M01-1.ipynb", "code": ref["code"]}])
        self.assertNotIn("notebooks", mods[0].sections[0].public(), "only a section with one pays for the field")
        self.assertEqual(self.course.problems(), [])
        _, result = self.course.build(os.path.join(self.tmp, "out"))
        self.assertEqual(result.notebooks, 1)
        self.assertIn("notebooks 1", result.summary())

    def test_a_notebook_needs_the_manifest_to_declare_the_runtime(self):
        self._with_notebook("M01-1.ipynb", GOOD_NB, declare=False)
        problems = self.course.problems()
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("M01: notebook M01-1.ipynb is referred to, but course.json declares no "
                      "notebooks runtime", problems[0])
        self.assertIsNone(config.load(self.course.root).runtime()["notebooks"])

    def test_a_missing_or_broken_notebook_is_a_check_problem(self):
        self._with_notebook("M01-1.ipynb", None)
        problems = self.course.problems()
        self.assertIn("M01: notebook M01-1.ipynb is missing from notebooks/", problems[0])
        self._with_notebook("M02-1.ipynb", "{not json", mid="M02")
        problems = self.course.problems()
        self.assertTrue(any("M02: notebook M02-1.ipynb is not valid JSON" in p for p in problems), problems)
        self._with_notebook("M03-1.ipynb", json.dumps({"nbformat": 3, "cells": []}), mid="M03")
        problems = self.course.problems()
        self.assertTrue(any("M03: notebook M03-1.ipynb is not an nbformat 4 notebook" in p
                            for p in problems), problems)

    def test_only_a_notebook_link_survives_as_a_link(self):
        """Relative links lose their anchor in a one-file site; a notebook reference is the
        one exception, because the build replaces it."""
        from coursekit.markdown_render import to_html
        self.assertEqual(to_html("[a](other.md)"), "<p><em>a</em></p>")
        self.assertIn('<a href="notebooks/x.ipynb">a</a>', to_html("[a](notebooks/x.ipynb)"))

    def test_names_for_lists_a_modules_notebooks_in_order(self):
        from coursekit import notebooks
        nb_dir = os.path.join(self.course.root, "notebooks")
        os.makedirs(nb_dir)
        for name in ("M01-2.ipynb", "M01-10.ipynb", "M01-1.ipynb", "M02-1.ipynb", "M01-x.ipynb"):
            open(os.path.join(nb_dir, name), "w").close()
        self.assertEqual(notebooks.names_for(nb_dir, "M01"), ["M01-1.ipynb", "M01-2.ipynb", "M01-10.ipynb"])
        self.assertEqual(notebooks.first_problem(""), "is empty")
        self.assertEqual(notebooks.first_problem(GOOD_NB), "")


class TestJupyterSettings(unittest.TestCase):
    """`jupyter.*` resolves like the bridge: an explicit URL wins, 0.0.0.0 is never told to a
    browser, the internal URL falls back to the public one, and the token stays out of
    CFG.platform (CLAUDE.md "Notebooks")."""

    def test_urls_and_token(self):
        s = settings.load(env={"JUPYTER_PORT": "9888", "JUPYTER_HOST": "0.0.0.0"}, dotenv={}, overlay="", studio_file="")
        self.assertEqual(s.jupyter_url, "http://127.0.0.1:9888")
        self.assertEqual(s.jupyter_internal_url, s.jupyter_url)
        self.assertNotIn(s.get("jupyter.token"), json.dumps(s.page()), "the token never reaches a built page")
        s = settings.load(env={"JUPYTER_URL": "http://jupyter.local:1234/",
                               "JUPYTER_INTERNAL_URL": "http://jupyter:8888"}, dotenv={}, overlay="", studio_file="")
        self.assertEqual(s.jupyter_url, "http://jupyter.local:1234")
        self.assertEqual(s.jupyter_internal_url, "http://jupyter:8888")
        self.assertIn("JUPYTER_TOKEN", settings.ENV_KEYS)

if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Self-tests for the course platform.

    python platform/tests/test_build.py

These build throwaway courses in a temp directory. They cover the two things most likely to
break quietly: the validator letting an inconsistent course through, and a subject-specific
string creeping back into the engine.
"""

from __future__ import annotations

import json
import os
import re
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
from coursekit.llm import anthropic as llm_anthropic  # noqa: E402
from coursekit.llm import chain as llm_chain  # noqa: E402
from coursekit.llm import cli as llm_cli  # noqa: E402
from coursekit.llm import gemini as llm_gemini  # noqa: E402
from coursekit.llm import openai as llm_openai  # noqa: E402
from coursekit.llm import shape as llm_shape  # noqa: E402
from coursekit.llm import wire as llm_wire  # noqa: E402
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
    (CONVENTIONS.md "Figures")."""

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

    # Who makes the model is configuration, not something either front end knows. The two
    # surfaces name a provider from `CFG.platform.providers` or from `/api/state`; a literal
    # here would be a second source of truth, and the one that goes stale.
    VENDORS = ("claude", "anthropic", "openai", "chatgpt", "gpt-", "gemini", "llama", "mistral")

    # The three places a vendor may be named, each for a reason that is not prose.
    VENDORS_ALLOWED = {
        # It is the adapters: one entry per wire format, named for the format it speaks.
        "14b-wire.js": ("anthropic", "openai", "gemini"),
        # A built page can be older than the Studio serving it, so it reads both the block's
        # name and the one it had before providers existed.
        "14-conn.js": ("claude",),
        # A save from before providers held one key, and it could only ever have been that one.
        "01-state.js": ("anthropic",),
    }

    def test_neither_front_end_names_who_makes_the_model(self):
        """The two-layer rule, applied to vendors instead of subjects: the engine may not
        say "Claude" any more than it may say "marketing". Every name a reader sees comes
        from the settings, through CFG.platform or /api/state."""
        roots = [os.path.join(PLATFORM, "web", "js"),
                 os.path.join(PLATFORM, "studio", "ui")]
        offenders = []
        for root in roots:
            for folder, _dirs, names in os.walk(root):
                for name in sorted(names):
                    if not name.endswith((".js", ".css", ".html")):
                        continue
                    allowed = self.VENDORS_ALLOWED.get(name, ())
                    text = open(os.path.join(folder, name), encoding="utf-8").read().lower()
                    for word in self.VENDORS:
                        if word in text and word not in allowed:
                            offenders.append("%s names %r" % (name, word))
        self.assertEqual(offenders, [], "\n".join(offenders) + "\n\n"
                         "Name it from CFG.platform.providers or /api/state, or add the file "
                         "to VENDORS_ALLOWED with the reason it is not prose.")

    def test_a_key_never_reaches_a_built_page(self):
        """A built page is a file anyone may be given. Every provider key is stripped from
        `page()` by rule, so a provider added later is stripped without this test changing."""
        keyed = settings.load(env={"ANTHROPIC_API_KEY": "sk-ant-leak",
                                   "OPENAI_API_KEY": "sk-oai-leak"},
                              dotenv={}, overlay="", studio_file="")
        page = json.dumps(keyed.page())
        self.assertNotIn("sk-ant-leak", page)
        self.assertNotIn("sk-oai-leak", page)
        self.assertNotIn("apiKey", page)
        self.assertTrue(keyed.get("providers.anthropic.apiKey"), "it was set, and still stripped")

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
        for key in ("bridgeUrl", "providers", "defaultModel", "models",
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
        for key in ("studio.host", "studio.port", "bridge.host", "bridge.port",
                    "providers.anthropic.apiUrl", "providers.anthropic.apiVersion",
                    "providers.claude-code.kind", "models.default", "llm.timeout",
                    "llm.defaultProvider", "logs.maxBytes",
                    "generation.timeouts.module", "build.excerptChars", "page.tutor.maxTokens",
                    "page.study.maxFreezes", "page.ui.railDefault", "page.learner.maxGaps",
                    "page.audio.rate"):
            self.assertIsNotNone(s.get(key), key)
        self.assertIn(s.default_provider, s.provider_names())
        self.assertTrue(all(m["provider"] in s.provider_names(True) for m in s.models))
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
        self.assertEqual(s.page()["models"],
                         [{"id": "claude-mini-9", "label": "Mini", "provider": "claude-code"}])
        self.assertEqual(s.overrides["studio.port"], overlay)
        self.assertIn({"key": "studio.port", "value": 8100, "source": overlay}, s.describe())

    def test_a_model_that_names_no_provider_belongs_to_the_default_one(self):
        """A model list saved before providers existed still resolves - which is what makes
        this change need no migration."""
        overlay = self._file("old.json", {
            "models": {"list": [{"id": "claude-mini-9", "alias": "mini", "label": "Mini"}]},
        })
        s = settings.load(env={}, dotenv={}, overlay=overlay, studio_file="")
        self.assertEqual(s.models[0]["provider"], s.default_provider)
        self.assertEqual(s.provider_of("mini"), s.default_provider)
        self.assertEqual([m["id"] for m in s.models_for(s.default_provider)], ["claude-mini-9"])

    def test_the_older_setting_names_are_moved_to_where_they_are_read_now(self):
        """An existing .env or overlay says `claude.timeout` and `anthropic.apiUrl`. Present
        at all means deliberately set, so it wins - and the settings page says where it came
        from rather than showing a key nothing reads."""
        overlay = self._file("legacy.json", {
            "claude": {"timeout": 111, "retries": 9},
            "anthropic": {"apiUrl": "https://example.test/v1/messages"},
        })
        s = settings.load(env={}, dotenv={}, overlay=overlay, studio_file="")
        self.assertEqual(s.get("llm.timeout"), 111)
        self.assertEqual(s.get("llm.retries"), 9)
        self.assertEqual(s.get("providers.anthropic.apiUrl"), "https://example.test/v1/messages")
        self.assertIsNone(s.get("claude.timeout"), "one place to look, not two")
        self.assertIsNone(s.get("anthropic.apiUrl"))
        self.assertEqual(s.overrides["llm.timeout"], overlay)
        self.assertEqual(s.page_providers()[0]["apiUrl"], "https://example.test/v1/messages")

    def test_an_old_env_name_still_reaches_the_setting_it_always_meant(self):
        s = settings.load(env={"BRIDGE_API_URL": "https://proxy.test/v1/messages",
                               "ANTHROPIC_API_VERSION": "2024-01-01"},
                          dotenv={}, overlay="", studio_file="")
        self.assertEqual(s.provider("anthropic")["apiUrl"], "https://proxy.test/v1/messages")
        self.assertEqual(s.page_providers()[0]["apiVersion"], "2024-01-01")

    def test_the_page_is_told_which_providers_it_may_call_itself(self):
        """A provider that runs a binary is no use to a browser, and a disabled one is no use
        to anybody. A key never goes: a built page is a file anyone may be given."""
        s = settings.load(env={"ANTHROPIC_API_KEY": "sk-ant-secret"}, dotenv={}, overlay="",
                          studio_file="")
        offered = {p["name"]: p for p in s.page()["providers"]}
        self.assertIn("anthropic", offered)
        self.assertNotIn("claude-code", offered, "a browser cannot spawn a process")
        self.assertNotIn("openai", offered, "not enabled")
        self.assertEqual(offered["anthropic"]["kind"], "anthropic")
        self.assertTrue(offered["anthropic"]["needsKey"])
        self.assertNotIn("sk-ant-secret", json.dumps(s.page()))

    def test_a_local_tool_says_which_api_serves_the_same_models(self):
        """A browser cannot spawn a process, so a model whose provider is a command-line tool
        would be unreachable from a page opened off disk - though the same model sits behind
        an API. Which API is a setting, not a guess made from the model's name."""
        s = settings.SETTINGS
        offered = {p["name"]: p for p in s.page().get("providers", [])}
        stands_in = {name: p.get("standsInFor", []) for name, p in offered.items()}
        self.assertIn("claude-code", stands_in.get("anthropic", []),
                      "the shipped cli row names its API twin")
        self.assertEqual(s.provider("claude-code")["apiProvider"], "anthropic")

    def test_secrets_are_masked_and_stay_off_the_page(self):
        """A provider key and the Jupyter token show as set or empty on the settings page and
        never reach `page()`. Which settings are secret is a rule - anything called apiKey -
        because a provider can be added without this file being edited."""
        s = settings.load(env={"ANTHROPIC_API_KEY": "sk-ant-test-secret"}, dotenv={}, overlay="",
                          studio_file="")
        self.assertEqual(s.get("providers.anthropic.apiKey"), "sk-ant-test-secret")
        self.assertTrue(settings.is_secret("providers.openai.apiKey"))
        rows = {r["key"]: r["value"] for r in s.describe()}
        self.assertEqual(rows["providers.anthropic.apiKey"], "(set)")
        self.assertEqual(rows["jupyter.token"], "(set)")
        self.assertNotIn("sk-ant-test-secret", json.dumps(s.describe()))
        self.assertNotIn("sk-ant-test-secret", json.dumps(s.page()))
        self.assertNotIn("apiKey", json.dumps(s.page()))
        blank = settings.load(env={}, dotenv={}, overlay="", studio_file="")
        self.assertEqual({r["key"]: r["value"] for r in blank.describe()}
                         ["providers.anthropic.apiKey"], "")

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
    label = "The test provider"

    def __init__(self, *script, name="claude-code"):
        self.name = name                # stand in for a real provider: the chain rules apply
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

    @staticmethod
    def _id(alias):
        """What a provider is actually sent for a model the chain calls `alias`."""
        return settings.SETTINGS.model_id(alias)

    # ---- the chain

    def test_the_asked_for_model_is_tried_first_then_the_default_then_none(self):
        """The last resort names no model at all, which is what the default of the provider
        itself means. Without it a run dies when every listed model is refused."""
        provider = Answers(refused("unrecognized_model"), refused("unrecognized_model"), "ok")
        self.assertEqual(self._ask(provider, model="sonnet"), "ok")
        self.assertEqual(provider.seen, [self._id("sonnet"),
                                         self._id(llm_chain.default_model()), ""])

    def test_weather_is_waited_out_on_the_same_model(self):
        provider = Answers(refused("529 overloaded_error"), "ok")
        self.assertEqual(self._ask(provider, model="sonnet"), "ok")
        self.assertEqual(provider.seen, [self._id("sonnet")] * 2, "the same model, not the next")

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
                         ["-p", "--output-format", "text", "--model", "claude-opus-5"])
        self.assertEqual(provider._args_for(""), ["-p", "--output-format", "text"],
                         "no model named means the default of the binary itself")

    def test_a_tool_that_will_not_read_stdin_can_take_the_prompt_as_an_argument(self):
        """Not the default, and it must not become one: a Windows command line caps at 8191
        characters and a module prompt passed that an order of magnitude ago."""
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"], seen["input"] = argv, kw.get("input")

            class Done:
                returncode, stdout, stderr = 0, "ok", ""

            return Done()

        provider = llm_cli.CliProvider(prompt_on="arg", commands=("claude",))
        real_run, real_find = llm_cli.subprocess.run, llm_cli.find_cli
        llm_cli.subprocess.run, llm_cli.find_cli = fake_run, lambda *a: "claude"
        try:
            provider.complete(llm_base.Request(prompt="WRITE M03", model="opus", timeout=5))
        finally:
            llm_cli.subprocess.run, llm_cli.find_cli = real_run, real_find
        self.assertEqual(seen["argv"][-1], "WRITE M03")
        self.assertIsNone(seen["input"], "it is on the command line, not on stdin")

    def test_a_shim_on_windows_is_run_through_cmd(self):
        """A .cmd or .bat cannot be executed directly, and every Windows install is one."""
        if os.name != "nt":
            self.skipTest("the shim only exists on Windows")
        self.assertEqual(llm_cli.argv("C:/x/claude.cmd", ["-p"]),
                         ["cmd", "/c", "C:/x/claude.cmd", "-p"])
        self.assertEqual(llm_cli.argv("C:/x/claude.exe", ["-p"]), ["C:/x/claude.exe", "-p"])

    def test_a_provider_is_sent_the_models_full_id_whatever_kind_it_is(self):
        """The chain works in the short names a person types; what a provider is given is the
        full id, because that is the one spelling everything accepts. An endpoint has never
        heard of `opus`, and only one command-line tool has - a second one would be handed a
        name it does not know."""
        cli = llm_cli.CliProvider()
        api = llm_anthropic.AnthropicProvider(api_url="https://x.test", key="k")
        default = settings.SETTINGS.default_model
        full = settings.SETTINGS.model_id(default)
        self.assertNotEqual(default, full, "the shipped list has aliases, or this proves nothing")
        for provider in (cli, api):
            self.assertEqual(provider.model_name(default), full)
            self.assertEqual(provider.model_name(full), full, "an id is already what was meant")
            self.assertEqual(provider.model_name(""), "", "no model named stays no model named")
            self.assertEqual(provider.model_name("llama3.1:70b"), "llama3.1:70b",
                             "a name the list does not carry is already what was meant")

    def test_a_provider_is_addressable_before_it_is_enabled(self):
        """`enabled` governs what is offered, not what may be addressed - otherwise a row
        cannot be tested until it is switched on, and switching it on is the thing you wanted
        to test first."""
        off = [name for name in settings.SETTINGS.provider_names(True)
               if name not in settings.SETTINGS.provider_names()]
        self.assertTrue(off, "settings.json ships some providers turned off")
        self.assertIsNotNone(llm.find(off[0]))
        self.assertNotIn(off[0], [p.name for p in llm.providers()])
        self.assertIn(off[0], [p.name for p in llm.providers(all_of_them=True)])

    def test_a_probe_is_never_quietly_answered_by_a_different_provider(self):
        """"Does this model work on OpenAI" must not be answered by Claude Code saying no."""
        off = [name for name in settings.SETTINGS.provider_names(True)
               if name not in settings.SETTINGS.provider_names()]
        answer = llm.probe("some-model", name=off[0])
        self.assertFalse(answer["ok"])
        self.assertIn(llm.find(off[0]).label, answer["error"])
        nowhere = llm.probe("some-model", name="no-such-provider")
        self.assertFalse(nowhere["ok"])
        self.assertIn("no provider called", nowhere["error"])

    def test_the_registry_offers_the_cli_provider(self):
        self.assertEqual(llm.provider_for().kind, "cli")
        self.assertEqual(llm.provider_for("nothing-by-that-name").kind, "cli")
        self.assertIn("available", llm.describe()[0])


class Answered:
    """One canned HTTP response, as urlopen hands it over."""

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def refusal(code, payload=None):
    """An HTTPError the way urllib raises one, body and all."""
    import io as streams
    import urllib.error

    body = json.dumps(payload or {}).encode("utf-8")
    return urllib.error.HTTPError("https://x.test", code, "no", {}, streams.BytesIO(body))


class WireTest(unittest.TestCase):
    """Shared scaffolding: one canned HTTP exchange, and the request that was sent."""

    def setUp(self):
        self.sent = []
        self.real = llm_wire.urllib.request.urlopen

    def tearDown(self):
        llm_wire.urllib.request.urlopen = self.real

    def _answers(self, *replies):
        """Queue the exchanges one script will have, and forget any earlier one."""
        answers = list(replies)
        self.sent = []

        def urlopen(request, timeout=0):
            self.sent.append(request)
            answer = answers.pop(0) if answers else {}
            if isinstance(answer, Exception):
                raise answer
            return Answered(answer)

        llm_wire.urllib.request.urlopen = urlopen

    def _body(self, n=0):
        return json.loads(self.sent[n].data.decode("utf-8"))


class TestAnthropicProvider(WireTest):
    """The second provider, and the one that proved the interface: a key instead of a
    signed-in binary, a system prompt beside the turns instead of inside them, and an HTTP
    status instead of an exit code. None of that may reach a caller."""

    def setUp(self):
        WireTest.setUp(self)
        self.provider = llm_anthropic.AnthropicProvider(
            api_url="https://x.test/v1/messages", models_url="https://x.test/v1/models",
            api_version="2023-06-01", key="sk-ant-test")

    @staticmethod
    def _said(text, stop="end_turn"):
        return {"content": [{"type": "text", "text": text}], "stop_reason": stop}

    def test_the_system_prompt_travels_beside_the_turns(self):
        self._answers(self._said("hello"))
        reply = self.provider.complete(llm_base.Request(
            system="SYSTEM", messages=[{"role": "user", "content": "why?"}],
            model="claude-opus-5", timeout=5, max_tokens=99))
        body = json.loads(self.sent[0].data.decode("utf-8"))
        self.assertEqual(body["system"], "SYSTEM")
        self.assertEqual(body["messages"], [{"role": "user", "content": "why?"}])
        self.assertEqual(body["max_tokens"], 99)
        self.assertEqual(body["model"], "claude-opus-5")
        self.assertEqual(reply.text, "hello")
        self.assertEqual(self.sent[0].headers["X-api-key"], "sk-ant-test")

    def test_a_built_prompt_becomes_the_one_turn(self):
        """A caller that built its own text is not holding a conversation."""
        self._answers(self._said("ok"))
        self.provider.complete(llm_base.Request(prompt="Write M03.", timeout=5))
        body = json.loads(self.sent[0].data.decode("utf-8"))
        self.assertEqual(body["messages"], [{"role": "user", "content": "Write M03."}])
        self.assertNotIn("system", body)

    def test_a_truncated_answer_says_so_in_the_notes(self):
        self._answers(self._said("half a th", stop="max_tokens"))
        self.assertIn("max_tokens", self.provider.complete(
            llm_base.Request(prompt="hi", timeout=5)).notes)

    def test_an_http_status_becomes_the_kind_every_layer_branches_on(self):
        for code, kind in ((429, failures.QUOTA), (401, failures.AUTH), (404, failures.MODEL),
                           (529, failures.TRANSIENT)):
            self._answers(refusal(code, {"error": {"type": "x_error", "message": "no"}}))
            with self.assertRaises(llm_base.LLMFailed) as caught:
                self.provider.complete(llm_base.Request(prompt="hi", timeout=5))
            self.assertEqual(caught.exception.kind, kind, code)
            self.assertIn("no", caught.exception.detail)

    def test_the_error_body_is_read_when_the_status_says_nothing_useful(self):
        self._answers(refusal(400, {"error": {"type": "not_found_error", "message": "gone"}}))
        with self.assertRaises(llm_base.LLMFailed) as caught:
            self.provider.complete(llm_base.Request(prompt="hi", timeout=5))
        self.assertEqual(caught.exception.kind, failures.MODEL)

    def test_no_key_is_an_auth_failure_and_not_a_call(self):
        self._answers()
        with self.assertRaises(llm_base.LLMFailed) as caught:
            self.provider.with_key("").complete(llm_base.Request(prompt="hi", timeout=5))
        self.assertEqual(caught.exception.kind, failures.AUTH)
        self.assertEqual(self.sent, [], "nothing was sent")

    def test_the_catalogue_reads_every_page(self):
        self._answers({"data": [{"id": "claude-a", "display_name": "A", "created_at": "2026-01"}],
                       "has_more": True, "last_id": "claude-a"},
                      {"data": [{"id": "claude-b", "display_name": "B", "created_at": "2026-02"}],
                       "has_more": False})
        found = self.provider.catalog()
        self.assertTrue(found["ok"])
        self.assertEqual([m["id"] for m in found["models"]], ["claude-a", "claude-b"])

    def test_a_catalogue_that_cannot_answer_says_so_rather_than_being_empty(self):
        """"Says nothing" and "offers nothing" mean opposite things to the merge."""
        self._answers(refusal(500))
        self.assertEqual(self.provider.catalog()["ok"], False)
        self.assertEqual(llm_anthropic.AnthropicProvider().catalog()["ok"], False)

    def test_the_probe_never_raises_and_names_the_kind(self):
        self._answers(refusal(429, {"error": {"message": "rate_limit_error"}}))
        result = self.provider.probe("claude-opus-5", timeout=5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["why"], failures.QUOTA)
        self.assertTrue(result["advice"])


class TestOpenAIProvider(WireTest):
    """Chat Completions, which is also Ollama, LM Studio, vLLM, OpenRouter, Groq and Azure -
    one adapter with the base URL as a setting."""

    def setUp(self):
        WireTest.setUp(self)
        self.provider = llm_openai.OpenAIProvider(
            name="openai", label="OpenAI", api_url="https://o.test/v1/chat/completions",
            models_url="https://o.test/v1/models", key="sk-test")

    @staticmethod
    def _said(text, why="stop"):
        return {"choices": [{"message": {"content": text}, "finish_reason": why}]}

    def test_the_system_prompt_is_a_turn_rather_than_a_field(self):
        self._answers(self._said("hello"))
        reply = self.provider.complete(llm_base.Request(
            system="SYSTEM", messages=[{"role": "user", "content": "why?"},
                                       {"role": "assistant", "content": "because"}],
            model="gpt-5.6", timeout=5, max_tokens=50))
        body = self._body()
        self.assertEqual(body["messages"][0], {"role": "system", "content": "SYSTEM"})
        self.assertEqual([m["role"] for m in body["messages"]],
                         ["system", "user", "assistant"])
        self.assertEqual(reply.text, "hello")
        self.assertEqual(self.sent[0].headers["Authorization"], "Bearer sk-test")

    def test_which_name_the_token_cap_goes_by_is_a_setting(self):
        """Newer reasoning models reject `max_tokens`; every older server rejects the other.
        Guessing here would be a literal in the code for something that differs per server."""
        self._answers(self._said("ok"), self._said("ok"))
        self.provider.complete(llm_base.Request(prompt="hi", timeout=5, max_tokens=9))
        self.assertIn("max_tokens", self._body(0))
        newer = self.provider.with_key("sk-test")
        newer.max_tokens_field = "max_completion_tokens"
        newer.complete(llm_base.Request(prompt="hi", timeout=5, max_tokens=9))
        self.assertIn("max_completion_tokens", self._body(1))
        self.assertNotIn("max_tokens", self._body(1))

    def test_a_truncated_answer_says_so_in_the_notes(self):
        self._answers(self._said("half a th", why="length"))
        self.assertIn("length",
                      self.provider.complete(llm_base.Request(prompt="hi", timeout=5)).notes)

    def test_the_error_body_names_the_kind_the_status_alone_would_miss(self):
        self._answers(refusal(400, {"error": {"code": "model_not_found", "message": "no"}}))
        with self.assertRaises(llm_base.LLMFailed) as caught:
            self.provider.complete(llm_base.Request(prompt="hi", timeout=5))
        self.assertEqual(caught.exception.kind, failures.MODEL)

    def test_the_catalogue_is_one_page_of_ids(self):
        self._answers({"data": [{"id": "gpt-5.6"}, {"id": "gpt-4o"}]})
        self.assertEqual([m["id"] for m in self.provider.catalog()["models"]],
                         ["gpt-5.6", "gpt-4o"])


class TestGeminiProvider(WireTest):
    """generateContent: the model in the path, `parts` instead of `content`, and the
    assistant called `model`."""

    def setUp(self):
        WireTest.setUp(self)
        self.provider = llm_gemini.GeminiProvider(
            name="google", label="Google Gemini", api_url="https://g.test/v1beta",
            key="AIza-test")

    @staticmethod
    def _said(text, why="STOP"):
        return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": why}]}

    def test_the_model_goes_in_the_path_and_the_prefix_is_not_repeated(self):
        self._answers(self._said("ok"), self._said("ok"))
        self.provider.complete(llm_base.Request(prompt="hi", model="gemini-flash-3", timeout=5))
        self.provider.complete(llm_base.Request(prompt="hi", model="models/gemini-flash-3",
                                                timeout=5))
        wanted = "https://g.test/v1beta/models/gemini-flash-3:generateContent"
        self.assertEqual([r.full_url for r in self.sent], [wanted, wanted])

    def test_the_assistant_is_called_model_and_the_system_prompt_is_an_instruction(self):
        self._answers(self._said("ok"))
        self.provider.complete(llm_base.Request(
            system="SYSTEM", messages=[{"role": "user", "content": "a"},
                                       {"role": "assistant", "content": "b"}],
            model="gemini-flash-3", timeout=5, max_tokens=50))
        body = self._body()
        self.assertEqual([c["role"] for c in body["contents"]], ["user", "model"])
        self.assertEqual(body["contents"][0]["parts"], [{"text": "a"}])
        self.assertEqual(body["systemInstruction"], {"parts": [{"text": "SYSTEM"}]})
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 50)

    def test_the_key_travels_in_a_header_not_the_url(self):
        """A key in a query string ends up in every log that records a URL."""
        self._answers(self._said("ok"))
        self.provider.complete(llm_base.Request(prompt="hi", model="g", timeout=5))
        self.assertEqual(self.sent[0].headers["X-goog-api-key"], "AIza-test")
        self.assertNotIn("AIza-test", self.sent[0].full_url)

    def test_the_parts_of_one_answer_are_joined(self):
        self._answers({"candidates": [{"content": {"parts": [{"text": "ha"}, {"text": "lf"}]}}]})
        self.assertEqual(
            self.provider.complete(llm_base.Request(prompt="hi", model="g", timeout=5)).text,
            "half")

    def test_the_catalogue_keeps_the_resource_path_as_the_id(self):
        """`models/gemini-flash-3` is what the model field takes, so it is what we store."""
        self._answers({"models": [{"name": "models/gemini-flash-3", "displayName": "Flash 3"}]})
        found = self.provider.catalog()["models"]
        self.assertEqual(found[0]["id"], "models/gemini-flash-3")
        self.assertEqual(found[0]["label"], "Flash 3")


class TestEveryProviderBehavesTheSameWayWhenItFails(WireTest):
    """The point of the layer: four wire formats, one set of kinds, one retry policy. A
    caller must not be able to tell which one answered."""

    def _providers(self):
        return (llm_anthropic.AnthropicProvider(api_url="https://a.test/v1/messages",
                                                api_version="2023-06-01", key="k"),
                llm_openai.OpenAIProvider(api_url="https://o.test/v1/chat", key="k"),
                llm_gemini.GeminiProvider(api_url="https://g.test/v1beta", key="k"))

    def test_a_status_means_the_same_thing_whoever_sent_it(self):
        for provider in self._providers():
            for code, kind in ((429, failures.QUOTA), (401, failures.AUTH),
                               (404, failures.MODEL), (503, failures.TRANSIENT)):
                self._answers(refusal(code))
                with self.assertRaises(llm_base.LLMFailed) as caught:
                    provider.complete(llm_base.Request(prompt="hi", model="m", timeout=5))
                self.assertEqual(caught.exception.kind, kind, (provider.kind, code))
                self.assertEqual(caught.exception.provider, provider.name)

    def test_no_key_is_an_auth_failure_and_never_a_call(self):
        for provider in self._providers():
            self._answers()
            with self.assertRaises(llm_base.LLMFailed) as caught:
                provider.with_key("").complete(llm_base.Request(prompt="hi", timeout=5))
            self.assertEqual(caught.exception.kind, failures.AUTH, provider.kind)
        self.assertEqual(self.sent, [], "nothing was sent")

    def test_the_words_three_vendors_use_for_one_kind(self):
        cases = {"insufficient_quota": failures.QUOTA,
                 "RESOURCE_EXHAUSTED": failures.QUOTA,
                 "invalid_api_key": failures.AUTH,
                 "PERMISSION_DENIED": failures.AUTH,
                 "model_not_found": failures.MODEL,
                 "The model `x` does not exist or you do not have access to it":
                     failures.MODEL,
                 "UNAVAILABLE": failures.TRANSIENT}
        for said, kind in cases.items():
            self.assertEqual(failures.classify(said), kind, said)

    def test_the_retry_policy_is_the_chain_and_not_the_provider(self):
        """A transient failure is waited out on the same model, whichever provider it was."""
        for provider in self._providers():
            self._answers(refusal(503), {"content": [{"type": "text", "text": "ok"}],
                                         "choices": [{"message": {"content": "ok"}}],
                                         "candidates": [{"content": {"parts": [{"text": "ok"}]}}]})
            backoff, llm_chain.BACKOFF = llm_chain.BACKOFF, 0
            try:
                reply = llm_chain.complete(provider, llm_base.Request(
                    prompt="hi", model="claude-opus-5", timeout=5))
            finally:
                llm_chain.BACKOFF = backoff
            self.assertEqual(reply.text, "ok", provider.kind)
            self.assertEqual(len(self.sent), 2, provider.kind)


class TestModelChainStaysWithOneProvider(unittest.TestCase):
    """Falling back from a model one provider refused to a model on another account answers
    a question nobody asked, and bills someone who did not agree to it."""

    def test_only_the_models_that_provider_reaches_are_on_the_chain(self):
        chain = llm_chain.model_chain(settings.SETTINGS.default_model, "claude-code")
        listed = {m["alias"] for m in settings.SETTINGS.models_for("claude-code")}
        self.assertTrue(chain)
        self.assertTrue(set(chain) <= listed)

    def test_the_default_is_a_fallback_only_where_it_is_the_default(self):
        """Asking a local server for the model Claude Code would have used wastes a call at
        best, and answers with the wrong model at worst."""
        mine = settings.SETTINGS.default_model
        self.assertIn(mine, llm_chain.model_chain("sonnet", "claude-code"))
        self.assertNotIn(mine, llm_chain.model_chain("gpt-5.6", "openai"))
        self.assertIn(mine, llm_chain.model_chain("sonnet"), "no provider named, no filtering")

    def test_a_model_the_list_never_heard_of_is_still_the_model_that_was_asked_for(self):
        """A local server's tag, or a model added to a provider but not to `models.list`.
        Quietly sending the default instead answers a different question than the caller
        asked, and on a different account."""
        self.assertEqual(llm_chain.model_chain("llama3.1:70b", "local"), ["llama3.1:70b"])


class TestBridge(unittest.TestCase):
    """The bridge keeps a socket, a key hunt and a budget. Everything about reaching a model
    goes through `coursekit.llm`, so there is one implementation rather than two that drift."""

    @classmethod
    def setUpClass(cls):
        import importlib.util

        path = os.path.join(os.path.dirname(PLATFORM), "tools", "bridge", "tutor-bridge.py")
        spec = importlib.util.spec_from_file_location("tutor_bridge_undertest", path)
        cls.bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.bridge)

    def test_it_reaches_a_model_only_through_the_provider_layer(self):
        source = open(os.path.join(os.path.dirname(PLATFORM), "tools", "bridge",
                                   "tutor-bridge.py"), encoding="utf-8").read()
        for gone in ("def call_api", "def call_cli", "def flatten", "def cli_argv",
                     "subprocess.run", "x-api-key"):
            self.assertNotIn(gone, source, "the bridge should not do this itself any more")

    def test_the_budget_drops_the_oldest_turns_first(self):
        older = [{"role": "user", "content": "a" * 400},
                 {"role": "assistant", "content": "b" * 400},
                 {"role": "user", "content": "the newest question"}]
        system, kept = self.bridge.trim("s" * 100, older, 600)
        self.assertEqual(kept[-1]["content"], "the newest question")
        self.assertLess(len(kept), 3)
        self.assertLessEqual(len(system) + sum(len(m["content"]) for m in kept), 700)

    def test_the_quoted_passage_is_shortened_before_the_question_is(self):
        system, kept = self.bridge.trim("s" * 8000, [{"role": "user", "content": "why?"}], 2000)
        self.assertIn("shortened to fit", system)
        self.assertEqual(kept[0]["content"], "why?")

    def test_a_route_is_chosen_by_what_is_configured(self):
        self.assertIn(self.bridge.active_mode(), ("cli", "api", "none", "echo"))
        self.assertEqual(self.bridge.cli_provider().kind, "cli")
        self.assertEqual(self.bridge.api_provider().kind, "anthropic")

    def test_a_key_is_recognised_whoever_issued_it(self):
        """The hunt looks for more than one company's key now."""
        self.assertEqual(self.bridge.KEY_NAMES[0], "ANTHROPIC_API_KEY")
        self.assertIn("OPENAI_API_KEY", self.bridge.KEY_NAMES)
        self.assertTrue("sk-ant-x".startswith(self.bridge.KEY_SHAPES))


class TestSkillStub(unittest.TestCase):
    """A skill lives in `common/skills/`, so that it belongs to the project rather than to
    whichever tool is reading it today. Every tool then has its own folder it scans, and its
    own file format, so each needs a stub - and a stub is a copy, which is the thing this
    arrangement exists to avoid. So the copies are held to what they claim."""

    ROOT = os.path.dirname(PLATFORM)
    REAL = os.path.join(ROOT, "common", "skills")

    # tool -> (path to its stub for skill <name>, does its description drive selection?)
    # Claude Code and Codex both read the description to decide whether a skill applies, so
    # theirs must match the skill's exactly. Gemini's is a one-line label in `/help`.
    STUBS = {
        "Claude Code": (os.path.join(".claude", "skills", "%s", "SKILL.md"), True),
        "Codex": (os.path.join(".codex", "skills", "%s.md"), True),
        "Gemini CLI": (os.path.join(".gemini", "commands", "%s.toml"), False),
    }

    @staticmethod
    def _description(text):
        """The description a stub declares, whichever of the three shapes it is written in."""
        found = re.search(r'^description\s*[:=]\s*"?(.+?)"?\s*$', text, re.M)
        return found.group(1) if found else ""

    def _skills(self):
        return sorted(n for n in os.listdir(self.REAL)
                      if os.path.isdir(os.path.join(self.REAL, n)))

    def test_every_tool_can_find_every_skill(self):
        """Each of these scans a folder of its own. A skill with a stub for one tool and not
        the others exists for one tool and not the others, which is what `common/` was made
        to stop."""
        self.assertTrue(self._skills(), "there is at least one skill to find")
        for name in self._skills():
            for tool, (shape, _selects) in self.STUBS.items():
                path = os.path.join(self.ROOT, shape % name)
                self.assertTrue(os.path.isfile(path),
                                "%s cannot find the %s skill: no %s" % (tool, name, path))
                text = open(path, encoding="utf-8").read()
                self.assertIn("common/skills/" + name, text,
                              "%s's stub does not say where the skill is" % tool)

    def test_a_stub_that_decides_when_to_apply_says_what_the_skill_says(self):
        """A description is what a tool reads to decide a skill applies at all. One that has
        drifted from the skill is worse than none: it offers the wrong thing confidently."""
        for name in self._skills():
            real = self._description(
                open(os.path.join(self.REAL, name, "SKILL.md"), encoding="utf-8").read())
            self.assertTrue(real, "%s has no description" % name)
            for tool, (shape, selects) in self.STUBS.items():
                if not selects:
                    continue
                stub = self._description(
                    open(os.path.join(self.ROOT, shape % name), encoding="utf-8").read())
                self.assertEqual(stub, real, "%s's stub for %s has drifted" % (tool, name))

    def test_every_index_names_every_skill(self):
        """The folders are how a tool finds a skill; these are how a person does, and how an
        agent reading the instructions rather than scanning a folder does."""
        indexes = ["common/skills/README.md", "AGENTS.md", "GEMINI.md", "CLAUDE.md"]
        for name in self._skills():
            for index in indexes:
                text = open(os.path.join(self.ROOT, index), encoding="utf-8").read()
                self.assertIn(name, text, "%s does not name the %s skill" % (index, name))

    def test_the_real_skill_names_its_references_from_the_repo_root(self):
        """A relative `references/x.md` means two different things to a tool that opened a
        stub and one that opened the skill. From the root it means one."""
        text = open(os.path.join(self.REAL, "course-author", "SKILL.md"), encoding="utf-8").read()
        self.assertNotIn("`references/", text)
        self.assertIn("`common/skills/course-author/references/", text)

    def test_the_gemini_command_is_valid_toml_that_carries_the_skill(self):
        """Its `prompt` is required, and `@{path}` injects a file - so the command carries
        the real instructions rather than a copy of them."""
        import tomllib

        for name in self._skills():
            path = os.path.join(self.ROOT, ".gemini", "commands", name + ".toml")
            with open(path, "rb") as fh:
                command = tomllib.load(fh)
            self.assertIn("prompt", command, "a Gemini command without a prompt does nothing")
            self.assertIn("@{common/skills/%s/SKILL.md}" % name, command["prompt"])


class TestCodeConventions(unittest.TestCase):
    """The rules in CONVENTIONS.md "Code conventions" that a test can hold."""

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
    # A size is a rung of the scale in 00-tokens.css, or one of the three relative sizes
    # prose sets against its own. This used to be a list of every number already written,
    # which is a ratchet and not a scale: it grew to twenty-six values.
    FONT_SIZES = {"0.87em", "1em", "1.17em", "inherit"}
    BTN_VARIANTS = {"primary", "ghost", "warm", "danger", "sm", "iconbtn", "disabled",
                    "rm", "kebab"}
    # The layout utilities a button may also wear. They place it; they are not the family.
    BTN_UTILITIES = {"gap-top", "gap-top-sm", "gap-bottom", "pushright", "grow", "hidden"}

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
        anywhere else is a second palette starting (CONVENTIONS.md "The design system")."""
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

    def test_radii_come_from_the_scale(self):
        """A corner is a rung of the radius scale in 00-tokens.css. `50%` is a circle and
        `0` is a deliberate square; everything else is a token. This was sixteen loose
        numbers, three of them a spacing token standing in for a radius
        (CONVENTIONS.md "The design system")."""
        import re
        rule = re.compile(r"border-radius:\s*([^;}\n]+)")
        offenders = []
        for path in self._css_files():
            if os.path.basename(path) == "00-tokens.css":
                continue
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    for m in rule.finditer(line):
                        for corner in m.group(1).strip().split():
                            if corner in ("0", "50%") or corner.startswith("var(--radius"):
                                continue
                            offenders.append("%s:%d %s" % (os.path.basename(path), n, corner))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_no_button_variant_outside_the_family(self):
        """`.btn` has one family. A variant defined nowhere is a button that looks like a
        mistake on one screen and nothing at all on another. The markup is read too:
        `class="btn sm kebab"` with the rule written as a bare `.kebab` used to pass."""
        import re
        found = set()
        for path in self._css_files():
            with open(path, encoding="utf-8") as fh:
                for m in re.finditer(r"\.btn((?:\.[a-z-]+)+)", fh.read()):
                    found.update(m.group(1).strip(".").split("."))
        for path in self._js_files():
            with open(path, encoding="utf-8") as fh:
                for m in re.finditer(r'class="btn ([a-z0-9 -]+)"', fh.read()):
                    found.update(m.group(1).split())
        stray = found - self.BTN_VARIANTS - self.BTN_UTILITIES
        self.assertEqual(stray, set(), "button variants with no rule: %s" % stray)

    def test_the_dark_palette_is_written_once_in_two_places(self):
        """CSS cannot share one declaration block between a media query and a selector, and
        the theme is three-state, so the dark palette is written twice. The two copies are
        one palette (CONVENTIONS.md "The design system")."""
        path = os.path.join(self.REPO, "platform/web/css/00-tokens.css")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        marks = (':root:not([data-theme="light"])', ':root[data-theme="dark"]')
        blocks = []
        for mark in marks:
            start = text.index(mark) + len(mark)
            start = text.index("{", start) + 1
            blocks.append(text[start:text.index("}", start)])
        rows = [sorted(x.strip() for x in b.strip().splitlines()) for b in blocks]
        self.assertEqual(rows[0], rows[1],
                         "the two dark blocks have drifted: %s" %
                         sorted(set(rows[0]) ^ set(rows[1])))

    def test_the_front_end_explains_itself_with_data_help_not_title(self):
        """A `title` is not a tooltip: it never shows on a touch screen, never shows on
        keyboard focus, and is announced inconsistently — which made `help()`, the one
        glossary, unreachable for most of the people it was written for. Every hint goes
        through `data-help` and the engine in 00-dom.js (CONVENTIONS.md "The design
        system"). An <iframe>'s `title` is its accessible name and is the exception."""
        import re
        offenders = []
        files = self._js_files() + [os.path.join(self.REPO, "platform/web/shell.html"),
                                    os.path.join(self.REPO, "platform/studio/ui/index.html")]
        for path in files:
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    hit = ' title="' in line or re.search(r"\w\.title\s*=", line)
                    if not hit:
                        continue
                    # <iframe title> is the frame's accessible name; document.title is the tab
                    if "iframe" in line or "live.title" in line or "document.title" in line:
                        continue
                        offenders.append("%s:%d" % (os.path.basename(path), n))
        self.assertEqual(offenders, [], "title= used instead of data-help: %s" % offenders)

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
        `--bg` used to sit at about 4.0 (CONVENTIONS.md "The design system")."""
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
    may carry one (CONVENTIONS.md "Notebooks")."""

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
    CFG.platform (CONVENTIONS.md "Notebooks")."""

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

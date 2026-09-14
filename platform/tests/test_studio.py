"""Self-tests for Course Studio.

    python platform/tests/test_studio.py

Nothing here calls Claude or opens a socket. What is tested is the part that has to be right
when a model returns something slightly wrong: JSON extraction, the coercion of model output
into shapes the validator accepts, and the job lifecycle including the approval gate.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = os.path.dirname(HERE)
sys.path.insert(0, PLATFORM)


def ui_scripts():
    """Studio's load order, read from the one place it lives: the <script> list in
    `ui/index.html`. The page's equivalent is `web/bundle.json`."""
    with open(os.path.join(PLATFORM, "studio", "ui", "index.html"), encoding="utf-8") as fh:
        return re.findall(r'<script src="/ui/js/([^"]+)"', fh.read())


from coursekit.course import config  # noqa: E402
from coursekit.errors import CourseError  # noqa: E402
from coursekit.settings import SETTINGS

# The tests describe the platform's list, not what this machine's Studio last saved over it.
SETTINGS.studio_file = ""
SETTINGS.reload()

from coursekit.llm import chain as llm_chain  # noqa: E402
from coursekit.llm import cli as llm_cli  # noqa: E402
from studio import catalog, modelcall  # noqa: E402
from studio.authoring import (coerce, curriculum, editing, figures,  # noqa: E402
                              generator, overrides, reviews)
from studio.store import jobs  # noqa: E402
from studio.support import files  # noqa: E402
from studio.support.errors import GenerationError  # noqa: E402


class TestJsonExtraction(unittest.TestCase):
    """Models wrap JSON in fences and prefaces roughly half the time."""

    def test_plain(self):
        self.assertEqual(json.loads(modelcall.slice_json('{"a": 1}')), {"a": 1})

    def test_code_fence(self):
        text = '```json\n{"a": 1}\n```'
        self.assertEqual(json.loads(modelcall.slice_json(text)), {"a": 1})

    def test_preamble_and_trailer(self):
        text = 'Sure! Here is the JSON you asked for:\n\n{"a": [1, 2]}\n\nLet me know.'
        self.assertEqual(json.loads(modelcall.slice_json(text)), {"a": [1, 2]})

    def test_array_at_top_level(self):
        self.assertEqual(json.loads(modelcall.slice_json('Here:\n[[1],[2]]')), [[1], [2]])

    def test_braces_inside_strings_do_not_confuse_it(self):
        text = 'Note:\n{"q": "what is {this} for?", "n": {"deep": "}"}}'
        parsed = json.loads(modelcall.slice_json(text))
        self.assertEqual(parsed["q"], "what is {this} for?")
        self.assertEqual(parsed["n"], {"deep": "}"})

    def test_escaped_quote_inside_string(self):
        text = r'{"q": "he said \"no\" firmly", "a": 1}'
        self.assertEqual(json.loads(modelcall.slice_json(text))["a"], 1)

    def test_strip_fence_on_markdown(self):
        self.assertEqual(modelcall.strip_fence("```markdown\n# Title\n```"), "# Title")


class TestHeadings(unittest.TestCase):
    """The count this returns is what the suggestion count must equal."""

    def test_counts_only_sections_with_content(self):
        md = ("# M01 — T\n\n**Time:** 60 minutes\n\n"
              "## One\n\ntext\n\n## Empty\n\n## Two\n\nmore text\n")
        self.assertEqual(generator.headings_of(md), ["One", "Two"])

    def test_horizontal_rules_do_not_count_as_content(self):
        md = "# M01 — T\n\n## One\n\ntext\n\n---\n\n## Hollow\n\n---\n"
        self.assertEqual(generator.headings_of(md), ["One"])

    def test_no_sections(self):
        self.assertEqual(generator.headings_of("# M01 — T\n\nprose only\n"), [])

    def test_matches_the_build_loader(self):
        """Studio must count sections exactly as the build does, or generated courses
        fail validation. They now share one implementation; this guards that."""
        from coursekit.course import loader as ck_loader
        md = ("# M01 — T\n\n**Time:** 60 minutes\n\n"
              "## A\n\nalpha\n\n---\n\n## B\n\n## C\n\ngamma\n")
        self.assertEqual(generator.headings_of(md),
                         [s.heading for s in ck_loader.parse_sections(md)])


class TestSuggestionCoercion(unittest.TestCase):
    HEADINGS = ["One", "Two", "Three"]

    def ok(self, rows):
        self.assertEqual(len(rows), len(self.HEADINGS))
        for row in rows:
            self.assertEqual(len(row), coerce.QUESTIONS_PER_SECTION)
            self.assertTrue(all(isinstance(q, str) and q for q in row))

    def test_exact_input_is_preserved(self):
        raw = [["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"]]
        rows = coerce.fix_suggestions(raw, self.HEADINGS)
        self.ok(rows)
        self.assertEqual(rows, raw)

    def test_too_few_sets_are_padded(self):
        self.ok(coerce.fix_suggestions([["a", "b", "c"]], self.HEADINGS))

    def test_too_many_sets_are_trimmed(self):
        raw = [["a", "b", "c"]] * 9
        self.ok(coerce.fix_suggestions(raw, self.HEADINGS))

    def test_ragged_rows_are_filled_and_capped(self):
        self.ok(coerce.fix_suggestions([["a"], ["b", "c", "d", "e", "f"], []], self.HEADINGS))

    def test_flat_list_is_regrouped(self):
        rows = coerce.fix_suggestions(["a", "b", "c", "d", "e", "f", "g", "h", "i"],
                                          self.HEADINGS)
        self.ok(rows)
        self.assertEqual(rows[0], ["a", "b", "c"])

    def test_garbage_still_yields_a_valid_shape(self):
        for raw in (None, {}, "nope", [None, 3, {"a": 1}]):
            self.ok(coerce.fix_suggestions(raw, self.HEADINGS))


class TestQuizItemCoercion(unittest.TestCase):
    """Every type comes out in a shape the validator accepts, or is dropped."""

    def ok(self, item):
        from coursekit.course import validate as ck_validate
        out = coerce.fix_quiz_item(item)
        self.assertIsNotNone(out, item)
        self.assertEqual(ck_validate.quiz_item_problems(out, "q"), [], out)
        return out

    def test_every_type_repairs_to_something_valid(self):
        self.assertEqual(self.ok({"q": "a", "options": ["x", "y"], "answer": "7", "why": "w"})["answer"], 1)
        self.assertEqual(self.ok({"type": "multi", "q": "b", "options": ["x", "y", "z"], "answer": [2, "0", 9], "why": "w"})["answer"], [0, 2])
        self.assertIs(self.ok({"type": "tf", "q": "c", "answer": "True", "why": "w"})["answer"], True)
        out = self.ok({"type": "numeric", "q": "d", "answer": "12.5", "tolerance": -1, "unit": "%", "why": "w"})
        self.assertEqual((out["answer"], out["tolerance"], out["unit"]), (12.5, 1, "%"))
        self.assertEqual(self.ok({"type": "order", "q": "e", "options": ["1", "2", "3"], "why": "w"})["options"], ["1", "2", "3"])
        self.assertEqual(self.ok({"type": "match", "q": "f", "pairs": [["a", "b"], {"left": "c", "right": "d"}], "why": "w"})["pairs"], [["a", "b"], ["c", "d"]])
        out = self.ok({"type": "cloze", "q": "the [blank] is", "answer": "x", "why": "w"})
        self.assertEqual((out["q"], out["answer"]), ("the ___ is", ["x"]))
        self.assertEqual(self.ok({"type": "short", "q": "g", "answer": "m", "why": "w"})["model"], "m")

    def test_unknown_type_falls_back_to_single_and_hopeless_items_are_dropped(self):
        self.assertEqual(self.ok({"type": "bogus", "q": "h", "options": ["1", "2"], "answer": 1, "why": "w"})["type"], "single")
        self.assertIsNone(coerce.fix_quiz_item({"type": "numeric", "q": "d", "answer": "lots", "why": "w"}))
        self.assertIsNone(coerce.fix_quiz_item({"type": "cloze", "q": "no blank", "answer": "x", "why": "w"}))
        self.assertIsNone(coerce.fix_quiz_item({"type": "match", "q": "f", "pairs": [["a", "b"]], "why": "w"}))
        self.assertIsNone(coerce.fix_quiz_item({"q": "h", "options": ["only"], "answer": 0, "why": "w"}))

    def test_feedback_only_kept_when_it_lines_up(self):
        keep = self.ok({"q": "a", "options": ["x", "y"], "answer": 0, "feedback": ["no", "yes"], "hints": ["h", "", "i"], "why": "w"})
        self.assertEqual((keep["feedback"], keep["hints"]), (["no", "yes"], ["h", "i"]))
        drop = self.ok({"q": "a", "options": ["x", "y"], "answer": 0, "feedback": ["only one"], "why": "w"})
        self.assertNotIn("feedback", drop)

    def test_roleplay_is_kept_when_whole_and_dropped_when_not(self):
        base = {"predict": "p", "quiz": [{"q": "a", "options": ["x", "y"], "answer": 0, "why": "w"}],
                "cards": [{"front": "f", "back": "b"}], "elaborate": [], "transfer": {}}
        whole = coerce.fix_assessment(dict(base, roleplay={"persona": "You are", "situation": "s", "goal": "g", "rubric": "one"}), "M01")
        self.assertEqual(whole["roleplay"]["rubric"], ["one"])
        partial = coerce.fix_assessment(dict(base, roleplay={"persona": "You are"}), "M01")
        self.assertNotIn("roleplay", partial)


class TestAssessmentCoercion(unittest.TestCase):
    def base(self, **over):
        row = {
            "predict": "Guess.",
            "quiz": [{"q": "Which?", "options": ["a", "b", "c", "d"], "answer": 1, "why": "Because b."}],
            "cards": [{"front": "Q", "back": "A"}],
            "elaborate": ["Explain it."],
            "transfer": {"scenario": "S", "prompt": "P", "model": "M"},
        }
        row.update(over)
        return row

    def test_clean_input(self):
        out = coerce.fix_assessment(self.base(), "M01")
        self.assertEqual(out["id"], "M01")
        self.assertEqual(out["quiz"][0]["answer"], 1)

    def test_out_of_range_answer_is_clamped(self):
        for bad, expected in ((9, 3), (-4, 0), ("2", 2), (None, 0)):
            quiz = [{"q": "Q", "options": ["a", "b", "c", "d"], "answer": bad, "why": "w"}]
            out = coerce.fix_assessment(self.base(quiz=quiz), "M01")
            self.assertEqual(out["quiz"][0]["answer"], expected, "answer=%r" % bad)

    def test_missing_why_is_filled(self):
        quiz = [{"q": "Q", "options": ["a", "b"], "answer": 0}]
        out = coerce.fix_assessment(self.base(quiz=quiz), "M01")
        self.assertTrue(out["quiz"][0]["why"])

    def test_quiz_is_capped(self):
        quiz = [{"q": "Q", "options": ["a", "b"], "answer": 0, "why": "w"}] * 40
        out = coerce.fix_assessment(self.base(quiz=quiz), "M01")
        self.assertEqual(len(out["quiz"]), coerce.QUIZ_ITEMS)

    def test_half_written_cards_are_dropped(self):
        cards = [{"front": "Q", "back": ""}, {"front": "", "back": "A"}, {"front": "Q2", "back": "A2"}]
        out = coerce.fix_assessment(self.base(cards=cards), "M01")
        self.assertEqual(out["cards"], [{"front": "Q2", "back": "A2"}])

    def test_unusable_input_raises_rather_than_shipping_empty(self):
        with self.assertRaises(GenerationError):
            coerce.fix_assessment(self.base(quiz=[]), "M01")
        with self.assertRaises(GenerationError):
            coerce.fix_assessment(self.base(cards=[]), "M01")
        with self.assertRaises(GenerationError):
            coerce.fix_assessment("not an object", "M01")

    def test_output_passes_the_real_validator(self):
        from coursekit.course import validate as ck_validate
        class FakeModule:
            id, source = "M01", "x.md"
            sections = [1, 2]

        assess = {"M01": coerce.fix_assessment(self.base(), "M01")}
        sugg = {"M01": [["a", "b", "c"], ["d", "e", "f"]]}
        self.assertEqual(ck_validate.check([FakeModule()], assess, sugg), [])


class TestPlanNormalisation(unittest.TestCase):
    BRIEF = {"theme": "bread", "hours": 6, "practitioner": "baker"}

    def plan(self, **over):
        base = {
            "title": "Bread",
            "parts": [{"id": "p1", "name": "Basics", "hours": 3, "dir": "01-basics"},
                      {"id": "p2", "name": "More", "hours": 3, "dir": "02-more"}],
            "modules": [{"id": "M01", "part": "p1", "title": "Flour", "minutes": 60},
                        {"id": "M02", "part": "p2", "title": "Water", "minutes": 60}],
        }
        base.update(over)
        return base

    def test_fills_defaults(self):
        out = curriculum.normalise_plan(self.plan(), "bread", 6, self.BRIEF)
        self.assertEqual(out["subject"], "bread")
        self.assertEqual(out["practitioner"], "baker")
        self.assertTrue(out["tutorPersona"].endswith("."))
        self.assertEqual(len(out["modules"][0]["sections"]), 7)

    def test_requires_only_points_backwards_at_real_modules(self):
        plan = {"parts": [{"id": "p1", "name": "P", "dir": "d"}],
                "modules": [{"id": "M01", "part": "p1", "title": "A", "requires": ["M2"]},
                            {"id": "M02", "part": "p1", "title": "B", "requires": ["M1", "m01", "M09", "M02"]},
                            {"id": "M03", "part": "p1", "title": "C"}]}
        out = curriculum.normalise_plan(plan, "x", 3, {})
        self.assertEqual([m["requires"] for m in out["modules"]], [[], ["M01"], []])

    def test_module_ids_are_renumbered_sequentially(self):
        modules = [{"id": "M05", "part": "p1", "title": "A"},
                   {"id": "M05", "part": "p2", "title": "B"},
                   {"id": "zzz", "part": "p1", "title": "C"}]
        out = curriculum.normalise_plan(self.plan(modules=modules), "bread", 6, self.BRIEF)
        self.assertEqual([m["id"] for m in out["modules"]], ["M01", "M02", "M03"])

    def test_unknown_part_reference_is_reassigned(self):
        modules = [{"id": "M01", "part": "nonsense", "title": "A"}]
        out = curriculum.normalise_plan(self.plan(modules=modules), "bread", 6, self.BRIEF)
        self.assertIn(out["modules"][0]["part"], ("p1", "p2"))

    def test_duplicate_directories_are_made_unique(self):
        parts = [{"id": "p1", "name": "A", "hours": 3, "dir": "same"},
                 {"id": "p2", "name": "B", "hours": 3, "dir": "same"}]
        out = curriculum.normalise_plan(self.plan(parts=parts), "bread", 6, self.BRIEF)
        self.assertNotEqual(out["parts"][0]["dir"], out["parts"][1]["dir"])

    def test_bad_minutes_fall_back(self):
        modules = [{"id": "M01", "part": "p1", "title": "A", "minutes": "ninety"}]
        out = curriculum.normalise_plan(self.plan(modules=modules), "bread", 6, self.BRIEF)
        self.assertEqual(out["modules"][0]["minutes"], 60)

    def test_empty_plan_is_rejected(self):
        for bad in ({"parts": [], "modules": []}, {"parts": [{"id": "p1", "name": "A", "dir": "d"}]}, "nope"):
            with self.assertRaises(GenerationError):
                curriculum.normalise_plan(bad, "bread", 6, self.BRIEF)

    def test_manifest_is_loadable_by_the_build(self):
        import tempfile
        from coursekit.course import config as ck_config
        plan = curriculum.normalise_plan(self.plan(), "bread", 6, self.BRIEF)
        manifest = curriculum.plan_to_manifest(plan, "bread")
        tmp = tempfile.mkdtemp(prefix="studio-test-")
        with open(os.path.join(tmp, "course.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        cfg = ck_config.load(tmp)
        self.assertEqual(cfg.id, "bread")
        self.assertEqual(len(cfg.parts), 2)
        self.assertEqual(cfg.runtime()["storageKey"], "course_bread_v1")


class TestPlanPromptPreview(unittest.TestCase):
    """The approval gate shows every prompt a module will be written from. Each has to be the
    prompt the run sends, which is why one builder per stage assembles both."""

    class Reply:
        """Just enough Handler for one route method."""

        def __init__(self, body):
            self.body, self.sent, self.code = body, None, 200

        def _body(self):
            return self.body

        def _fail(self, message, code=400, **extra):
            self.sent, self.code = dict(extra, error=message), code

        def _json(self, obj, code=200):
            self.sent, self.code = obj, code

    PLAN = {"title": "Bread", "subject": "bread", "hours": 6, "audience": "a beginner",
            "practitioner": "baker",
            "parts": [{"id": "p1", "name": "Basics", "hours": 6, "dir": "01-basics"}],
            "modules": [{"id": "M01", "part": "p1", "title": "Flour", "minutes": 45,
                         "summary": "What flour is.", "sections": ["Why this matters", "Close"]},
                        {"id": "M02", "part": "p1", "title": "Water", "minutes": 60}]}

    def _prompt(self, body):
        from studio import server
        reply = self.Reply(body)
        server.Handler.plan_prompt(reply)
        return reply

    def _stage(self, reply, stage):
        return next(row for row in reply.sent["stages"] if row["stage"] == stage)

    def test_the_preview_is_what_the_writer_would_send(self):
        reply = self._prompt({"plan": self.PLAN, "mid": "M01"})
        self.assertEqual(reply.code, 200)
        expected = generator.module_prompt(curriculum.plan_for_prompt(self.PLAN),
                                           self.PLAN["modules"][0])
        text = self._stage(reply, "module")["prompt"]
        self.assertEqual(text, expected)
        self.assertIn("## Why this matters", text)
        self.assertIn("What flour is.", text)
        self.assertIn("45 minutes", text)

    def test_every_per_module_call_is_offered(self):
        stages = [row["stage"] for row in self._prompt({"plan": self.PLAN, "mid": "M01"}).sent["stages"]]
        self.assertEqual(stages, ["module", "figures", "assessment", "suggestions", "review"])
        with_notebooks = dict(self.PLAN, notebooks={"kernel": "python3", "packages": []})
        stages = [row["stage"] for row in self._prompt({"plan": with_notebooks, "mid": "M01"}).sent["stages"]]
        self.assertIn("notebooks", stages)

    def test_what_is_only_known_at_the_call_is_shown_as_a_token(self):
        reply = self._prompt({"plan": self.PLAN, "mid": "M01"})
        for stage in ("assessment", "suggestions", "figures", "review"):
            self.assertIn(overrides.BODY, self._stage(reply, stage)["prompt"], stage)
        self.assertIn(overrides.STUDY, self._stage(reply, "review")["prompt"])

    def test_a_prompt_edited_at_the_gate_is_the_one_shown(self):
        plan = dict(self.PLAN, prompts={"M01": {"assessment": "Six items about %s." % overrides.BODY}})
        row = self._stage(self._prompt({"plan": plan, "mid": "M01"}), "assessment")
        self.assertTrue(row["overridden"])
        self.assertEqual(row["prompt"], "Six items about {{module_text}}.")
        self.assertIn("Return ONLY", row["default"])

    def test_a_half_edited_plan_still_previews(self):
        plan = json.loads(json.dumps(self.PLAN))
        plan["modules"][1].update(title="", minutes="soon")
        del plan["audience"]
        reply = self._prompt({"plan": plan, "mid": "M02"})
        self.assertEqual(reply.code, 200)
        self.assertIn("60 minutes", self._stage(reply, "module")["prompt"])

    def test_a_module_with_no_sections_gets_the_standard_ones(self):
        reply = self._prompt({"plan": self.PLAN, "mid": "M02"})
        for heading in curriculum.DEFAULT_SECTIONS:
            self.assertIn("## " + heading, self._stage(reply, "module")["prompt"])

    def test_an_unknown_module_and_a_missing_plan_are_refused(self):
        self.assertEqual(self._prompt({"plan": self.PLAN, "mid": "M09"}).code, 404)
        self.assertEqual(self._prompt({"mid": "M01"}).code, 400)


class TestPromptOverrides(unittest.TestCase):
    """A course carries its own prompts in plan/prompts.json, and every per-module call
    honours them: the run sends what the course says, with the tokens filled in."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="studio-overrides-")
        self.plan = {"title": "Bread", "subject": "bread", "hours": 6,
                     "audience": "a beginner", "practitioner": "baker",
                     "parts": [{"id": "p1", "name": "Basics", "hours": 6, "dir": "01"}],
                     "modules": [{"id": "M01", "part": "p1", "title": "Flour", "minutes": 45,
                                  "sections": ["Why this matters", "Exercise"]}]}
        self.mod = self.plan["modules"][0]

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_an_override_is_sent_with_the_tokens_filled_in(self):
        overrides.put(self.root, "M01", "assessment",
                      "Six items, all numeric.\n%s\nEnd." % overrides.BODY)
        sent = generator.assessment_prompt(self.plan, self.mod, "THE BODY", self.root)
        self.assertEqual(sent, "Six items, all numeric.\nTHE BODY\nEnd.")

    def test_without_an_override_the_platforms_prompt_is_sent(self):
        sent = generator.assessment_prompt(self.plan, self.mod, "THE BODY", self.root)
        self.assertIn("Return ONLY", sent)
        self.assertIn("THE BODY", sent)

    def test_the_review_stage_gets_its_quiz(self):
        overrides.put(self.root, "M01", "review",
                      "Judge:%s\nQuiz:%s" % (overrides.BODY, overrides.STUDY))
        sent = reviews.review_prompt(self.plan, self.mod, "TEXT",
                                     {"quiz": [{"type": "tf", "q": "Is it?"}]}, self.root)
        self.assertEqual(sent, "Judge:TEXT\nQuiz:  - [tf] Is it?")

    def test_empty_text_takes_the_override_away(self):
        overrides.put(self.root, "M01", "module", "Write it my way.")
        self.assertEqual(overrides.overridden(self.root, "M01"), ["module"])
        overrides.put(self.root, "M01", "module", "  ")
        self.assertEqual(overrides.overridden(self.root, "M01"), [])
        self.assertIn("Hard requirements", generator.module_prompt(self.plan, self.mod, root=self.root))

    def test_an_unknown_stage_is_refused_and_junk_on_disk_is_ignored(self):
        with self.assertRaises(ValueError):
            overrides.put(self.root, "M01", "glossary", "no such stage")
        os.makedirs(os.path.join(self.root, "plan"), exist_ok=True)
        with open(os.path.join(self.root, overrides.FILE), "w", encoding="utf-8") as fh:
            json.dump({"M01": {"module": "keep", "nonsense": "drop", "review": 7},
                       "not-a-module": {"module": "drop"}}, fh)
        self.assertEqual(overrides.load(self.root), {"M01": {"module": "keep"}})

    def test_an_override_does_not_make_the_course_look_out_of_date(self):
        """A prompt changes what the next run writes, never the page a reader is reading,
        so plan/prompts.json must not turn Rebuild into the thing to do."""
        from studio import catalog
        os.makedirs(os.path.join(self.root, "modules"), exist_ok=True)
        module = os.path.join(self.root, "modules", "M01-flour.md")
        with open(module, "w", encoding="utf-8") as fh:
            fh.write("# M01\n")
        before = catalog.newest_source(self.root)
        os.utime(module, (1, 1))
        overrides.put(self.root, "M01", "module", "Write it my way.")
        after = catalog.newest_source(self.root)
        self.assertEqual(after, os.path.getmtime(module))
        self.assertNotEqual(before, 0)

    def test_the_gates_overrides_are_saved_into_the_course(self):
        overrides.merge(self.root, {"M01": {"figures": "Draw one 2x2."}, "M02": {"module": ""}})
        self.assertEqual(overrides.load(self.root), {"M01": {"figures": "Draw one 2x2."}})
        overrides.forget(self.root, "M01")
        self.assertEqual(overrides.load(self.root), {})


class TestJobs(unittest.TestCase):
    def test_runs_and_records(self):
        job = jobs.Job("t").start(lambda j: (j.log("hello"), "result")[1])
        self._settle(job)
        self.assertEqual(job.status, jobs.DONE)
        self.assertEqual(job.result, "result")
        self.assertIn("hello", [e.get("message") for e in job.events])

    def test_failure_is_captured_not_raised(self):
        def boom(_):
            raise ValueError("nope")
        job = jobs.Job("t").start(boom)
        self._settle(job)
        self.assertEqual(job.status, jobs.FAILED)
        self.assertEqual(job.error, "nope")

    def test_cancellation(self):
        def spin(j):
            for _ in range(400):
                j.check_cancelled()
                time.sleep(0.01)
        job = jobs.Job("t").start(spin)
        time.sleep(0.1)
        job.cancel()
        self._settle(job)
        self.assertEqual(job.status, jobs.CANCELLED)

    def test_approval_gate_round_trip(self):
        job = jobs.Job("t").start(lambda j: j.await_input("approve", {"n": 1}))
        self._wait(lambda: job.status == jobs.WAITING)
        self.assertTrue(job.provide({"ok": True}))
        self._settle(job)
        self.assertEqual(job.result, {"ok": True})

    def test_cancel_while_parked_at_the_gate(self):
        job = jobs.Job("t").start(lambda j: j.await_input("approve", {}))
        self._wait(lambda: job.status == jobs.WAITING)
        job.cancel()
        self._settle(job)
        self.assertEqual(job.status, jobs.CANCELLED)

    def test_answering_a_job_that_is_not_waiting_is_refused(self):
        job = jobs.Job("t").start(lambda j: "done")
        self._settle(job)
        self.assertFalse(job.provide({"x": 1}))

    def test_replay_from_an_index(self):
        job = jobs.Job("t").start(lambda j: [j.log("m%d" % i) for i in range(5)])
        self._settle(job)
        tail = job.since(3)
        self.assertTrue(all(e["i"] >= 3 for e in tail))
        self.assertEqual([e["i"] for e in tail], list(range(3, len(job.events))))

    def test_registry_tracks_active_jobs_by_course(self):
        reg = jobs.Registry()
        job = reg.add(jobs.Job("generate", {"course": "abc"}))
        job.start(lambda j: j.await_input("x", {}))
        self._wait(lambda: job.status == jobs.WAITING)
        self.assertIs(reg.active_for("abc"), job)
        self.assertIsNone(reg.active_for("other"))
        job.cancel()
        self._settle(job)
        self.assertIsNone(reg.active_for("abc"))

    def test_the_running_job_is_visible_from_its_own_thread_only(self):
        seen = []
        job = jobs.Job("t").start(lambda j: seen.append(jobs.current() is j))
        self._settle(job)
        self.assertEqual(seen, [True])
        self.assertIsNone(jobs.current())

    def test_summary_carries_the_current_step_and_the_call_in_flight(self):
        """The listing shows where a job is without replaying its log."""
        def work(j):
            j.progress(2, 5, "Writing M02")
            j.emit("call", phase="start", what="the text of M02")
            j.await_input("hold", {})
        job = jobs.Job("t").start(work)
        self._wait(lambda: job.status == jobs.WAITING)
        s = job.summary()
        self.assertEqual((s["progress"]["done"], s["progress"]["label"]), (2, "Writing M02"))
        self.assertEqual(s["call"]["what"], "the text of M02")
        self.assertIsNotNone(s["started"])
        json.dumps(s)                      # it travels in /api/state
        job.provide(None)
        self._settle(job)
        self.assertIsNone(job.summary()["call"])

    # helpers
    def _wait(self, cond, timeout=5):
        end = time.time() + timeout
        while time.time() < end and not cond():
            time.sleep(0.01)
        self.assertTrue(cond(), "condition not reached in %ss" % timeout)

    def _settle(self, job, timeout=10):
        self._wait(lambda: job.finished, timeout)


class TestCallEvents(unittest.TestCase):
    """The provider layer reports every call to the job on its thread, so the screen watching
    the job can say what the model is doing while a call runs for minutes."""

    def _run(self, fn):
        job = jobs.Job("t").start(fn)
        end = time.time() + 10
        while time.time() < end and not job.finished:
            time.sleep(0.01)
        self.assertTrue(job.finished)
        return job

    def _with_cli(self, run, fn):
        original = (llm_cli.find_cli, modelcall.subprocess.run)
        llm_cli.find_cli, modelcall.subprocess.run = (lambda *a: "claude"), run
        try:
            return self._run(fn)
        finally:
            llm_cli.find_cli, modelcall.subprocess.run = original

    def test_call_start_and_end_are_emitted_with_what_and_model(self):
        import subprocess
        ok = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, stdout="hello", stderr="")
        job = self._with_cli(ok, lambda j: modelcall.ask("hi", what="the text of M01"))
        self.assertEqual(job.result, "hello")
        calls = [e for e in job.events if e["kind"] == "call"]
        self.assertEqual([c["phase"] for c in calls], ["start", "end"])
        self.assertEqual(calls[0]["what"], "the text of M01")
        self.assertEqual(calls[0]["chars"], 2)
        self.assertIn("model", calls[0])
        self.assertTrue(calls[1]["ok"])
        self.assertEqual(calls[1]["reply"], 5)
        self.assertIsNone(job.summary()["call"])       # nothing in flight once it is over

    def test_a_refused_model_is_reported_and_the_next_one_tried(self):
        import subprocess
        seen = []
        def run(argv, **kw):
            seen.append(argv)
            if len(seen) == 1:
                return subprocess.CompletedProcess(argv, 1, stdout="", stderr="unrecognized_model")
            return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")
        job = self._with_cli(run, lambda j: modelcall.ask("hi", what="x"))
        self.assertEqual(job.result, "ok")
        ends = [e for e in job.events if e["kind"] == "call" and e["phase"] == "end"]
        self.assertEqual([e["ok"] for e in ends], [False, True])
        self.assertIn("unrecognized_model", ends[0]["error"])
        self.assertTrue(any("trying" in e.get("message", "") for e in job.events if e["kind"] == "log"))

    def test_a_json_retry_is_narrated(self):
        replies = iter(["not json at all", '{"a": 1}'])
        original = modelcall.ask
        modelcall.ask = lambda prompt, **kw: next(replies)
        try:
            job = self._run(lambda j: modelcall.ask_json("q", what="the curriculum"))
        finally:
            modelcall.ask = original
        self.assertEqual(job.result, {"a": 1})
        messages = [e["message"] for e in job.events if e["kind"] == "log"]
        self.assertTrue(any("not valid JSON" in m and "the curriculum" in m for m in messages))

    def test_reporting_without_a_job_is_a_no_op(self):
        """The tutor route calls ask() on a request thread, where there is no job."""
        self.assertIsNone(jobs.current())
        llm_chain.REPORTER.event("call", phase="start")
        llm_chain.REPORTER.say("nothing listens")


class TestFailureHandling(unittest.TestCase):
    """What `ask` does when Claude says no. The kind decides: weather is waited out, a model
    that was refused is swapped, and an exhausted account ends the run at once - trying the
    next model there wastes a minute and then blames the wrong thing."""

    def setUp(self):
        self.backoff = llm_chain.BACKOFF
        llm_chain.BACKOFF = 0          # the waiting is the point, not the wall clock

    def tearDown(self):
        llm_chain.BACKOFF = self.backoff

    def _with_cli(self, run, fn):
        original = (llm_cli.find_cli, modelcall.subprocess.run)
        llm_cli.find_cli, modelcall.subprocess.run = (lambda *a: "claude"), run
        try:
            job = jobs.Job("t").start(fn)
            end = time.time() + 10
            while time.time() < end and not job.finished:
                time.sleep(0.01)
            self.assertTrue(job.finished)
            return job
        finally:
            llm_cli.find_cli, modelcall.subprocess.run = original

    @staticmethod
    def _says(stderr, code=1):
        import subprocess
        return lambda argv, **kw: subprocess.CompletedProcess(argv, code, stdout="", stderr=stderr)

    def test_an_exhausted_account_stops_the_chain_at_the_first_model(self):
        seen = []
        refuse = self._says("Claude usage limit reached. Your limit will reset at 3pm.")
        def run(argv, **kw):
            seen.append(argv)
            return refuse(argv)
        job = self._with_cli(run, lambda j: modelcall.ask("hi", what="x"))
        self.assertEqual(len(seen), 1, "every model draws on the same account")
        self.assertEqual(job.status, jobs.FAILED)
        self.assertEqual(job.why, "quota")
        self.assertIn("3pm", job.error)
        self.assertNotIn("stderr", job.error)
        self.assertEqual(job.summary()["why"], "quota")

    def test_weather_is_waited_out_on_the_same_model(self):
        seen = []
        import subprocess
        def run(argv, **kw):
            seen.append(argv)
            if len(seen) == 1:
                return subprocess.CompletedProcess(argv, 1, stdout="", stderr="529 overloaded_error")
            return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")
        job = self._with_cli(run, lambda j: modelcall.ask("hi", what="x"))
        self.assertEqual(job.result, "ok")
        self.assertEqual(seen[0], seen[1], "the same model, not the next one on the chain")
        said = [e["message"] for e in job.events if e["kind"] == "log"]
        self.assertTrue(any("trying again" in m for m in said), said)

    def test_weather_that_never_clears_gives_up_after_the_settings_say_so(self):
        seen = []
        refuse = self._says("529 overloaded_error")
        def run(argv, **kw):
            seen.append(argv)
            return refuse(argv)
        job = self._with_cli(run, lambda j: modelcall.ask("hi", what="x"))
        self.assertEqual(job.status, jobs.FAILED)
        self.assertEqual(job.why, "transient")
        # every model on the chain, each tried claude.retries + 1 times
        self.assertEqual(len(seen), len(set(map(tuple, seen))) * (llm_chain.RETRIES + 1))

    def test_a_timeout_is_not_paid_for_twice(self):
        """A call that already spent its whole timeout is not worth another model's."""
        seen = []
        def run(argv, **kw):
            seen.append(argv)
            raise modelcall.subprocess.TimeoutExpired(argv, 1)
        job = self._with_cli(run, lambda j: modelcall.ask("hi", timeout=1, what="x"))
        self.assertEqual(len(seen), 1)
        self.assertEqual(job.why, "timeout")

    def test_the_call_event_carries_the_kind(self):
        job = self._with_cli(self._says("Claude usage limit reached."),
                             lambda j: modelcall.ask("hi", what="x"))
        ends = [e for e in job.events if e["kind"] == "call" and e["phase"] == "end"]
        self.assertEqual(ends[0]["why"], "quota")

    def test_the_probe_does_not_blame_a_model_for_the_account(self):
        """The settings page asks about one model; an out-of-quota account would refuse
        every id on the list, and calling that a bad model sends the reader off editing
        something that was never wrong."""
        original = (llm_cli.find_cli, modelcall.subprocess.run)
        llm_cli.find_cli = lambda *a: "claude"
        modelcall.subprocess.run = self._says("Claude usage limit reached, resets at 3pm.")
        try:
            result = modelcall.probe("claude-x", timeout=1)
        finally:
            llm_cli.find_cli, modelcall.subprocess.run = original
        self.assertFalse(result["ok"])
        self.assertEqual(result["why"], "quota")
        self.assertIn("3pm", result["advice"])
        self.assertIn("usage limit", result["error"])     # the CLI's own words are kept


class TestTutorRouteReportsWhy(unittest.TestCase):
    """`/api/ask` sends the kind with the error, because the page decides from it whether to
    offer Try again or send the reader to Settings."""

    class Reply:
        """Just enough Handler for one route method."""

        def __init__(self, body):
            self.body, self.sent, self.code = body, None, 200

        def _body(self):
            return self.body

        def _fail(self, message, code=400, **extra):
            self.sent, self.code = dict(extra, error=message), code

        def _json(self, obj, code=200):
            self.sent, self.code = obj, code

        def _model(self, brief):
            return ""

    def _ask(self, raises=None, text="hello"):
        from studio import server
        original = (modelcall.available, modelcall.ask)
        modelcall.available = lambda: True
        def fake(prompt, **kw):
            if raises:
                raise raises
            return text
        modelcall.ask = fake
        reply = self.Reply({"messages": [{"role": "user", "content": "hi"}]})
        try:
            server.Handler.ask(reply)
        finally:
            modelcall.available, modelcall.ask = original
        return reply

    def test_a_good_answer_is_unchanged(self):
        reply = self._ask()
        self.assertEqual(reply.code, 200)
        self.assertEqual(reply.sent["text"], "hello")

    def test_an_exhausted_account_is_named_as_one(self):
        failed = modelcall.LLMFailed("out until 3pm.", kind="quota", detail="usage limit",
                                         resets_at="3pm")
        reply = self._ask(raises=failed)
        self.assertEqual(reply.code, 502)
        self.assertEqual(reply.sent["why"], "quota")
        self.assertEqual(reply.sent["resetsAt"], "3pm")
        self.assertEqual(reply.sent["error"], "out until 3pm.")


class TestPrompts(unittest.TestCase):
    """Prompts are content, but a few properties are load-bearing."""

    CFG = {"title": "T", "subject": "bread", "hours": 6, "audience": "a beginner",
           "practitioner": "baker"}
    MODS = [{"id": "M01", "part": "p1", "title": "Flour", "minutes": 60,
             "sections": ["Why this matters", "Core concepts"], "summary": "s"}]

    def test_module_prompt_names_the_exact_headings(self):
        from studio.authoring import prompts
        text = prompts.module(self.CFG, self.MODS, self.MODS[0])
        self.assertIn("## Why this matters", text)
        self.assertIn("# M01 — Flour", text)
        self.assertIn("**Time:**", text)

    def test_suggestion_prompt_states_the_required_count(self):
        from studio.authoring import prompts
        text = prompts.suggestions(self.CFG, "M01", ["A", "B", "C", "D"], "body")
        self.assertIn("exactly 4 arrays", text)
        self.assertIn("4 sections", text)

    def test_resources_prompt_forbids_inventing_sources(self):
        from studio.authoring import prompts
        self.assertIn("Never fabricate", prompts.resources(self.CFG))

    def test_direction_is_empty_without_notes_and_quoted_with(self):
        from studio.authoring import prompts
        self.assertEqual(prompts.direction(""), "")
        self.assertEqual(prompts.direction("   "), "")
        self.assertIn("go deeper on X", prompts.direction("go deeper on X"))

    def test_module_spec_prompt_names_topic_and_part(self):
        from studio.authoring import prompts
        text = prompts.module_spec(self.CFG, self.MODS, "reading a failed loaf", "Judgement", 45)
        self.assertIn("reading a failed loaf", text)
        self.assertIn('"Judgement"', text)
        self.assertIn("M01", text)


class TestChatPrompt(unittest.TestCase):
    """The tutor over the CLI: one flat transcript, ending in an open Assistant turn."""

    def test_shape(self):
        text = modelcall.chat_prompt("Be brief.", [
            {"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "why?"}])
        self.assertTrue(text.startswith("Be brief."))
        self.assertIn("User: hi", text)
        self.assertIn("Assistant: hello", text)
        self.assertTrue(text.endswith("User: why?\n\nAssistant:"))

    def test_only_the_last_twenty_turns_travel(self):
        msgs = [{"role": "user", "content": "m%d" % i} for i in range(40)]
        text = modelcall.chat_prompt("", msgs)
        self.assertNotIn("User: m0\n", text)
        self.assertIn("User: m39", text)


class TestProgressStore(unittest.TestCase):
    """The platform-side copy of a reader's progress."""

    def setUp(self):
        import shutil
        import tempfile
        from studio.store import progress
        self.tmp = tempfile.mkdtemp(prefix="studio-progress-")
        self.store = progress.Store(os.path.join(self.tmp, "nested", "progress"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_round_trip_and_atomic_write(self):
        record = self.store.save("bread", {"progress": {"M01": {"done": True}}, "updatedAt": 7})
        self.assertEqual(record["updatedAt"], 7)
        self.assertEqual(self.store.load("bread")["state"]["progress"]["M01"]["done"], True)
        self.assertEqual([f for f in os.listdir(self.store.directory) if f.startswith(".")], [],
                         "no temp file left behind")

    def test_device_settings_never_reach_disk(self):
        self.store.save("bread", {"bridge": {"key": "sk-ant-x"}, "theme": "dark",
                                  "ui": {"rail": False}, "usage": {"calls": 3},
                                  "notes": {"M01": "n"}})
        state = self.store.load("bread")["state"]
        self.assertNotIn("bridge", state)
        self.assertNotIn("theme", state)
        self.assertNotIn("ui", state)
        self.assertNotIn("usage", state, "what a key spent belongs to the browser it is in")
        self.assertEqual(state["notes"], {"M01": "n"})

    def test_bad_ids_and_bad_bodies_are_refused(self):
        with self.assertRaises(ValueError):
            self.store.save("../etc", {})
        with self.assertRaises(ValueError):
            self.store.save("bread", ["not", "an", "object"])

    def test_missing_or_corrupt_file_reads_as_none(self):
        self.assertIsNone(self.store.load("bread"))
        os.makedirs(self.store.directory, exist_ok=True)
        with open(self.store.path("bread"), "w") as fh:
            fh.write("{broken")
        self.assertIsNone(self.store.load("bread"))

    def test_summary_counts_and_next_module(self):
        from studio.store import progress
        ids = ["M01", "M02", "M03"]
        empty = self.store.summary("bread", ids)
        self.assertEqual((empty["done"], empty["next"], empty["pct"]), (0, "M01", 0.0))
        self.store.save("bread", {"progress": {
            "M01": {"done": True, "time": 610},
            "M03": {"done": False, "secs": {"0": True}, "time": 30},
        }, "cards": {"a": {"due": 0}, "b": {"due": 10 ** 9}}})
        s = self.store.summary("bread", ids)
        self.assertEqual(s["done"], 1)
        self.assertEqual(s["started"], 1)
        self.assertEqual(s["next"], "M03", "continue at the module already begun")
        self.assertEqual(s["minutes"], 10)
        self.assertEqual((s["cards"], s["due"]), (2, 1))
        self.assertAlmostEqual(s["pct"], 1 / 3)
        # Garbage entries are ignored rather than fatal.
        self.assertEqual(progress.summarise({"progress": {"M01": "junk"}, "cards": "junk"}, ids)["done"], 0)

    def test_delete(self):
        self.store.save("bread", {"a": 1})
        self.assertTrue(self.store.delete("bread"))
        self.assertFalse(self.store.delete("bread"))


class TestModelChoice(unittest.TestCase):
    """Every CLI call names a model; the chain says which ones, in order."""

    def test_requested_then_default(self):
        from coursekit.settings import SETTINGS
        default = modelcall.default_model()
        other = next(m["id"] for m in SETTINGS.models if m.get("alias") != default)
        alias = modelcall.model_aliases()[other]
        self.assertEqual(modelcall.model_chain(other), [alias, default])
        self.assertEqual(modelcall.model_chain(""), [default])
        self.assertEqual(modelcall.model_chain("nonsense"), [default])
        self.assertEqual(modelcall.model_chain(default), [default])

    def test_models_come_from_platform_settings(self):
        from coursekit.settings import SETTINGS
        from studio import server
        from studio.store import prefs
        self.assertEqual([m["name"] for m in prefs.models()],
                         [m["alias"] for m in SETTINGS.models])
        self.assertTrue(all(m["provider"] for m in prefs.models()),
                        "every model says which provider reaches it")
        self.assertEqual(modelcall.model_aliases(), SETTINGS.model_aliases)
        view = catalog.settings_view()
        self.assertEqual([m["id"] for m in view["models"]],
                         [m["name"] for m in prefs.models()])
        self.assertEqual([m["apiId"] for m in view["models"]], [m["id"] for m in SETTINGS.models],
                         "a served page stores the full id")
        self.assertEqual([m["provider"] for m in view["models"]],
                         [m["provider"] for m in SETTINGS.models],
                         "and which provider reaches it")
        state = catalog.state()
        self.assertEqual(state["llm"]["models"], view["models"],
                         "every writing form offers the list, so /api/state carries it")
        self.assertEqual(state["llm"]["defaultModel"], SETTINGS.model_id(catalog.PREFS.model))
        self.assertTrue(state["llm"]["providers"], "and every provider Studio could use")
        self.assertEqual(view["modelList"]["list"], SETTINGS.models)
        self.assertEqual(view["paths"]["settings"], SETTINGS.path)

        self.assertIn("STUDIO_PORT", view["envKeys"])
        keys = {row["key"] for row in view["platform"]}
        self.assertIn("studio.port", keys)
        self.assertIn("page.tutor.maxTokens", keys)
        self.assertEqual(server.DEFAULT_PORT, SETTINGS.get("studio.port"))

    def test_a_request_may_name_the_model_for_one_job(self):
        """Every writing form sends `model`; a known alias or id is used for that job alone,
        anything else means Studio's default."""
        from studio import server
        pick = lambda brief: server.Handler._model(None, brief)  # noqa: E731
        self.assertEqual(pick({"model": "haiku"}), "haiku")
        self.assertEqual(pick({"model": "claude-fable-5-1"}), "claude-fable-5-1")
        self.assertEqual(pick({"model": "claude-fable-5-1[1m]"}), catalog.PREFS.model)
        self.assertEqual(pick({}), catalog.PREFS.model)

    def test_prefs_store(self):
        import shutil
        import tempfile
        from studio.store import prefs
        tmp = tempfile.mkdtemp(prefix="studio-prefs-")
        self.addCleanup(shutil.rmtree, tmp, True)
        store = prefs.Prefs(os.path.join(tmp, "nested", "studio.json"))
        self.assertEqual(store.model, modelcall.default_model())
        self.assertEqual(store.save({"model": "opus"})["model"], "opus")
        self.assertEqual(prefs.Prefs(store.path).model, "opus")
        with self.assertRaises(ValueError):
            store.save({"model": "claude-fable-5-1[1m]"})
        with open(store.path, "w") as fh:
            fh.write("{broken")
        self.assertEqual(store.model, modelcall.default_model(), "a corrupt file falls back")


class TestModelList(unittest.TestCase):
    """The model list is editable from the settings page (studio/models.py): saved to the
    Studio layer of the settings, validated first, live everywhere at once, and a reset
    brings the platform's list back."""

    def setUp(self):
        import shutil
        import tempfile
        from coursekit.settings import SETTINGS
        self.tmp = tempfile.mkdtemp(prefix="studio-models-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.was = SETTINGS.studio_file
        SETTINGS.studio_file = os.path.join(self.tmp, "settings.json")
        SETTINGS.reload()
        self.addCleanup(self._restore)
        self.settings = SETTINGS

    def _restore(self):
        self.settings.studio_file = self.was
        self.settings.reload()

    def test_validation(self):
        from studio import models
        good = models.normalise([{"id": "claude-x-9", "alias": "x", "label": " X ", "note": "n"},
                                 {"id": "claude-y-1"}])
        self.assertEqual(good, [{"provider": "claude-code", "id": "claude-x-9", "label": "X",
                                 "note": "n", "alias": "x"},
                                {"provider": "claude-code", "id": "claude-y-1",
                                 "label": "claude-y-1", "note": ""}])
        priced = models.normalise([{"id": "claude-x-9", "price": {"in": "3", "out": 15}}])
        self.assertEqual(priced[0]["price"], {"in": 3.0, "out": 15.0},
                         "a price survives the settings page, as numbers")
        with self.assertRaises(ValueError):
            models.normalise([{"id": "claude-x-9", "price": {"in": "cheap"}}])
        for bad in ([], "x", [{}], [{"id": "Claude Opus"}], [{"id": "claude-x", "alias": "bad alias"}],
                    [{"id": "claude-x"}, {"id": "claude-x"}],
                    [{"id": "claude-x", "alias": "a"}, {"id": "claude-y", "alias": "a"}],
                    [{"id": "claude-x", "alias": "claude-y"}, {"id": "claude-y"}],
                    [{"id": "claude-x", "provider": "no-such-provider"}]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                models.normalise(bad)

    def test_two_providers_may_offer_the_same_model(self):
        """An id is a model of one provider - the same open model behind OpenAI and behind a
        local server is two rows. An alias is a name a person types, so it stays unique."""
        from studio import models
        both = models.normalise([{"id": "gpt-5.6", "provider": "openai", "alias": "sol"},
                                 {"id": "gpt-5.6", "provider": "local", "alias": "sol-local"}])
        self.assertEqual([m["provider"] for m in both], ["openai", "local"])
        with self.assertRaises(ValueError):
            models.normalise([{"id": "gpt-5.6", "provider": "openai", "alias": "sol"},
                              {"id": "gpt-5.6", "provider": "local", "alias": "sol"}])

    def test_replace_is_live_and_reset_forgets(self):
        from studio import models
        from studio.store import prefs
        before = models.platform_list()
        self.assertFalse(models.current()["custom"])
        saved = models.replace([{"id": "claude-new-1", "alias": "new", "label": "New"},
                                {"id": "claude-haiku-4-5-20251001", "alias": "haiku"}])
        self.assertTrue(saved["custom"])
        self.assertEqual([m["id"] for m in self.settings.models], ["claude-new-1", "claude-haiku-4-5-20251001"])
        self.assertIn("new", modelcall.model_aliases(), "the CLI alias table follows")
        self.assertIn("new", prefs.allowed(), "the default may now be the new model")
        self.assertEqual(modelcall.model_chain("opus"), [modelcall.default_model()],
                         "a model taken off the list is no longer tried")
        self.assertEqual([m["apiId"] for m in catalog.models_view()],
                         ["claude-new-1", "claude-haiku-4-5-20251001"])
        self.assertEqual(models.platform_list(), before, "the platform's list is untouched")
        with open(self.settings.studio_file, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        self.assertEqual([m["id"] for m in on_disk["models"]["list"]], ["claude-new-1", "claude-haiku-4-5-20251001"])

        back = models.reset()
        self.assertFalse(back["custom"])
        self.assertEqual(self.settings.models, before)
        with open(self.settings.studio_file, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {}, "only the list is forgotten, nothing else")

    def test_probe_asks_once_with_that_model_only(self):
        """A test from the settings page never falls back to another model."""
        import subprocess
        calls = []

        class Done:
            returncode = 0
            stdout = "OK"
            stderr = ""

        def fake_run(self, cli, args, prompt, timeout):
            calls.append(args)
            if "claude-gone-0" in args:
                raise subprocess.TimeoutExpired("claude", timeout)
            return Done()

        real_run, real_find = llm_cli.CliProvider._run, llm_cli.find_cli
        llm_cli.CliProvider._run, llm_cli.find_cli = fake_run, lambda *a: "claude"
        try:
            self.assertTrue(modelcall.probe("claude-new-1", timeout=5)["ok"])
            slow = modelcall.probe("claude-gone-0", timeout=5)
        finally:
            llm_cli.CliProvider._run, llm_cli.find_cli = real_run, real_find
        self.assertFalse(slow["ok"])
        self.assertIn("within 5s", slow["error"])
        self.assertEqual([a[a.index("--model") + 1] for a in calls], ["claude-new-1", "claude-gone-0"])
        self.assertEqual(len(calls), 2, "one attempt per probe, no fallback")


FAKE_CLI = (
    b'junk{id:"claude-opus-5",family:"opus",display_name:"Opus 5",knowledge_cutoff:"x"}'
    b'{id:"claude-sonnet-5",family:"sonnet",display_name:"Sonnet 5",k:1}'
    b'{id:"claude-haiku-4-5",family:"haiku",display_name:"Haiku 4.5",k:1}'
    b'{id:"claude-opus-4-1",family:"opus",display_name:"Opus 4.1",k:1}'
    b'model_selector_config:[{id:"cc",models:[{id:"claude-opus-5",name:"Opus 5",short_name:"Opus",section:"main"},'
    b'{id:"claude-sonnet-5",name:"Sonnet 5",short_name:"Sonnet",section:"main"},'
    b'{id:"claude-haiku-4-5",name:"Haiku 4.5",short_name:"Haiku",section:"main"}]}]more'
)


class TestModelDiscovery(unittest.TestCase):
    """The model list keeps itself current (studio/discover.py): every provider is asked what
    it knows, and the merge adds what is offered, removes what that provider does not
    recognise, and never empties. Everything is scoped to one provider - a Claude Code build
    says nothing about what OpenAI offers."""

    @staticmethod
    def _source(name="claude-code", label="Claude Code", complete=False, **fields):
        """One provider's answer, as `sources()` hands it to the merge."""
        answer = {"ok": True, "models": [], "known": {}, "error": "", "label": label,
                  "kind": "cli", "ready": True, "complete": complete}
        answer.update(fields)
        return {name: answer}

    def test_the_catalogue_is_parsed_out_of_the_binary(self):
        from coursekit.llm import claude_code
        cat = claude_code.parse(FAKE_CLI)
        self.assertTrue(cat["ok"])
        self.assertEqual([m["id"] for m in cat["models"]],
                         ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"])
        self.assertEqual(cat["models"][0]["label"], "Claude Opus 5")
        self.assertEqual(set(cat["known"]),
                         {"claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5",
                          "claude-opus-4-1"})
        nothing = claude_code.parse(b"a different build")
        self.assertFalse(nothing["ok"])
        self.assertIn("no model catalogue", nothing["error"])
        self.assertEqual(nothing["models"], [], "and it must never read as 'no models'")

    def test_a_binary_that_is_not_claude_code_reads_as_could_not_be_read(self):
        """The regular expressions are one program's internals. Anything else knows nothing
        about what that tool accepts, which is not the same as knowing it accepts nothing."""
        from coursekit.llm import cli as llm_cli
        provider = llm_cli.CliProvider(name="other", label="Some tool", commands=("no-such-cli",))
        found = provider.catalog()
        self.assertFalse(found["ok"])
        self.assertEqual(found["models"], [])
        self.assertFalse(provider.catalog_is_complete, "so it may never remove a model alone")

    def test_a_second_cli_tool_is_never_handed_claude_codes_reader(self):
        """"A Claude Code build says nothing about what another tool offers, and is not
        allowed to" - `claude_code` also reads the catalogue cached under ~/.claude, so a
        second `cli` row asking it would report those models as its own."""
        import tempfile
        from coursekit.llm import cli as llm_cli
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as fh:
            fh.write(FAKE_CLI)
        self.addCleanup(os.remove, fh.name)
        row = {"kind": "cli", "label": "Some tool", "command": [fh.name]}
        found = llm_cli.CliProvider.from_settings("other", row).catalog()
        self.assertFalse(found["ok"], "a present binary nothing understands is still unread")
        self.assertEqual(found["models"], [])
        named = llm_cli.CliProvider.from_settings("other", dict(row, catalog="claude-code"))
        self.assertTrue(named.catalog()["ok"], "and `catalog` is how a row asks for one")

    def test_the_catalogue_is_cached_per_file_version(self):
        import tempfile
        from coursekit.llm import claude_code
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as fh:
            fh.write(FAKE_CLI)
        self.addCleanup(os.remove, fh.name)
        first = claude_code.read(fh.name)
        self.assertTrue(first["ok"])
        self.assertEqual(first["path"], fh.name)
        self.assertEqual(claude_code.read(fh.name)["known"], first["known"])
        self.assertFalse(claude_code.read("")["ok"])


    def test_a_windows_shim_is_followed_to_the_cli_js_it_runs(self):
        """`binary()`: a native executable is itself; an npm `.cmd` shim is read for the
        cli.js it runs; a shim that names nothing, or names a file that is not there, and no
        CLI at all, are all "" rather than a guess."""
        import shutil
        import tempfile
        from coursekit.llm import claude_code
        tmp = tempfile.mkdtemp(prefix="studio-shim-")
        self.addCleanup(shutil.rmtree, tmp, True)
        target = os.path.join(tmp, "node_modules", "@anthropic-ai", "claude-code", "cli.js")
        os.makedirs(os.path.dirname(target))
        with open(target, "wb") as fh:
            fh.write(FAKE_CLI)
        shim = os.path.join(tmp, "claude.cmd")
        with open(shim, "w", encoding="utf-8") as fh:
            fh.write('@ECHO off\r\n"%~dp0\\node_modules\\@anthropic-ai\\claude-code\\cli.js" %*\r\n')
        self.assertEqual(claude_code.binary(shim), os.path.realpath(target), "the npm 6 shim")
        self.assertTrue(claude_code.read(claude_code.binary(shim))["ok"], "and it parses")
        with open(os.path.join(tmp, "node.exe"), "wb") as fh:
            fh.write(b"the runner, not the catalogue")
        with open(shim, "w", encoding="utf-8") as fh:
            fh.write('@ECHO off\r\nSET dp0=%~dp0\r\n'
                     'IF EXIST "%dp0%\\node.exe" (\r\n  SET "_prog=%dp0%\\node.exe"\r\n)\r\n'
                     '"%_prog%"  "%dp0%\\node_modules\\@anthropic-ai\\claude-code\\cli.js" %*\r\n')
        self.assertEqual(claude_code.binary(shim), os.path.realpath(target),
                         "the shim npm writes now: %dp0%, and node.exe named first is the runner")
        self.assertEqual(claude_code.binary(target), os.path.realpath(target), "not a shim: itself")
        self.assertEqual(claude_code.binary(""), "")
        with open(shim, "w", encoding="utf-8") as fh:
            fh.write("@ECHO off\r\necho no target here\r\n")
        self.assertEqual(claude_code.binary(shim), "", "a shim naming nothing")
        with open(shim, "w", encoding="utf-8") as fh:
            fh.write('"%~dp0\\gone\\cli.js" %*\r\n')
        self.assertEqual(claude_code.binary(shim), "", "a shim naming a file that is not there")
        self.assertEqual(claude_code.binary(os.path.join(tmp, "absent.cmd")), "", "no such shim")

    def test_a_fetched_catalogue_beats_the_binary_seed(self):
        import tempfile
        from coursekit.llm import claude_code
        home = tempfile.mkdtemp(prefix="claude-home-")
        self.addCleanup(__import__("shutil").rmtree, home, True)
        folder = os.path.join(home, "cache", "model-catalog")
        os.makedirs(folder)
        with open(os.path.join(folder, "cc-x.json"), "w", encoding="utf-8") as fh:
            json.dump({"fetchedAt": 1, "catalog": {"surface": "cc", "config": {"models": [
                {"id": "claude-next-7", "name": "Next 7", "section": "main"}]}}}, fh)
        with open(os.path.join(folder, "broken.json"), "w", encoding="utf-8") as fh:
            fh.write("{nope")
        self.assertEqual(claude_code.cached_rows(home),
                         [{"id": "claude-next-7", "label": "Claude Next 7"}])
        self.assertEqual(claude_code.cached_rows(os.path.join(home, "absent")), [])
        # the binary's picker rows survive a release that adds fields between name and section
        rows = claude_code.parse(
            b'{id:"claude-a-1",family:"a",display_name:"A 1"}'
            b'{id:"claude-a-1",name:"A 1",short_name:"A",extra:{x:1},section:"main"}')
        self.assertEqual([m["id"] for m in rows["models"]], ["claude-a-1"])

    def test_every_provider_is_asked_and_the_answers_are_filled_in(self):
        from studio import discover
        found = discover.sources()
        self.assertIn("claude-code", found)
        for name, source in found.items():
            self.assertIn("known", source, name)
            self.assertIn("complete", source, name)
            self.assertTrue(source["label"], name)

    def test_plan_adds_offered_removes_unknown_and_stays_with_one_provider(self):
        from coursekit.llm import claude_code
        from studio import discover
        current = [
            {"provider": "claude-code", "id": "claude-opus-5", "alias": "opus",
             "label": "Claude Opus 5", "note": "n"},
            {"provider": "claude-code", "id": "claude-haiku-4-5-20251001", "alias": "haiku",
             "label": "Claude Haiku 4.5", "note": ""},
            {"provider": "claude-code", "id": "claude-gone-3", "label": "Gone", "note": ""},
            {"provider": "openai", "id": "gpt-5.6", "alias": "sol", "label": "Sol", "note": ""},
        ]
        cli = claude_code.parse(FAKE_CLI)
        found = self._source(**{k: cli[k] for k in ("ok", "models", "known", "error")})
        new, added, candidates = discover.plan(current, found, "2026-09-09")
        self.assertEqual([m["id"] for m in added], ["claude-sonnet-5"],
                         "what its picker offers and the list lacks")
        self.assertEqual(added[0]["provider"], "claude-code")
        self.assertIn("added automatically on 2026-09-09", added[0]["note"])
        self.assertEqual([m["id"] for m in candidates], ["claude-gone-3"],
                         "the dated haiku is known by its bare id; gpt-5.6 is not its business")
        self.assertEqual(new[0]["alias"], "opus", "existing entries are untouched")

    def test_a_source_with_dates_offers_only_what_is_newer(self):
        """Otherwise a first run against an API drags in the whole back catalogue."""
        from studio import discover
        current = [{"provider": "anthropic", "id": "claude-opus-5", "label": "Opus", "note": ""}]
        listing = [
            {"id": "claude-opus-5", "label": "Claude Opus 5", "created": "2026-04-01"},
            {"id": "claude-new-6", "label": "Claude New 6", "created": "2026-09-01"},
            {"id": "claude-new-6-20260901", "label": "Claude New 6", "created": "2026-09-01"},
            {"id": "claude-old-2", "label": "Claude Old 2", "created": "2024-01-01"},
        ]
        found = self._source("anthropic", "Anthropic API", complete=True, models=listing,
                             known={m["id"]: m["label"] for m in listing})
        _new, added, candidates = discover.plan(current, found, "2026-09-09")
        self.assertEqual([m["id"] for m in added], ["claude-new-6"],
                         "newer than what is listed, and a dated snapshot is the same model")
        self.assertEqual(candidates, [])

    def test_a_provider_whose_source_failed_keeps_every_model_it_has(self):
        from studio import discover
        current = [{"provider": "claude-code", "id": "claude-x", "label": "X", "note": ""},
                   {"provider": "anthropic", "id": "claude-y", "label": "Y", "note": ""}]
        found = self._source(ok=False, error="could not be read")
        found.update(self._source("anthropic", "Anthropic API", complete=True,
                                  models=[], known={}))
        new, added, candidates = discover.plan(current, found, "2026-09-09")
        self.assertEqual(added, [])
        self.assertEqual([m["id"] for m in candidates], ["claude-y"],
                         "only the provider that answered may name a candidate")
        self.assertEqual(new, current)

    def test_removals_need_a_complete_source_or_a_refused_probe(self):
        """An older Claude Code passes an id its table lacks straight to the API and it works
        (Fable 5.1 on 2.1.252), so a binary scan alone never removes a model."""
        from studio import discover
        gone = {"provider": "claude-code", "id": "claude-gone-3", "label": "Gone", "note": ""}
        fine = {"provider": "claude-code", "id": "claude-fable-5-1", "label": "Fable", "note": ""}
        asked = []

        def probe(model_id):
            asked.append(model_id)
            return {"ok": model_id == "claude-fable-5-1"}

        removed, checked = discover.removals([gone, fine], complete=False, probe=probe,
                                             keep_one=False)
        self.assertEqual([m["id"] for m in removed], ["claude-gone-3"])
        self.assertEqual(checked, {"claude-gone-3": False, "claude-fable-5-1": True})
        self.assertEqual(asked, ["claude-gone-3", "claude-fable-5-1"])

        removed, checked = discover.removals([gone, fine], complete=True, probe=probe,
                                             keep_one=False)
        self.assertEqual([m["id"] for m in removed], ["claude-gone-3", "claude-fable-5-1"],
                         "absent from a listing of what the account may use means gone")
        self.assertEqual(checked, {})

        removed, _ = discover.removals([gone], complete=True, probe=probe, keep_one=True)
        self.assertEqual(removed, [], "never emptied")

    def test_an_account_problem_removes_nothing(self):
        """A probe refused for anything but the model - an exhausted account, a signed-out
        CLI, a dropped connection - would refuse every id there is. A check that ran at three
        in the morning must not empty the list because of it."""
        from studio import discover
        rows = [{"id": "claude-a"}, {"id": "claude-b"}]
        out_of_quota = lambda mid: {"ok": False, "why": "quota", "error": "usage limit"}
        removed, checked = discover.removals(rows, complete=False, probe=out_of_quota,
                                             keep_one=False)
        self.assertEqual(removed, [])
        self.assertEqual(checked, {"claude-a": False, "claude-b": False})
        refused = lambda mid: {"ok": False, "why": "model", "error": "unrecognized_model"}
        removed, _ = discover.removals(rows, complete=False, probe=refused, keep_one=False)
        self.assertEqual(removed, rows)

    def test_run_reports_one_row_per_provider_without_saving(self):
        from studio import discover
        report = discover.run(save=False)
        self.assertIn("claude-code", report["sources"])
        for name, row in report["sources"].items():
            self.assertIn("label", row, name)
            self.assertIn("complete", row, name)
        self.assertIsInstance(report["added"], list)
        self.assertIn("at", report)
        status = discover.status()
        self.assertIn("hours", status)
        self.assertTrue(status["providers"])
        self.assertIn("ready", status["providers"][0])


class TestLog(unittest.TestCase):
    def test_ring_buffer_filters(self):
        from studio.support import log as logmod
        logmod.configure("")
        logmod.clear()
        logmod.log.info("alpha one")
        logmod.log.warning("beta two")
        logmod.log.error("gamma three")
        self.assertEqual([r["msg"] for r in logmod.recent()], ["alpha one", "beta two", "gamma three"])
        self.assertEqual([r["level"] for r in logmod.recent(level="WARNING")], ["WARNING", "ERROR"])
        self.assertEqual([r["msg"] for r in logmod.recent(contains="TWO")], ["beta two"])
        self.assertEqual(len(logmod.recent(limit=1)), 1)
        logmod.clear()
        self.assertEqual(logmod.recent(), [])


class TestJobPersistence(unittest.TestCase):
    """A finished job survives the process that ran it."""

    def setUp(self):
        import shutil
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="studio-jobs-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _run(self, registry, fn):
        job = registry.add(jobs.Job("extend", {"course": "bread"}))
        job.start(fn)
        for _ in range(200):
            if job.finished and os.path.isfile(registry._path(job.id)):
                break
            time.sleep(0.01)
        return job

    def test_finished_job_is_written_and_replayable_from_a_fresh_registry(self):
        first = jobs.Registry(self.tmp)
        job = self._run(first, lambda j: (j.log("hello"), {"module": "M07"})[1])
        self.assertEqual(job.status, jobs.DONE)

        second = jobs.Registry(self.tmp)          # a new server process
        stored = second.get(job.id)
        self.assertIsNotNone(stored)
        self.assertTrue(stored.finished)
        self.assertEqual(stored.result, {"module": "M07"})
        self.assertEqual(stored.meta["course"], "bread")
        kinds = [e["kind"] for e in stored.since(0)]
        self.assertEqual(kinds[0], "started")
        self.assertIn("log", kinds)
        self.assertEqual(kinds[-1], "end")
        self.assertEqual([j.id for j in second.all()], [job.id])
        self.assertFalse(stored.provide({}), "a stored job cannot be answered")
        self.assertIsNone(second.active_for("bread"), "stored jobs are never active")

    def test_failed_job_is_persisted_too(self):
        def boom(_):
            raise RuntimeError("no")
        reg = jobs.Registry(self.tmp)
        job = self._run(reg, boom)
        self.assertEqual(job.status, jobs.FAILED)
        self.assertEqual(jobs.Registry(self.tmp).get(job.id).error, "no")

    def test_ids_do_not_collide_across_processes(self):
        self.assertTrue(jobs.Job("x").id.startswith("j" + jobs._BOOT + "-"))

    def test_prune_keeps_the_newest(self):
        reg = jobs.Registry(self.tmp)
        reg.KEEP = 3
        os.makedirs(self.tmp, exist_ok=True)
        for i in range(5):
            path = os.path.join(self.tmp, "old%d.json" % i)
            with open(path, "w") as fh:
                json.dump({"id": "old%d" % i, "kind": "x", "status": "done", "created": i}, fh)
            os.utime(path, (i, i))
        reg._prune()
        self.assertEqual(sorted(os.listdir(self.tmp)), ["old2.json", "old3.json", "old4.json"])

    def test_no_store_dir_means_memory_only(self):
        reg = jobs.Registry()
        job = reg.add(jobs.Job("x"))
        self.assertIsNone(job.on_end)
        self.assertEqual(reg.all(), [job])


class TestCourseEditing(unittest.TestCase):
    """Adding to and rewriting an existing course: the parts that do not need Claude."""

    def setUp(self):
        import shutil
        import tempfile
        sys.path.insert(0, HERE)
        from test_build import CourseFixture
        from coursekit.course import config as ck_config
        from coursekit.course import loader as ck_loader
        self.tmp = tempfile.mkdtemp(prefix="studio-edit-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fixture = CourseFixture(self.tmp)
        self.cfg = ck_config.load(self.fixture.root)
        self.modules = ck_loader.load_modules(self.cfg)

    def test_next_module_id_never_reuses(self):
        self.assertEqual(curriculum.next_module_id(self.modules), "M07")
        self.assertEqual(curriculum.next_module_id([{"id": "M03"}, {"id": "M10"}, {"id": "x"}]), "M11")
        self.assertEqual(curriculum.next_module_id([]), "M01")

    def test_plan_from_course_has_what_the_prompts_need(self):
        plan = curriculum.plan_from_course(self.cfg, self.modules)
        for key in ("title", "subject", "hours", "audience", "practitioner", "parts", "modules"):
            self.assertIn(key, plan)
        self.assertEqual(plan["modules"][0]["id"], "M01")
        self.assertEqual(len(plan["modules"][0]["sections"]), 3)
        self.assertEqual([p["dir"] for p in plan["parts"]][0], "01-foundations")

    def test_fix_spec_repairs_a_sloppy_design(self):
        spec = coerce.fix_spec({"title": " Deep dive ", "minutes": "abc", "sections": []},
                                   "M07", "p2", "topic", 45)
        self.assertEqual(spec["id"], "M07")
        self.assertEqual(spec["title"], "Deep dive")
        self.assertEqual(spec["minutes"], 45)
        self.assertEqual(len(spec["sections"]), 7)
        self.assertEqual(coerce.fix_spec("garbage", "M07", "p2", "topic", 45)["title"], "topic")
        self.assertEqual(coerce.fix_spec({"minutes": 9999}, "M07", "p2", "t", 45)["minutes"], 240)

    def test_store_module_data_adds_new_files_for_a_new_module(self):
        from coursekit.course import assessments as ck_assess
        assess = coerce.fix_assessment({
            "quiz": [{"q": "Q", "options": ["a", "b"], "answer": 1, "why": "w"}],
            "cards": [{"front": "f", "back": "b"}]}, "M07")
        editing.store_module_data(self.fixture.root, self.cfg, "M07", assess, [["a", "b", "c"]])
        self.assertTrue(os.path.isfile(os.path.join(self.fixture.root, "data/assessments/M07.json")))
        self.assertIn("M07", ck_assess.load_assessments(self.cfg))
        self.assertEqual(ck_assess.load_suggestions(self.cfg)["M07"], [["a", "b", "c"]])

    def test_store_module_data_replaces_in_place_for_an_existing_module(self):
        from coursekit.course import assessments as ck_assess
        assess = coerce.fix_assessment({
            "predict": "new", "quiz": [{"q": "Q", "options": ["a", "b"], "answer": 0, "why": "w"}],
            "cards": [{"front": "f", "back": "b"}]}, "M02")
        editing.store_module_data(self.fixture.root, self.cfg, "M02", assess, [["x", "y", "z"]] * 3)
        self.assertFalse(os.path.isfile(os.path.join(self.fixture.root, "data/assessments/M02.json")),
                         "no second file: the validator would see two claims on M02")
        loaded = ck_assess.load_assessments(self.cfg)
        self.assertEqual(loaded["M02"]["predict"], "new")
        self.assertEqual(len(loaded), 6)
        self.assertEqual(self.fixture.problems(), [])

    def test_set_short_title(self):
        editing.set_short_title(self.fixture.root, "M07", "Deep dive")
        with open(self.fixture.cfg_path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["shortTitles"]["M07"], "Deep dive")

    def test_extend_writes_a_module_then_rebuilds(self):
        """The whole extend pipeline with Claude stubbed out."""
        calls = []

        def fake_ask(prompt, **kw):
            calls.append(prompt)
            if "Return ONLY a JSON object of this shape" in prompt and '"sections": [str]' in prompt:
                return json.dumps({"title": "Reading a failed loaf", "short": "Failed loaf",
                                   "minutes": 45, "summary": "s",
                                   "sections": ["Why this matters", "Core concepts", "Exercise"]})
            if "study data for module" in prompt:
                return json.dumps({"predict": "p",
                                   "quiz": [{"q": "Q", "options": ["a", "b", "c", "d"], "answer": 2, "why": "w"}],
                                   "cards": [{"front": "f", "back": "b"}], "elaborate": ["e"],
                                   "transfer": {"scenario": "s", "prompt": "p", "model": "m"}})
            if "one-tap questions" in prompt:
                return json.dumps([["a", "b", "c"]] * 3)
            return ("# M07 — Reading a failed loaf\n\n**Time:** 45 minutes\n\n"
                    "## Why this matters\n\ntext\n\n## Core concepts\n\ntext\n\n## Exercise\n\ntext\n")

        original = modelcall.ask
        modelcall.ask = fake_ask
        try:
            job = jobs.Job("extend")
            dist = os.path.join(self.tmp, "dist")
            result = editing.extend(job, self.tmp, dist, "fixture",
                                      {"topic": "reading a failed loaf", "part": "p3", "minutes": 45,
                                       "notes": "assume the starter is healthy"})
        finally:
            modelcall.ask = original

        self.assertEqual(result["module"], "M07")
        self.assertEqual(result["modules"], 7)
        path = os.path.join(self.fixture.root, "modules", "03-expert-layer", "M07-reading-a-failed-loaf.md")
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self.fixture.problems(), [])
        self.assertTrue(any("assume the starter is healthy" in c for c in calls), "direction reached the model")
        self.assertTrue(os.path.isfile(os.path.join(dist, "fixture", "fixture-course-local.html")))
        # And the server's cheap id listing agrees with the loader.
        from coursekit.course import config as ck_config
        self.assertEqual(catalog.module_ids(ck_config.load(self.fixture.root))[-1], "M07")

    # ---- manage: settings, remove, trash ----

    def test_patch_changes_only_what_the_notes_say(self):
        """Patch mode: the text comes back with the notes applied and nothing else touched;
        the quiz is patched in place and the suggested questions are kept when the section
        headings did not move."""
        from coursekit.course import assessments as ck_assess
        from coursekit.course import config as ck_config
        from coursekit.course import loader as ck_loader
        root = os.path.join(self.tmp, "fixture")
        cfg = ck_config.load(root)
        m3 = next(m for m in ck_loader.load_modules(cfg) if m.id == "M03")
        with open(m3.source, encoding="utf-8") as fh:
            before = fh.read()
        assess_before = ck_assess.load_assessments(cfg)["M03"]
        sugg_before = ck_assess.load_suggestions(cfg)["M03"]
        after = before.rstrip("\n") + "\n\nOne more sentence the notes asked for.\n"
        seen = []

        def fake_ask(prompt, **kw):
            seen.append(prompt)
            if "Edit the study data for module M03" in prompt:
                self.assertIn("the notes asked for", prompt, "the quiz patch sees the new text")
                return json.dumps(assess_before)
            if "Edit module M03" in prompt:
                self.assertIn("keep everything else word for word", prompt)
                self.assertIn("add one sentence", prompt)
                return after
            raise AssertionError("unexpected call: " + prompt[:80])

        original = modelcall.ask
        modelcall.ask = fake_ask
        try:
            job = jobs.Job("rewrite")
            result = editing.rewrite(job, self.tmp, os.path.join(self.tmp, "dist"), "fixture", "M03",
                                       {"notes": "add one sentence", "mode": "patch"})
        finally:
            modelcall.ask = original

        self.assertEqual(result["mode"], "patch")
        self.assertEqual(len(seen), 2, "text and quiz only; the suggestions were kept")
        with open(m3.source, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), after)
        cfg = ck_config.load(root)
        self.assertEqual(ck_assess.load_suggestions(cfg)["M03"], sugg_before)
        self.assertEqual([q["q"] for q in ck_assess.load_assessments(cfg)["M03"]["quiz"]],
                         [q["q"] for q in assess_before["quiz"]])
        mod = next(e for e in job.events if e["kind"] == "module")
        self.assertTrue(mod["patched"])
        self.assertGreaterEqual(mod["changedLines"], 1)
        self.assertTrue(any("kept" in e.get("message", "") for e in job.events if e["kind"] == "log"))


    def test_rewrite_regenerates_text_figures_and_study_data(self):
        """A full rewrite: same id, same file, same position; the text, the figures and the
        study data are all written again, and the notes reach the writer as direction."""
        from coursekit.course import assessments as ck_assess
        from coursekit.course import config as ck_config
        from coursekit.course import loader as ck_loader
        m3 = next(m for m in self.modules if m.id == "M03")
        calls = []

        def fake_ask(prompt, **kw):
            calls.append(prompt)
            if "=== FIGURE" in prompt:
                return FIGURE_REPLY
            if "study data for module M03" in prompt:
                return json.dumps({"predict": "rewritten",
                                   "quiz": [{"q": "Q", "options": ["a", "b", "c", "d"], "answer": 1, "why": "w"}],
                                   "cards": [{"front": "f", "back": "b"}], "elaborate": ["e"],
                                   "transfer": {"scenario": "s", "prompt": "p", "model": "m"}})
            if "one-tap questions" in prompt:
                return json.dumps([["a", "b", "c"]] * 3)
            if "Write module M03" in prompt:
                return ("# M03 - Rewritten\n\n**Time:** 60 minutes\n\n"
                        "## Why this matters\n\nnew\n\n## Core concepts\n\nnew\n\n## Exercise\n\nnew\n")
            raise AssertionError("unexpected call: " + prompt[:80])

        original = modelcall.ask
        modelcall.ask = fake_ask
        try:
            job = jobs.Job("rewrite")
            result = editing.rewrite(job, self.tmp, os.path.join(self.tmp, "dist"), "fixture", "M03",
                                     {"notes": "make it shorter", "figures": True})
        finally:
            modelcall.ask = original

        self.assertEqual((result["mode"], result["module"]), ("rewrite", "M03"))
        self.assertEqual(result["modules"], 6, "same count: nothing was added")
        self.assertIn("Rewritten", files.read_text(m3.source), "same file, new text")
        written = next(c for c in calls if "Write module M03" in c)
        self.assertIn("A rewrite of the existing module", written)
        self.assertIn("make it shorter", written, "the notes reached the writer")
        self.assertTrue(any("=== FIGURE" in c for c in calls), "figures were drawn")
        self.assertTrue(os.path.isfile(os.path.join(self.fixture.root, "figures", "M03-1.svg")))
        cfg = ck_config.load(self.fixture.root)
        self.assertEqual(ck_assess.load_assessments(cfg)["M03"]["predict"], "rewritten")
        self.assertFalse(os.path.isfile(os.path.join(self.fixture.root, "data/assessments/M03.json")),
                         "replaced in place, not written as a second claim on M03")
        self.assertEqual([m.id for m in ck_loader.load_modules(cfg)][2], "M03", "same position")
        self.assertEqual(self.fixture.problems(), [])
        steps = [e["label"] for e in job.events if e["kind"] == "progress"]
        self.assertTrue(any(s.startswith("Figures for M03") for s in steps), steps)
        self.assertEqual(steps[-1], "Done")

    def test_rewrite_can_skip_figures_and_refuses_an_unknown_module(self):
        """`figures: false` keeps the figure stage out of the run; a module id the course
        does not have is a GenerationError before anything is asked."""
        calls = []

        def fake_ask(prompt, **kw):
            calls.append(prompt)
            self.assertNotIn("=== FIGURE", prompt, "figures were switched off")
            if "study data for module M02" in prompt:
                return json.dumps({"predict": "p",
                                   "quiz": [{"q": "Q", "options": ["a", "b", "c", "d"], "answer": 0, "why": "w"}],
                                   "cards": [{"front": "f", "back": "b"}], "elaborate": ["e"],
                                   "transfer": {"scenario": "s", "prompt": "p", "model": "m"}})
            if "one-tap questions" in prompt:
                return json.dumps([["a", "b", "c"]] * 3)
            return ("# M02 - Rewritten\n\n**Time:** 60 minutes\n\n"
                    "## Why this matters\n\nx\n\n## Core concepts\n\ny\n\n## Exercise\n\nz\n")

        original = modelcall.ask
        modelcall.ask = fake_ask
        try:
            result = editing.rewrite(jobs.Job("rewrite"), self.tmp, os.path.join(self.tmp, "dist"),
                                     "fixture", "M02", {"notes": "", "figures": False})
            with self.assertRaises(GenerationError):
                editing.rewrite(jobs.Job("rewrite"), self.tmp, os.path.join(self.tmp, "dist"),
                                "fixture", "M99", {"notes": ""})
        finally:
            modelcall.ask = original

        self.assertEqual(result["mode"], "rewrite")
        self.assertEqual(len(calls), 3, "text, study data, suggestions - and no figures")
        self.assertEqual(self.fixture.problems(), [])

    def test_settings_round_trip_and_id_lock(self):
        from studio import manage
        before = manage.settings(self.fixture.root)
        self.assertEqual(before["id"], "fixture")
        after = manage.update_settings(self.fixture.root, {
            "title": "  Bread, properly ", "tutorPersona": "You are a baker",
            "milestones": [{"after": "3", "text": "Halfway."}, {"after": 0, "text": "Start."},
                           {"after": 1, "text": ""}, "junk"],
            "parts": [{"id": "p1", "name": "Basics", "hours": 2, "blurb": "b"}],
            "anchor": {"label": " Your kitchen ", "noun": "my kitchen", "prompt": "", "junk": "x"},
        })
        self.assertEqual(after["title"], "Bread, properly")
        self.assertEqual(after["anchor"], {"label": "Your kitchen", "noun": "my kitchen", "prompt": "", "placeholder": ""})
        self.assertEqual(config.load(self.fixture.root).runtime()["anchor"]["label"], "Your kitchen")
        self.assertEqual(config.load(self.fixture.root).runtime()["anchor"]["prompt"],
                         config.DEFAULT_ANCHOR["prompt"], "an empty field falls back to the default")
        self.assertEqual(after["tutorPersona"], "You are a baker.")
        self.assertEqual([m["after"] for m in after["milestones"]], [0, 3])
        self.assertEqual(after["parts"][0]["name"], "Basics")
        self.assertEqual(after["hours"], 2 + sum(p["hours"] for p in before["parts"][1:]))
        with self.assertRaises(CourseError):
            manage.update_settings(self.fixture.root, {"id": "other"})
        with self.assertRaises(CourseError):
            manage.update_settings(self.fixture.root, {"title": "   "})
        self.assertEqual(self.fixture.problems(), [], "still a valid course")

    def test_remove_module_cleans_every_place_and_keeps_the_file(self):
        from studio import manage
        from coursekit.course import assessments as ck_assess
        trash = os.path.join(self.tmp, "trash")
        removed = manage.remove_module(self.fixture.root, "M03", trash)
        self.assertTrue(removed["assessment"] and removed["suggestions"])
        self.assertEqual(removed["file"], ["modules/02-core/M03-lesson.md"])
        self.assertTrue(os.path.isfile(os.path.join(removed["trash"], "M03-lesson.md")))
        self.assertNotIn("M03", ck_assess.load_assessments(self.cfg))
        self.assertNotIn("M03", ck_assess.load_suggestions(self.cfg))
        with open(self.fixture.cfg_path, encoding="utf-8") as fh:
            self.assertNotIn("M03", json.load(fh)["shortTitles"])
        self.assertEqual(self.fixture.problems(), [], "no orphan data left for the validator")
        self.assertEqual(curriculum.next_module_id(self.modules), "M07", "ids are not reused")
        with self.assertRaises(CourseError):
            manage.remove_module(self.fixture.root, "M03", trash)
        with self.assertRaises(CourseError):
            manage.remove_module(self.fixture.root, "../x", trash)

    def test_trash_course_moves_rather_than_deletes(self):
        from studio import manage
        dist = os.path.join(self.tmp, "dist", "fixture")
        os.makedirs(dist)
        with open(os.path.join(dist, "x.html"), "w") as fh:
            fh.write("x")
        out = manage.trash_course(self.tmp, os.path.join(self.tmp, "dist"),
                                  os.path.join(self.tmp, "trash"), "fixture")
        self.assertFalse(os.path.exists(self.fixture.root))
        self.assertFalse(os.path.exists(dist))
        self.assertTrue(os.path.isfile(os.path.join(out["trash"], "course", "course.json")))
        self.assertTrue(os.path.isfile(os.path.join(out["trash"], "dist", "x.html")))
        with self.assertRaises(CourseError):
            manage.trash_course(self.tmp, self.tmp, self.tmp, "fixture")

    def test_open_questions_from_marks(self):
        state = {"marks": {"M02": [
            {"id": "k1", "sec": 1, "text": "a passage", "q": "why?", "status": "open", "ts": 5},
            {"id": "k2", "sec": 0, "text": "plain highlight", "status": "hl", "ts": 9},
            {"id": "k3", "sec": 2, "text": "answered one", "status": "answered", "ts": 7},
        ], "M09": "junk"}}
        mods = [{"id": "M02", "title": "Water"}]
        qs = catalog.open_questions(state, mods)
        self.assertEqual([q["id"] for q in qs], ["k3", "k1"], "newest first, highlights excluded")
        self.assertEqual(qs[1]["title"], "Water")
        self.assertEqual(catalog.open_questions({}, mods), [])

    def test_flagged_questions_from_state(self):
        """A quiz question the reader flagged reaches the Questions tab as a patch brief;
        a row without a question index is not one."""
        state = {"flags": {"M02": [
            {"id": "f1", "qi": 3, "q": "Which is it?", "note": "B is also right", "ts": 5},
            {"id": "f2", "qi": 0, "q": "First?", "note": "", "ts": 9},
            {"id": "f3", "q": "no index"},
        ], "M09": "junk"}}
        mods = [{"id": "M02", "title": "Water"}]
        flags = catalog.flagged_questions(state, mods)
        self.assertEqual([f["id"] for f in flags], ["f2", "f1"], "newest first")
        self.assertEqual(flags[1]["title"], "Water")
        self.assertEqual(flags[1]["qi"], 3)
        self.assertEqual(catalog.flagged_questions({}, mods), [])

    def test_learner_view_keeps_open_gaps_only(self):
        """The page's learner memory reaches Studio as the brief and the open gaps; a gap
        closed by status or by the reader's `closed` map is left out."""
        state = {"learner": {
            "brief": "Guesses when unsure.", "strengths": ["Definitions"], "at": 5,
            "closed": {"g3": 9},
            "gaps": [
                {"id": "g1", "mid": "M02", "topic": "Boiling", "why": "missed", "ask": "Why?",
                 "status": "open"},
                {"id": "g2", "mid": "M02", "topic": "Old", "why": "", "ask": "", "status": "closed"},
                {"id": "g3", "mid": "M02", "topic": "Dismissed", "why": "", "ask": "",
                 "status": "open"},
                "junk",
            ],
        }}
        mods = [{"id": "M02", "title": "Water"}]
        view = catalog.learner_view(state, mods)
        self.assertEqual([g["id"] for g in view["gaps"]], ["g1"])
        self.assertEqual(view["gaps"][0]["title"], "Water")
        self.assertEqual(view["brief"], "Guesses when unsure.")
        self.assertEqual(view["at"], 5)
        empty = catalog.learner_view({}, mods)
        self.assertEqual(empty, {"brief": "", "strengths": [], "gaps": [], "at": None})


    def test_module_progress_reads_the_badges_off_the_reader_state(self):
        """Per module: done, minutes, sections read, quiz finished - and nothing the page
        stored in an unexpected shape is fatal."""
        state = {"progress": {
            "M01": {"done": True, "time": 610, "secs": {"0": True, "1": False, "2": True},
                    "quiz": {"finished": True}},
            "M02": {"time": "abc", "secs": "junk", "quiz": "junk"},
            "M03": {"secs": {"0": True}, "time": 59.9},
            "M04": "junk",
        }}
        view = catalog.module_progress(state)
        self.assertEqual(view["M01"], {"done": True, "minutes": 10, "read": 2, "quiz": True})
        self.assertEqual(view["M02"], {"done": False, "minutes": 0, "read": 0, "quiz": False})
        self.assertEqual(view["M03"], {"done": False, "minutes": 0, "read": 1, "quiz": False})
        self.assertNotIn("M04", view)
        self.assertEqual(catalog.module_progress({}), {})
        self.assertEqual(catalog.module_progress({"progress": None}), {})

    # ---- resuming a run that died ----

    def _stub_claude(self, calls):
        def fake_ask(prompt, **kw):
            calls.append(prompt)
            if "study data for module" in prompt:
                mid = prompt.split("study data for module ")[1].split(" ")[0]
                return json.dumps({"predict": "p",
                                   "quiz": [{"q": "Q", "options": ["a", "b", "c", "d"], "answer": 1, "why": "w"}],
                                   "cards": [{"front": "f", "back": "b"}], "elaborate": ["e"],
                                   "transfer": {"scenario": "s", "prompt": "p", "model": "m"}})
            if "one-tap questions" in prompt:
                n = int(prompt.split("exactly ")[1].split(" ")[0])
                return json.dumps([["a", "b", "c"]] * n)
            if "Write module " in prompt:
                mid = prompt.split("Write module ")[1].split(" ")[0]
                return ("# %s — Written on resume\n\n**Time:** 60 minutes\n\n"
                        "## Why this matters\n\nx\n\n## Core concepts\n\ny\n\n## Exercise\n\nz\n" % mid)
            if "worksheets" in prompt and "JSON array" in prompt:
                return "[]"
            return "# Doc\n\n" + ("real content " * 60)
        return fake_ask

    def test_resume_keeps_what_exists_and_writes_only_the_rest(self):
        """The fixture has six finished modules; the manifest says there should be an M07."""
        from coursekit.course import assessments as ck_assess
        import shutil
        # Make it look like a run that died: one module listed but never written, and the
        # study data file shaped the way generate() writes it (all.json).
        self.fixture.edit_manifest(shortTitles=dict(
            {mid: "Lesson " + mid for mid in self.fixture.ids}, M07="The missing one"))
        assess = ck_assess.load_assessments(self.cfg)
        sugg = ck_assess.load_suggestions(self.cfg)
        data_dir = os.path.join(self.fixture.root, "data")
        shutil.rmtree(data_dir)
        os.makedirs(os.path.join(data_dir, "assessments"))
        os.makedirs(os.path.join(data_dir, "suggestions"))
        files.write_json(os.path.join(data_dir, "assessments/all.json"), list(assess.values()))
        files.write_json(os.path.join(data_dir, "suggestions/all.json"), sugg)
        self.assertFalse(os.path.isfile(os.path.join(self.fixture.root, curriculum.PLAN_FILE)))

        calls = []
        original = modelcall.ask
        modelcall.ask = self._stub_claude(calls)
        try:
            job = jobs.Job("generate")
            result = generator.generate(job, self.tmp, os.path.join(self.tmp, "dist"),
                                        {"id": "fixture", "theme": "bread baking", "hours": 6, "resume": True})
        finally:
            modelcall.ask = original

        self.assertEqual(result["modules"], 7)
        written = [c for c in calls if "Write module " in c]
        self.assertEqual(len(written), 1, "only the missing module was written")
        self.assertIn("Write module M07", written[0])
        self.assertEqual(sum(1 for c in calls if "study data for module" in c), 1)
        self.assertTrue(os.path.isfile(os.path.join(self.fixture.root, curriculum.PLAN_FILE)),
                        "the curriculum is saved for the next resume")
        self.assertEqual(self.fixture.problems(), [])
        kinds = [e["kind"] for e in job.events]
        self.assertNotIn("await", kinds, "a resume never asks for approval again")
        # Reference docs that were stubs got written; a second resume would keep them.
        self.assertTrue(generator.is_real_file(os.path.join(self.fixture.root, "reference/glossary.md")))


    def test_worksheets_are_optional_and_never_lose_a_finished_course(self):
        """`_write_worksheets`: a plan that fails, a plan that is not a list, a spec with no
        name, a worksheet whose call fails - each is logged or skipped, never raised; the
        rest are written under templates/ and capped at the setting."""
        templates = os.path.join(self.fixture.root, "templates")
        before = set(os.listdir(templates))
        plan = curriculum.plan_from_course(self.cfg, self.modules)
        spec_list = [
            {"name": "Hydration calculator", "slug": "Hydration Calc!", "purpose": "each bake"},
            {"name": "Never written", "slug": "never-written"},
            {"slug": "no-name"},
            "junk",
        ] + [{"name": "Filler %d" % i} for i in range(generator.MAX_WORKSHEETS)]
        mode = {"plan": "ok"}

        def fake_ask(prompt, **kw):
            if "fill-in worksheets it should ship" in prompt:
                if mode["plan"] == "fail":
                    raise GenerationError("the model is out")
                if mode["plan"] == "object":
                    return json.dumps({"not": "a list"})
                return json.dumps(spec_list)
            if "Worksheet: Never written" in prompt:
                raise GenerationError("boom")
            name = prompt.split("Worksheet: ")[1].split("\n")[0]
            return "```markdown\n# %s\n\nUse it when...\n```" % name

        original = modelcall.ask
        modelcall.ask = fake_ask
        try:
            job = jobs.Job("generate")
            generator._write_worksheets(job, self.fixture.root, plan, plan["modules"], "")
            new = set(os.listdir(templates)) - before
            self.assertIn("hydration-calc.md", new, "the slug is cleaned")
            self.assertNotIn("never-written.md", new, "a failed worksheet is skipped")
            self.assertEqual(len(new), generator.MAX_WORKSHEETS - 3,
                             "the cap counts entries: four leading slots, one of them written")
            text = files.read_text(os.path.join(templates, "hydration-calc.md"))
            self.assertTrue(text.startswith("# Hydration calculator"), "the fence is stripped")
            written = [e["slug"] for e in job.events if e["kind"] == "worksheet"]
            self.assertEqual(written[0], "hydration-calc")
            logs = [e["message"] for e in job.events if e["kind"] == "log"]
            self.assertTrue(any("never-written" in m and "skipping" in m for m in logs), logs)

            for failing in ("fail", "object"):
                mode["plan"] = failing
                job = jobs.Job("generate")
                seen = set(os.listdir(templates))
                generator._write_worksheets(job, self.fixture.root, plan, plan["modules"], "")
                self.assertEqual(set(os.listdir(templates)), seen, failing)
                if failing == "fail":
                    logs = [e["message"] for e in job.events if e["kind"] == "log"]
                    self.assertTrue(any("Could not plan worksheets" in m for m in logs), logs)
        finally:
            modelcall.ask = original

    def test_reconstruct_plan_orders_and_fills(self):
        self.fixture.edit_manifest(shortTitles=dict(
            {mid: "Lesson " + mid for mid in self.fixture.ids}, M09="Nine", M08="Eight"))
        plan = curriculum.reconstruct_plan(self.fixture.root)
        self.assertEqual([m["id"] for m in plan["modules"]], ["M01", "M02", "M03", "M04", "M05", "M06", "M08", "M09"])
        self.assertEqual(plan["modules"][-1]["title"], "Nine")
        self.assertEqual(plan["modules"][0]["sections"], ["Why this matters", "Core concepts", "Exercise"])

    def test_resolve_course_file_stays_inside_the_course(self):
        root = self.fixture.root
        ok = catalog.resolve_course_file(root, "modules/01-foundations/M01-lesson.md")
        self.assertTrue(ok.startswith(os.path.abspath(root)))
        for bad in ("../other/course.json", "course.py", "", "modules/../../x.md"):
            with self.subTest(bad=bad):
                try:
                    full = catalog.resolve_course_file(root, bad)
                except ValueError:
                    continue
                self.assertTrue(full.startswith(os.path.abspath(root)),
                                "%r resolved outside the course" % bad)


class TestPhase3(unittest.TestCase):
    """Reordering, profiles, the study calendar, search, export/import and the review pass."""

    def setUp(self):
        import shutil
        import tempfile
        sys.path.insert(0, HERE)
        from test_build import CourseFixture
        self.tmp = tempfile.mkdtemp(prefix="studio-p3-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.courses = os.path.join(self.tmp, "courses")
        self.fixture = CourseFixture(self.courses)

    def _ids(self):
        from coursekit.course import loader as ck_loader
        return [m.id for m in ck_loader.load_modules(config.load(self.fixture.root))]

    # ---- P3.1 order ----

    def test_order_in_manifest_drives_the_loader_and_the_cheap_listing(self):
        from studio import server
        self.assertEqual(self._ids(), ["M01", "M02", "M03", "M04", "M05", "M06"])
        self.fixture.edit_manifest(order=["M02", "M01", "M04", "M03", "M99"])
        cfg = config.load(self.fixture.root)
        self.assertEqual(self._ids(), ["M02", "M01", "M04", "M03", "M05", "M06"],
                         "listed ids first in that sequence, unknown ids ignored, the rest by filename")
        self.assertEqual(catalog.module_ids(cfg), self._ids())
        self.assertEqual(self.fixture.problems(), [])

    def test_move_module_within_and_between_parts(self):
        from studio import manage
        r = manage.move_module(self.fixture.root, "M02", "p1", 0)
        self.assertEqual(r["order"][:2], ["M02", "M01"])
        self.assertFalse(r["moved"])
        self.assertEqual(self._ids()[:2], ["M02", "M01"])
        r = manage.move_module(self.fixture.root, "M01", "p3", 0)
        self.assertTrue(r["moved"])
        cfg = config.load(self.fixture.root)
        from coursekit.course import loader as ck_loader
        mods = ck_loader.load_modules(cfg)
        m01 = next(m for m in mods if m.id == "M01")
        self.assertEqual(m01.part, "p3")
        self.assertEqual([m.id for m in mods if m.part == "p3"][0], "M01")
        self.assertEqual(self.fixture.problems(), [], "moving touches no study data")
        with self.assertRaises(CourseError):
            manage.move_module(self.fixture.root, "M02", "p2", 0)   # p1 would be left empty
        with self.assertRaises(CourseError):
            manage.move_module(self.fixture.root, "M42", "p1", 0)
        manage.remove_module(self.fixture.root, "M04", os.path.join(self.tmp, "trash"))
        with open(self.fixture.cfg_path, encoding="utf-8") as fh:
            self.assertNotIn("M04", json.load(fh)["order"])

    # ---- P3.3 profiles ----

    def test_profile_stores_and_prefs(self):
        from studio.store import prefs, progress
        base = os.path.join(self.tmp, "progress")
        default = progress.Store(base)
        alex = progress.Store(base, "alex")
        self.assertEqual(default.path("bread"), os.path.join(base, "bread.json"))
        self.assertEqual(alex.path("bread"), os.path.join(base, "alex", "bread.json"))
        default.save("bread", {"progress": {"M01": {"done": True}}})
        alex.save("bread", {"progress": {}})
        self.assertEqual(progress.profiles(base), ["default", "alex"])
        self.assertTrue(default.load("bread")["state"]["progress"]["M01"]["done"])
        self.assertEqual(alex.load("bread")["state"]["progress"], {})
        self.assertEqual(default.delete_everywhere("bread"), 2)
        self.assertIsNone(alex.load("bread"))
        with self.assertRaises(ValueError):
            progress.Store(base, "../x")
        pf = prefs.Prefs(os.path.join(self.tmp, "studio.json"))
        self.assertEqual(pf.profile, "default")
        pf.save({"profile": "Alex"})
        self.assertEqual(pf.profile, "alex")
        with self.assertRaises(ValueError):
            pf.save({"profile": "not ok"})

    # ---- P3.4 calendar ----

    def test_calendar_across_courses(self):
        from studio import server
        from studio.store import progress
        today = int(time.time() // 86400)
        summary = progress.summarise({"streak": {"seen": [today, today - 1, today - 5]}}, ["M01"])
        self.assertEqual(summary["seen"], [today - 5, today - 1, today])
        cal = catalog.calendar([
            {"id": "a", "progress": {"seen": [today - 1, today - 2]}},
            {"id": "b", "progress": {"seen": [today - 2, today - 9]}},
        ])
        self.assertEqual(cal["streak"], 2, "yesterday and the day before, today not yet studied")
        self.assertEqual(sorted(cal["days"][str(today - 2)]), ["a", "b"])
        self.assertEqual(cal["total"], 3)
        self.assertEqual(catalog.calendar([])["streak"], 0)

    # ---- P3.2 search ----

    def test_search_finds_titles_sections_passages_and_terms(self):
        from studio import search
        with open(os.path.join(self.fixture.root, "reference", "glossary.md"), "a", encoding="utf-8") as fh:
            fh.write("\n**Autolyse** — Resting flour and water before the salt.\n")
        r = search.search(self.courses, "lesson 3")
        self.assertEqual(r["courses"], 1)
        kinds = {(h["kind"], h["mid"]) for h in r["hits"]}
        self.assertIn(("module", "M03"), kinds)
        self.assertIn(("passage", "M03"), kinds)
        self.assertEqual(r["hits"][0]["kind"], "module", "a title hit outranks a passage")
        r = search.search(self.courses, "autolyse")
        self.assertEqual([h["kind"] for h in r["hits"]], ["term"])
        r = search.search(self.courses, "core concepts", limit=2)
        self.assertEqual(len(r["hits"]), 2)
        self.assertGreater(r["total"], 2)
        self.assertEqual(search.search(self.courses, "x")["hits"], [])

    # ---- P3.5 / P3.6 export and import ----

    def test_zip_round_trip_and_refusals(self):
        import zipfile
        import io as _io
        from studio import transfer
        os.makedirs(os.path.join(self.fixture.root, ".git"))
        with open(os.path.join(self.fixture.root, ".git", "HEAD"), "w") as fh:
            fh.write("ref: refs/heads/main\n")
        data = transfer.export_zip(self.fixture.root)
        names = zipfile.ZipFile(_io.BytesIO(data)).namelist()
        self.assertIn("fixture/course.json", names)
        self.assertFalse(any("/.git/" in n for n in names), ".git stays behind")

        other = os.path.join(self.tmp, "elsewhere")
        course = transfer.import_zip(other, data)
        self.assertEqual(course["id"], "fixture")
        self.assertEqual(course["modules"], 6)
        self.assertTrue(os.path.isfile(os.path.join(other, "fixture", "course.json")))
        with self.assertRaises(CourseError):
            transfer.import_zip(other, data)            # already there
        self.assertEqual(sorted(os.listdir(other)), ["fixture"], "a refused import leaves no staging folder")

        buf = _io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("notes.md", "hello")
        with self.assertRaises(CourseError):
            transfer.import_zip(other, buf.getvalue())   # no course.json
        with self.assertRaises(CourseError):
            transfer.import_zip(other, b"not a zip")

        # a hostile member never escapes the staging folder
        buf = _io.BytesIO()
        with zipfile.ZipFile(_io.BytesIO(data)) as src, zipfile.ZipFile(buf, "w") as zf:
            for m in src.infolist():
                zf.writestr(m.filename.replace("fixture/", "evil/", 1), src.read(m))
            zf.writestr("evil/../../escaped.txt", "x")
        evil_dir = os.path.join(self.tmp, "evil-target")
        # the id inside course.json is still "fixture", so import into a fresh dir
        transfer.import_zip(evil_dir, buf.getvalue())
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "escaped.txt")))
        self.assertFalse(os.path.exists(os.path.join(evil_dir, "escaped.txt")))

    def test_git_url_is_checked_before_anything_runs(self):
        from studio import transfer
        for bad in ("", "ftp://x/y", "https://host/path; rm -rf /", "--upload-pack=evil", "file:///etc"):
            self.assertFalse(transfer.is_git_url(bad), bad)
            with self.assertRaises(CourseError):
                transfer.import_git(self.tmp, bad)
        for good in ("https://github.com/you/course-repo", "https://github.com/you/course-repo.git",
                     "git@github.com:you/course-repo.git", "http://localhost:3000/a/b"):
            self.assertTrue(transfer.is_git_url(good), good)

    # ---- P3.7 review ----

    def test_review_prompt_and_coercion(self):
        from studio.authoring import prompts
        from coursekit.course import loader as ck_loader
        cfg = config.load(self.fixture.root)
        mods = ck_loader.load_modules(cfg)
        plan = curriculum.plan_from_course(cfg, mods)
        spec = plan["modules"][2]
        text = prompts.review(plan, plan["modules"], spec, "# M03 — Lesson 3\n\n## Why", {"quiz": [{"type": "tf", "q": "Is it?"}]})
        for needle in ("M03", "Lesson 3", "[tf] Is it?", '"verdict"', "rewriteBrief", "Do not list what is fine",
                       "publishable as it stands", "do not lower"):
            self.assertIn(needle, text)

        fixed = coerce.fix_review({
            "verdict": "Needs Work", "summary": "  ok  ",
            "gaps": [{"where": "Core concepts", "issue": "no numbers", "fix": "add two"}, "loose string", {"issue": ""}, 7],
            "errors": "not a list", "quiz": [{"item": "Q2", "issue": "key wrong"}],
            "rewriteBrief": "Add the arithmetic.",
        })
        self.assertEqual(fixed["verdict"], "needs work")
        self.assertEqual(fixed["summary"], "ok")
        self.assertEqual([g["issue"] for g in fixed["gaps"]], ["no numbers", "loose string"])
        self.assertEqual(fixed["errors"], [])
        self.assertEqual(fixed["quiz"][0]["item"], "Q2")
        self.assertEqual(coerce.fix_review("garbage")["verdict"], "needs work")
        self.assertEqual(coerce.fix_review({"verdict": "solid"})["verdict"], "solid")

        state_root = os.path.join(self.tmp, "state")
        d = reviews.reviews_dir(state_root, "fixture")
        os.makedirs(d)
        with open(os.path.join(d, "M03.json"), "w", encoding="utf-8") as fh:
            json.dump(dict(fixed, module="M03", at=1), fh)
        self.assertEqual(list(reviews.load_reviews(state_root, "fixture")), ["M03"])
        self.assertEqual(reviews.load_reviews(state_root, "nothing"), {})


FIGURE_REPLY = """Here are the figures.
=== FIGURE
section: core concepts
caption: The [two] halves and how they meet
<svg viewBox='0 0 800 450'><title>Halves</title>
<g data-step='1'><rect x='0' y='0' width='100' height='50' class='fig-1'/></g>
<g data-step='2'><rect x='0' y='60' width='100' height='50' class='fig-2'/></g>
</svg>
=== FIGURE
section: Exercise
caption: Broken on purpose
<svg viewBox='0 0 1 1'><rect></svg>
=== FIGURE
section: No such section
caption: Orphan
<svg viewBox='0 0 1 1'><rect x='0' y='0' width='1' height='1'/></svg>
=== FIGURE
section: Why this matters
caption: Scripted
<svg viewBox='0 0 1 1'><script>alert(1)</script><rect x='0' y='0' width='1' height='1'/></svg>
"""


class TestFigureWriting(unittest.TestCase):
    """Figures for a module: the reply parsed figure by figure, coerced towards what the
    build accepts, written under figures/ and referenced from the named section."""

    def setUp(self):
        import tempfile
        sys.path.insert(0, HERE)
        from test_build import CourseFixture
        from coursekit.course import loader as ck_loader
        self.tmp = tempfile.mkdtemp(prefix="studio-fig-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fixture = CourseFixture(self.tmp)
        self.cfg = config.load(self.fixture.root)
        self.modules = ck_loader.load_modules(self.cfg)
        self.headings = ["Why this matters", "Core concepts", "Exercise"]

    def test_reply_parsing_and_coercion(self):
        raw = figures.parse_reply(FIGURE_REPLY)
        self.assertEqual([r["section"] for r in raw],
                         ["core concepts", "Exercise", "No such section", "Why this matters"])
        self.assertTrue(raw[0]["svg"].startswith("<svg") and raw[0]["svg"].endswith("</svg>"))

        fixed = coerce.fix_figures(raw, self.headings, 3)
        self.assertEqual([f["section"] for f in fixed], ["Core concepts", "Why this matters"],
                         "the malformed one and the orphan are dropped; the heading's case is repaired")
        self.assertEqual(fixed[0]["caption"], "The (two) halves and how they meet",
                         "brackets would break the markdown reference")
        self.assertEqual(fixed[0]["steps"], 2)
        self.assertNotIn("<script", fixed[1]["svg"])
        self.assertEqual(coerce.fix_figures(raw, self.headings, 1), fixed[:1], "capped")
        self.assertEqual(coerce.fix_figures("junk", self.headings, 2), [])
        self.assertEqual(figures.parse_reply("no figures here"), [])

    def test_references_go_in_and_come_out(self):
        body = ("# M01 — L\n\n**Time:** 60 minutes\n\n---\n\n## Core concepts\n\nText.\n\n---\n\n"
                "## Exercise\n\nDo it.\n")
        line = "![Cap](figures/M01-1.svg)"
        after = figures.insert_reference(body, "Core concepts", line)
        self.assertIn("Text.\n\n![Cap](figures/M01-1.svg)\n\n---\n\n## Exercise", after)
        self.assertEqual(figures.insert_reference(body, "Nowhere", line), body)
        end = figures.insert_reference(body, "Exercise", line)
        self.assertTrue(end.rstrip().endswith("Do it.\n\n" + line))
        self.assertEqual(figures.references_in(after, "M01"), ["M01-1.svg"])
        self.assertEqual(figures.references_in(after, "M02"), [])
        self.assertEqual(figures.strip_references(after, "M01"), body)
        self.assertEqual(figures.strip_references(after, "M02"), after, "another module's figures stay")

    def test_write_figures_replaces_files_and_references_then_builds(self):
        from studio.authoring import prompts
        plan = curriculum.plan_from_course(self.cfg, self.modules)
        spec = plan["modules"][0]
        path = self.modules[0].source
        fig_dir = os.path.join(self.fixture.root, "figures")
        os.makedirs(fig_dir)
        with open(os.path.join(fig_dir, "M01-7.svg"), "w", encoding="utf-8") as fh:
            fh.write("<svg viewBox='0 0 1 1'/>")
        prompts_seen = []

        def fake_ask(prompt, **kw):
            prompts_seen.append(prompt)
            return FIGURE_REPLY

        original = modelcall.ask
        modelcall.ask = fake_ask
        try:
            job = jobs.Job("figures")
            body = figures.write_figures(job, self.fixture.root, plan, spec,
                                         files.read_text(path), path)
        finally:
            modelcall.ask = original

        self.assertFalse(os.path.exists(os.path.join(fig_dir, "M01-7.svg")), "old figures go")
        self.assertEqual(sorted(os.listdir(fig_dir)), ["M01-1.svg", "M01-2.svg"])
        self.assertEqual(sorted(figures.references_in(body, "M01")), ["M01-1.svg", "M01-2.svg"])
        self.assertIn("![The (two) halves and how they meet](figures/M01-1.svg)", body)
        self.assertEqual(files.read_text(path), body)
        self.assertEqual(self.fixture.problems(), [])
        events = [e for e in job.since(0) if e["kind"] == "figures"]
        self.assertEqual(events[0]["count"], 2)
        text = prompts_seen[0]
        for needle in ("=== FIGURE", "fig-soft", "data-step", "SINGLE quotes", "- Core concepts", "M01",
                       "what to notice", "guess the next stage", '"Common mistakes": a wrong/right',
                       'Never "Why this matters"'):
            self.assertIn(needle, text)
        self.assertIn("Draw up to %d figures" % figures.FIGURES_PER_MODULE, text)
        # a rebuild carries them into the page
        _, result = self.fixture.build(os.path.join(self.tmp, "dist"))
        self.assertEqual(result.figures, 2)

    def test_draw_job_targets_the_modules_without_figures(self):
        original = modelcall.ask
        modelcall.ask = lambda prompt, **kw: FIGURE_REPLY
        try:
            job = jobs.Job("figures")
            result = editing.draw(job, self.tmp, os.path.join(self.tmp, "dist"), "fixture",
                                  {"module": "M02"})
            self.assertEqual(result["module"], "M02")
            self.assertEqual(result["drawn"], ["M02"])
            self.assertEqual(result["figures"], 2)

            job = jobs.Job("figures")
            result = editing.draw(job, self.tmp, os.path.join(self.tmp, "dist"), "fixture", {})
            self.assertEqual(result["drawn"], ["M01", "M03", "M04", "M05", "M06"], "M02 already had figures")
            self.assertEqual(result["module"], "")
            with self.assertRaises(GenerationError):
                editing.draw(jobs.Job("figures"), self.tmp, os.path.join(self.tmp, "dist"), "fixture", {})
            with self.assertRaises(GenerationError):
                editing.draw(jobs.Job("figures"), self.tmp, os.path.join(self.tmp, "dist"), "fixture",
                             {"module": "M99"})
        finally:
            modelcall.ask = original
        detail = catalog.course_detail("fixture") if catalog.course_root("fixture") == self.fixture.root else None
        if detail:
            self.assertEqual(detail["moduleList"][1]["figures"], 2)

    def test_remove_module_takes_its_figures_to_the_trash(self):
        from studio import manage
        fig_dir = os.path.join(self.fixture.root, "figures")
        os.makedirs(fig_dir)
        for name in ("M02-1.svg", "M03-1.svg"):
            with open(os.path.join(fig_dir, name), "w", encoding="utf-8") as fh:
                fh.write("<svg viewBox='0 0 1 1'/>")
        trash = os.path.join(self.tmp, "trash")
        removed = manage.remove_module(self.fixture.root, "M02", trash)
        self.assertEqual(removed["figures"], 1)
        self.assertEqual(os.listdir(fig_dir), ["M03-1.svg"])
        self.assertIn("M02-1.svg", os.listdir(removed["trash"]))

    def test_a_generation_run_draws_figures_after_each_module(self):
        """With figures on, the pipeline asks for them right after a module's text and
        keeps them on a resume."""
        from test_build import CourseFixture  # noqa: F401 - the fixture above is the course
        asked = []

        def fake_ask(prompt, **kw):
            asked.append(kw.get("what", ""))
            if kw.get("what", "").startswith("the figures for"):
                return FIGURE_REPLY
            if "study data for module" in prompt:
                return json.dumps({"predict": "p",
                                   "quiz": [{"q": "Q", "options": ["a", "b", "c", "d"], "answer": 2, "why": "w"}],
                                   "cards": [{"front": "f", "back": "b"}], "elaborate": ["e"],
                                   "transfer": {"scenario": "s", "prompt": "p", "model": "m"}})
            if "one-tap questions" in prompt:
                return json.dumps([["a", "b", "c"]] * 3)
            return "# X — Y\n\n**Time:** 60 minutes\n\n## Why this matters\n\nt\n\n## Core concepts\n\nt\n\n## Exercise\n\nt\n"

        # the study data shaped the way generate() writes it, so the resume can extend it
        from coursekit.course import assessments as ck_assess
        assess = ck_assess.load_assessments(self.cfg)
        sugg = ck_assess.load_suggestions(self.cfg)
        data_dir = os.path.join(self.fixture.root, "data")
        shutil.rmtree(data_dir)
        files.write_json(os.path.join(data_dir, "assessments/all.json"), list(assess.values()))
        files.write_json(os.path.join(data_dir, "suggestions/all.json"), sugg)
        original = modelcall.ask
        modelcall.ask = fake_ask
        try:
            # drop M06 so the run has something to write, then resume it
            os.remove(self.modules[-1].source)
            job = jobs.Job("generate")
            result = generator.generate(job, self.tmp, os.path.join(self.tmp, "dist"),
                                        {"id": "fixture", "resume": True})
        finally:
            modelcall.ask = original
        self.assertEqual(result["modules"], 6)
        self.assertEqual(asked.count("the figures for M06"), 1, asked)
        self.assertEqual([w for w in asked if w.startswith("the figures for")],
                         ["the figures for M01", "the figures for M02", "the figures for M03",
                          "the figures for M04", "the figures for M05", "the figures for M06"],
                         "kept modules without figures get theirs too")
        progress = [e for e in job.since(0) if e["kind"] == "progress"]
        self.assertTrue(any("Figures for M06" in e.get("label", "") for e in progress), progress)


class TestStaleReviews(unittest.TestCase):
    """A review describes the module as it was; once the module changes it must say so."""

    def test_review_older_than_the_module_is_marked_stale(self):
        import tempfile
        import shutil
        tmp = tempfile.mkdtemp()
        try:
            module = os.path.join(tmp, "M01.md")
            with open(module, "w", encoding="utf-8") as fh:
                fh.write("# M01 - x\n\n## A\n\ntext\n")
            directory = reviews.reviews_dir(tmp, "c")
            os.makedirs(directory)
            written = os.path.getmtime(module) * 1000
            with open(os.path.join(directory, "M01.json"), "w", encoding="utf-8") as fh:
                json.dump({"verdict": "needs work", "at": int(written - 60_000)}, fh)
            with open(os.path.join(directory, "M02.json"), "w", encoding="utf-8") as fh:
                json.dump({"verdict": "solid", "at": int(written + 60_000)}, fh)
            loaded = reviews.load_reviews(tmp, "c", {"M01": module, "M02": module})
            self.assertTrue(loaded["M01"].get("stale"))
            self.assertEqual(loaded["M01"]["moduleChangedAt"], int(written))
            self.assertNotIn("stale", loaded["M02"])
            # Without sources nothing can be judged, and nothing is claimed.
            self.assertNotIn("stale", reviews.load_reviews(tmp, "c")["M01"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_owner_can_mark_a_module_good_and_take_it_back(self):
        import tempfile
        import shutil
        tmp = tempfile.mkdtemp()
        try:
            module = os.path.join(tmp, "M01.md")
            with open(module, "w", encoding="utf-8") as fh:
                fh.write("# M01 - x")
            path = os.path.join(reviews.reviews_dir(tmp, "c"), "M01.json")

            # Without a review: a record of its own, gone again when withdrawn.
            reviews.accept_module(tmp, "c", "M01", True)
            rv = reviews.load_reviews(tmp, "c", {"M01": module})["M01"]
            self.assertTrue(rv["accepted"] and rv["ownerOnly"])
            self.assertEqual(rv["verdict"], "solid")
            self.assertNotIn("stale", rv)
            reviews.accept_module(tmp, "c", "M01", False)
            self.assertFalse(os.path.exists(path))

            # Over a review: the findings stay, the mark comes and goes.
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"verdict": "needs work", "gaps": [{"issue": "x"}], "at": 1}, fh)
            reviews.accept_module(tmp, "c", "M01", True)
            rv = reviews.load_reviews(tmp, "c", {"M01": module})["M01"]
            self.assertEqual(rv["verdict"], "needs work", "the review is kept; the UI shows the mark")
            self.assertTrue(rv["accepted"])
            self.assertNotIn("ownerOnly", rv)
            self.assertNotIn("stale", rv, "the mark is newer than the file, so not stale")

            # The module changes after the mark: the mark is stale like a review would be.
            future = time.time() + 120
            os.utime(module, (future, future))
            rv = reviews.load_reviews(tmp, "c", {"M01": module})["M01"]
            self.assertTrue(rv.get("stale"))

            reviews.accept_module(tmp, "c", "M01", False)
            rv = reviews.load_reviews(tmp, "c")["M01"]
            self.assertNotIn("accepted", rv)
            self.assertEqual(rv["gaps"], [{"issue": "x"}])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)



class TestServerConventions(unittest.TestCase):
    """The route table and the Studio UI, checked without starting a server."""

    def test_index_html_loads_every_ui_script(self):
        """`ui/index.html` is Studio's manifest, the way `web/bundle.json` is the page's:
        it is the one place the load order lives, and a file added to `ui/js/` and not
        listed there boots under the smoke test and is silently absent in the browser."""
        listed = ui_scripts()
        on_disk = []
        base = os.path.join(PLATFORM, "studio", "ui", "js")
        for where, _dirs, names in os.walk(base):
            rel = os.path.relpath(where, base).replace(os.sep, "/")
            on_disk += ["%s/%s" % (rel, n) if rel != "." else n
                        for n in names if n.endswith(".js")]
        self.assertEqual(sorted(listed), sorted(on_disk))
        self.assertEqual(listed[-1], "router.js", "the router boots the app and stays last")

    def test_every_claude_action_in_the_ui_sends_a_model(self):
        """Every place the UI works with Claude picks its model: the writing forms through
        `modelChoice` / `modelBrief`, the one-click actions - review, figures, notebooks -
        through the Modules tab's pick (`quickModelBrief`). A call that sends none would
        silently run on the default while the page shows a pick."""
        ui = os.path.join(os.path.dirname(HERE), "studio", "ui", "js")

        def body(name, fn):
            with open(os.path.join(ui, name), encoding="utf-8") as fh:
                src = fh.read()
            start = src.index("async function %s(" % fn)
            return src[start:src.index("\n}\n", start)]

        forms = {("library.js", "startGeneration"): '"f"',
                 ("course/course.js", "extendCourse"): '"x"',
                 ("course/course.js", "rewriteModule"): '"rw-" + mid',
                 ("course/course.js", "resumeCourse"): 'prefix || "rs"'}
        for (name, fn), prefix in forms.items():
            self.assertIn("modelBrief(%s)" % prefix, body(name, fn), "%s in %s" % (fn, name))
        for name, fn in (("course/course.js", "reviewModule"),
                         ("course/figures.js", "drawFigures"),
                         ("course/notebooks.js", "writeNotebooks")):
            self.assertIn("quickModelBrief()", body(name, fn), "%s in %s" % (fn, name))
        with open(os.path.join(ui, "course", "course.js"), encoding="utf-8") as fh:
            self.assertIn("quickModelBar()", fh.read(), "the Modules tab shows the pick")

    def test_every_route_is_registered_once(self):
        from studio import server
        seen = {}
        for method, pattern, fn in server.ROUTES:
            key = (method, pattern.pattern)
            self.assertNotIn(key, seen, "%s %s is registered by %s and %s"
                             % (method, pattern.pattern, seen.get(key), fn.__name__))
            seen[key] = fn.__name__
        self.assertGreater(len(seen), 30)

    def test_every_documented_route_has_a_handler(self):
        """The table in the server docstring is the API reference; it must not drift."""
        import re
        from studio import server
        documented = re.findall(r"^\s+(GET|PUT|POST)\s+(/\S*)", server.__doc__, re.M)
        self.assertGreater(len(documented), 30)
        for method, path in documented:
            probe = re.sub(r"<[^>]+>", "x", path.split("?")[0]).replace("/x/x", "/x/M01")
            probe = probe.replace("/modules/x/", "/modules/M01/")
            hit = any(m == method and p.match(probe) for m, p, _ in server.ROUTES)
            self.assertTrue(hit, "%s %s is documented but no route matches %s" % (method, path, probe))

    @unittest.skipUnless(shutil.which("node"), "node not on PATH")
    def test_studio_ui_boots_under_node(self):
        """Every file in ui/js/, in the order index.html loads them, under the stub DOM:
        catches a name one file uses that no file declares."""
        import subprocess
        ui = os.path.join(PLATFORM, "studio", "ui", "js")
        # The shared design system loads first, exactly as index.html links it.
        files = [os.path.join(PLATFORM, "web", "js", "core", "dom.js")]
        files += [os.path.join(ui, *rel.split("/")) for rel in ui_scripts()]
        harness = os.path.join(HERE, "page_smoke.js")
        proc = subprocess.run(["node", harness] + files, capture_output=True, text=True,
                              encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("booted", proc.stdout)



NOTEBOOK_REPLY = """Here you go.
=== NOTEBOOK
section: core concepts
caption: Double a [number] and watch the output
--- markdown
Change **n** and rerun.
--- code
n = 3
print(n * 2)  # your turn
--- code
assert n * 2 == 6
=== NOTEBOOK
section: Exercise
caption: Only prose
--- markdown
No code here, so this one is dropped.
=== NOTEBOOK
section: No such section
caption: Orphan
--- code
print(1)
"""


class TestNotebookWriting(unittest.TestCase):
    """Notebooks for a module: the reply parsed notebook by notebook and cell by cell,
    coerced towards what the build accepts, written under notebooks/ as nbformat 4 and
    referenced from the named section; only for a course whose manifest declares them
    (CONVENTIONS.md "Notebooks")."""

    def setUp(self):
        import tempfile
        sys.path.insert(0, HERE)
        from test_build import CourseFixture
        from coursekit.course import loader as ck_loader
        self.tmp = tempfile.mkdtemp(prefix="studio-nb-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fixture = CourseFixture(self.tmp)
        self.fixture.edit_manifest(notebooks={"kernel": "python3", "packages": ["numpy"]})
        self.cfg = config.load(self.fixture.root)
        self.modules = ck_loader.load_modules(self.cfg)
        self.headings = ["Why this matters", "Core concepts", "Exercise"]

    def test_reply_parsing_and_coercion(self):
        from coursekit.course import notebooks as ck_notebooks
        from studio.authoring import notebooks
        raw = notebooks.parse_reply(NOTEBOOK_REPLY)
        self.assertEqual([nb["section"] for nb in raw], ["core concepts", "Exercise", "No such section"])
        self.assertEqual([c["type"] for c in raw[0]["cells"]], ["markdown", "code", "code"])
        self.assertEqual(raw[0]["cells"][1]["source"], "n = 3\nprint(n * 2)  # your turn")
        fixed = coerce.fix_notebooks(raw, self.headings, 3, 12)
        self.assertEqual(len(fixed), 1, "no code cell, or no such section: dropped")
        self.assertEqual(fixed[0]["section"], "Core concepts")
        self.assertEqual(fixed[0]["caption"], "Double a (number) and watch the output")
        self.assertEqual(len(coerce.fix_notebooks(raw, self.headings, 3, 2)[0]["cells"]), 2, "cells capped")
        self.assertEqual(coerce.fix_notebooks("junk", self.headings, 2, 12), [])
        self.assertEqual(notebooks.parse_reply("nothing here"), [])
        nb = notebooks.make_notebook(fixed[0]["cells"], "python3")
        self.assertEqual(nb["nbformat"], 4)
        self.assertEqual(nb["metadata"]["kernelspec"]["language"], "python")
        self.assertEqual([c["cell_type"] for c in nb["cells"]], ["markdown", "code", "code"])
        self.assertEqual(nb["cells"][1]["outputs"], [])
        self.assertEqual(ck_notebooks.problems(json.dumps(nb)), [])

    def test_write_notebooks_replaces_files_and_references_then_builds(self):
        from studio.authoring import notebooks
        plan = curriculum.plan_from_course(self.cfg, self.modules)
        self.assertEqual(plan["notebooks"], {"kernel": "python3", "packages": ["numpy"]})
        spec = plan["modules"][0]
        path = self.modules[0].source
        nb_dir = os.path.join(self.fixture.root, "notebooks")
        files.write_json(os.path.join(nb_dir, "M01-7.ipynb"), {"nbformat": 4, "cells": []})
        prompts_seen = []

        def fake_ask(prompt, **kw):
            prompts_seen.append(prompt)
            return NOTEBOOK_REPLY

        original = modelcall.ask
        modelcall.ask = fake_ask
        try:
            job = jobs.Job("notebooks")
            body = notebooks.write_notebooks(job, self.fixture.root, plan, spec,
                                             files.read_text(path), path)
        finally:
            modelcall.ask = original

        self.assertFalse(os.path.exists(os.path.join(nb_dir, "M01-7.ipynb")), "old notebooks go")
        self.assertEqual(os.listdir(nb_dir), ["M01-1.ipynb"])
        self.assertEqual(notebooks.references_in(body, "M01"), ["M01-1.ipynb"])
        self.assertIn("[Double a (number) and watch the output](notebooks/M01-1.ipynb)", body)
        self.assertEqual(files.read_text(path), body)
        self.assertEqual(self.fixture.problems(), [])
        self.assertNotIn("notebooks/", notebooks.strip_references(body, "M01"))
        events = [e for e in job.since(0) if e["kind"] == "notebooks"]
        self.assertEqual((events[0]["count"], events[0]["cells"]), (1, 3))
        text = prompts_seen[0]
        for needle in ("=== NOTEBOOK", "--- code", "python3", "numpy", "- Core concepts", "M01",
                       "# your turn", '"Exercise" is the home', "predict what the first code cell",
                       "a cell that raises", 'Never "Why this matters"'):
            self.assertIn(needle, text)
        self.assertIn("up to %d Jupyter notebooks" % notebooks.NOTEBOOKS_PER_MODULE, text)
        _, result = self.fixture.build(os.path.join(self.tmp, "dist"))
        self.assertEqual(result.notebooks, 1)

    def test_notebooks_job_needs_the_manifest_and_targets_modules_without_any(self):
        original = modelcall.ask
        modelcall.ask = lambda prompt, **kw: NOTEBOOK_REPLY
        dist = os.path.join(self.tmp, "dist")
        try:
            result = editing.notebooks_job(jobs.Job("notebooks"), self.tmp, dist, "fixture", {"module": "M02"})
            self.assertEqual(result["written"], ["M02"])
            result = editing.notebooks_job(jobs.Job("notebooks"), self.tmp, dist, "fixture", {})
            self.assertEqual(result["written"], ["M01", "M03", "M04", "M05", "M06"], "M02 already had one")
            with self.assertRaises(GenerationError):
                editing.notebooks_job(jobs.Job("notebooks"), self.tmp, dist, "fixture", {})
            self.fixture.edit_manifest(notebooks=None)
            with self.assertRaisesRegex(GenerationError, "declares no notebooks"):
                editing.notebooks_job(jobs.Job("notebooks"), self.tmp, dist, "fixture", {"module": "M01"})
        finally:
            modelcall.ask = original

    def test_settings_form_turns_notebooks_on_and_off(self):
        from studio import manage
        root = self.fixture.root
        self.assertEqual(manage.settings(root)["notebooks"], {"kernel": "python3", "packages": ["numpy"]})
        out = manage.update_settings(root, {"notebooks": {"kernel": "", "packages": "pandas, matplotlib scipy"}})
        self.assertEqual(out["notebooks"], {"kernel": "python3", "packages": ["pandas", "matplotlib", "scipy"]})
        out = manage.update_settings(root, {"notebooks": None})
        self.assertIsNone(out["notebooks"])
        self.assertNotIn("notebooks", files.read_json(os.path.join(root, "course.json")))

    def test_remove_module_takes_its_notebooks_to_the_trash(self):
        from studio import manage
        nb_dir = os.path.join(self.fixture.root, "notebooks")
        files.write_json(os.path.join(nb_dir, "M01-1.ipynb"), {"nbformat": 4, "cells": []})
        removed = manage.remove_module(self.fixture.root, "M01", os.path.join(self.tmp, "trash"))
        self.assertEqual(removed["notebooks"], 1)
        self.assertFalse(os.path.exists(os.path.join(nb_dir, "M01-1.ipynb")))

    def test_plan_decides_notebooks_and_the_person_can_overrule(self):
        from studio.authoring import prompts
        base = {"title": "Data", "parts": [{"id": "p1", "name": "P", "hours": 3, "dir": "d"}],
                "modules": [{"id": "M01", "part": "p1", "title": "A"}],
                "notebooks": {"kernel": "python3", "packages": ["pandas", 3, " "]}}
        fresh = lambda **over: dict(json.loads(json.dumps(base)), **over)  # noqa: E731
        out = curriculum.normalise_plan(fresh(), "data", 3, {})
        self.assertEqual(out["notebooks"], {"kernel": "python3", "packages": ["pandas"]})
        self.assertEqual(curriculum.plan_to_manifest(out, "data")["notebooks"], out["notebooks"])
        out = curriculum.normalise_plan(fresh(), "data", 3, {"notebooks": "no"})
        self.assertEqual(out["notebooks"], {})
        self.assertNotIn("notebooks", curriculum.plan_to_manifest(out, "data"))
        out = curriculum.normalise_plan(fresh(notebooks=None), "data", 3, {"notebooks": True})
        self.assertEqual(out["notebooks"], {"kernel": "python3", "packages": []})
        self.assertEqual(curriculum.wants_notebooks({}), "auto")
        self.assertIn('"notebooks" is null', prompts.plan("x", 3, "a", "p", [], notebooks="no"))
        self.assertIn('"notebooks": null |', prompts.plan("x", 3, "a", "p", []))

    def test_a_generation_run_writes_notebooks_after_each_module(self):
        """With the manifest declaring notebooks, the pipeline asks for them right after a
        module's text (and its figures) and keeps them on a resume."""
        asked = []

        def fake_ask(prompt, **kw):
            asked.append(kw.get("what", ""))
            if kw.get("what", "").startswith("the notebooks for"):
                return NOTEBOOK_REPLY
            if kw.get("what", "").startswith("the figures for"):
                return FIGURE_REPLY
            if "study data for module" in prompt:
                return json.dumps({"predict": "p",
                                   "quiz": [{"q": "Q", "options": ["a", "b", "c", "d"], "answer": 2, "why": "w"}],
                                   "cards": [{"front": "f", "back": "b"}], "elaborate": ["e"],
                                   "transfer": {"scenario": "s", "prompt": "p", "model": "m"}})
            if "one-tap questions" in prompt:
                return json.dumps([["a", "b", "c"]] * 3)
            return "# X — Y\n\n**Time:** 60 minutes\n\n## Why this matters\n\nt\n\n## Core concepts\n\nt\n\n## Exercise\n\nt\n"

        from coursekit.course import assessments as ck_assess
        assess = ck_assess.load_assessments(self.cfg)
        sugg = ck_assess.load_suggestions(self.cfg)
        data_dir = os.path.join(self.fixture.root, "data")
        shutil.rmtree(data_dir)
        files.write_json(os.path.join(data_dir, "assessments/all.json"), list(assess.values()))
        files.write_json(os.path.join(data_dir, "suggestions/all.json"), sugg)
        original = modelcall.ask
        modelcall.ask = fake_ask
        try:
            os.remove(self.modules[-1].source)
            job = jobs.Job("generate")
            result = generator.generate(job, self.tmp, os.path.join(self.tmp, "dist"),
                                        {"id": "fixture", "resume": True})
        finally:
            modelcall.ask = original
        self.assertEqual(result["modules"], 6)
        self.assertEqual(result["notebooks"], 6)
        self.assertEqual([w for w in asked if w.startswith("the notebooks for")],
                         ["the notebooks for M0%d" % n for n in range(1, 7)],
                         "kept modules without notebooks get theirs too")
        progress = [e for e in job.since(0) if e["kind"] == "progress"]
        self.assertTrue(any("Notebooks for M06" in e.get("label", "") for e in progress), progress)
        self.assertTrue(os.path.isfile(os.path.join(self.fixture.root, "notebooks", "M06-1.ipynb")))

    def test_a_resume_can_leave_figures_and_notebooks_out(self):
        """The Resume form's two switches reach the run as `figures` and `notebooks`; off
        means no call for either, even in a course that declares notebooks."""
        asked = []

        def fake_ask(prompt, **kw):
            asked.append(kw.get("what", ""))
            if "study data for module" in prompt:
                return json.dumps({"predict": "p",
                                   "quiz": [{"q": "Q", "options": ["a", "b", "c", "d"], "answer": 2, "why": "w"}],
                                   "cards": [{"front": "f", "back": "b"}], "elaborate": ["e"],
                                   "transfer": {"scenario": "s", "prompt": "p", "model": "m"}})
            if "one-tap questions" in prompt:
                return json.dumps([["a", "b", "c"]] * 3)
            return "# X — Y\n\n**Time:** 60 minutes\n\n## Why this matters\n\nt\n\n## Core concepts\n\nt\n\n## Exercise\n\nt\n"

        from coursekit.course import assessments as ck_assess
        assess = ck_assess.load_assessments(self.cfg)
        sugg = ck_assess.load_suggestions(self.cfg)
        data_dir = os.path.join(self.fixture.root, "data")
        shutil.rmtree(data_dir)
        files.write_json(os.path.join(data_dir, "assessments/all.json"), list(assess.values()))
        files.write_json(os.path.join(data_dir, "suggestions/all.json"), sugg)
        original = modelcall.ask
        modelcall.ask = fake_ask
        try:
            os.remove(self.modules[-1].source)
            result = generator.generate(jobs.Job("generate"), self.tmp, os.path.join(self.tmp, "dist"),
                                        {"id": "fixture", "resume": True, "figures": False,
                                         "notebooks": False})
        finally:
            modelcall.ask = original
        self.assertEqual(result["modules"], 6)
        self.assertEqual([w for w in asked if w.startswith(("the figures for", "the notebooks for"))], [])
        self.assertEqual(result["notebooks"], 0)

    def test_the_model_a_form_picked_reaches_every_call_of_the_run(self):
        """`model` in the brief names the model for that run only: every CLI call asks for it."""
        models = []

        def fake_ask(prompt, **kw):
            models.append(kw.get("model"))
            if "study data for module" in prompt:
                return json.dumps({"predict": "p",
                                   "quiz": [{"q": "Q", "options": ["a", "b", "c", "d"], "answer": 2, "why": "w"}],
                                   "cards": [{"front": "f", "back": "b"}], "elaborate": ["e"],
                                   "transfer": {"scenario": "s", "prompt": "p", "model": "m"}})
            if "one-tap questions" in prompt:
                return json.dumps([["a", "b", "c"]] * 3)
            return "# X — Y\n\n**Time:** 60 minutes\n\n## Why this matters\n\nt\n\n## Core concepts\n\nt\n\n## Exercise\n\nt\n"

        from coursekit.course import assessments as ck_assess
        assess = ck_assess.load_assessments(self.cfg)
        sugg = ck_assess.load_suggestions(self.cfg)
        data_dir = os.path.join(self.fixture.root, "data")
        shutil.rmtree(data_dir)
        files.write_json(os.path.join(data_dir, "assessments/all.json"), list(assess.values()))
        files.write_json(os.path.join(data_dir, "suggestions/all.json"), sugg)
        original = modelcall.ask
        modelcall.ask = fake_ask
        try:
            os.remove(self.modules[-1].source)
            generator.generate(jobs.Job("generate"), self.tmp, os.path.join(self.tmp, "dist"),
                               {"id": "fixture", "resume": True, "figures": False,
                                "notebooks": False, "model": "haiku"})
        finally:
            modelcall.ask = original
        self.assertTrue(models, "the missing module was written")
        self.assertEqual(set(models), {"haiku"})


class TestJupyter(unittest.TestCase):
    """Studio only asks whether the Jupyter server is up and tells a served page where it
    is; the token goes to the page through /api/jupyter and to nothing else, and a dead
    server is not probed on every poll (CONVENTIONS.md "Notebooks")."""

    def test_view_and_the_public_view(self):
        from coursekit.settings import SETTINGS
        from studio import jupyter
        original = jupyter.probe
        jupyter.probe = lambda force=False: "2.14.0"
        try:
            view = jupyter.view()
            self.assertTrue(view["available"])
            self.assertEqual(view["url"], SETTINGS.jupyter_url)
            self.assertEqual(view["token"], SETTINGS.get("jupyter.token"))
            self.assertTrue(view["config"].endswith("jupyter_server_config.py"))
            self.assertTrue(os.path.isfile(view["config"]))
            public = catalog.jupyter_public()
            self.assertNotIn("token", public)
            self.assertTrue(public["available"])
            jupyter.probe = lambda force=False: None
            self.assertFalse(jupyter.view()["available"])
        finally:
            jupyter.probe = original

    def test_a_dead_server_is_probed_once_per_cache_window(self):
        import urllib.request
        from coursekit.settings import SETTINGS
        from studio import jupyter
        calls = []

        def down(url, timeout=0):
            calls.append(url)
            raise OSError("connection refused")

        original = urllib.request.urlopen
        urllib.request.urlopen = down
        try:
            self.assertIsNone(jupyter.probe(force=True))
            self.assertIsNone(jupyter.probe())
            self.assertFalse(jupyter.available())
        finally:
            urllib.request.urlopen = original
        self.assertEqual(len(calls), 1, "cached")
        self.assertEqual(calls[0], SETTINGS.jupyter_internal_url + "/api/")


class TestTransfer(unittest.TestCase):
    """Moving a whole course in or out. Nothing existing is ever overwritten, and the folder
    is always renamed to the id inside its `course.json` - the folder name *is* the id."""

    def setUp(self):
        sys.path.insert(0, HERE)
        from test_build import CourseFixture
        self.tmp = tempfile.mkdtemp(prefix="studio-transfer-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.courses = os.path.join(self.tmp, "courses")
        os.makedirs(self.courses)
        self.fixture = CourseFixture(self.courses)

    def _zip(self):
        from studio import transfer
        return transfer.export_zip(os.path.join(self.courses, "fixture"))

    def test_the_export_leaves_git_and_the_tool_folders_behind(self):
        import io as _io
        import zipfile
        os.makedirs(os.path.join(self.courses, "fixture", ".git"))
        with open(os.path.join(self.courses, "fixture", ".git", "HEAD"), "w") as fh:
            fh.write("ref: refs/heads/main")
        names = zipfile.ZipFile(_io.BytesIO(self._zip())).namelist()
        self.assertIn("fixture/course.json", names)
        self.assertFalse([n for n in names if ".git" in n], "a zip is the course, not the repo")

    def test_exporting_something_that_is_not_a_course_is_refused(self):
        from studio import transfer
        with self.assertRaises(CourseError):
            transfer.export_zip(self.tmp)

    def test_the_folder_is_renamed_to_the_id_in_the_manifest(self):
        from studio import transfer
        data = self._zip()
        shutil.rmtree(os.path.join(self.courses, "fixture"))
        elsewhere = os.path.join(self.tmp, "other-library")
        course = transfer.import_zip(elsewhere, data)
        self.assertEqual(course["id"], "fixture")
        self.assertEqual(course["modules"], 6)
        self.assertTrue(os.path.isfile(os.path.join(elsewhere, "fixture", "course.json")))

    def test_a_zip_whose_files_sit_at_its_root_works_too(self):
        import io as _io
        import zipfile
        from studio import transfer
        source = os.path.join(self.courses, "fixture")
        buf = _io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for where, _dirs, names in os.walk(source):
                for name in names:
                    full = os.path.join(where, name)
                    zf.write(full, os.path.relpath(full, source).replace(os.sep, "/"))
        elsewhere = os.path.join(self.tmp, "flat")
        self.assertEqual(transfer.import_zip(elsewhere, buf.getvalue())["id"], "fixture")

    def test_an_import_never_overwrites_what_is_there(self):
        from studio import transfer
        with self.assertRaises(CourseError):
            transfer.import_zip(self.courses, self._zip())

    def test_a_member_climbing_out_of_the_folder_is_dropped(self):
        """A zip is a file from anywhere; its member names are not to be trusted."""
        import io as _io
        import zipfile
        from studio import transfer
        with open(self.fixture.cfg_path, encoding="utf-8") as fh:
            manifest = fh.read()
        buf = _io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("c/course.json", manifest)
            zf.writestr("c/../../escaped.txt", "no")
        elsewhere = os.path.join(self.tmp, "safe")
        transfer.import_zip(elsewhere, buf.getvalue())
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "escaped.txt")))

    def test_only_a_repository_url_is_ever_a_subprocess_argument(self):
        from studio import transfer
        for good in ("https://example.com/someone/course.git", "git@example.com:someone/course"):
            self.assertTrue(transfer.is_git_url(good), good)
        for bad in ("", "file:///etc", "https://example.com", "; rm -rf /",
                    "https://example.com/a b", None):
            self.assertFalse(transfer.is_git_url(bad), bad)

    def _git_says(self, run):
        import subprocess
        from studio import transfer
        self.addCleanup(setattr, transfer.shutil, "which", transfer.shutil.which)
        self.addCleanup(setattr, transfer.subprocess, "run", transfer.subprocess.run)
        transfer.shutil.which = lambda name: "/usr/bin/git"
        transfer.subprocess.run = run
        del subprocess

    def test_a_clone_that_fails_says_the_last_thing_git_said(self):
        import subprocess
        from studio import transfer
        self._git_says(lambda *a, **kw: subprocess.CompletedProcess(
            a[0], 128, "", "remote: not found\nfatal: repository not found\n"))
        with self.assertRaises(CourseError) as caught:
            transfer.import_git(self.courses, "https://example.com/nope.git")
        self.assertIn("repository not found", str(caught.exception))

    def test_a_clone_that_hangs_is_stopped_and_said_to_have_been(self):
        import subprocess
        from studio import transfer

        def hang(*a, **kw):
            raise subprocess.TimeoutExpired(a[0], kw.get("timeout", 1))

        self._git_says(hang)
        with self.assertRaises(CourseError) as caught:
            transfer.import_git(self.courses, "https://example.com/slow.git", timeout=1)
        self.assertIn("stopped", str(caught.exception))


class TestSearch(unittest.TestCase):
    """Every course at once, through the build's own loader."""

    def setUp(self):
        sys.path.insert(0, HERE)
        from test_build import CourseFixture
        self.tmp = tempfile.mkdtemp(prefix="studio-search-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.courses = os.path.join(self.tmp, "courses")
        os.makedirs(self.courses)
        self.fixture = CourseFixture(self.courses)

    def find(self, query):
        from studio import search
        return search.search(self.courses, query)

    def test_one_letter_is_not_a_search(self):
        self.assertEqual(self.find("a"), {"query": "a", "hits": [], "courses": 0})

    def test_a_heading_outranks_a_passage(self):
        hits = self.find("core concepts")["hits"]
        self.assertEqual(hits[0]["kind"], "section")
        self.assertEqual(hits[0]["text"], "Core concepts")

    def test_a_passage_comes_back_with_the_words_around_it(self):
        hit = [h for h in self.find("stated plainly")["hits"] if h["kind"] == "passage"][0]
        self.assertIn("stated plainly", hit["text"])
        self.assertIn("heading", hit)

    def test_a_course_that_does_not_load_is_skipped_rather_than_ending_the_search(self):
        broken = os.path.join(self.courses, "broken")
        os.makedirs(broken)
        with open(os.path.join(broken, "course.json"), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        found = self.find("lesson")
        self.assertEqual(found["courses"], 1)
        self.assertTrue(found["hits"])

    def test_a_library_that_is_not_there_yet_is_no_hits(self):
        from studio import search
        self.assertEqual(search.search(os.path.join(self.tmp, "nowhere"), "anything")["hits"], [])


class TestOwnerVerdicts(unittest.TestCase):
    """Mark as good is the owner's own verdict, stored in the same file as the model's
    review so a module row shows one thing."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="studio-verdict-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_marking_a_module_good_without_a_review_says_so(self):
        record = reviews.accept_module(self.tmp, "c", "M01", True)
        self.assertTrue(record["ownerOnly"])
        self.assertEqual(record["verdict"], "solid")
        self.assertIn("M01", reviews.load_reviews(self.tmp, "c"))

    def test_withdrawing_it_removes_the_record_that_was_only_the_mark(self):
        reviews.accept_module(self.tmp, "c", "M01", True)
        self.assertEqual(reviews.accept_module(self.tmp, "c", "M01", False), {})
        self.assertEqual(reviews.load_reviews(self.tmp, "c"), {})

    def test_withdrawing_it_keeps_a_real_review_underneath(self):
        path = os.path.join(reviews.reviews_dir(self.tmp, "c"), "M02.json")
        files.write_json(path, {"module": "M02", "verdict": "thin", "gaps": ["g"],
                                "errors": [], "quiz": [], "rewriteBrief": "b", "at": 1})
        reviews.accept_module(self.tmp, "c", "M02", True)
        record = reviews.accept_module(self.tmp, "c", "M02", False)
        self.assertNotIn("accepted", record)
        self.assertEqual(record["verdict"], "thin", "a mark never changes what the model found")

    def test_a_file_that_cannot_be_read_is_skipped_not_fatal(self):
        path = os.path.join(reviews.reviews_dir(self.tmp, "c"), "M03.json")
        files.write_text(path, "{not json")
        self.assertEqual(reviews.load_reviews(self.tmp, "c"), {})


class TestReviewJob(unittest.TestCase):
    """A review is an opinion about content, so it is stored beside the course, not in it."""

    def setUp(self):
        sys.path.insert(0, HERE)
        from test_build import CourseFixture
        self.tmp = tempfile.mkdtemp(prefix="studio-review-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.courses = os.path.join(self.tmp, "courses")
        self.state = os.path.join(self.tmp, "state")
        os.makedirs(self.courses)
        self.fixture = CourseFixture(self.courses)
        self.addCleanup(setattr, modelcall, "ask", modelcall.ask)

    def _answer(self, payload):
        modelcall.ask = lambda prompt, **kw: json.dumps(payload)

    def test_what_the_model_found_is_stored_under_the_state_directory(self):
        self._answer({"verdict": "solid", "summary": "Reads well.", "gaps": ["one gap"],
                      "errors": [], "quiz": [], "rewriteBrief": "Tighten the opening."})
        job = jobs.Job("review")
        result = reviews.review(job, self.courses, self.state, "fixture", "M02", {"model": "opus"})
        self.assertEqual(result["verdict"], "solid")
        self.assertEqual(job.meta, {"course": "fixture", "module": "M02"})
        stored = reviews.load_reviews(self.state, "fixture")["M02"]
        self.assertEqual(stored["title"], "Lesson 2")
        self.assertFalse(os.path.isdir(os.path.join(self.courses, "fixture", "reviews")))

    def test_a_module_that_is_not_in_the_course_is_refused(self):
        self._answer({"verdict": "solid"})
        with self.assertRaises(GenerationError):
            reviews.review(jobs.Job("review"), self.courses, self.state, "fixture", "M99", {})

    def test_the_prompt_is_the_course_s_own_when_it_has_one(self):
        from coursekit.course import loader as ck_loader
        root = os.path.join(self.courses, "fixture")
        overrides.put(root, "M01", "review", "Only answer with the word HELLO.")
        cfg = config.load(root)
        modules = ck_loader.load_modules(cfg)
        plan = curriculum.plan_from_course(cfg, modules)
        spec = next(m for m in plan["modules"] if m["id"] == "M01")
        prompt = reviews.review_prompt(plan, spec, "the module text", {}, root)
        self.assertIn("HELLO", prompt)



class TestJupyterServer(unittest.TestCase):
    """Studio only probes Jupyter and tells the page where it is; it never runs it itself."""

    def setUp(self):
        from studio import jupyter
        jupyter._probe.update(at=0.0, version=None)
        self.addCleanup(jupyter._probe.update, dict(at=0.0, version=None))

    def test_a_server_that_answers_is_reported_with_its_version(self):
        import urllib.request
        from studio import jupyter

        class Answer:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'{"version": "7.1.2"}'

        self.addCleanup(setattr, urllib.request, "urlopen", urllib.request.urlopen)
        urllib.request.urlopen = lambda url, timeout=0: Answer()
        self.assertEqual(jupyter.probe(force=True), "7.1.2")
        self.assertTrue(jupyter.available())
        view = jupyter.view()
        self.assertTrue(view["available"])
        self.assertEqual(view["url"], SETTINGS.jupyter_url)

    def test_the_token_the_page_is_given_is_never_in_a_built_page(self):
        """It reaches the page through this route on Studio's loopback origin instead."""
        from studio import jupyter
        self.assertIn("token", jupyter.view())
        self.assertNotIn("jupyter", json.dumps(SETTINGS.page()).lower())

    def test_running_it_needs_the_package_and_says_so_when_it_is_absent(self):
        from studio import jupyter
        self.addCleanup(setattr, jupyter, "installed", jupyter.installed)
        jupyter.installed = lambda: False
        import contextlib
        import io as _io
        with contextlib.redirect_stderr(_io.StringIO()):
            self.assertEqual(jupyter.run(), 1)

    def test_running_it_hands_the_courses_directory_to_the_server(self):
        from studio import jupyter
        seen = {}

        def call(argv, **kw):
            seen["argv"], seen["env"] = argv, kw.get("env") or {}
            return 0

        self.addCleanup(setattr, jupyter, "installed", jupyter.installed)
        self.addCleanup(setattr, jupyter.subprocess, "call", jupyter.subprocess.call)
        jupyter.installed = lambda: True
        jupyter.subprocess.call = call
        import contextlib
        import io as _io
        with contextlib.redirect_stdout(_io.StringIO()):
            self.assertEqual(jupyter.run(), 0)
        self.assertIn(jupyter.CONFIG_FILE, " ".join(seen["argv"]))
        self.assertEqual(seen["env"]["COURSES_DIR"], jupyter.COURSES_DIR)


class TestDiscoveryRun(unittest.TestCase):
    """A whole check: every provider asked what it knows, the answers merged per provider,
    a report written. Nobody has to type a new model's id."""

    class Source:
        """A provider that answers `catalog()` however the test says."""

        def __init__(self, name, models=(), known=None, ok=True, complete=False, error=""):
            self.name, self.label, self.kind = name, name.title(), "cli"
            self.catalog_is_complete = complete
            self._answer = {"ok": ok, "models": [dict(m) for m in models],
                            "known": dict(known or {}), "error": error}

        def available(self):
            return True

        def catalog(self, timeout=0):
            return dict(self._answer)

    def setUp(self):
        from studio import discover
        self.discover = discover
        self.tmp = tempfile.mkdtemp(prefix="studio-discovery-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(setattr, discover, "report_path", discover.report_path)
        discover.report_path = lambda: os.path.join(self.tmp, "models-discovery.json")

    def sources(self, *providers):
        from coursekit import llm
        self.addCleanup(setattr, llm, "providers", llm.providers)
        llm.providers = lambda all_of_them=False: list(providers)

    def listed(self, *entries):
        """The model list in use, written as the layer Studio saves - the real path."""
        path = os.path.join(self.tmp, "settings.json")
        files.write_json(path, {"models": {"list": [dict(e) for e in entries],
                                           "default": entries[0]["alias"]}})
        was = SETTINGS.studio_file

        def back():
            SETTINGS.studio_file = was
            SETTINGS.reload()

        self.addCleanup(back)
        SETTINGS.studio_file = path
        SETTINGS.reload()

    def test_a_model_a_provider_offers_and_the_list_lacks_is_added_under_that_provider(self):
        self.sources(self.Source("one", [{"id": "one-new"}],
                                 known={"one-old": "", "one-new": ""}))
        self.listed({"provider": "one", "id": "one-old", "alias": "old", "label": "Old"})
        report = self.discover.run(save=False)
        self.assertEqual([m["id"] for m in report["added"]], ["one-new"])
        self.assertEqual([m["provider"] for m in report["added"]], ["one"])
        self.assertTrue(report["changed"])
        self.assertEqual(report["sources"]["one"]["offered"], 1)

    def test_one_provider_says_nothing_about_another_s_models(self):
        """A Claude Code build says nothing about what OpenAI offers, and is not allowed to."""
        self.sources(self.Source("one", [{"id": "shared"}], known={"shared": ""}),
                     self.Source("two", ok=False, error="could not be read"))
        self.listed({"provider": "two", "id": "two-only", "alias": "t", "label": "T"})
        report = self.discover.run(save=False)
        self.assertEqual(report["removed"], [], "a source that cannot answer removes nothing")
        self.assertEqual([m["id"] for m in report["added"]], ["shared"])
        self.assertFalse(report["sources"]["two"]["ok"])

    def test_a_provider_s_models_are_never_all_removed(self):
        self.sources(self.Source("one", known={"something-else": ""}, complete=True))
        self.listed({"provider": "one", "id": "one-old", "alias": "old", "label": "Old"})
        report = self.discover.run(save=False)
        self.assertEqual(report["removed"], [], "the last one stays whatever the source says")

    def test_a_check_that_finds_nothing_new_says_so_and_writes_a_report(self):
        self.sources(self.Source("one", [{"id": "one-old"}], known={"one-old": ""}))
        self.listed({"provider": "one", "id": "one-old", "alias": "old", "label": "Old"})
        report = self.discover.run(save=True)
        self.assertFalse(report["changed"])
        self.assertIs(self.discover.status()["last"]["changed"], False)

    def test_the_new_list_is_saved_and_is_the_one_in_use(self):
        self.sources(self.Source("anthropic", [{"id": "a-new-one"}],
                                 known={"an-old-one": "", "a-new-one": ""}))
        self.listed({"provider": "anthropic", "id": "an-old-one", "alias": "old", "label": "Old"})
        self.discover.run(save=True)
        self.assertIn("a-new-one", [m["id"] for m in SETTINGS.models])

    def test_a_list_the_validator_refuses_is_reported_rather_than_thrown(self):
        """`models.replace` is the same gate the settings page goes through."""
        self.sources(self.Source("one", [{"id": "one-new"}],
                                 known={"one-old": "", "one-new": ""}))
        self.listed({"provider": "one", "id": "one-old", "alias": "old", "label": "Old"})
        report = self.discover.run(save=True)
        self.assertIn("no provider called", report["error"])

    def test_the_settings_page_is_told_what_would_be_asked(self):
        self.sources(self.Source("one", [{"id": "x"}]))
        status = self.discover.status()
        self.assertEqual([p["name"] for p in status["providers"]], ["one"])
        self.assertEqual(status["hours"], self.discover.HOURS)

    def test_a_report_that_cannot_be_read_is_not_a_crash(self):
        files.write_text(self.discover.report_path(), "{not json")
        self.assertIsNone(self.discover.status()["last"])

    def test_the_schedule_is_off_when_the_setting_is_zero(self):
        self.addCleanup(setattr, self.discover, "HOURS", self.discover.HOURS)
        self.discover.HOURS = 0
        self.assertFalse(self.discover.schedule())

if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Self-tests for Course Studio.

    python platform/tests/test_studio.py

Nothing here calls Claude or opens a socket. What is tested is the part that has to be right
when a model returns something slightly wrong: JSON extraction, the coercion of model output
into shapes the validator accepts, and the job lifecycle including the approval gate.
"""

from __future__ import annotations

import json
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = os.path.dirname(HERE)
sys.path.insert(0, PLATFORM)

from studio import claude_cli, generator, jobs  # noqa: E402


class TestJsonExtraction(unittest.TestCase):
    """Models wrap JSON in fences and prefaces roughly half the time."""

    def test_plain(self):
        self.assertEqual(json.loads(claude_cli._slice_json('{"a": 1}')), {"a": 1})

    def test_code_fence(self):
        text = '```json\n{"a": 1}\n```'
        self.assertEqual(json.loads(claude_cli._slice_json(text)), {"a": 1})

    def test_preamble_and_trailer(self):
        text = 'Sure! Here is the JSON you asked for:\n\n{"a": [1, 2]}\n\nLet me know.'
        self.assertEqual(json.loads(claude_cli._slice_json(text)), {"a": [1, 2]})

    def test_array_at_top_level(self):
        self.assertEqual(json.loads(claude_cli._slice_json('Here:\n[[1],[2]]')), [[1], [2]])

    def test_braces_inside_strings_do_not_confuse_it(self):
        text = 'Note:\n{"q": "what is {this} for?", "n": {"deep": "}"}}'
        parsed = json.loads(claude_cli._slice_json(text))
        self.assertEqual(parsed["q"], "what is {this} for?")
        self.assertEqual(parsed["n"], {"deep": "}"})

    def test_escaped_quote_inside_string(self):
        text = r'{"q": "he said \"no\" firmly", "a": 1}'
        self.assertEqual(json.loads(claude_cli._slice_json(text))["a"], 1)

    def test_strip_fence_on_markdown(self):
        self.assertEqual(claude_cli.strip_fence("```markdown\n# Title\n```"), "# Title")


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
        from coursekit import loader as ck_loader
        md = ("# M01 — T\n\n**Time:** 60 minutes\n\n"
              "## A\n\nalpha\n\n---\n\n## B\n\n## C\n\ngamma\n")
        self.assertEqual(generator.headings_of(md),
                         [s.heading for s in ck_loader.parse_sections(md)])


class TestSuggestionCoercion(unittest.TestCase):
    HEADINGS = ["One", "Two", "Three"]

    def ok(self, rows):
        self.assertEqual(len(rows), len(self.HEADINGS))
        for row in rows:
            self.assertEqual(len(row), generator.QUESTIONS_PER_SECTION)
            self.assertTrue(all(isinstance(q, str) and q for q in row))

    def test_exact_input_is_preserved(self):
        raw = [["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"]]
        rows = generator._fix_suggestions(raw, self.HEADINGS)
        self.ok(rows)
        self.assertEqual(rows, raw)

    def test_too_few_sets_are_padded(self):
        self.ok(generator._fix_suggestions([["a", "b", "c"]], self.HEADINGS))

    def test_too_many_sets_are_trimmed(self):
        raw = [["a", "b", "c"]] * 9
        self.ok(generator._fix_suggestions(raw, self.HEADINGS))

    def test_ragged_rows_are_filled_and_capped(self):
        self.ok(generator._fix_suggestions([["a"], ["b", "c", "d", "e", "f"], []], self.HEADINGS))

    def test_flat_list_is_regrouped(self):
        rows = generator._fix_suggestions(["a", "b", "c", "d", "e", "f", "g", "h", "i"],
                                          self.HEADINGS)
        self.ok(rows)
        self.assertEqual(rows[0], ["a", "b", "c"])

    def test_garbage_still_yields_a_valid_shape(self):
        for raw in (None, {}, "nope", [None, 3, {"a": 1}]):
            self.ok(generator._fix_suggestions(raw, self.HEADINGS))


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
        out = generator._fix_assessment(self.base(), "M01")
        self.assertEqual(out["id"], "M01")
        self.assertEqual(out["quiz"][0]["answer"], 1)

    def test_out_of_range_answer_is_clamped(self):
        for bad, expected in ((9, 3), (-4, 0), ("2", 2), (None, 0)):
            quiz = [{"q": "Q", "options": ["a", "b", "c", "d"], "answer": bad, "why": "w"}]
            out = generator._fix_assessment(self.base(quiz=quiz), "M01")
            self.assertEqual(out["quiz"][0]["answer"], expected, "answer=%r" % bad)

    def test_missing_why_is_filled(self):
        quiz = [{"q": "Q", "options": ["a", "b"], "answer": 0}]
        out = generator._fix_assessment(self.base(quiz=quiz), "M01")
        self.assertTrue(out["quiz"][0]["why"])

    def test_quiz_is_capped(self):
        quiz = [{"q": "Q", "options": ["a", "b"], "answer": 0, "why": "w"}] * 40
        out = generator._fix_assessment(self.base(quiz=quiz), "M01")
        self.assertEqual(len(out["quiz"]), generator.QUIZ_ITEMS)

    def test_half_written_cards_are_dropped(self):
        cards = [{"front": "Q", "back": ""}, {"front": "", "back": "A"}, {"front": "Q2", "back": "A2"}]
        out = generator._fix_assessment(self.base(cards=cards), "M01")
        self.assertEqual(out["cards"], [{"front": "Q2", "back": "A2"}])

    def test_unusable_input_raises_rather_than_shipping_empty(self):
        with self.assertRaises(generator.GenerationError):
            generator._fix_assessment(self.base(quiz=[]), "M01")
        with self.assertRaises(generator.GenerationError):
            generator._fix_assessment(self.base(cards=[]), "M01")
        with self.assertRaises(generator.GenerationError):
            generator._fix_assessment("not an object", "M01")

    def test_output_passes_the_real_validator(self):
        from coursekit import validate as ck_validate

        class FakeModule:
            id, source = "M01", "x.md"
            sections = [1, 2]

        assess = {"M01": generator._fix_assessment(self.base(), "M01")}
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
        out = generator.normalise_plan(self.plan(), "bread", 6, self.BRIEF)
        self.assertEqual(out["subject"], "bread")
        self.assertEqual(out["practitioner"], "baker")
        self.assertTrue(out["tutorPersona"].endswith("."))
        self.assertEqual(len(out["modules"][0]["sections"]), 7)

    def test_module_ids_are_renumbered_sequentially(self):
        modules = [{"id": "M05", "part": "p1", "title": "A"},
                   {"id": "M05", "part": "p2", "title": "B"},
                   {"id": "zzz", "part": "p1", "title": "C"}]
        out = generator.normalise_plan(self.plan(modules=modules), "bread", 6, self.BRIEF)
        self.assertEqual([m["id"] for m in out["modules"]], ["M01", "M02", "M03"])

    def test_unknown_part_reference_is_reassigned(self):
        modules = [{"id": "M01", "part": "nonsense", "title": "A"}]
        out = generator.normalise_plan(self.plan(modules=modules), "bread", 6, self.BRIEF)
        self.assertIn(out["modules"][0]["part"], ("p1", "p2"))

    def test_duplicate_directories_are_made_unique(self):
        parts = [{"id": "p1", "name": "A", "hours": 3, "dir": "same"},
                 {"id": "p2", "name": "B", "hours": 3, "dir": "same"}]
        out = generator.normalise_plan(self.plan(parts=parts), "bread", 6, self.BRIEF)
        self.assertNotEqual(out["parts"][0]["dir"], out["parts"][1]["dir"])

    def test_bad_minutes_fall_back(self):
        modules = [{"id": "M01", "part": "p1", "title": "A", "minutes": "ninety"}]
        out = generator.normalise_plan(self.plan(modules=modules), "bread", 6, self.BRIEF)
        self.assertEqual(out["modules"][0]["minutes"], 60)

    def test_empty_plan_is_rejected(self):
        for bad in ({"parts": [], "modules": []}, {"parts": [{"id": "p1", "name": "A", "dir": "d"}]}, "nope"):
            with self.assertRaises(generator.GenerationError):
                generator.normalise_plan(bad, "bread", 6, self.BRIEF)

    def test_manifest_is_loadable_by_the_build(self):
        import tempfile
        from coursekit import config as ck_config
        plan = generator.normalise_plan(self.plan(), "bread", 6, self.BRIEF)
        manifest = generator.plan_to_manifest(plan, "bread")
        tmp = tempfile.mkdtemp(prefix="studio-test-")
        with open(os.path.join(tmp, "course.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        cfg = ck_config.load(tmp)
        self.assertEqual(cfg.id, "bread")
        self.assertEqual(len(cfg.parts), 2)
        self.assertEqual(cfg.runtime()["storageKey"], "course_bread_v1")


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

    # helpers
    def _wait(self, cond, timeout=5):
        end = time.time() + timeout
        while time.time() < end and not cond():
            time.sleep(0.01)
        self.assertTrue(cond(), "condition not reached in %ss" % timeout)

    def _settle(self, job, timeout=10):
        self._wait(lambda: job.finished, timeout)


class TestPrompts(unittest.TestCase):
    """Prompts are content, but a few properties are load-bearing."""

    CFG = {"title": "T", "subject": "bread", "hours": 6, "audience": "a beginner",
           "practitioner": "baker"}
    MODS = [{"id": "M01", "part": "p1", "title": "Flour", "minutes": 60,
             "sections": ["Why this matters", "Core concepts"], "summary": "s"}]

    def test_module_prompt_names_the_exact_headings(self):
        from studio import prompts
        text = prompts.module(self.CFG, self.MODS, self.MODS[0])
        self.assertIn("## Why this matters", text)
        self.assertIn("# M01 — Flour", text)
        self.assertIn("**Time:**", text)

    def test_suggestion_prompt_states_the_required_count(self):
        from studio import prompts
        text = prompts.suggestions(self.CFG, "M01", ["A", "B", "C", "D"], "body")
        self.assertIn("exactly 4 arrays", text)
        self.assertIn("4 sections", text)

    def test_resources_prompt_forbids_inventing_sources(self):
        from studio import prompts
        self.assertIn("Never fabricate", prompts.resources(self.CFG))


if __name__ == "__main__":
    unittest.main(verbosity=2)

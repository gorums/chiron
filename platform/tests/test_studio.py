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

from coursekit.errors import CourseError  # noqa: E402
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

    def test_direction_is_empty_without_notes_and_quoted_with(self):
        from studio import prompts
        self.assertEqual(prompts.direction(""), "")
        self.assertEqual(prompts.direction("   "), "")
        self.assertIn("go deeper on X", prompts.direction("go deeper on X"))

    def test_module_spec_prompt_names_topic_and_part(self):
        from studio import prompts
        text = prompts.module_spec(self.CFG, self.MODS, "reading a failed loaf", "Judgement", 45)
        self.assertIn("reading a failed loaf", text)
        self.assertIn('"Judgement"', text)
        self.assertIn("M01", text)


class TestChatPrompt(unittest.TestCase):
    """The tutor over the CLI: one flat transcript, ending in an open Assistant turn."""

    def test_shape(self):
        text = claude_cli.chat_prompt("Be brief.", [
            {"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "why?"}])
        self.assertTrue(text.startswith("Be brief."))
        self.assertIn("User: hi", text)
        self.assertIn("Assistant: hello", text)
        self.assertTrue(text.endswith("User: why?\n\nAssistant:"))

    def test_only_the_last_twenty_turns_travel(self):
        msgs = [{"role": "user", "content": "m%d" % i} for i in range(40)]
        text = claude_cli.chat_prompt("", msgs)
        self.assertNotIn("User: m0\n", text)
        self.assertIn("User: m39", text)


class TestProgressStore(unittest.TestCase):
    """The platform-side copy of a reader's progress."""

    def setUp(self):
        import shutil
        import tempfile
        from studio import progress
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
                                  "ui": {"rail": False}, "notes": {"M01": "n"}})
        state = self.store.load("bread")["state"]
        self.assertNotIn("bridge", state)
        self.assertNotIn("theme", state)
        self.assertNotIn("ui", state)
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
        from studio import progress
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
        self.assertEqual(claude_cli.model_chain("claude-opus-5"), ["opus", claude_cli.DEFAULT_MODEL])
        self.assertEqual(claude_cli.model_chain(""), [claude_cli.DEFAULT_MODEL])
        self.assertEqual(claude_cli.model_chain("nonsense"), [claude_cli.DEFAULT_MODEL])
        self.assertEqual(claude_cli.model_chain(claude_cli.DEFAULT_MODEL), [claude_cli.DEFAULT_MODEL])

    def test_prefs_store(self):
        import shutil
        import tempfile
        from studio import prefs
        tmp = tempfile.mkdtemp(prefix="studio-prefs-")
        self.addCleanup(shutil.rmtree, tmp, True)
        store = prefs.Prefs(os.path.join(tmp, "nested", "studio.json"))
        self.assertEqual(store.model, claude_cli.DEFAULT_MODEL)
        self.assertEqual(store.save({"model": "opus"})["model"], "opus")
        self.assertEqual(prefs.Prefs(store.path).model, "opus")
        with self.assertRaises(ValueError):
            store.save({"model": "claude-fable-5-1[1m]"})
        with open(store.path, "w") as fh:
            fh.write("{broken")
        self.assertEqual(store.model, claude_cli.DEFAULT_MODEL, "a corrupt file falls back")


class TestLog(unittest.TestCase):
    def test_ring_buffer_filters(self):
        from studio import log as logmod
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
        from coursekit import config as ck_config
        from coursekit import loader as ck_loader
        self.tmp = tempfile.mkdtemp(prefix="studio-edit-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fixture = CourseFixture(self.tmp)
        self.cfg = ck_config.load(self.fixture.root)
        self.modules = ck_loader.load_modules(self.cfg)

    def test_next_module_id_never_reuses(self):
        self.assertEqual(generator.next_module_id(self.modules), "M07")
        self.assertEqual(generator.next_module_id([{"id": "M03"}, {"id": "M10"}, {"id": "x"}]), "M11")
        self.assertEqual(generator.next_module_id([]), "M01")

    def test_plan_from_course_has_what_the_prompts_need(self):
        plan = generator.plan_from_course(self.cfg, self.modules)
        for key in ("title", "subject", "hours", "audience", "practitioner", "parts", "modules"):
            self.assertIn(key, plan)
        self.assertEqual(plan["modules"][0]["id"], "M01")
        self.assertEqual(len(plan["modules"][0]["sections"]), 3)
        self.assertEqual([p["dir"] for p in plan["parts"]][0], "01-foundations")

    def test_fix_spec_repairs_a_sloppy_design(self):
        spec = generator._fix_spec({"title": " Deep dive ", "minutes": "abc", "sections": []},
                                   "M07", "p2", "topic", 45)
        self.assertEqual(spec["id"], "M07")
        self.assertEqual(spec["title"], "Deep dive")
        self.assertEqual(spec["minutes"], 45)
        self.assertEqual(len(spec["sections"]), 7)
        self.assertEqual(generator._fix_spec("garbage", "M07", "p2", "topic", 45)["title"], "topic")
        self.assertEqual(generator._fix_spec({"minutes": 9999}, "M07", "p2", "t", 45)["minutes"], 240)

    def test_store_module_data_adds_new_files_for_a_new_module(self):
        from coursekit import assessments as ck_assess
        assess = generator._fix_assessment({
            "quiz": [{"q": "Q", "options": ["a", "b"], "answer": 1, "why": "w"}],
            "cards": [{"front": "f", "back": "b"}]}, "M07")
        generator._store_module_data(self.fixture.root, self.cfg, "M07", assess, [["a", "b", "c"]])
        self.assertTrue(os.path.isfile(os.path.join(self.fixture.root, "data/assessments/M07.json")))
        self.assertIn("M07", ck_assess.load_assessments(self.cfg))
        self.assertEqual(ck_assess.load_suggestions(self.cfg)["M07"], [["a", "b", "c"]])

    def test_store_module_data_replaces_in_place_for_an_existing_module(self):
        from coursekit import assessments as ck_assess
        assess = generator._fix_assessment({
            "predict": "new", "quiz": [{"q": "Q", "options": ["a", "b"], "answer": 0, "why": "w"}],
            "cards": [{"front": "f", "back": "b"}]}, "M02")
        generator._store_module_data(self.fixture.root, self.cfg, "M02", assess, [["x", "y", "z"]] * 3)
        self.assertFalse(os.path.isfile(os.path.join(self.fixture.root, "data/assessments/M02.json")),
                         "no second file: the validator would see two claims on M02")
        loaded = ck_assess.load_assessments(self.cfg)
        self.assertEqual(loaded["M02"]["predict"], "new")
        self.assertEqual(len(loaded), 6)
        self.assertEqual(self.fixture.problems(), [])

    def test_set_short_title(self):
        generator._set_short_title(self.fixture.root, "M07", "Deep dive")
        with open(self.fixture.cfg_path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["shortTitles"]["M07"], "Deep dive")

    def test_extend_writes_a_module_then_rebuilds(self):
        """The whole extend pipeline with Claude stubbed out."""
        from studio import server
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

        original = claude_cli.ask
        claude_cli.ask = fake_ask
        try:
            job = jobs.Job("extend")
            dist = os.path.join(self.tmp, "dist")
            result = generator.extend(job, self.tmp, dist, "fixture",
                                      {"topic": "reading a failed loaf", "part": "p3", "minutes": 45,
                                       "notes": "assume the starter is healthy"})
        finally:
            claude_cli.ask = original

        self.assertEqual(result["module"], "M07")
        self.assertEqual(result["modules"], 7)
        path = os.path.join(self.fixture.root, "modules", "03-expert-layer", "M07-reading-a-failed-loaf.md")
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self.fixture.problems(), [])
        self.assertTrue(any("assume the starter is healthy" in c for c in calls), "direction reached the model")
        self.assertTrue(os.path.isfile(os.path.join(dist, "fixture", "fixture-course-local.html")))
        # And the server's cheap id listing agrees with the loader.
        from coursekit import config as ck_config
        self.assertEqual(server._module_ids(ck_config.load(self.fixture.root))[-1], "M07")

    # ---- manage: settings, remove, trash ----

    def test_settings_round_trip_and_id_lock(self):
        from studio import manage
        before = manage.settings(self.fixture.root)
        self.assertEqual(before["id"], "fixture")
        after = manage.update_settings(self.fixture.root, {
            "title": "  Bread, properly ", "tutorPersona": "You are a baker",
            "milestones": [{"after": "3", "text": "Halfway."}, {"after": 0, "text": "Start."},
                           {"after": 1, "text": ""}, "junk"],
            "parts": [{"id": "p1", "name": "Basics", "hours": 2, "blurb": "b"}],
        })
        self.assertEqual(after["title"], "Bread, properly")
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
        from coursekit import assessments as ck_assess
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
        self.assertEqual(generator.next_module_id(self.modules), "M07", "ids are not reused")
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
        from studio import server
        state = {"marks": {"M02": [
            {"id": "k1", "sec": 1, "text": "a passage", "q": "why?", "status": "open", "ts": 5},
            {"id": "k2", "sec": 0, "text": "plain highlight", "status": "hl", "ts": 9},
            {"id": "k3", "sec": 2, "text": "answered one", "status": "answered", "ts": 7},
        ], "M09": "junk"}}
        mods = [{"id": "M02", "title": "Water"}]
        qs = server.open_questions(state, mods)
        self.assertEqual([q["id"] for q in qs], ["k3", "k1"], "newest first, highlights excluded")
        self.assertEqual(qs[1]["title"], "Water")
        self.assertEqual(server.open_questions({}, mods), [])

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
        from coursekit import assessments as ck_assess
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
        generator._write_json(os.path.join(data_dir, "assessments/all.json"), list(assess.values()))
        generator._write_json(os.path.join(data_dir, "suggestions/all.json"), sugg)
        self.assertFalse(os.path.isfile(os.path.join(self.fixture.root, generator.PLAN_FILE)))

        calls = []
        original = claude_cli.ask
        claude_cli.ask = self._stub_claude(calls)
        try:
            job = jobs.Job("generate")
            result = generator.generate(job, self.tmp, os.path.join(self.tmp, "dist"),
                                        {"id": "fixture", "theme": "bread baking", "hours": 6, "resume": True})
        finally:
            claude_cli.ask = original

        self.assertEqual(result["modules"], 7)
        written = [c for c in calls if "Write module " in c]
        self.assertEqual(len(written), 1, "only the missing module was written")
        self.assertIn("Write module M07", written[0])
        self.assertEqual(sum(1 for c in calls if "study data for module" in c), 1)
        self.assertTrue(os.path.isfile(os.path.join(self.fixture.root, generator.PLAN_FILE)),
                        "the curriculum is saved for the next resume")
        self.assertEqual(self.fixture.problems(), [])
        kinds = [e["kind"] for e in job.events]
        self.assertNotIn("await", kinds, "a resume never asks for approval again")
        # Reference docs that were stubs got written; a second resume would keep them.
        self.assertTrue(generator._real_file(os.path.join(self.fixture.root, "reference/glossary.md")))

    def test_reconstruct_plan_orders_and_fills(self):
        self.fixture.edit_manifest(shortTitles=dict(
            {mid: "Lesson " + mid for mid in self.fixture.ids}, M09="Nine", M08="Eight"))
        plan = generator.reconstruct_plan(self.fixture.root)
        self.assertEqual([m["id"] for m in plan["modules"]], ["M01", "M02", "M03", "M04", "M05", "M06", "M08", "M09"])
        self.assertEqual(plan["modules"][-1]["title"], "Nine")
        self.assertEqual(plan["modules"][0]["sections"], ["Why this matters", "Core concepts", "Exercise"])

    def test_resolve_course_file_stays_inside_the_course(self):
        from studio import server
        saved = server.COURSES_DIR
        server.COURSES_DIR = self.tmp
        try:
            ok = server.resolve_course_file("fixture", "modules/01-foundations/M01-lesson.md")
            self.assertTrue(ok.startswith(os.path.abspath(self.fixture.root)))
            for bad in ("../other/course.json", "course.py", "", "modules/../../x.md"):
                with self.subTest(bad=bad):
                    try:
                        full = server.resolve_course_file("fixture", bad)
                    except ValueError:
                        continue
                    self.assertTrue(full.startswith(os.path.abspath(self.fixture.root)),
                                    "%r resolved outside the course" % bad)
        finally:
            server.COURSES_DIR = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)

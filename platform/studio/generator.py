"""The generation pipeline: a brief in, a built course out.

    plan  ->  [approval gate]  ->  modules  ->  study data  ->  reference  ->  check  ->  build

Two design points worth knowing before changing anything here.

**Everything is written to disk as it is produced.** A run that dies at module 14 leaves
fourteen real modules behind, and rerunning overwrites cleanly. Nothing is held in memory
waiting for a final commit.

**The section/suggestion invariant is satisfied by construction, not by hope.** After a
module is written, its actual headings are parsed back off disk and passed to the suggestion
prompt, which is asked for exactly that many sets. The result is then counted, and padded or
trimmed if the model still miscounted. Asking a model to "remember to produce N" and trusting
it is how this breaks.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from coursekit import assessments as ck_assess
from coursekit import config as ck_config
from coursekit import library as ck_library
from coursekit import loader as ck_loader
from coursekit import renderer as ck_renderer
from coursekit import scaffold as ck_scaffold
from coursekit import validate as ck_validate

from . import claude_cli, prompts
from .jobs import Job

# Model output is trusted for prose and distrusted for structure; these bound the latter.
QUIZ_ITEMS = 6
CARD_ITEMS = 6
QUESTIONS_PER_SECTION = 3
MAX_CORPUS_CHARS = 60000     # what the glossary and mental-models calls see of the course

_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}$")


class GenerationError(RuntimeError):
    pass


# --------------------------------------------------------------------------- helpers


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text.rstrip() + "\n")


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "module"


def headings_of(markdown: str) -> List[str]:
    """The `##` headings that will survive the build.

    Delegates to the loader so this can never disagree with what the build actually counts -
    an empty heading is dropped by both, which is what keeps the suggestion count honest.
    """
    return [s.heading for s in ck_loader.parse_sections(markdown)]


# --------------------------------------------------------------------------- planning


def make_plan(job: Job, brief: Dict[str, Any], model: str = "") -> Dict[str, Any]:
    theme = brief["theme"]
    hours = float(brief["hours"])
    hint = ck_scaffold.plan_parts(hours)
    job.log("Designing the curriculum for %s (%g hours)…" % (theme, hours))
    plan = claude_cli.ask_json(
        prompts.plan(
            theme, hours,
            brief.get("audience") or "a complete beginner",
            brief.get("practitioner") or "practitioner",
            hint,
            brief.get("notes", ""),
        ),
        model=model,
        timeout=420,
    )
    return normalise_plan(plan, theme, hours, brief)


def normalise_plan(plan: Dict[str, Any], theme: str, hours: float,
                   brief: Dict[str, Any]) -> Dict[str, Any]:
    """Repair what a model reliably gets slightly wrong, and reject what cannot be repaired."""
    if not isinstance(plan, dict):
        raise GenerationError("The planner did not return a JSON object.")
    parts = plan.get("parts") or []
    modules = plan.get("modules") or []
    if not parts or not modules:
        raise GenerationError("The plan has no parts or no modules.")

    seen_dirs = set()
    for i, part in enumerate(parts):
        part["id"] = part.get("id") or "p%d" % (i + 1)
        part["name"] = part.get("name") or "Part %d" % (i + 1)
        directory = _slug(part.get("dir") or part["name"])
        while directory in seen_dirs:
            directory += "-x"
        seen_dirs.add(directory)
        part["dir"] = directory
        part["hours"] = part.get("hours") or 0
        part["blurb"] = part.get("blurb") or ""

    part_ids = [p["id"] for p in parts]
    for i, mod in enumerate(modules):
        mod["id"] = "M%02d" % (i + 1)                      # renumber; models drift here
        if mod.get("part") not in part_ids:
            mod["part"] = part_ids[min(i * len(part_ids) // max(1, len(modules)),
                                       len(part_ids) - 1)]
        mod["title"] = (mod.get("title") or "Module %d" % (i + 1)).strip()
        mod["short"] = (mod.get("short") or mod["title"])[:60]
        try:
            mod["minutes"] = max(15, int(mod.get("minutes") or 60))
        except (TypeError, ValueError):
            mod["minutes"] = 60
        mod["summary"] = mod.get("summary") or ""
        sections = [str(s).strip() for s in (mod.get("sections") or []) if str(s).strip()]
        mod["sections"] = sections or [
            "Why this matters", "Core concepts", "How it works in practice",
            "2026 reality check", "Common mistakes", "Exercise", "If you remember one thing",
        ]

    plan["parts"] = parts
    plan["modules"] = modules
    plan["title"] = plan.get("title") or "%s Mastery" % theme.title()
    plan["tagline"] = plan.get("tagline") or "%g hours · beginner to practitioner" % hours
    plan["subject"] = theme.strip().lower()
    plan["hours"] = hours
    plan["practitioner"] = (brief.get("practitioner")
                            or plan.get("practitioner") or "practitioner")
    plan["audience"] = brief.get("audience") or plan.get("audience") or "a complete beginner"
    plan["tutorPersona"] = (plan.get("tutorPersona")
                            or "You are a sharp, plain-spoken %s tutor." % plan["subject"])
    plan["milestones"] = [m for m in (plan.get("milestones") or [])
                          if isinstance(m, dict) and "text" in m]
    return plan


def plan_to_manifest(plan: Dict[str, Any], course_id: str) -> Dict[str, Any]:
    manifest = ck_scaffold.manifest(plan["subject"], plan["hours"], course_id=course_id,
                                    title=plan["title"], practitioner=plan["practitioner"])
    manifest.update({
        "title": plan["title"],
        "tagline": plan["tagline"],
        "audience": plan["audience"],
        "tutorPersona": plan["tutorPersona"],
        "parts": [{k: p[k] for k in ("id", "name", "hours", "dir", "blurb")}
                  for p in plan["parts"]],
        "shortTitles": {m["id"]: m["short"] for m in plan["modules"]},
        "milestones": plan["milestones"],
        "folderLabel": "courses/%s" % course_id,
    })
    return manifest


# --------------------------------------------------------------------------- writing


def _module_path(root: str, plan: Dict[str, Any], mod: Dict[str, Any]) -> str:
    directory = next(p["dir"] for p in plan["parts"] if p["id"] == mod["part"])
    return os.path.join(root, "modules", directory, "%s-%s.md" % (mod["id"], _slug(mod["title"])))


def write_module(job: Job, root: str, plan: Dict[str, Any], mod: Dict[str, Any],
                 model: str = "") -> str:
    prompt = prompts.module(plan, plan["modules"], mod)
    if mod["id"] == "M01":
        prompt += prompts.module_first(plan)
    body = claude_cli.strip_fence(claude_cli.ask(prompt, model=model, timeout=900))

    # The build keys everything off the title line; repair it rather than failing the run.
    expected = "# %s — %s" % (mod["id"], mod["title"])
    lines = body.split("\n")
    if not lines or not lines[0].startswith("# "):
        body = expected + "\n\n" + body
    elif not lines[0].startswith("# %s " % mod["id"]):
        lines[0] = expected
        body = "\n".join(lines)
    if "**Time:**" not in body.split("\n## ")[0]:
        head, sep, rest = body.partition("\n")
        body = head + "\n\n**Time:** %d minutes\n" % mod["minutes"] + sep + rest

    path = _module_path(root, plan, mod)
    _write(path, body)
    found = headings_of(body)
    if not found:
        raise GenerationError("%s came back with no usable sections." % mod["id"])
    job.emit("module", id=mod["id"], title=mod["title"], sections=len(found),
             words=len(body.split()), path=os.path.relpath(path, root))
    return body


def _fix_assessment(raw: Any, mid: str) -> Dict[str, Any]:
    """Coerce a model's assessment into something the validator will accept, or fail loudly."""
    if not isinstance(raw, dict):
        raise GenerationError("%s assessment was not a JSON object." % mid)
    out: Dict[str, Any] = {"id": mid}
    out["predict"] = str(raw.get("predict") or "Before reading: what do you expect this to say?")

    quiz = []
    for q in (raw.get("quiz") or [])[:QUIZ_ITEMS]:
        options = [str(o) for o in (q.get("options") or []) if str(o).strip()]
        if len(options) < 2:
            continue
        try:
            answer = int(q.get("answer"))
        except (TypeError, ValueError):
            answer = 0
        quiz.append({
            "q": str(q.get("q") or "").strip() or "Which statement follows from this module?",
            "options": options,
            "answer": max(0, min(answer, len(options) - 1)),
            "why": str(q.get("why") or "").strip() or "See the module section this draws on.",
        })
    if not quiz:
        raise GenerationError("%s assessment produced no usable quiz questions." % mid)
    out["quiz"] = quiz

    cards = [{"front": str(c.get("front") or "").strip(), "back": str(c.get("back") or "").strip()}
             for c in (raw.get("cards") or [])[:CARD_ITEMS]]
    cards = [c for c in cards if c["front"] and c["back"]]
    if not cards:
        raise GenerationError("%s assessment produced no usable flashcards." % mid)
    out["cards"] = cards

    elaborate = [str(e).strip() for e in (raw.get("elaborate") or []) if str(e).strip()]
    out["elaborate"] = elaborate or ["Explain this module's main idea in your own words."]

    transfer = raw.get("transfer") or {}
    out["transfer"] = {
        "scenario": str(transfer.get("scenario") or "").strip(),
        "prompt": str(transfer.get("prompt") or "Apply this module to the situation above.").strip(),
        "model": str(transfer.get("model") or "").strip(),
    }
    return out


def _fix_suggestions(raw: Any, headings: List[str]) -> List[List[str]]:
    """Force the per-section count to match. This invariant is not negotiable."""
    rows = raw if isinstance(raw, list) else []
    if rows and isinstance(rows[0], str):        # a flat list of questions
        rows = [rows[i:i + QUESTIONS_PER_SECTION]
                for i in range(0, len(rows), QUESTIONS_PER_SECTION)]
    fixed: List[List[str]] = []
    for i, heading in enumerate(headings):
        row = rows[i] if i < len(rows) and isinstance(rows[i], list) else []
        questions = [str(q).strip() for q in row if str(q).strip()][:QUESTIONS_PER_SECTION]
        while len(questions) < QUESTIONS_PER_SECTION:
            questions.append(["Why does this matter?",
                              "Can you show me an example?",
                              "How does this apply to my situation?"][len(questions)])
        fixed.append(questions)
    return fixed


def write_study_data(job: Job, root: str, plan: Dict[str, Any], mod: Dict[str, Any],
                     body: str, model: str = "") -> Dict[str, Any]:
    headings = headings_of(body)
    assess = _fix_assessment(
        claude_cli.ask_json(prompts.assessment(plan, mod, body), model=model, timeout=600),
        mod["id"],
    )
    sugg = _fix_suggestions(
        claude_cli.ask_json(prompts.suggestions(plan, mod["id"], headings, body),
                            model=model, timeout=600),
        headings,
    )
    job.emit("studydata", id=mod["id"], quiz=len(assess["quiz"]),
             cards=len(assess["cards"]), sections=len(sugg))
    return {"assess": assess, "suggest": sugg}


# --------------------------------------------------------------------------- pipeline


def _corpus(bodies: Dict[str, str]) -> str:
    """A budgeted sample of the course for the glossary and mental-models calls."""
    if not bodies:
        return ""
    per = max(1200, MAX_CORPUS_CHARS // len(bodies))
    return "\n\n".join("### %s\n%s" % (mid, text[:per]) for mid, text in sorted(bodies.items()))


def generate(job: Job, courses_dir: str, dist_dir: str, brief: Dict[str, Any]) -> Dict[str, Any]:
    """Run the whole pipeline. Parks once for curriculum approval."""
    course_id = brief.get("id") or ck_scaffold.slugify(brief["theme"])
    if not _SAFE_ID.match(course_id):
        raise GenerationError("'%s' is not a usable course id." % course_id)
    model = brief.get("model", "")
    job.meta["course"] = course_id

    # ---- 1. plan, then wait for the human ----
    plan = make_plan(job, brief, model)
    job.emit("plan", plan=plan)
    approved = job.await_input("approve-plan", {"plan": plan, "id": course_id})
    if isinstance(approved, dict) and approved.get("plan"):
        plan = normalise_plan(approved["plan"], brief["theme"], float(brief["hours"]), brief)
    job.log("Curriculum approved: %d modules across %d parts."
            % (len(plan["modules"]), len(plan["parts"])))

    # ---- 2. lay down the tree ----
    root = os.path.join(courses_dir, course_id)
    for part in plan["parts"]:
        os.makedirs(os.path.join(root, "modules", part["dir"]), exist_ok=True)
    for sub in ("plan", "reference", "templates", "data/assessments", "data/suggestions"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    _write_json(os.path.join(root, "course.json"), plan_to_manifest(plan, course_id))

    modules = plan["modules"]
    total = len(modules) * 2 + 6          # modules + study data + reference + build
    step = 0

    # ---- 3. modules, each with its study data written immediately after ----
    bodies: Dict[str, str] = {}
    assess_rows: List[Dict[str, Any]] = []
    suggest_rows: Dict[str, Any] = {}
    for mod in modules:
        job.check_cancelled()
        step += 1
        job.progress(step, total, "Writing %s · %s" % (mod["id"], mod["title"]))
        bodies[mod["id"]] = write_module(job, root, plan, mod, model)

        job.check_cancelled()
        step += 1
        job.progress(step, total, "Quiz and flashcards for %s" % mod["id"])
        data = write_study_data(job, root, plan, mod, bodies[mod["id"]], model)
        assess_rows.append(data["assess"])
        suggest_rows[mod["id"]] = data["suggest"]
        # Written every iteration so an interrupted run still leaves valid data behind.
        _write_json(os.path.join(root, "data/assessments/all.json"), assess_rows)
        _write_json(os.path.join(root, "data/suggestions/all.json"), suggest_rows)

    corpus = _corpus(bodies)

    # ---- 4. the reference shelf ----
    job.check_cancelled()
    step += 1
    job.progress(step, total, "Glossary")
    _write(os.path.join(root, "reference/glossary.md"),
           claude_cli.strip_fence(claude_cli.ask(
               prompts.glossary(plan, modules, corpus), model=model, timeout=900)))

    job.check_cancelled()
    step += 1
    job.progress(step, total, "Mental models")
    _write(os.path.join(root, "reference/mental-models.md"),
           claude_cli.strip_fence(claude_cli.ask(
               prompts.mental_models(plan, corpus), model=model, timeout=900)))

    job.check_cancelled()
    step += 1
    job.progress(step, total, "Resources")
    _write(os.path.join(root, "reference/resources.md"),
           claude_cli.strip_fence(claude_cli.ask(
               prompts.resources(plan), model=model, timeout=600)))

    job.check_cancelled()
    step += 1
    job.progress(step, total, "Plan documents")
    for kind, filename in (("curriculum", "curriculum.md"), ("how", "how-to-study.md"),
                           ("expert", "path-to-expert.md")):
        _write(os.path.join(root, "plan", filename),
               claude_cli.strip_fence(claude_cli.ask(
                   prompts.plan_docs(plan, modules, kind), model=model, timeout=600)))

    job.check_cancelled()
    step += 1
    job.progress(step, total, "Worksheets")
    _write_worksheets(job, root, plan, modules, model)

    # ---- 5. validate and build ----
    job.check_cancelled()
    step += 1
    job.progress(step, total, "Validating and building")
    result = build_course(root, dist_dir)
    job.emit("built", **result)
    return dict(result, course=course_id, root=root)


def _write_worksheets(job: Job, root: str, plan: Dict[str, Any],
                      modules: List[Dict[str, Any]], model: str) -> None:
    """Worksheets are optional: a failure here must not lose a finished course."""
    try:
        wanted = claude_cli.ask_json(prompts.worksheet_plan(plan, modules),
                                     model=model, timeout=420)
    except Exception as exc:  # noqa: BLE001
        job.log("Could not plan worksheets (%s); continuing without them." % exc)
        return
    if not isinstance(wanted, list):
        return
    for spec in wanted[:10]:
        if not isinstance(spec, dict) or not spec.get("name"):
            continue
        job.check_cancelled()
        slug = _slug(spec.get("slug") or spec["name"])
        try:
            text = claude_cli.strip_fence(claude_cli.ask(
                prompts.worksheet(plan, spec["name"], spec.get("purpose", "")),
                model=model, timeout=600))
        except Exception as exc:  # noqa: BLE001
            job.log("Worksheet '%s' failed (%s); skipping." % (slug, exc))
            continue
        _write(os.path.join(root, "templates", "%s.md" % slug), text)
        job.emit("worksheet", slug=slug, name=spec["name"])


def build_course(root: str, dist_dir: str) -> Dict[str, Any]:
    """Validate then build. Shared by the generator and the UI's Build button."""
    cfg = ck_config.load(root)
    modules = ck_loader.load_modules(cfg)
    assess = ck_assess.load_assessments(cfg)
    suggest = ck_assess.load_suggestions(cfg)
    ck_validate.raise_if_broken(ck_validate.check(modules, assess, suggest))
    ck_assess.attach(modules, assess, suggest)
    out = ck_renderer.write(cfg, modules, ck_library.build(cfg),
                            os.path.join(dist_dir, cfg.id))
    return {
        "modules": out.modules, "sections": out.sections, "quiz": out.quiz_items,
        "cards": out.cards, "glossary": out.glossary, "models": out.models,
        "templates": out.templates, "kb": round(out.kb),
        "web": out.web_path, "local": out.local_path,
    }


def check_course(root: str) -> List[str]:
    cfg = ck_config.load(root)
    modules = ck_loader.load_modules(cfg)
    return ck_validate.check(modules, ck_assess.load_assessments(cfg),
                             ck_assess.load_suggestions(cfg))

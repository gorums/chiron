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
from coursekit.errors import CourseError
from coursekit.settings import SETTINGS

from . import claude_cli, prompts
from .jobs import Job

# Model output is trusted for prose and distrusted for structure; these bound the latter.
# All from the `generation` block of settings.json.
QUIZ_ITEMS = int(SETTINGS.get("generation.quizItems"))
CARD_ITEMS = int(SETTINGS.get("generation.cardItems"))
QUESTIONS_PER_SECTION = int(SETTINGS.get("generation.questionsPerSection"))
MAX_CORPUS_CHARS = int(SETTINGS.get("generation.maxCorpusChars"))   # what the glossary and mental-models calls see
MAX_WORKSHEETS = int(SETTINGS.get("generation.maxWorksheets"))


def _timeout(step: str) -> int:
    """Seconds allowed for one kind of Claude call: `generation.timeouts.<step>`."""
    return int(SETTINGS.get("generation.timeouts." + step, claude_cli.DEFAULT_TIMEOUT))

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
        timeout=_timeout("plan"),
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
    # Prerequisites may only point backwards, at modules that exist. Models write "M3".
    ids = [m["id"] for m in modules]
    for i, mod in enumerate(modules):
        wanted = []
        for r in (mod.get("requires") or []):
            found = re.match(r"^M(\d+)$", str(r).strip().upper())
            rid = "M%02d" % int(found.group(1)) if found else ""
            if rid in ids[:i] and rid not in wanted:
                wanted.append(rid)
        mod["requires"] = wanted[:3]

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
        "folderLabel": course_id,
    })
    return manifest


# --------------------------------------------------------------------------- writing


def _module_path(root: str, plan: Dict[str, Any], mod: Dict[str, Any]) -> str:
    directory = next(p["dir"] for p in plan["parts"] if p["id"] == mod["part"])
    return os.path.join(root, "modules", directory, "%s-%s.md" % (mod["id"], _slug(mod["title"])))


def write_module(job: Job, root: str, plan: Dict[str, Any], mod: Dict[str, Any],
                 model: str = "", path: str = "", notes: str = "") -> str:
    prompt = prompts.module(plan, plan["modules"], mod)
    if mod["id"] == "M01":
        prompt += prompts.module_first(plan)
    prompt += prompts.direction(notes)
    body = claude_cli.strip_fence(claude_cli.ask(prompt, model=model, timeout=_timeout("module")))

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
    requires = [r for r in (mod.get("requires") or []) if r != mod["id"]]
    if requires and "**Requires:**" not in body.split("\n## ")[0]:
        head, sep, rest = body.partition("\n## ")
        head = head.rstrip() + "\n\n**Requires:** " + ", ".join(requires) + "\n"
        body = head + sep + rest

    path = path or _module_path(root, plan, mod)
    _write(path, body)
    found = headings_of(body)
    if not found:
        raise GenerationError("%s came back with no usable sections." % mod["id"])
    job.emit("module", id=mod["id"], title=mod["title"], sections=len(found),
             words=len(body.split()), path=os.path.relpath(path, root))
    return body


def _strs(value: Any, cap: int = 12) -> List[str]:
    if isinstance(value, str):
        value = [value]
    return [str(v).strip() for v in (value if isinstance(value, list) else []) if str(v).strip()][:cap]


def _num(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fix_quiz_item(q: Any) -> Dict[str, Any] | None:
    """One quiz item into a shape `validate.quiz_item_problems` accepts, or None to drop it.

    Prose is kept as written; only structure is repaired. A type that cannot be repaired is
    dropped rather than shipped broken, and a whole quiz of drops fails the run loudly.
    """
    if not isinstance(q, dict):
        return None
    kind = str(q.get("type") or "single").strip().lower()
    if kind not in ck_validate.QUIZ_TYPES:
        kind = "single"
    out: Dict[str, Any] = {
        "type": kind,
        "q": str(q.get("q") or "").strip() or "Which statement follows from this module?",
        "why": str(q.get("why") or "").strip() or "See the module section this draws on.",
    }
    options = _strs(q.get("options"), 8)
    answer = q.get("answer")

    if kind == "single":
        if len(options) < 2:
            return None
        idx = int(_num(answer) or 0) if _num(answer) is not None else 0
        out["options"] = options
        out["answer"] = max(0, min(idx, len(options) - 1))
    elif kind == "multi":
        if len(options) < 2:
            return None
        picks = answer if isinstance(answer, list) else [answer]
        idxs = sorted({int(_num(a)) for a in picks if _num(a) is not None and 0 <= int(_num(a)) < len(options)})
        if not idxs:
            return None
        out["options"] = options
        out["answer"] = idxs
    elif kind == "tf":
        if isinstance(answer, bool):
            out["answer"] = answer
        elif isinstance(answer, str) and answer.strip().lower() in ("true", "false"):
            out["answer"] = answer.strip().lower() == "true"
        else:
            return None
    elif kind == "numeric":
        value = _num(answer)
        if value is None:
            return None
        out["answer"] = int(value) if value == int(value) else value
        tol = _num(q.get("tolerance"))
        out["tolerance"] = abs(tol) if tol is not None else 0
        if q.get("unit"):
            out["unit"] = str(q["unit"]).strip()[:12]
    elif kind == "order":
        if len(options) < 2:
            return None
        out["options"] = options
    elif kind == "match":
        pairs = []
        for pair in (q.get("pairs") if isinstance(q.get("pairs"), list) else []):
            if isinstance(pair, dict):
                pair = [pair.get("left") or pair.get("term"), pair.get("right") or pair.get("match")]
            if isinstance(pair, list) and len(pair) == 2 and all(str(x).strip() for x in pair):
                pairs.append([str(pair[0]).strip(), str(pair[1]).strip()])
        if len(pairs) < 2:
            return None
        out["pairs"] = pairs[:6]
    elif kind == "cloze":
        text = out["q"]
        if "___" not in text:
            if "____" in text or "[blank]" in text.lower():
                text = re.sub(r"_{2,}|\[blank\]", "___", text, flags=re.I)
            else:
                return None
        out["q"] = text
        fills = _strs(answer, 8)
        if not fills:
            return None
        out["answer"] = fills
    elif kind == "short":
        model = str(q.get("model") or q.get("answer") or "").strip()
        if not model:
            return None
        out["model"] = model

    feedback = _strs(q.get("feedback"), 8)
    expected = 2 if kind == "tf" else len(out.get("options", []))
    if kind in ck_validate.OPTION_TYPES and feedback and len(feedback) == expected:
        out["feedback"] = feedback
    hints = _strs(q.get("hints"), 3)
    if hints:
        out["hints"] = hints
    return out


def _fix_roleplay(raw: Any) -> Dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    out = {k: str(raw.get(k) or "").strip() for k in ck_validate.ROLEPLAY_KEYS}
    if not all(out.values()):
        return None
    out["rubric"] = _strs(raw.get("rubric"), 5) or ["Reached the goal without giving ground on the essentials."]
    return out


def _fix_assessment(raw: Any, mid: str) -> Dict[str, Any]:
    """Coerce a model's assessment into something the validator will accept, or fail loudly."""
    if not isinstance(raw, dict):
        raise GenerationError("%s assessment was not a JSON object." % mid)
    out: Dict[str, Any] = {"id": mid}
    out["predict"] = str(raw.get("predict") or "Before reading: what do you expect this to say?")

    quiz = [item for item in (_fix_quiz_item(q) for q in (raw.get("quiz") or [])[:QUIZ_ITEMS]) if item]
    if not quiz:
        raise GenerationError("%s assessment produced no usable quiz questions." % mid)
    out["quiz"] = quiz

    cards = [{"front": str(c.get("front") or "").strip(), "back": str(c.get("back") or "").strip()}
             for c in (raw.get("cards") or [])[:CARD_ITEMS] if isinstance(c, dict)]
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
    roleplay = _fix_roleplay(raw.get("roleplay"))
    if roleplay:
        out["roleplay"] = roleplay
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
        claude_cli.ask_json(prompts.assessment(plan, mod, body), model=model, timeout=_timeout("studyData")),
        mod["id"],
    )
    sugg = _fix_suggestions(
        claude_cli.ask_json(prompts.suggestions(plan, mod["id"], headings, body),
                            model=model, timeout=_timeout("studyData")),
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


PLAN_FILE = "plan/plan.json"    # the approved curriculum, kept so a dead run can resume


def _load_plan(root: str) -> Dict[str, Any]:
    """The saved curriculum - or, for a course generated before it was saved, one rebuilt
    from course.json and whatever modules are on disk."""
    path = os.path.join(root, PLAN_FILE)
    if not os.path.isfile(path):
        return reconstruct_plan(root)
    with open(path, encoding="utf-8") as fh:
        plan = json.load(fh)
    if not isinstance(plan, dict) or not plan.get("modules"):
        raise GenerationError("The saved curriculum is unreadable.")
    return plan


def reconstruct_plan(root: str) -> Dict[str, Any]:
    """A plan from the manifest alone. Modules on disk keep their titles and sections; ids
    that only exist in shortTitles become specs still to be written, spread across parts in
    order. Good enough to finish a run; not as rich as the model's own design."""
    cfg = ck_config.load(root)
    written: List[Any] = []
    for part in cfg.parts:
        directory = os.path.join(cfg.modules_dir, part.dir)
        if not os.path.isdir(directory):
            continue
        for name in sorted(f for f in os.listdir(directory) if f.endswith(".md")):
            try:
                written.append(ck_loader.parse_module(os.path.join(directory, name), part.id,
                                                      len(written) + 1, cfg))
            except CourseError:
                continue
    plan = plan_from_course(cfg, written)
    have = {m["id"] for m in plan["modules"]}
    missing = sorted((mid for mid in cfg.short_titles if mid not in have),
                     key=lambda m: int(m[1:]) if m[1:].isdigit() else 0)
    if not plan["modules"] and not missing:
        raise GenerationError("Nothing to resume: this course has no modules and no module list.")
    last_part = plan["parts"][-1]["id"] if plan["parts"] else "p1"
    for mid in missing:
        plan["modules"].append({
            "id": mid, "part": last_part, "title": cfg.short_titles[mid],
            "short": cfg.short_titles[mid], "minutes": 60, "summary": "",
            "sections": list(DEFAULT_SECTIONS),
        })
    plan["modules"].sort(key=lambda m: int(m["id"][1:]) if m["id"][1:].isdigit() else 0)
    return plan


def _existing_module(root: str, plan: Dict[str, Any], mod: Dict[str, Any]) -> str:
    """The body of a module already on disk for this id, or '' if none."""
    directory = os.path.dirname(_module_path(root, plan, mod))
    if not os.path.isdir(directory):
        return ""
    for name in sorted(os.listdir(directory)):
        if name.endswith(".md") and name.split("-", 1)[0] == mod["id"]:
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                body = fh.read()
            return body if headings_of(body) else ""
    return ""


def _existing_rows(root: str):
    """Study data a previous run already wrote, keyed by module id."""
    assess, suggest = {}, {}
    path = os.path.join(root, "data/assessments/all.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            rows = json.load(fh)
        assess = {r["id"]: r for r in rows if isinstance(r, dict) and r.get("id")} \
            if isinstance(rows, list) else {}
    path = os.path.join(root, "data/suggestions/all.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            rows = json.load(fh)
        suggest = rows if isinstance(rows, dict) else {}
    return assess, suggest


def _real_file(path: str) -> bool:
    """A reference document that was actually written, not a scaffold stub."""
    if not os.path.isfile(path) or os.path.getsize(path) < 400:
        return False
    with open(path, encoding="utf-8") as fh:
        return ck_scaffold.PLACEHOLDER.strip() not in fh.read(600)


def generate(job: Job, courses_dir: str, dist_dir: str, brief: Dict[str, Any]) -> Dict[str, Any]:
    """Run the whole pipeline. Parks once for curriculum approval.

    With `brief["resume"]`, picks up a course whose earlier run died: the saved curriculum is
    reused without a new approval, modules and study data already on disk are kept, and only
    what is missing gets written. A run can therefore be resumed any number of times.
    """
    resume = bool(brief.get("resume"))
    course_id = brief.get("id") or ck_scaffold.slugify(brief["theme"])
    if not _SAFE_ID.match(course_id):
        raise GenerationError("'%s' is not a usable course id." % course_id)
    model = brief.get("model", "")
    job.meta["course"] = course_id
    root = os.path.join(courses_dir, course_id)

    # ---- 1. plan, then wait for the human ----
    if resume:
        plan = _load_plan(root)
        job.log("Resuming %s from its saved curriculum: %d modules across %d parts."
                % (course_id, len(plan["modules"]), len(plan["parts"])))
    else:
        plan = make_plan(job, brief, model)
        job.emit("plan", plan=plan)
        approved = job.await_input("approve-plan", {"plan": plan, "id": course_id})
        if isinstance(approved, dict) and approved.get("plan"):
            plan = normalise_plan(approved["plan"], brief["theme"], float(brief["hours"]), brief)
        job.log("Curriculum approved: %d modules across %d parts."
                % (len(plan["modules"]), len(plan["parts"])))

    # ---- 2. lay down the tree ----
    for part in plan["parts"]:
        os.makedirs(os.path.join(root, "modules", part["dir"]), exist_ok=True)
    for sub in ("plan", "reference", "templates", "data/assessments", "data/suggestions"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    if not resume:
        _write_json(os.path.join(root, "course.json"), plan_to_manifest(plan, course_id))
    ck_scaffold.write_readme(root, course_id, plan["title"])
    _write_json(os.path.join(root, PLAN_FILE), plan)

    modules = plan["modules"]
    total = len(modules) * 2 + 6          # modules + study data + reference + build
    step = 0
    had_assess, had_suggest = _existing_rows(root) if resume else ({}, {})

    # ---- 3. modules, each with its study data written immediately after ----
    bodies: Dict[str, str] = {}
    assess_rows: List[Dict[str, Any]] = []
    suggest_rows: Dict[str, Any] = {}
    for mod in modules:
        job.check_cancelled()
        step += 1
        kept = _existing_module(root, plan, mod) if resume else ""
        if kept:
            job.progress(step, total, "Keeping %s · %s" % (mod["id"], mod["title"]))
            job.log("%s is already written; keeping it." % mod["id"])
            bodies[mod["id"]] = kept
        else:
            job.progress(step, total, "Writing %s · %s" % (mod["id"], mod["title"]))
            bodies[mod["id"]] = write_module(job, root, plan, mod, model)

        job.check_cancelled()
        step += 1
        if kept and mod["id"] in had_assess and mod["id"] in had_suggest:
            job.progress(step, total, "Keeping study data for %s" % mod["id"])
            data = {"assess": had_assess[mod["id"]], "suggest": had_suggest[mod["id"]]}
        else:
            job.progress(step, total, "Quiz and flashcards for %s" % mod["id"])
            data = write_study_data(job, root, plan, mod, bodies[mod["id"]], model)
        assess_rows.append(data["assess"])
        suggest_rows[mod["id"]] = data["suggest"]
        # Written every iteration so an interrupted run still leaves valid data behind.
        _write_json(os.path.join(root, "data/assessments/all.json"), assess_rows)
        _write_json(os.path.join(root, "data/suggestions/all.json"), suggest_rows)

    corpus = _corpus(bodies)

    # ---- 4. the reference shelf ----
    def shelf(label: str, rel: str, make):
        nonlocal step
        job.check_cancelled()
        step += 1
        path = os.path.join(root, rel)
        if resume and _real_file(path):
            job.progress(step, total, "Keeping " + label)
            return
        job.progress(step, total, label)
        _write(path, claude_cli.strip_fence(make()))

    shelf("Glossary", "reference/glossary.md",
          lambda: claude_cli.ask(prompts.glossary(plan, modules, corpus), model=model, timeout=_timeout("reference")))
    shelf("Mental models", "reference/mental-models.md",
          lambda: claude_cli.ask(prompts.mental_models(plan, corpus), model=model, timeout=_timeout("reference")))
    shelf("Resources", "reference/resources.md",
          lambda: claude_cli.ask(prompts.resources(plan), model=model, timeout=_timeout("resources")))

    job.check_cancelled()
    step += 1
    job.progress(step, total, "Plan documents")
    for kind, filename in (("curriculum", "curriculum.md"), ("how", "how-to-study.md"),
                           ("expert", "path-to-expert.md")):
        path = os.path.join(root, "plan", filename)
        if resume and _real_file(path):
            continue
        _write(path, claude_cli.strip_fence(claude_cli.ask(
            prompts.plan_docs(plan, modules, kind), model=model, timeout=_timeout("planDocs"))))

    job.check_cancelled()
    step += 1
    templates_dir = os.path.join(root, "templates")
    if resume and any(f.endswith(".md") for f in os.listdir(templates_dir)):
        job.progress(step, total, "Keeping worksheets")
    else:
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
                                     model=model, timeout=_timeout("worksheetPlan"))
    except Exception as exc:  # noqa: BLE001
        job.log("Could not plan worksheets (%s); continuing without them." % exc)
        return
    if not isinstance(wanted, list):
        return
    for spec in wanted[:MAX_WORKSHEETS]:
        if not isinstance(spec, dict) or not spec.get("name"):
            continue
        job.check_cancelled()
        slug = _slug(spec.get("slug") or spec["name"])
        try:
            text = claude_cli.strip_fence(claude_cli.ask(
                prompts.worksheet(plan, spec["name"], spec.get("purpose", "")),
                model=model, timeout=_timeout("worksheet")))
        except Exception as exc:  # noqa: BLE001
            job.log("Worksheet '%s' failed (%s); skipping." % (slug, exc))
            continue
        _write(os.path.join(root, "templates", "%s.md" % slug), text)
        job.emit("worksheet", slug=slug, name=spec["name"])


# --------------------------------------------------------------------------- editing a course
#
# A course is never finished. The reader meets a section that stops short, or a topic the
# curriculum skipped, and wants the course to go there. These entry points change one module
# of an existing course and leave the rest alone: a new module appended to a part, or an
# existing one rewritten in place with direction. Both reuse the same writers as a fresh run,
# fed a plan reconstructed from the course on disk rather than from a brief.

DEFAULT_SECTIONS = (
    "Why this matters", "Core concepts", "How it works in practice",
    "2026 reality check", "Common mistakes", "Exercise", "If you remember one thing",
)


def plan_from_course(cfg, modules) -> Dict[str, Any]:
    """The plan-shaped view of an existing course that the module prompts expect."""
    return {
        "title": cfg.title,
        "tagline": cfg.tagline,
        "subject": cfg.subject,
        "hours": cfg.hours,
        "audience": cfg.audience,
        "practitioner": cfg.practitioner,
        "tutorPersona": cfg.tutor_persona,
        "parts": [{"id": p.id, "name": p.name, "hours": p.hours, "dir": p.dir, "blurb": p.blurb}
                  for p in cfg.parts],
        "modules": [{
            "id": m.id, "part": m.part, "title": m.title, "short": m.short,
            "minutes": m.minutes, "summary": "",
            "sections": [s.heading for s in m.sections],
            "requires": list(getattr(m, "requires", []) or []),
        } for m in modules],
    }


def next_module_id(modules) -> str:
    """One past the highest numbered id. Ids are never reused: progress is keyed by them."""
    highest = 0
    for m in modules:
        mid = getattr(m, "id", None) if not isinstance(m, dict) else m.get("id", "")
        found = re.match(r"^M(\d+)$", mid or "")
        if found:
            highest = max(highest, int(found.group(1)))
    return "M%02d" % (highest + 1)


def _fix_spec(raw: Any, mid: str, part_id: str, topic: str, minutes: int,
              known_ids=()) -> Dict[str, Any]:
    """Coerce a designed module spec into the shape the writer needs."""
    raw = raw if isinstance(raw, dict) else {}
    spec = {
        "id": mid,
        "part": part_id,
        "title": (str(raw.get("title") or topic).strip() or topic)[:120],
        "short": (str(raw.get("short") or topic).strip() or topic)[:60],
        "summary": str(raw.get("summary") or "").strip(),
    }
    try:
        spec["minutes"] = max(15, min(240, int(raw.get("minutes") or minutes)))
    except (TypeError, ValueError):
        spec["minutes"] = minutes
    sections = [str(x).strip() for x in (raw.get("sections") or []) if str(x).strip()]
    spec["sections"] = sections or list(DEFAULT_SECTIONS)
    known = set(known_ids)
    spec["requires"] = [str(r).strip() for r in (raw.get("requires") or [])
                        if str(r).strip() in known and str(r).strip() != mid][:3]
    return spec


def _read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _store_module_data(root: str, cfg, mid: str, assess: Dict[str, Any],
                       suggest: List[List[str]]) -> None:
    """Put one module's study data where the build will find it.

    If some file already holds an entry for this id, it is replaced there, so a rewrite does
    not leave a duplicate for the validator to reject. Otherwise the module gets files of its
    own - the loader merges every .json in the directory, so nothing else has to change.
    """
    assess_dir = cfg.path(cfg.data["assessments"])
    sugg_dir = cfg.path(cfg.data["suggestions"])
    os.makedirs(assess_dir, exist_ok=True)
    os.makedirs(sugg_dir, exist_ok=True)

    placed = False
    for name in sorted(os.listdir(assess_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(assess_dir, name)
        rows = _read_json(path)
        if isinstance(rows, list) and any(isinstance(r, dict) and r.get("id") == mid for r in rows):
            _write_json(path, [assess if (isinstance(r, dict) and r.get("id") == mid) else r
                               for r in rows])
            placed = True
    if not placed:
        _write_json(os.path.join(assess_dir, "%s.json" % mid), [assess])

    placed = False
    for name in sorted(os.listdir(sugg_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(sugg_dir, name)
        rows = _read_json(path)
        if isinstance(rows, dict) and mid in rows:
            rows[mid] = suggest
            _write_json(path, rows)
            placed = True
    if not placed:
        _write_json(os.path.join(sugg_dir, "%s.json" % mid), {mid: suggest})


def _set_short_title(root: str, mid: str, short: str) -> None:
    path = os.path.join(root, "course.json")
    manifest = _read_json(path)
    titles = manifest.get("shortTitles") or {}
    titles[mid] = short
    manifest["shortTitles"] = titles
    _write_json(path, manifest)


def extend(job: Job, courses_dir: str, dist_dir: str, course_id: str,
           brief: Dict[str, Any]) -> Dict[str, Any]:
    """Add one module on a topic the course does not cover yet, then rebuild."""
    root = os.path.join(courses_dir, course_id)
    cfg = ck_config.load(root)
    modules = ck_loader.load_modules(cfg)
    plan = plan_from_course(cfg, modules)
    model = brief.get("model", "")
    job.meta["course"] = course_id

    topic = (brief.get("topic") or "").strip()
    if not topic:
        raise GenerationError("Say what the new module should cover.")
    part = (next((p for p in plan["parts"] if p["id"] == brief.get("part")), None)
            or plan["parts"][-1])
    try:
        minutes = max(15, min(240, int(brief.get("minutes") or 60)))
    except (TypeError, ValueError):
        minutes = 60
    notes = brief.get("notes", "")
    mid = next_module_id(modules)
    total = 5

    job.progress(1, total, "Designing %s · %s" % (mid, topic))
    spec = _fix_spec(
        claude_cli.ask_json(prompts.module_spec(plan, plan["modules"], topic, part["name"],
                                                minutes, notes), model=model, timeout=_timeout("moduleSpec")),
        mid, part["id"], topic, minutes, known_ids=[m["id"] for m in plan["modules"]],
    )
    plan["modules"].append(spec)
    job.emit("spec", id=mid, title=spec["title"], part=part["id"], minutes=spec["minutes"])

    job.check_cancelled()
    job.progress(2, total, "Writing %s · %s" % (mid, spec["title"]))
    body = write_module(job, root, plan, spec, model, notes=notes)

    job.check_cancelled()
    job.progress(3, total, "Quiz and flashcards for %s" % mid)
    data = write_study_data(job, root, plan, spec, body, model)
    _store_module_data(root, cfg, mid, data["assess"], data["suggest"])
    _set_short_title(root, mid, spec["short"])

    job.check_cancelled()
    job.progress(4, total, "Validating and building")
    result = build_course(root, dist_dir)
    job.progress(5, total, "Done")
    job.emit("built", **result)
    return dict(result, course=course_id, root=root, module=mid)


def rewrite(job: Job, courses_dir: str, dist_dir: str, course_id: str, mid: str,
            brief: Dict[str, Any]) -> Dict[str, Any]:
    """Rewrite one existing module in place, with direction, then rebuild.

    The id, the file and the position in the course all stay. The reader's progress for the
    module is keyed by id and survives; section ticks may no longer line up if the section
    count changes, which is the honest price of a rewrite.
    """
    root = os.path.join(courses_dir, course_id)
    cfg = ck_config.load(root)
    modules = ck_loader.load_modules(cfg)
    current = next((m for m in modules if m.id == mid), None)
    if current is None:
        raise GenerationError("No module '%s' in this course." % mid)
    plan = plan_from_course(cfg, modules)
    model = brief.get("model", "")
    notes = brief.get("notes", "")
    job.meta["course"] = course_id

    spec = next(m for m in plan["modules"] if m["id"] == mid)
    spec["summary"] = "A rewrite of the existing module." + (
        " The person asked for: " + notes if notes else "")
    total = 4

    job.progress(1, total, "Rewriting %s · %s" % (mid, current.title))
    body = write_module(job, root, plan, spec, model, path=current.source, notes=notes)

    job.check_cancelled()
    job.progress(2, total, "Quiz and flashcards for %s" % mid)
    data = write_study_data(job, root, plan, spec, body, model)
    _store_module_data(root, cfg, mid, data["assess"], data["suggest"])

    job.check_cancelled()
    job.progress(3, total, "Validating and building")
    result = build_course(root, dist_dir)
    job.progress(4, total, "Done")
    job.emit("built", **result)
    return dict(result, course=course_id, root=root, module=mid)


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

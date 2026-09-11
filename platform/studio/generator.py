"""The generation pipeline: a brief in, a built course out.

    plan  ->  [approval gate]  ->  modules (+ figures)  ->  study data  ->  reference  ->  check  ->  build

Two design points worth knowing before changing anything here.

**Everything is written to disk as it is produced.** A run that dies at module 14 leaves
fourteen real modules behind, and rerunning overwrites cleanly. Nothing is held in memory
waiting for a final commit.

**The section/suggestion invariant is satisfied by construction, not by hope.** After a
module is written, its actual headings are parsed back off disk and passed to the suggestion
prompt, which is asked for exactly that many sets. The result is then counted, and padded or
trimmed if the model still miscounted (`coerce.fix_suggestions`). Asking a model to
"remember to produce N" and trusting it is how this breaks.

The writers here (`write_module`, `write_study_data`) are shared with `editing.py`, which
adds or rewrites one module of an existing course.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from coursekit import assessments as ck_assess
from coursekit import config as ck_config
from coursekit import library as ck_library
from coursekit import loader as ck_loader
from coursekit import renderer as ck_renderer
from coursekit import scaffold as ck_scaffold
from coursekit import validate as ck_validate
from coursekit.settings import SETTINGS

from . import modelcall, figures, notebooks, overrides, prompts
from .coerce import fix_assessment, fix_suggestions
from .curriculum import (DEFAULT_SECTIONS, PLAN_FILE, load_plan, make_plan, normalise_plan,
                         plan_to_manifest, wants_notebooks)
from .errors import GenerationError
from .files import read_json, read_text, slug, write_json, write_text
from .ids import is_course_id
from .jobs import Job

MAX_CORPUS_CHARS = int(SETTINGS.get("generation.maxCorpusChars"))   # what the glossary and mental-models calls see
MAX_WORKSHEETS = int(SETTINGS.get("generation.maxWorksheets"))

ASSESSMENTS_FILE = "data/assessments/all.json"
SUGGESTIONS_FILE = "data/suggestions/all.json"


def headings_of(markdown: str) -> List[str]:
    """The `##` headings that will survive the build.

    Delegates to the loader so this can never disagree with what the build actually counts -
    an empty heading is dropped by both, which is what keeps the suggestion count honest.
    """
    return [s.heading for s in ck_loader.parse_sections(markdown)]


# --------------------------------------------------------------------------- writers


def module_path(root: str, plan: Dict[str, Any], mod: Dict[str, Any]) -> str:
    """Where a module of the plan lives: `modules/<part dir>/<id>-<slug>.md`."""
    directory = next(p["dir"] for p in plan["parts"] if p["id"] == mod["part"])
    return os.path.join(root, "modules", directory, "%s-%s.md" % (mod["id"], slug(mod["title"])))


def module_prompt(plan: Dict[str, Any], mod: Dict[str, Any], notes: str = "",
                  root: str = "") -> str:
    """The whole prompt one module is written from.

    It is a function of its own because both the approval gate and the course page show it:
    what a person is asked to approve is a curriculum, and a curriculum is only worth editing
    if you can read what each line of it turns into - and change it (`overrides`). A prompt
    assembled anywhere else would drift from the one the run sends.
    """
    spec = dict(mod)
    spec["sections"] = [s for s in (spec.get("sections") or []) if str(s).strip()] or list(
        DEFAULT_SECTIONS)
    prompt = prompts.module(plan, plan["modules"], spec)
    if spec["id"] == "M01":
        prompt += prompts.module_first(plan)
    return overrides.apply(root, spec["id"], "module", prompt + prompts.direction(notes))


def assessment_prompt(plan: Dict[str, Any], mod: Dict[str, Any], body: str,
                      root: str = "") -> str:
    """The prompt the quiz and flashcards are written from."""
    return overrides.apply(root, mod["id"], "assessment", prompts.assessment(plan, mod, body),
                           body=body)


def suggestions_prompt(plan: Dict[str, Any], mod: Dict[str, Any], headings: List[str],
                       body: str, root: str = "") -> str:
    """The prompt the chat rail's suggested questions are written from."""
    return overrides.apply(root, mod["id"], "suggestions",
                           prompts.suggestions(plan, mod["id"], headings, body), body=body)


def write_module(job: Job, root: str, plan: Dict[str, Any], mod: Dict[str, Any],
                 model: str = "", path: str = "", notes: str = "") -> str:
    """Ask for the text of one module, repair its head, write it, and return the body."""
    prompt = module_prompt(plan, mod, notes, root)
    reply = modelcall.ask(prompt, model=model, timeout=modelcall.timeout_for("module"),
                           what="the text of %s" % mod["id"])
    body = repair_head(modelcall.strip_fence(reply), mod)

    path = path or module_path(root, plan, mod)
    write_text(path, body)
    found = headings_of(body)
    if not found:
        raise GenerationError("%s came back with no usable sections." % mod["id"])
    job.emit("module", id=mod["id"], title=mod["title"], sections=len(found),
             words=len(body.split()), path=os.path.relpath(path, root))
    return body


def repair_head(body: str, mod: Dict[str, Any]) -> str:
    """Make the head of a module what the build expects, whatever the model returned.

    The build keys everything off the title line, so it is repaired rather than failing the
    run; `**Time:**` and `**Requires:**` are added when missing.
    """
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
    return body


def write_study_data(job: Job, root: str, plan: Dict[str, Any], mod: Dict[str, Any],
                     body: str, model: str = "") -> Dict[str, Any]:
    """The quiz, flashcards and suggested questions for one module, coerced to valid shapes."""
    headings = headings_of(body)
    assess = fix_assessment(
        modelcall.ask_json(assessment_prompt(plan, mod, body, root), model=model,
                            timeout=modelcall.timeout_for("studyData"),
                            what="the quiz and flashcards for %s" % mod["id"]),
        mod["id"],
    )
    suggest = fix_suggestions(
        modelcall.ask_json(suggestions_prompt(plan, mod, headings, body, root),
                            model=model, timeout=modelcall.timeout_for("studyData"),
                            what="the suggested questions for %s" % mod["id"]),
        headings,
    )
    job.emit("studydata", id=mod["id"], quiz=len(assess["quiz"]),
             cards=len(assess["cards"]), sections=len(suggest))
    return {"assess": assess, "suggest": suggest}


# --------------------------------------------------------------------------- resuming


def existing_module(root: str, plan: Dict[str, Any], mod: Dict[str, Any]) -> str:
    """The body of a module already on disk for this id, or '' if none."""
    path = existing_module_path(root, plan, mod)
    if not path:
        return ""
    body = read_text(path)
    return body if headings_of(body) else ""


def existing_module_path(root: str, plan: Dict[str, Any], mod: Dict[str, Any]) -> str:
    """Where a module of this id already sits, whatever its slug, or '' if nowhere."""
    directory = os.path.dirname(module_path(root, plan, mod))
    if not os.path.isdir(directory):
        return ""
    for name in sorted(os.listdir(directory)):
        if name.endswith(".md") and name.split("-", 1)[0] == mod["id"]:
            return os.path.join(directory, name)
    return ""


def draw_figures(job: Job, root: str, plan: Dict[str, Any], mod: Dict[str, Any], body: str,
                 path: str, model: str) -> str:
    """Figures for a module just written. Optional: a failure here must not lose the run,
    so it is logged and the module ships without them."""
    try:
        return figures.write_figures(job, root, plan, mod, body, path, model)
    except Exception as exc:  # noqa: BLE001 - any failure of an optional step is reported, not raised
        job.log("Could not draw figures for %s (%s); continuing without them." % (mod["id"], exc))
        return body


def draw_notebooks(job: Job, root: str, plan: Dict[str, Any], mod: Dict[str, Any], body: str,
                   path: str, model: str) -> str:
    """Notebooks for a module just written. Optional, like figures: a failure is logged
    and the module ships without them."""
    try:
        return notebooks.write_notebooks(job, root, plan, mod, body, path, model)
    except Exception as exc:  # noqa: BLE001 - any failure of an optional step is reported, not raised
        job.log("Could not write notebooks for %s (%s); continuing without them." % (mod["id"], exc))
        return body


def existing_study_data(root: str):
    """Study data a previous run already wrote, keyed by module id: (assessments, suggestions)."""
    assess, suggest = {}, {}
    path = os.path.join(root, ASSESSMENTS_FILE)
    if os.path.isfile(path):
        rows = read_json(path)
        if isinstance(rows, list):
            assess = {r["id"]: r for r in rows if isinstance(r, dict) and r.get("id")}
    path = os.path.join(root, SUGGESTIONS_FILE)
    if os.path.isfile(path):
        rows = read_json(path)
        suggest = rows if isinstance(rows, dict) else {}
    return assess, suggest


def is_real_file(path: str) -> bool:
    """A reference document that was actually written, not a scaffold stub."""
    if not os.path.isfile(path) or os.path.getsize(path) < 400:
        return False
    return ck_scaffold.PLACEHOLDER.strip() not in read_text(path)[:600]


# --------------------------------------------------------------------------- the pipeline


def generate(job: Job, courses_dir: str, dist_dir: str, brief: Dict[str, Any]) -> Dict[str, Any]:
    """Run the whole pipeline. Parks once for curriculum approval.

    With `brief["resume"]`, picks up a course whose earlier run died: the saved curriculum is
    reused without a new approval, modules and study data already on disk are kept, and only
    what is missing gets written. A run can therefore be resumed any number of times.
    """
    resume = bool(brief.get("resume"))
    course_id = brief.get("id") or ck_scaffold.slugify(brief["theme"])
    if not is_course_id(course_id):
        raise GenerationError("'%s' is not a usable course id." % course_id)
    model = brief.get("model", "")
    job.meta["course"] = course_id
    root = os.path.join(courses_dir, course_id)

    plan = _approved_plan(job, root, course_id, brief, resume, model)
    _lay_down_tree(root, course_id, plan, resume)

    modules = plan["modules"]
    with_figures = figures.enabled() and brief.get("figures", True) is not False
    # The plan says whether the course has notebooks; the request (a resume's switch) can
    # still leave them out of this run.
    with_notebooks = (notebooks.enabled() and bool(plan.get("notebooks"))
                      and wants_notebooks(brief) != "no")
    per_module = 2 + int(with_figures) + int(with_notebooks)   # text, figures, notebooks, study data
    steps = _Steps(job, total=len(modules) * per_module + 6)   # + reference + build
    bodies = _write_modules(job, root, plan, model, resume, steps, with_figures, with_notebooks)
    _write_reference(job, root, plan, bodies, model, resume, steps)

    steps.next("Validating and building")
    job.log("Checking every module, quiz and suggestion file, then rendering the page.")
    result = build_course(root, dist_dir)
    job.emit("built", **result)
    return dict(result, course=course_id, root=root)


class _Steps:
    """Counts the progress steps of a run so each stage need not know the others' lengths."""

    def __init__(self, job: Job, total: int):
        self.job, self.total, self.done = job, total, 0

    def next(self, label: str) -> None:
        self.job.check_cancelled()
        self.done += 1
        self.job.progress(self.done, self.total, label)


def _approved_plan(job: Job, root: str, course_id: str, brief: Dict[str, Any],
                   resume: bool, model: str) -> Dict[str, Any]:
    """The curriculum to write: the saved one on a resume, else a new one the person approved."""
    if resume:
        plan = load_plan(root)
        job.log("Resuming %s from its saved curriculum: %d modules across %d parts."
                % (course_id, len(plan["modules"]), len(plan["parts"])))
        return plan
    plan = make_plan(job, brief, model)
    job.emit("plan", plan=plan)
    approved = job.await_input("approve-plan", {"plan": plan, "id": course_id})
    if isinstance(approved, dict) and approved.get("plan"):
        # The gate is where the length is really decided: a curriculum trimmed there is a
        # shorter course, and the manifest and every module prompt should say so.
        plan = normalise_plan(approved["plan"], brief["theme"],
                              _approved_hours(approved["plan"], float(brief["hours"])), brief)
    job.log("Curriculum approved: %d modules across %d parts."
            % (len(plan["modules"]), len(plan["parts"])))
    return plan


def _approved_hours(plan: Dict[str, Any], asked: float) -> float:
    """The hours the approved curriculum claims, or what was asked for if it says nothing."""
    try:
        hours = float(plan.get("hours") or 0)
    except (TypeError, ValueError):
        hours = 0
    return hours if hours > 0 else asked


def _lay_down_tree(root: str, course_id: str, plan: Dict[str, Any], resume: bool) -> None:
    """The folders, the manifest, the README and the saved plan."""
    for part in plan["parts"]:
        os.makedirs(os.path.join(root, "modules", part["dir"]), exist_ok=True)
    for sub in ("plan", "reference", "templates", "figures", "data/assessments", "data/suggestions"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    if plan.get("notebooks"):
        os.makedirs(os.path.join(root, notebooks.ck_notebooks.NOTEBOOKS_DIR), exist_ok=True)
    if not resume:
        write_json(os.path.join(root, "course.json"), plan_to_manifest(plan, course_id))
    ck_scaffold.write_readme(root, course_id, plan["title"])
    # Prompts edited at the gate were written before the course existed; they belong to the
    # course from here on, and every later rewrite reads them from there.
    overrides.merge(root, plan.get("prompts"))
    write_json(os.path.join(root, PLAN_FILE), plan)


def _write_modules(job: Job, root: str, plan: Dict[str, Any], model: str, resume: bool,
                   steps: _Steps, with_figures: bool = False,
                   with_notebooks: bool = False) -> Dict[str, str]:
    """Every module with its figures, its notebooks and its study data written
    immediately after. Returns the bodies."""
    had_assess, had_suggest = existing_study_data(root) if resume else ({}, {})
    bodies: Dict[str, str] = {}
    assess_rows: List[Dict[str, Any]] = []
    suggest_rows: Dict[str, Any] = {}
    for mod in plan["modules"]:
        mid = mod["id"]
        kept = existing_module(root, plan, mod) if resume else ""
        if kept:
            steps.next("Keeping %s · %s" % (mid, mod["title"]))
            job.log("%s is already written; keeping it." % mid)
            bodies[mid] = kept
        else:
            steps.next("Writing %s · %s" % (mid, mod["title"]))
            bodies[mid] = write_module(job, root, plan, mod, model)

        if with_figures:
            path = existing_module_path(root, plan, mod) or module_path(root, plan, mod)
            if kept and figures.references_in(kept, mid):
                steps.next("Keeping the figures of %s" % mid)
            else:
                steps.next("Figures for %s" % mid)
                bodies[mid] = draw_figures(job, root, plan, mod, bodies[mid], path, model)

        if with_notebooks:
            path = existing_module_path(root, plan, mod) or module_path(root, plan, mod)
            if kept and notebooks.references_in(kept, mid):
                steps.next("Keeping the notebooks of %s" % mid)
            else:
                steps.next("Notebooks for %s" % mid)
                bodies[mid] = draw_notebooks(job, root, plan, mod, bodies[mid], path, model)

        if kept and mid in had_assess and mid in had_suggest:
            steps.next("Keeping study data for %s" % mid)
            data = {"assess": had_assess[mid], "suggest": had_suggest[mid]}
        else:
            steps.next("Quiz and flashcards for %s" % mid)
            data = write_study_data(job, root, plan, mod, bodies[mid], model)
        assess_rows.append(data["assess"])
        suggest_rows[mid] = data["suggest"]
        # Written every iteration so an interrupted run still leaves valid data behind.
        write_json(os.path.join(root, ASSESSMENTS_FILE), assess_rows)
        write_json(os.path.join(root, SUGGESTIONS_FILE), suggest_rows)
    return bodies


def _write_reference(job: Job, root: str, plan: Dict[str, Any], bodies: Dict[str, str],
                     model: str, resume: bool, steps: _Steps) -> None:
    """The glossary, mental models, resources, plan documents and worksheets."""
    modules = plan["modules"]
    corpus = _corpus(bodies)

    def shelf(label: str, rel: str, prompt: str, step: str, what: str) -> None:
        path = os.path.join(root, rel)
        if resume and is_real_file(path):
            steps.next("Keeping " + label)
            return
        steps.next(label)
        reply = modelcall.ask(prompt, model=model, timeout=modelcall.timeout_for(step), what=what)
        write_text(path, modelcall.strip_fence(reply))

    shelf("Glossary", "reference/glossary.md",
          prompts.glossary(plan, modules, corpus), "reference", "the glossary")
    shelf("Mental models", "reference/mental-models.md",
          prompts.mental_models(plan, corpus), "reference", "the mental models")
    shelf("Resources", "reference/resources.md",
          prompts.resources(plan), "resources", "the resources list")

    steps.next("Plan documents")
    for kind, filename in (("curriculum", "curriculum.md"), ("how", "how-to-study.md"),
                           ("expert", "path-to-expert.md")):
        path = os.path.join(root, "plan", filename)
        if resume and is_real_file(path):
            continue
        reply = modelcall.ask(prompts.plan_docs(plan, modules, kind), model=model,
                               timeout=modelcall.timeout_for("planDocs"), what="plan/" + filename)
        write_text(path, modelcall.strip_fence(reply))

    templates_dir = os.path.join(root, "templates")
    if resume and any(f.endswith(".md") for f in os.listdir(templates_dir)):
        steps.next("Keeping worksheets")
    else:
        steps.next("Worksheets")
        _write_worksheets(job, root, plan, modules, model)


def _corpus(bodies: Dict[str, str]) -> str:
    """A budgeted sample of the course for the glossary and mental-models calls."""
    if not bodies:
        return ""
    per = max(1200, MAX_CORPUS_CHARS // len(bodies))
    return "\n\n".join("### %s\n%s" % (mid, text[:per]) for mid, text in sorted(bodies.items()))


def _write_worksheets(job: Job, root: str, plan: Dict[str, Any],
                      modules: List[Dict[str, Any]], model: str) -> None:
    """Worksheets are optional: a failure here must not lose a finished course."""
    try:
        wanted = modelcall.ask_json(prompts.worksheet_plan(plan, modules), model=model,
                                     timeout=modelcall.timeout_for("worksheetPlan"),
                                     what="the worksheet list")
    except Exception as exc:  # noqa: BLE001
        job.log("Could not plan worksheets (%s); continuing without them." % exc)
        return
    if not isinstance(wanted, list):
        return
    for spec in wanted[:MAX_WORKSHEETS]:
        if not isinstance(spec, dict) or not spec.get("name"):
            continue
        job.check_cancelled()
        name = slug(spec.get("slug") or spec["name"])
        try:
            text = modelcall.strip_fence(modelcall.ask(
                prompts.worksheet(plan, spec["name"], spec.get("purpose", "")), model=model,
                timeout=modelcall.timeout_for("worksheet"), what="the worksheet '%s'" % spec["name"]))
        except Exception as exc:  # noqa: BLE001
            job.log("Worksheet '%s' failed (%s); skipping." % (name, exc))
            continue
        write_text(os.path.join(root, "templates", "%s.md" % name), text)
        job.emit("worksheet", slug=name, name=spec["name"])


# --------------------------------------------------------------------------- check and build


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
        "modules": out.modules, "sections": out.sections, "figures": out.figures,
        "notebooks": out.notebooks, "quiz": out.quiz_items,
        "cards": out.cards, "glossary": out.glossary, "models": out.models,
        "templates": out.templates, "kb": round(out.kb),
        "web": out.web_path, "local": out.local_path,
    }


def check_course(root: str) -> List[str]:
    """Every validation problem of a course, as `build.py check` reports them."""
    cfg = ck_config.load(root)
    modules = ck_loader.load_modules(cfg)
    return ck_validate.check(modules, ck_assess.load_assessments(cfg),
                             ck_assess.load_suggestions(cfg))

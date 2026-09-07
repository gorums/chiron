"""Changing one module of an existing course.

A course is never finished. The reader meets a section that stops short, or a topic the
curriculum skipped, and wants the course to go there. Three entry points change one module
and leave the rest alone:

    extend(...)    a new module appended to a part, under the next free id
    rewrite(...)   an existing module written again in place, with direction
    patch (rewrite with mode "patch")   the module as it is, with only the notes applied
    draw(...)      figures for one module, or for every module that has none

All of them reuse the writers in `generator.py`, fed a plan reconstructed from the course on
disk rather than from a brief, and end with a build. Ids are never reused: the reader's
progress is keyed by them.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from coursekit import assessments as ck_assess
from coursekit import config as ck_config
from coursekit import loader as ck_loader

from . import claude_cli, figures, notebooks, prompts
from .coerce import fix_assessment, fix_spec, fix_suggestions
from .curriculum import next_module_id, plan_from_course
from .errors import GenerationError
from .files import read_json, read_text, write_json, write_text
from .generator import (build_course, draw_figures, draw_notebooks, headings_of, module_path,
                        repair_head,
                        write_module, write_study_data)
from .jobs import Job


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
    with_figures = _wants_figures(brief)
    with_notebooks = _wants_notebooks(cfg, brief)
    mid = next_module_id(modules)
    total = 5 + int(with_figures) + int(with_notebooks)

    job.progress(1, total, "Designing %s · %s" % (mid, topic))
    spec = fix_spec(
        claude_cli.ask_json(prompts.module_spec(plan, plan["modules"], topic, part["name"],
                                                minutes, notes), model=model,
                            timeout=claude_cli.timeout_for("moduleSpec"),
                            what="the design of %s" % mid),
        mid, part["id"], topic, minutes, known_ids=[m["id"] for m in plan["modules"]],
    )
    plan["modules"].append(spec)
    job.emit("spec", id=mid, title=spec["title"], part=part["id"], minutes=spec["minutes"])

    job.check_cancelled()
    job.progress(2, total, "Writing %s · %s" % (mid, spec["title"]))
    body = write_module(job, root, plan, spec, model, notes=notes)
    step = 3
    if with_figures:
        job.check_cancelled()
        job.progress(step, total, "Figures for %s" % mid)
        body = draw_figures(job, root, plan, spec, body, module_path(root, plan, spec), model)
        step += 1
    if with_notebooks:
        job.check_cancelled()
        job.progress(step, total, "Notebooks for %s" % mid)
        body = draw_notebooks(job, root, plan, spec, body, module_path(root, plan, spec), model)
        step += 1

    job.check_cancelled()
    job.progress(step, total, "Quiz and flashcards for %s" % mid)
    data = write_study_data(job, root, plan, spec, body, model)
    store_module_data(root, cfg, mid, data["assess"], data["suggest"])
    set_short_title(root, mid, spec["short"])

    job.check_cancelled()
    job.progress(step + 1, total, "Validating and building")
    result = _finish(job, root, dist_dir)
    job.progress(total, total, "Done")
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
    if brief.get("mode") == "patch":
        job.meta["mode"] = "patch"
        return _patch(job, root, dist_dir, cfg, course_id, current, plan, spec, model, notes)
    spec["summary"] = "A rewrite of the existing module." + (
        " The person asked for: " + notes if notes else "")
    with_figures = _wants_figures(brief)
    with_notebooks = _wants_notebooks(cfg, brief)
    total = 4 + int(with_figures) + int(with_notebooks)

    job.progress(1, total, "Rewriting %s · %s" % (mid, current.title))
    body = write_module(job, root, plan, spec, model, path=current.source, notes=notes)
    step = 2
    if with_figures:
        job.check_cancelled()
        job.progress(step, total, "Figures for %s" % mid)
        body = draw_figures(job, root, plan, spec, body, current.source, model)
        step += 1
    if with_notebooks:
        job.check_cancelled()
        job.progress(step, total, "Notebooks for %s" % mid)
        body = draw_notebooks(job, root, plan, spec, body, current.source, model)
        step += 1

    job.check_cancelled()
    job.progress(step, total, "Quiz and flashcards for %s" % mid)
    data = write_study_data(job, root, plan, spec, body, model)
    store_module_data(root, cfg, mid, data["assess"], data["suggest"])

    job.check_cancelled()
    job.progress(step + 1, total, "Validating and building")
    result = _finish(job, root, dist_dir)
    job.progress(total, total, "Done")
    return dict(result, course=course_id, root=root, module=mid, mode="rewrite")


def _wants_figures(brief: Dict[str, Any]) -> bool:
    """Figures are drawn unless settings turn them off or the request says `figures: false`."""
    return figures.enabled() and brief.get("figures", True) is not False


def _wants_notebooks(cfg, brief: Dict[str, Any]) -> bool:
    """Notebooks are written only for a course whose manifest declares them, and then
    unless settings turn them off or the request says `notebooks: false`."""
    return notebooks.enabled() and bool(cfg.notebooks) and brief.get("notebooks", True) is not False


def draw(job: Job, courses_dir: str, dist_dir: str, course_id: str,
         brief: Dict[str, Any]) -> Dict[str, Any]:
    """Figures for one module (`brief["module"]`), or for every module without any
    (`brief["all"]` redraws them all), then rebuild.

    A module's old figures are replaced, not added to. The text changes only by the
    reference lines, so the reader's section ticks stay where they were.
    """
    root = os.path.join(courses_dir, course_id)
    cfg = ck_config.load(root)
    modules = ck_loader.load_modules(cfg)
    plan = plan_from_course(cfg, modules)
    model = brief.get("model", "")
    job.meta["course"] = course_id

    wanted = _targets(modules, brief, lambda m: not m.figures)
    if not wanted:
        raise GenerationError("Every module already has figures. Ask for one module to redraw it.")
    total = len(wanted) + 2
    drawn: List[str] = []
    for i, current in enumerate(wanted, start=1):
        job.check_cancelled()
        job.progress(i, total, "Figures for %s · %s" % (current.id, current.title))
        spec = next(m for m in plan["modules"] if m["id"] == current.id)
        body = read_text(current.source)
        after = figures.write_figures(job, root, plan, spec, body, current.source, model)
        if figures.references_in(after, current.id):
            drawn.append(current.id)

    job.check_cancelled()
    job.progress(total - 1, total, "Validating and building")
    result = _finish(job, root, dist_dir)
    job.progress(total, total, "Done")
    single = wanted[0].id if len(wanted) == 1 else ""
    return dict(result, course=course_id, root=root, module=single, drawn=drawn)


def notebooks_job(job: Job, courses_dir: str, dist_dir: str, course_id: str,
                  brief: Dict[str, Any]) -> Dict[str, Any]:
    """Notebooks for one module (`brief["module"]`), or for every module without any
    (`brief["all"]` replaces them all), then rebuild. Refused for a course whose manifest
    declares no notebooks: the Settings tab is where they are turned on.

    A module's old notebooks are replaced, not added to. The text changes only by the
    reference lines, so the reader's section ticks stay where they were.
    """
    root = os.path.join(courses_dir, course_id)
    cfg = ck_config.load(root)
    if not cfg.notebooks:
        raise GenerationError("This course declares no notebooks. Turn them on in its Settings first.")
    modules = ck_loader.load_modules(cfg)
    plan = plan_from_course(cfg, modules)
    model = brief.get("model", "")
    job.meta["course"] = course_id

    wanted = _targets(modules, brief, lambda m: not m.notebooks)
    if not wanted:
        raise GenerationError("Every module already has notebooks. Ask for one module to replace them.")
    total = len(wanted) + 2
    written: List[str] = []
    for i, current in enumerate(wanted, start=1):
        job.check_cancelled()
        job.progress(i, total, "Notebooks for %s · %s" % (current.id, current.title))
        spec = next(m for m in plan["modules"] if m["id"] == current.id)
        body = read_text(current.source)
        after = notebooks.write_notebooks(job, root, plan, spec, body, current.source, model)
        if notebooks.references_in(after, current.id):
            written.append(current.id)

    job.check_cancelled()
    job.progress(total - 1, total, "Validating and building")
    result = _finish(job, root, dist_dir)
    job.progress(total, total, "Done")
    single = wanted[0].id if len(wanted) == 1 else ""
    return dict(result, course=course_id, root=root, module=single, written=written)


def _targets(modules, brief: Dict[str, Any], lacking) -> List[Any]:
    """The modules a figures or notebooks job works on: the one named, every one with
    `all`, else those `lacking` says have none yet."""
    mid = str(brief.get("module") or "").strip()
    if mid:
        current = next((m for m in modules if m.id == mid), None)
        if current is None:
            raise GenerationError("No module '%s' in this course." % mid)
        return [current]
    if brief.get("all"):
        return list(modules)
    return [m for m in modules if lacking(m)]


def _patch(job: Job, root: str, dist_dir: str, cfg, course_id: str, current, plan: Dict[str, Any],
           spec: Dict[str, Any], model: str, notes: str) -> Dict[str, Any]:
    """Change only what the notes name, in the text and in the study data.

    A full rewrite regenerates every sentence, so each pass fixes the last review's findings
    and creates new ones; the module never converges. A patch sends the module as it is and
    asks for it back with the notes applied. The suggested questions are kept unless the
    section headings changed, because they are matched to sections by position.
    """
    mid = spec["id"]
    before = read_text(current.source)
    total = 4

    job.progress(1, total, "Patching %s · %s" % (mid, current.title))
    reply = claude_cli.ask(prompts.patch_module(plan, plan["modules"], spec, before, notes),
                           model=model, timeout=claude_cli.timeout_for("module"),
                           what="the edited text of %s" % mid)
    body = repair_head(claude_cli.strip_fence(reply), spec)
    old_headings, new_headings = headings_of(before), headings_of(body)
    if not new_headings:
        raise GenerationError("%s came back with no usable sections." % mid)
    write_text(current.source, body)
    job.emit("module", id=mid, title=current.title, sections=len(new_headings),
             words=len(body.split()), path=os.path.relpath(current.source, root),
             patched=True, changedLines=_changed_lines(before, body))

    job.check_cancelled()
    job.progress(2, total, "Patching the quiz for %s" % mid)
    assess = ck_assess.load_assessments(cfg).get(mid)
    suggest = ck_assess.load_suggestions(cfg).get(mid)
    if isinstance(assess, dict) and assess.get("quiz"):
        prompt = prompts.patch_assessment(plan, spec, assess, notes, body)
        what = "the edited quiz for %s" % mid
    else:
        job.log("%s had no study data to patch; writing it fresh." % mid)
        prompt = prompts.assessment(plan, spec, body)
        what = "the quiz and flashcards for %s" % mid
    assess = fix_assessment(claude_cli.ask_json(
        prompt, model=model, timeout=claude_cli.timeout_for("studyData"), what=what), mid)

    headings_moved = (new_headings != old_headings or not isinstance(suggest, list)
                      or len(suggest) != len(new_headings))
    if headings_moved:
        job.log("The section headings changed, so the suggested questions are written again.")
        suggest = fix_suggestions(claude_cli.ask_json(
            prompts.suggestions(plan, mid, new_headings, body), model=model,
            timeout=claude_cli.timeout_for("studyData"),
            what="the suggested questions for %s" % mid), new_headings)
    else:
        job.log("Section headings unchanged: the suggested questions are kept as they were.")
    store_module_data(root, cfg, mid, assess, suggest)
    job.emit("studydata", id=mid, quiz=len(assess["quiz"]), cards=len(assess["cards"]),
             sections=len(suggest), patched=True)

    job.check_cancelled()
    job.progress(3, total, "Validating and building")
    result = _finish(job, root, dist_dir)
    job.progress(4, total, "Done")
    return dict(result, course=course_id, root=root, module=mid, mode="patch")


def _changed_lines(before: str, after: str) -> int:
    a, b = before.split("\n"), after.split("\n")
    return sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))


def _finish(job: Job, root: str, dist_dir: str) -> Dict[str, Any]:
    job.log("Checking every module, quiz and suggestion file, then rendering the page.")
    result = build_course(root, dist_dir)
    job.emit("built", **result)
    return result


# --------------------------------------------------------------------------- study data files


def store_module_data(root: str, cfg, mid: str, assess: Dict[str, Any],
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

    def holds(row: Any) -> bool:
        return isinstance(row, dict) and row.get("id") == mid

    placed = False
    for path in _json_files(assess_dir):
        rows = read_json(path)
        if isinstance(rows, list) and any(holds(r) for r in rows):
            write_json(path, [assess if holds(r) else r for r in rows])
            placed = True
    if not placed:
        write_json(os.path.join(assess_dir, "%s.json" % mid), [assess])

    placed = False
    for path in _json_files(sugg_dir):
        rows = read_json(path)
        if isinstance(rows, dict) and mid in rows:
            rows[mid] = suggest
            write_json(path, rows)
            placed = True
    if not placed:
        write_json(os.path.join(sugg_dir, "%s.json" % mid), {mid: suggest})


def set_short_title(root: str, mid: str, short: str) -> None:
    path = os.path.join(root, "course.json")
    manifest = read_json(path)
    titles = manifest.get("shortTitles") or {}
    titles[mid] = short
    manifest["shortTitles"] = titles
    write_json(path, manifest)


def _json_files(directory: str) -> List[str]:
    return [os.path.join(directory, n) for n in sorted(os.listdir(directory)) if n.endswith(".json")]

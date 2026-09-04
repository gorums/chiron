"""The curriculum: the plan a course is written from.

A plan is a JSON object - parts, modules, title, audience - that every prompt in
`prompts.py` reads. It comes from three places:

    make_plan(job, brief)          the model designs one from a theme and an hour budget
    plan_from_course(cfg, modules) the plan-shaped view of a course already on disk
    load_plan(root)                the approved plan a run saved, so a dead run can resume

`normalise_plan` repairs what a model reliably gets slightly wrong (ids, part references,
minutes) and rejects what cannot be repaired. `plan_to_manifest` turns an approved plan into
the `course.json` the build reads.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from coursekit import config as ck_config
from coursekit import loader as ck_loader
from coursekit import scaffold as ck_scaffold
from coursekit.errors import CourseError

from . import claude_cli, prompts
from .errors import GenerationError
from .files import read_json, slug
from .jobs import Job

PLAN_FILE = "plan/plan.json"    # the approved curriculum, kept so a dead run can resume

# The sections a module gets when the plan names none.
DEFAULT_SECTIONS = (
    "Why this matters", "Core concepts", "How it works in practice",
    "2026 reality check", "Common mistakes", "Exercise", "If you remember one thing",
)

_MODULE_REF = re.compile(r"^M(\d+)$")


# --------------------------------------------------------------------------- from a brief


def make_plan(job: Job, brief: Dict[str, Any], model: str = "") -> Dict[str, Any]:
    """Ask the model for a curriculum and normalise it."""
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
        timeout=claude_cli.timeout_for("plan"),
        what="the curriculum",
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

    _normalise_parts(parts)
    _normalise_modules(modules, [p["id"] for p in parts])

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
    anchor = plan.get("anchor") if isinstance(plan.get("anchor"), dict) else {}
    plan["anchor"] = {k: str(anchor[k]).strip() for k in ck_config.DEFAULT_ANCHOR
                      if anchor.get(k) and str(anchor[k]).strip()}
    return plan


def _normalise_parts(parts: List[Dict[str, Any]]) -> None:
    """Every part gets an id, a name and a folder name unique within the course."""
    seen_dirs = set()
    for i, part in enumerate(parts):
        part["id"] = part.get("id") or "p%d" % (i + 1)
        part["name"] = part.get("name") or "Part %d" % (i + 1)
        directory = slug(part.get("dir") or part["name"])
        while directory in seen_dirs:
            directory += "-x"
        seen_dirs.add(directory)
        part["dir"] = directory
        part["hours"] = part.get("hours") or 0
        part["blurb"] = part.get("blurb") or ""


def _normalise_modules(modules: List[Dict[str, Any]], part_ids: List[str]) -> None:
    """Modules are renumbered M01.. in order (models drift), placed in a real part, and
    given sections; prerequisites may only point backwards at modules that exist."""
    for i, mod in enumerate(modules):
        mod["id"] = "M%02d" % (i + 1)
        if mod.get("part") not in part_ids:
            spread = i * len(part_ids) // max(1, len(modules))
            mod["part"] = part_ids[min(spread, len(part_ids) - 1)]
        mod["title"] = (mod.get("title") or "Module %d" % (i + 1)).strip()
        mod["short"] = (mod.get("short") or mod["title"])[:60]
        try:
            mod["minutes"] = max(15, int(mod.get("minutes") or 60))
        except (TypeError, ValueError):
            mod["minutes"] = 60
        mod["summary"] = mod.get("summary") or ""
        sections = [str(s).strip() for s in (mod.get("sections") or []) if str(s).strip()]
        mod["sections"] = sections or list(DEFAULT_SECTIONS)

    ids = [m["id"] for m in modules]
    for i, mod in enumerate(modules):
        wanted = []
        for ref in (mod.get("requires") or []):
            found = _MODULE_REF.match(str(ref).strip().upper())     # models write "M3"
            rid = "M%02d" % int(found.group(1)) if found else ""
            if rid in ids[:i] and rid not in wanted:
                wanted.append(rid)
        mod["requires"] = wanted[:3]


def plan_to_manifest(plan: Dict[str, Any], course_id: str) -> Dict[str, Any]:
    """The `course.json` an approved plan describes."""
    manifest = ck_scaffold.manifest(plan["subject"], plan["hours"], course_id=course_id,
                                    title=plan["title"], practitioner=plan["practitioner"])
    manifest.update({
        "title": plan["title"],
        "tagline": plan["tagline"],
        "audience": plan["audience"],
        "tutorPersona": plan["tutorPersona"],
        "anchor": dict(ck_config.DEFAULT_ANCHOR, **(plan.get("anchor") or {})),
        "parts": [{k: p[k] for k in ("id", "name", "hours", "dir", "blurb")}
                  for p in plan["parts"]],
        "shortTitles": {m["id"]: m["short"] for m in plan["modules"]},
        "milestones": plan["milestones"],
        "folderLabel": course_id,
    })
    return manifest


# --------------------------------------------------------------------------- from a course


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
        mid = m.get("id", "") if isinstance(m, dict) else getattr(m, "id", None)
        found = _MODULE_REF.match(mid or "")
        if found:
            highest = max(highest, int(found.group(1)))
    return "M%02d" % (highest + 1)


def load_plan(root: str) -> Dict[str, Any]:
    """The saved curriculum - or, for a course generated before it was saved, one rebuilt
    from course.json and whatever modules are on disk."""
    path = os.path.join(root, PLAN_FILE)
    if not os.path.isfile(path):
        return reconstruct_plan(root)
    plan = read_json(path)
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
    missing = sorted((mid for mid in cfg.short_titles if mid not in have), key=_module_number)
    if not plan["modules"] and not missing:
        raise GenerationError("Nothing to resume: this course has no modules and no module list.")
    last_part = plan["parts"][-1]["id"] if plan["parts"] else "p1"
    for mid in missing:
        plan["modules"].append({
            "id": mid, "part": last_part, "title": cfg.short_titles[mid],
            "short": cfg.short_titles[mid], "minutes": 60, "summary": "",
            "sections": list(DEFAULT_SECTIONS),
        })
    plan["modules"].sort(key=lambda m: _module_number(m["id"]))
    return plan


def _module_number(mid: str) -> int:
    return int(mid[1:]) if mid[1:].isdigit() else 0

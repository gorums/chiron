"""Creating an empty course from a theme and an hour budget.

This lays down the folders, a filled-in `course.json` and placeholder documents. It writes
no teaching content — that is the authoring skill's job. The split matters: the shape of a
course is mechanical and deterministic, so it belongs in code; the content is judgement, so
it belongs to a model working from a brief.

Budget model
------------
An hour budget becomes modules by dividing at a target module length, then splitting the
modules across three parts in a fixed ratio. The ratio encodes the pedagogy the marketing
course was built on and the authoring skill inherits: durable fundamentals first, the bulk
of the time on the working core, and a final layer of the judgement calls that separate a
practitioner from a beginner.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from .errors import CourseError

MINUTES_PER_MODULE = 60
MIN_MODULES = 3

# (folder, display name, share of total hours, blurb template)
PART_PLAN = [
    ("01-foundations", "Foundations", 0.27,
     "The part that does not expire. Tactics change; this does not."),
    ("02-core", "Core", 0.46,
     "The working middle of the subject. This is where most of your hours go."),
    ("03-expert-layer", "Expert layer", 0.27,
     "What separates someone who follows instructions from someone who makes the call."),
]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    if not slug:
        raise CourseError("Could not make a folder name from %r." % text)
    return slug


def _tidy(value: float):
    """Keep whole hours as ints so the manifest reads `5`, not `5.0`."""
    return int(value) if float(value).is_integer() else round(float(value), 2)


def plan_parts(hours: float) -> List[Dict[str, Any]]:
    """Split an hour budget into parts with whole-hour budgets that sum exactly to `hours`."""
    if hours < MIN_MODULES:
        raise CourseError(
            "%g hours is too short to structure — the minimum is %d." % (hours, MIN_MODULES)
        )
    parts, assigned = [], 0.0
    for i, (folder, name, share, blurb) in enumerate(PART_PLAN):
        last = i == len(PART_PLAN) - 1
        budget = _tidy(hours - assigned) if last else _tidy(round(hours * share))
        assigned += budget
        parts.append(
            {
                "id": "p%d" % (i + 1),
                "name": name,
                "hours": budget,
                "dir": folder,
                "blurb": blurb,
            }
        )
    return parts


def module_counts(parts: List[Dict[str, Any]]) -> List[int]:
    """How many modules each part should hold at the target module length."""
    return [max(1, round(p["hours"] * 60 / MINUTES_PER_MODULE)) for p in parts]


def manifest(theme: str, hours: float, *, course_id: str = "", title: str = "",
             practitioner: str = "") -> Dict[str, Any]:
    course_id = course_id or slugify(theme)
    title = title or "%s Mastery" % theme.strip().title()
    parts = plan_parts(hours)
    return {
        "id": course_id,
        "title": title,
        "tagline": "%g hours · beginner to practitioner" % hours,
        "subject": theme.strip().lower(),
        "practitioner": practitioner or "practitioner",
        "audience": "a complete beginner",
        "hours": _tidy(hours),
        "output": "%s-course" % course_id,
        "folderLabel": "courses/%s" % course_id,
        "tutorPersona": "You are a sharp, plain-spoken %s tutor." % theme.strip().lower(),
        "parts": parts,
        "shortTitles": {},
        "milestones": [],
        "library": {
            "glossary": "reference/glossary.md",
            "models": "reference/mental-models.md",
            "resources": "reference/resources.md",
            "templates": "templates",
            "plan": {
                "curriculum": "plan/curriculum.md",
                "how": "plan/how-to-study.md",
                "expert": "plan/path-to-expert.md",
            },
        },
        "data": {"assessments": "data/assessments", "suggestions": "data/suggestions"},
    }


PLACEHOLDER = "<!-- Written by the course-author skill. Delete this line when you fill it in. -->\n"


def create(courses_dir: str, theme: str, hours: float, *, course_id: str = "",
           force: bool = False) -> str:
    """Lay down an empty but valid course tree. Returns its root path."""
    data = manifest(theme, hours, course_id=course_id)
    root = os.path.join(courses_dir, data["id"])
    if os.path.exists(root) and not force:
        raise CourseError("%s already exists. Pass --force to add to it." % root)

    for part in data["parts"]:
        os.makedirs(os.path.join(root, "modules", part["dir"]), exist_ok=True)
    for sub in ("plan", "reference", "templates", "data/assessments", "data/suggestions"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)

    with open(os.path.join(root, "course.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    stubs = {
        "plan/curriculum.md": "# Curriculum\n",
        "plan/how-to-study.md": "# How to study\n",
        "plan/path-to-expert.md": "# After the last module\n",
        "reference/glossary.md": "# Glossary\n",
        "reference/mental-models.md": "# Mental models\n",
        "reference/resources.md": "# Resources\n",
    }
    for rel, heading in stubs.items():
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(heading + "\n" + PLACEHOLDER)
    return root

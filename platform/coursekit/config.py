"""Reading and validating a course manifest.

`course.json` is the only thing that makes a folder a course. Everything the engine needs
to know that is not derivable from the markdown lives here, and nothing else in the engine
is allowed to hardcode a subject.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .errors import ManifestError

MANIFEST = "course.json"

# Fields a course must declare. Anything else has a defensible default.
REQUIRED = ("id", "title", "subject", "hours", "parts")

DEFAULT_LIBRARY: Dict[str, Any] = {
    "glossary": "reference/glossary.md",
    "models": "reference/mental-models.md",
    "resources": "reference/resources.md",
    "templates": "templates",
    "plan": {},
}

DEFAULT_DATA: Dict[str, str] = {
    "assessments": "data/assessments",
    "suggestions": "data/suggestions",
}

# The reader's own case: the one real thing every exercise is applied to. A marketing course
# calls it a business, a baking course a kitchen. The engine only ever says `anchor.label`.
DEFAULT_ANCHOR: Dict[str, str] = {
    "label": "Your own case",
    "prompt": "Every exercise in this course applies to one real situation of yours. "
              "Name it once and the tutor, the questions and the examples aim at it.",
    "placeholder": "e.g. the project, team or situation you have in mind",
    "noun": "my own case",
}


@dataclass
class Part:
    """One top-level division of a course: a folder of modules with an hour budget."""

    id: str
    name: str
    hours: float
    dir: str
    blurb: str = ""

    def public(self) -> Dict[str, Any]:
        """The subset the front end renders. `dir` is a build detail and stays behind."""
        return {"id": self.id, "name": self.name, "hours": self.hours, "blurb": self.blurb}


@dataclass
class CourseConfig:
    """A parsed, validated course.json plus the root it was loaded from."""

    root: str
    id: str
    title: str
    subject: str
    hours: float
    parts: List[Part]
    tagline: str = ""
    practitioner: str = "practitioner"
    audience: str = "a complete beginner"
    output: str = ""
    folder_label: str = ""
    tutor_persona: str = ""
    short_titles: Dict[str, str] = field(default_factory=dict)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    anchor: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ANCHOR))
    # Module ids in reading order. Optional: a module not listed sorts after the listed ones,
    # by filename, so an untouched course still reads M01, M02, ... Studio writes this when
    # a module is moved; part membership is still the folder the file sits in.
    order: List[str] = field(default_factory=list)
    library: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_LIBRARY))
    data: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_DATA))

    # ---- paths ----

    def path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    @property
    def modules_dir(self) -> str:
        return self.path("modules")

    @property
    def local_file(self) -> str:
        """Filename of the offline copy — the only one allowed to reach Anthropic."""
        return self.output + "-local.html"

    @property
    def web_file(self) -> str:
        return self.output + ".html"

    # ---- what the browser gets ----

    def runtime(self) -> Dict[str, Any]:
        """The CFG object injected into the page.

        Deliberately small: presentation strings and prompt fragments only. Course *content*
        travels in DATA. If a value is needed to render a sentence, it belongs here; if it is
        the sentence itself, it belongs in the markdown.
        """
        return {
            "id": self.id,
            "title": self.title,
            "tagline": self.tagline,
            "subject": self.subject,
            "practitioner": self.practitioner,
            "audience": self.audience,
            "hours": self.hours,
            "storageKey": "course_%s_v1" % self.id,
            "localFile": self.local_file,
            "folderLabel": self.folder_label,
            "tutorPersona": self.tutor_persona,
            "milestones": self.milestones,
            "anchor": self.anchor,
        }


def load(root: str) -> CourseConfig:
    """Load and validate `<root>/course.json`."""
    path = os.path.join(root, MANIFEST)
    if not os.path.isfile(path):
        raise ManifestError(
            "No %s in %s. A course folder needs one; run `build.py new` to scaffold." % (MANIFEST, root)
        )
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ManifestError("%s is not valid JSON: %s" % (path, exc)) from exc

    missing = [k for k in REQUIRED if k not in raw]
    if missing:
        raise ManifestError("%s is missing required field(s): %s" % (path, ", ".join(missing)))

    parts = []
    for i, p in enumerate(raw["parts"]):
        for key in ("id", "name", "dir"):
            if key not in p:
                raise ManifestError("%s: parts[%d] is missing '%s'" % (path, i, key))
        parts.append(
            Part(id=p["id"], name=p["name"], hours=p.get("hours", 0), dir=p["dir"], blurb=p.get("blurb", ""))
        )
    if not parts:
        raise ManifestError("%s declares no parts" % path)

    dup = _first_duplicate([p.id for p in parts])
    if dup:
        raise ManifestError("%s: two parts share the id '%s'" % (path, dup))

    library = dict(DEFAULT_LIBRARY)
    library.update(raw.get("library") or {})
    data = dict(DEFAULT_DATA)
    data.update(raw.get("data") or {})
    anchor = dict(DEFAULT_ANCHOR)
    if isinstance(raw.get("anchor"), dict):
        anchor.update({k: str(v) for k, v in raw["anchor"].items() if k in DEFAULT_ANCHOR and v})

    course_id = raw["id"]
    return CourseConfig(
        root=root,
        id=course_id,
        title=raw["title"],
        subject=raw["subject"],
        hours=raw["hours"],
        parts=parts,
        tagline=raw.get("tagline") or "%s hours" % raw["hours"],
        practitioner=raw.get("practitioner", "practitioner"),
        audience=raw.get("audience", "a complete beginner"),
        output=raw.get("output") or "%s-course" % course_id,
        folder_label=raw.get("folderLabel") or course_id,
        tutor_persona=raw.get("tutorPersona")
        or "You are a sharp, plain-spoken %s tutor." % raw["subject"],
        short_titles=raw.get("shortTitles") or {},
        milestones=raw.get("milestones") or [],
        anchor=anchor,
        order=[str(x) for x in (raw.get("order") or []) if isinstance(x, str)],
        library=library,
        data=data,
    )


def _first_duplicate(values):
    seen = set()
    for v in values:
        if v in seen:
            return v
        seen.add(v)
    return None

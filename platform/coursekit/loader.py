"""Turning a folder of module markdown into the structure the front end renders.

The module contract, which the authoring skill also enforces:

    # <ID> — <Title>

    **Time:** <n> minutes ...

    ## <Section heading>
    ...body...

    ## <Section heading>
    ...body...

Every `##` becomes one addressable section: a scroll target, a checkbox, a unit of chat
context, and one row of authored follow-up questions. That one-to-one mapping is why the
section count is validated rather than trusted.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .config import CourseConfig
from .errors import ContentError
from .markdown_render import to_html, to_text
from .settings import SETTINGS

# How much of a section the tutor is handed as context. Long enough to reason about,
# short enough to keep the prompt cheap on every message.
EXCERPT_CHARS = int(SETTINGS.get("build.excerptChars"))

_TIME = re.compile(r"^\*\*Time:\*\*\s*(.+)$", re.M)
_REQUIRES = re.compile(r"^\*\*Requires:\*\*\s*(.+)$", re.M)
_MODULE_ID = re.compile(r"\bM\d+\b")
_MINUTES = re.compile(r"(\d+)")
_TRAILING_RULE = re.compile(r"\n---\s*$")
_NEXT_LINK = re.compile(r"\*\*Next:\*\*.*$", re.S)
_BARE_RULE = re.compile(r"^---\s*$", re.M)


@dataclass
class Section:
    heading: str
    html: str
    text: str

    def public(self) -> Dict[str, str]:
        return {"h": self.heading, "html": self.html, "text": self.text}


@dataclass
class Module:
    id: str
    num: int
    part: str
    title: str
    short: str
    meta: str
    minutes: int
    sections: List[Section]
    source: str
    requires: List[str] = field(default_factory=list)
    assess: Dict[str, Any] = field(default_factory=dict)
    suggest: List[Any] = field(default_factory=list)

    def public(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "num": self.num,
            "part": self.part,
            "title": self.title,
            "short": self.short,
            "meta": self.meta,
            "minutes": self.minutes,
            "sections": [s.public() for s in self.sections],
            "requires": self.requires,
            "assess": self.assess,
            "suggest": self.suggest,
        }


def module_files(cfg: CourseConfig, part) -> List[str]:
    """The .md files of one part, in reading order.

    Filename order unless `course.json` carries an `order` list; then listed ids come first
    in that sequence and anything unlisted follows by filename. Studio's course listing uses
    this too, so the two never disagree about what "M03 comes after M07" means.
    """
    directory = os.path.join(cfg.modules_dir, part.dir)
    files = sorted(f for f in os.listdir(directory) if f.endswith(".md"))
    if not cfg.order:
        return files
    rank = {mid: i for i, mid in enumerate(cfg.order)}
    return sorted(files, key=lambda f: (rank.get(f.split("-", 1)[0], len(rank)), f))


def load_modules(cfg: CourseConfig) -> List[Module]:
    """Read every part folder in manifest order; number modules across the whole course."""
    modules: List[Module] = []
    for part in cfg.parts:
        directory = os.path.join(cfg.modules_dir, part.dir)
        if not os.path.isdir(directory):
            raise ContentError(
                "Part '%s' points at %s, which does not exist." % (part.id, directory)
            )
        files = module_files(cfg, part)
        if not files:
            raise ContentError("Part '%s' has no .md modules in %s." % (part.id, directory))
        for name in files:
            modules.append(
                parse_module(os.path.join(directory, name), part.id, len(modules) + 1, cfg)
            )
    return modules


def parse_module(path: str, part_id: str, num: int, cfg: CourseConfig) -> Module:
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()

    lines = raw.split("\n")
    if not lines or not lines[0].startswith("#"):
        raise ContentError("%s: first line must be '# <ID> — <Title>'." % path)

    title_line = lines[0].lstrip("# ").strip()
    head = title_line.split("—")
    module_id = head[0].strip().split()[0] if head[0].strip() else ""
    if not module_id:
        raise ContentError("%s: could not read a module id from the title line." % path)
    title = head[1].strip() if len(head) > 1 else title_line

    head_lines = "\n".join(lines[1:8])
    time_match = _TIME.search(head_lines)
    meta = time_match.group(1).strip() if time_match else ""
    minutes_match = _MINUTES.search(meta) if meta else None
    minutes = int(minutes_match.group(1)) if minutes_match else 60
    # An optional `**Requires:** M03, M04` line declares what this module builds on. The
    # page uses it to warn when a prerequisite is weak; nothing is ever locked.
    req_match = _REQUIRES.search(head_lines)
    requires: List[str] = []
    for rid in (_MODULE_ID.findall(req_match.group(1)) if req_match else []):
        if rid != module_id and rid not in requires:
            requires.append(rid)

    sections = parse_sections(raw)
    if not sections:
        raise ContentError("%s: no '## ' sections found — nothing to render." % path)

    return Module(
        id=module_id,
        num=num,
        part=part_id,
        title=title,
        short=cfg.short_titles.get(module_id, title),
        meta=meta,
        minutes=minutes,
        sections=sections,
        source=path,
        requires=requires,
    )


def parse_sections(raw: str) -> List[Section]:
    """Split a module body into its `##` sections.

    Public because it is the single definition of what counts as a section: Studio has to
    know the exact count to keep the suggestion files in step, and a second implementation
    would drift."""
    body = raw.split("\n## ", 1)
    if len(body) < 2:
        return []
    sections = []
    for chunk in ("## " + body[1]).split("\n## "):
        heading, _, rest = chunk.lstrip("# ").rstrip().partition("\n")
        rest = _TRAILING_RULE.sub("", rest).strip()
        rest = _NEXT_LINK.sub("", rest).strip()   # navigation belongs to the app, not the text
        rest = _BARE_RULE.sub("", rest).strip()
        if not rest:
            continue
        html = to_html(rest)
        sections.append(Section(heading=heading.strip(), html=html, text=to_text(html)[:EXCERPT_CHARS]))
    return sections

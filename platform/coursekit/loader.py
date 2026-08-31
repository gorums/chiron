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

# How much of a section the tutor is handed as context. Long enough to reason about,
# short enough to keep the prompt cheap on every message.
EXCERPT_CHARS = 2200

_TIME = re.compile(r"^\*\*Time:\*\*\s*(.+)$", re.M)
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
            "assess": self.assess,
            "suggest": self.suggest,
        }


def load_modules(cfg: CourseConfig) -> List[Module]:
    """Read every part folder in manifest order; number modules across the whole course."""
    modules: List[Module] = []
    for part in cfg.parts:
        directory = os.path.join(cfg.modules_dir, part.dir)
        if not os.path.isdir(directory):
            raise ContentError(
                "Part '%s' points at %s, which does not exist." % (part.id, directory)
            )
        files = sorted(f for f in os.listdir(directory) if f.endswith(".md"))
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

    time_match = _TIME.search("\n".join(lines[1:8]))
    meta = time_match.group(1).strip() if time_match else ""
    minutes_match = _MINUTES.search(meta) if meta else None
    minutes = int(minutes_match.group(1)) if minutes_match else 60

    sections = _parse_sections(raw)
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
    )


def _parse_sections(raw: str) -> List[Section]:
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

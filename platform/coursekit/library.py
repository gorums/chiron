"""The reference shelf: glossary, mental models, worksheets and plan documents.

Every piece here is optional. A course with no glossary should build; the Library view
simply shows less. This is the one part of the loader that degrades rather than fails,
because reference material is genuinely supplementary to the modules.

Worksheets are the one place markdown gets a small extension. A worksheet is meant to be
filled in, so the blanks an author writes naturally — a run of underscores, an empty table
cell, a `[ ]` checklist item, a fenced block tagged `answer` — become real inputs on the page.
The values live in the reader's progress, keyed by worksheet slug and field number.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple

from .config import CourseConfig
from .markdown_render import read_html, to_html

# **Term** — definition.  A leading \* marks a term worth memorising first.
_GLOSSARY_LINE = re.compile(r"^\*\*(\\\*)?(.+?)\*\*\s*[—–-]\s*(.+)$")
_NUMBERED = re.compile(r"^\d+\.")
_LEADING_NUMBER = re.compile(r"^\d+\.\s*")
_BARE_RULE = re.compile(r"^---\s*$", re.M)
_INLINE_MD = re.compile(r"[*_`\[\]]")
_USE_WITH = re.compile(r"\*\*Use with:\*\*\s*(.+)")
_MODULE_ID = re.compile(r"\bM\d+\b")

# The fill-in syntax, applied to rendered HTML outside <pre> blocks.
_ANSWER_BLOCK = re.compile(r'<pre><code class="language-answer">(.*?)</code></pre>', re.S)
_PRE = re.compile(r"(<pre>.*?</pre>)", re.S)
_BLANK = re.compile(r"_{4,}")
_EMPTY_CELL = re.compile(r"<td>(?:\s|&nbsp;)*</td>")
_CHECK_ITEM = re.compile(r"<li>\s*\[ \]\s*")
_HTML_TAG = re.compile(r"<[^>]+>")

BLURB_CHARS = 95


def build(cfg: CourseConfig) -> Dict[str, Any]:
    lib = cfg.library
    models, models_note = _models(cfg.path(lib["models"])) if lib.get("models") else ([], "")
    return {
        "glossary": _glossary(cfg.path(lib["glossary"])) if lib.get("glossary") else [],
        "models": models,
        "models_note": models_note,
        "templates": _templates(cfg.path(lib["templates"])) if lib.get("templates") else [],
        "resources": _optional_page(cfg.path(lib["resources"])) if lib.get("resources") else "",
        "plan": {key: _optional_page(cfg.path(rel)) for key, rel in (lib.get("plan") or {}).items()},
    }


def _optional_page(path: str) -> str:
    return read_html(path) if os.path.isfile(path) else ""


def _glossary(path: str) -> List[Dict[str, Any]]:
    if not os.path.isfile(path):
        return []
    entries = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = _GLOSSARY_LINE.match(line.strip())
            if m:
                entries.append(
                    {
                        "term": m.group(2).replace("\\*", "").strip(),
                        "star": bool(m.group(1)),
                        "def": m.group(3).strip(),
                    }
                )
    return entries


def _models(path: str):
    """Numbered `## 1. Name` headings become cards; any other heading becomes prose above them."""
    if not os.path.isfile(path):
        return [], ""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    models, note = [], ""
    for chunk in raw.split("\n## ")[1:]:
        heading, _, rest = chunk.partition("\n")
        rest = _BARE_RULE.sub("", rest).strip()
        heading = heading.strip()
        if _NUMBERED.match(heading):
            models.append({"title": _LEADING_NUMBER.sub("", heading), "html": to_html(rest)})
        else:
            note += "<h3>" + heading + "</h3>" + to_html(rest)
    return models, note


def _templates(directory: str) -> List[Dict[str, Any]]:
    if not os.path.isdir(directory):
        return []
    out = []
    for name in sorted(f for f in os.listdir(directory) if f.endswith(".md")):
        with open(os.path.join(directory, name), encoding="utf-8") as fh:
            raw = fh.read()
        lines = raw.split("\n")
        html, fields = fillable(to_html(raw))
        uses = _USE_WITH.search(raw)
        out.append(
            {
                "slug": name[:-3],
                "title": lines[0].lstrip("# ").strip(),
                "blurb": _blurb(lines[1:]),
                "html": html,
                "fields": fields,
                "uses": _MODULE_ID.findall(uses.group(1)) if uses else [],
            }
        )
    return out


def fillable(html: str) -> Tuple[str, int]:
    """Turn a worksheet's natural blanks into inputs. Returns (html, field count).

    Numbering is by position in the document, so a worksheet edited to add a blank in the
    middle renumbers the ones after it — which is the honest behaviour for a template that
    changed shape. Fenced code is left alone unless tagged `answer`.
    """
    counter = [0]

    def field(tag: str) -> str:
        n = counter[0]
        counter[0] += 1
        return tag % n

    def answer_block(m):
        return field('<textarea class="wsta" data-f="%d" rows="5"></textarea>')

    html = _ANSWER_BLOCK.sub(answer_block, html)
    parts = _PRE.split(html)
    for i, chunk in enumerate(parts):
        if chunk.startswith("<pre>"):
            continue
        chunk = _CHECK_ITEM.sub(lambda m: field('<li class="wsli"><input type="checkbox" class="wscb" data-f="%d"> '), chunk)
        chunk = _EMPTY_CELL.sub(lambda m: field('<td><input type="text" class="wsin" data-f="%d"></td>'), chunk)
        chunk = _BLANK.sub(lambda m: field('<input type="text" class="wsin" data-f="%d">'), chunk)
        parts[i] = chunk
    return "".join(parts), counter[0]


def _blurb(lines) -> str:
    """First real sentence of a worksheet — skipping headings, rules and table rows."""
    for line in lines:
        s = line.strip()
        if s and not s.startswith(("#", "---", "|")):
            text = _INLINE_MD.sub("", s)
            return text[:BLURB_CHARS] + "…" if len(text) > BLURB_CHARS else text
    return ""

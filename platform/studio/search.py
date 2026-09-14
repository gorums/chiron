"""Search across every course in the library.

A reader who remembers "there was a module about pricing somewhere" should not have to open
three courses to find it. The search parses each course's modules the way the build does -
same loader, same sections - and matches the query against module titles, section headings,
section text and glossary terms. It is a plain case-insensitive substring match, ranked by
where the hit landed: a title beats a heading beats a body.

Nothing is indexed ahead of time. A library of a few courses parses in well under a second,
and an index would be one more thing to keep in step with files a person edits by hand.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from coursekit.course import config as ck_config
from coursekit.course import library as ck_library
from coursekit.course import loader as ck_loader
from coursekit.errors import CourseError

SNIPPET = 160
_WS = re.compile(r"\s+")


def search(courses_dir: str, query: str, limit: int = 60) -> Dict[str, Any]:
    """Every hit for `query`, best first, grouped for the UI as a flat list with course info."""
    q = _WS.sub(" ", (query or "").strip().lower())
    if len(q) < 2:
        return {"query": query, "hits": [], "courses": 0}
    hits: List[Dict[str, Any]] = []
    scanned = 0
    for course_id in sorted(_course_ids(courses_dir)):
        root = os.path.join(courses_dir, course_id)
        try:
            cfg = ck_config.load(root)
            modules = ck_loader.load_modules(cfg)
        except CourseError:
            continue
        scanned += 1
        base = {"course": course_id, "title": cfg.title, "localFile": cfg.local_file}
        for m in modules:
            hits += _module_hits(q, base, m)
        hits += _glossary_hits(q, base, cfg)
    hits.sort(key=lambda h: (-h["score"], h["course"], h["mid"] or "", h["sec"] or 0))
    return {"query": query, "hits": hits[:limit], "total": len(hits), "courses": scanned}


def _module_hits(q: str, base: Dict[str, Any], m) -> List[Dict[str, Any]]:
    """A module's title scores 100, a section heading 70, a passage of its text 40."""
    hits = []
    if q in m.title.lower() or q in m.short.lower():
        hits.append(dict(base, kind="module", mid=m.id, module=m.title, score=100,
                         text=m.title, sec=None))
    for i, s in enumerate(m.sections):
        if q in s.heading.lower():
            hits.append(dict(base, kind="section", mid=m.id, module=m.title, score=70,
                             text=s.heading, sec=i))
            continue
        pos = s.text.lower().find(q)
        if pos >= 0:
            hits.append(dict(base, kind="passage", mid=m.id, module=m.title, score=40,
                             text=_snippet(s.text, pos, len(q)), sec=i, heading=s.heading))
    return hits


def _glossary_hits(q: str, base: Dict[str, Any], cfg) -> List[Dict[str, Any]]:
    """A glossary term scores 80, a match inside its definition 30; no glossary, no hits."""
    try:
        glossary = ck_library.build(cfg).get("glossary") or []
    except (CourseError, OSError):
        return []
    hits = []
    for g in glossary:
        term, definition = str(g.get("term", "")), str(g.get("def", ""))
        if q in term.lower():
            hits.append(dict(base, kind="term", mid=None, module="", score=80,
                             text=term + " — " + definition[:SNIPPET], sec=None))
        elif q in definition.lower():
            hits.append(dict(base, kind="term", mid=None, module="", score=30,
                             text=term + " — " + _snippet(definition, definition.lower().find(q), len(q)),
                             sec=None))
    return hits


def _snippet(text: str, pos: int, length: int) -> str:
    start = max(0, pos - SNIPPET // 2)
    end = min(len(text), pos + length + SNIPPET // 2)
    out = _WS.sub(" ", text[start:end]).strip()
    return ("…" if start > 0 else "") + out + ("…" if end < len(text) else "")


def _course_ids(courses_dir: str) -> List[str]:
    if not os.path.isdir(courses_dir):
        return []
    return [d for d in os.listdir(courses_dir)
            if os.path.isfile(os.path.join(courses_dir, d, "course.json"))]

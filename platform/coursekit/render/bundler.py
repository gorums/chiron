"""Assembling the front end from its source files.

The whole app ships as one HTML file with no network dependency beyond a webfont, because
a course has to work offline, from a USB stick, and from a `file://` URL. That constraint
is why this concatenates rather than bundles — but the source is still one file per concern,
and this module is the only thing that knows they get glued together.

There is no module system in the page: every file shares one scope, so load order is a real
contract. It lives in `web/bundle.json` and nowhere else. It used to be a number on the
front of every filename, which made the name carry two jobs at once and did neither well —
the order was unreadable, a file could only be inserted by appending a letter to its
neighbour (`07d-audio.js`), and the name said nothing about what was inside. A manifest
says the order once and leaves the files free to be named and foldered for meaning.

The manifest is checked rather than trusted: a listed file that is not on disk fails the
build, and a file on disk that nobody listed fails the test suite (`unlisted()`). Either
one would otherwise be a page silently missing a feature.
"""

from __future__ import annotations

import json
import os
from typing import List

from ..errors import CourseError
from ..settings import PLATFORM_DIR

WEB = os.path.join(PLATFORM_DIR, "web")
MANIFEST = os.path.join(WEB, "bundle.json")
CSS_DIR = os.path.join(WEB, "css")
JS_DIR = os.path.join(WEB, "js")
SHELL = os.path.join(WEB, "shell.html")

# Where each group of the manifest lives, and what a file in it is called.
GROUPS = {"css": (CSS_DIR, ".css"), "js": (JS_DIR, ".js")}


def manifest() -> dict:
    """The load order, as written. Keys other than the groups are comments and are ignored."""
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def _listed(group: str) -> List[str]:
    entries = manifest().get(group) or []
    directory, suffix = GROUPS[group]
    for rel in entries:
        if not rel.endswith(suffix):
            raise CourseError("bundle.json lists %s under %r" % (rel, group))
        if not os.path.isfile(os.path.join(directory, rel)):
            raise CourseError("bundle.json lists %s, which is not in web/%s/" % (rel, group))
    return entries


def _on_disk(group: str) -> List[str]:
    directory, suffix = GROUPS[group]
    found: List[str] = []
    for root, _dirs, names in os.walk(directory):
        for name in sorted(names):
            if name.endswith(suffix):
                path = os.path.join(root, name)
                found.append(os.path.relpath(path, directory).replace(os.sep, "/"))
    return sorted(found)


def unlisted() -> List[str]:
    """Source files nobody put in the manifest — reported by `build.py check`."""
    missing: List[str] = []
    for group in GROUPS:
        listed = set(manifest().get(group) or [])
        missing += ["web/%s/%s" % (group, rel) for rel in _on_disk(group) if rel not in listed]
    return missing


def _concat(group: str) -> str:
    directory, _suffix = GROUPS[group]
    chunks: List[str] = []
    for rel in _listed(group):
        with open(os.path.join(directory, rel), encoding="utf-8") as fh:
            chunks.append("/* ==== %s ==== */\n%s" % (rel, fh.read().rstrip()))
    return "\n\n".join(chunks)


def css() -> str:
    return _concat("css")


def js() -> str:
    return _concat("js")


def shell() -> str:
    with open(SHELL, encoding="utf-8") as fh:
        return fh.read()


def source_files() -> List[str]:
    """Everything the built page is made of, in load order — used by `build.py check`."""
    out = [SHELL, MANIFEST]
    for group, (directory, _suffix) in GROUPS.items():
        out += [os.path.join(directory, rel) for rel in _listed(group)]
    return out

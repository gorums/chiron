"""Assembling the front end from its source files.

The whole app ships as one HTML file with no network dependency beyond a webfont, because
a course has to work offline, from a USB stick, and from a `file://` URL. That constraint
is why this concatenates rather than bundles — but the source is still one file per concern,
and this module is the only thing that knows they get glued together.

Load order is significant and is the numeric filename prefix. Files declare functions and
are order-independent apart from the last one, which boots the app, so the prefix is the
contract: `21-boot.js` must stay last.
"""

from __future__ import annotations

import os
from typing import List

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
CSS_DIR = os.path.join(WEB, "css")
JS_DIR = os.path.join(WEB, "js")
SHELL = os.path.join(WEB, "shell.html")


def _concat(directory: str, suffix: str) -> str:
    names = sorted(f for f in os.listdir(directory) if f.endswith(suffix))
    chunks: List[str] = []
    for name in names:
        with open(os.path.join(directory, name), encoding="utf-8") as fh:
            chunks.append("/* ==== %s ==== */\n%s" % (name, fh.read().rstrip()))
    return "\n\n".join(chunks)


def css() -> str:
    return _concat(CSS_DIR, ".css")


def js() -> str:
    return _concat(JS_DIR, ".js")


def shell() -> str:
    with open(SHELL, encoding="utf-8") as fh:
        return fh.read()


def source_files() -> List[str]:
    """Everything the built page is made of — used by `build.py check`."""
    out = [SHELL]
    for d in (CSS_DIR, JS_DIR):
        out += [os.path.join(d, f) for f in sorted(os.listdir(d))]
    return out

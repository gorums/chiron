"""Reading and writing the small files Studio keeps: JSON and markdown.

Every JSON file Studio writes goes through `write_json`, so they all look the same on disk
(UTF-8, indented, a trailing newline) and a crash mid-write can never leave half a file
behind: the text is written beside the target and renamed over it.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Optional


def read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write_json(path: str, obj: Any, indent: Optional[int] = 1) -> None:
    """Write `obj` as JSON, atomically. `indent=None` gives the compact form for big records."""
    text = json.dumps(obj, ensure_ascii=False, indent=indent) + "\n"
    _replace(path, text)


def write_text(path: str, text: str) -> None:
    """Write markdown or plain text with exactly one trailing newline."""
    _replace(path, text.rstrip() + "\n")


def _replace(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def stamp() -> str:
    """A file-name-safe timestamp, for trash folders and the like."""
    return time.strftime("%Y%m%d-%H%M%S")


def slug(text: str, fallback: str = "module") -> str:
    """A file-name fragment made of `[a-z0-9-]`, never empty."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or fallback

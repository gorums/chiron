"""What models one particular headless binary knows about: Claude Code's.

A `cli` provider has no endpoint to ask, so the only way to learn what it accepts is to look
inside it. Claude Code carries two tables — the rows its `/model` picker offers, and a fuller
one of everything `--model` will take — and, once it has fetched one, a published catalogue
cached under its config directory. This file reads all three.

It is vendor-specific on purpose, and that is why it is a file of its own rather than part of
`cli.py`: the regular expressions are one program's internals and may change between its
releases. **A scan that finds nothing reports "could not be read", never "no models"** — the
two mean opposite things to the merge, and treating a changed build as an empty catalogue
would quietly empty somebody's model list. Any other `cli` provider reads as "could not be
read" too, which is exactly right: nothing here knows anything about it.

Nothing in the platform depends on this succeeding. It is how the list keeps itself current
without anyone typing a model id; when it cannot, the list simply stays as it is.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

# The picker rows: {id:"claude-opus-5",name:"Opus 5",short_name:"Opus",section:"main"} - the
# fields between name and section vary by release.
SELECTOR = re.compile(
    rb'\{id:"(claude-[a-z0-9.-]+)",name:"([^"]+)"(?:[^{}]|\{[^{}]*\})*?section:"[a-z_]+"\}')
# The catalogue rows: {id:"claude-opus-5",family:"opus",display_name:"Opus 5",...
CATALOG = re.compile(rb'\{id:"(claude-[a-z0-9.-]+)",family:"[a-z]+",display_name:"([^"]+)"')
# A path a Windows npm shim runs: "%~dp0\node_modules\@anthropic-ai\claude-code\cli.js"
SHIM_TARGET = re.compile(r'"?%~dp0\\?([^"\s]+\.(?:js|exe))"?', re.I)

CACHE_DIR = os.path.join("cache", "model-catalog")     # under the config directory


def label_for(display_name: str, model_id: str) -> str:
    """The picker prints "Opus 5"; a list of models from several makers needs the maker."""
    name = (display_name or "").strip() or model_id
    return name if name.lower().startswith("claude") else "Claude " + name


def binary(cli: str) -> str:
    """The file that holds the catalogue: the native executable, or the cli.js an npm shim
    runs. "" when there is no CLI or the shim cannot be followed."""
    if not cli:
        return ""
    if not cli.lower().endswith((".cmd", ".bat")):
        return os.path.realpath(cli)
    try:
        with open(cli, encoding="utf-8", errors="replace") as fh:
            shim = fh.read()
    except OSError:
        return ""
    found = SHIM_TARGET.search(shim)
    if not found:
        return ""
    target = os.path.join(os.path.dirname(cli), found.group(1).replace("\\", os.sep))
    return os.path.realpath(target) if os.path.isfile(target) else ""


def config_dir() -> str:
    """Where Claude Code keeps its state: CLAUDE_CONFIG_DIR, else ~/.claude."""
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def cached_rows(directory: str = "") -> List[Dict[str, str]]:
    """The picker rows from the catalogue it last fetched, newest file first; [] when it has
    not fetched one, or the shape is not the expected one."""
    folder = os.path.join(directory or config_dir(), CACHE_DIR)
    try:
        files = sorted((os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".json")),
                       key=os.path.getmtime, reverse=True)
    except OSError:
        return []
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            continue
        config = ((doc.get("catalog") or {}).get("config") or {}) if isinstance(doc, dict) else {}
        rows = config.get("models") if isinstance(config, dict) else None
        offered = [{"id": str(r["id"]), "label": label_for(str(r.get("name") or ""), str(r["id"]))}
                   for r in (rows or []) if isinstance(r, dict) and r.get("id")]
        if offered:
            return offered
    return []


def parse(data: bytes) -> Dict[str, Any]:
    """The two tables out of the binary's bytes. Nothing found means the shape changed - or
    that this was never Claude Code."""
    known: Dict[str, str] = {}
    for model_id, name in CATALOG.findall(data):
        known.setdefault(model_id.decode(), label_for(name.decode(), model_id.decode()))
    offered: List[Dict[str, str]] = []
    seen = set()
    for model_id, name in SELECTOR.findall(data):
        mid = model_id.decode()
        if mid not in seen:
            seen.add(mid)
            offered.append({"id": mid, "label": label_for(name.decode(), mid)})
    if not known:
        return {"ok": False, "models": [], "known": {},
                "error": "no model catalogue found in this build"}
    return {"ok": True, "models": offered, "known": known, "error": "", "from": "binary"}


_cache: Dict[str, Any] = {"key": None, "value": None}


def read(path: str) -> Dict[str, Any]:
    """{ok, path, models: [{id, label}], known: {id: label}, error}. Cached per file version,
    so the daily check and the settings page do not re-read a couple of hundred megabytes."""
    if not path:
        return {"ok": False, "path": "", "models": [], "known": {},
                "error": "no command-line tool on this PATH"}
    try:
        stat = os.stat(path)
    except OSError as exc:
        return {"ok": False, "path": path, "models": [], "known": {}, "error": str(exc)}
    key = (path, stat.st_mtime, stat.st_size)
    if _cache["key"] == key:
        return dict(_cache["value"])
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        return {"ok": False, "path": path, "models": [], "known": {}, "error": str(exc)}
    result = parse(data)
    result["path"] = path
    cached = cached_rows()
    if cached:
        result["models"] = cached
        result["from"] = "cache"
    _cache["key"], _cache["value"] = key, dict(result)
    return result

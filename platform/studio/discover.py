"""Where new models come from, so the list keeps itself current.

Nobody should have to type a model id the day it ships, or notice by hand that one has
gone. Two sources say what exists, and neither needs the owner to do anything:

- **Claude Code's own catalog.** Claude Code fetches a published model catalog and caches
  it under its config directory (`cache/model-catalog/*.json`); the `claude` binary also
  carries a seed of that catalog - the rows its `/model` picker offers - and a fuller table
  of the models it knows. Studio reads the cache when there is one and the binary otherwise
  (`CLI_SELECTOR`, `CLI_CATALOG`: regular expressions over its bytes, a shape that may
  change between releases, which is why a scan that finds nothing is reported as "could not
  read", never as "no models"). What the picker offers is what gets added.
- **Anthropic's model list**, `GET /v1/models`, when an API key is configured
  (`ANTHROPIC_API_KEY` in `.env` or the environment; `anthropic.apiKey`). It is what a
  course page in direct mode and the bridge can call, and it carries a creation date per
  model, so only models newer than the newest one already listed are added - never the
  whole back catalogue.

`plan()` is the merge rule, a pure function: a model a source offers and the list lacks is
added; a model the list has that every answering source lacks becomes a candidate for
removal; a dated snapshot (`...-20251001`) and its bare id count as the same model.
`removals()` decides the candidates: gone from Anthropic's list means gone; unknown only to
the binary's table is not enough - an older Claude Code passes an id it has never heard of
straight to the API and it works - so such a candidate is kept unless one real call with it
(`claude_cli.probe`) is refused. The list is never emptied. `run()` applies the result
through `models.replace`, so it is validated like a hand edit and live everywhere at once,
and writes a report to `state/models-discovery.json` for the settings page. `schedule()`
runs it shortly after Studio starts and every `discovery.hours` after that;
`POST /api/models/discover` runs it on demand.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from coursekit.settings import SETTINGS

from . import claude_cli, models
from .files import read_json, write_json
from .log import log

HOURS = float(SETTINGS.get("discovery.hours") or 0)            # 0 turns the schedule off
START_DELAY = int(SETTINGS.get("discovery.startDelaySeconds"))
TIMEOUT = int(SETTINGS.get("discovery.timeout"))
API_PAGE = int(SETTINGS.get("discovery.apiPage"))
REPORT_NAME = "models-discovery.json"

# The picker rows in the claude binary: {id:"claude-opus-5",name:"Opus 5",short_name:"Opus",section:"main"}
# - the fields between name and section vary by release.
CLI_SELECTOR = re.compile(rb'\{id:"(claude-[a-z0-9.-]+)",name:"([^"]+)"(?:[^{}]|\{[^{}]*\})*?section:"[a-z_]+"\}')
CATALOG_CACHE = os.path.join("cache", "model-catalog")     # under Claude Code's config directory
# The catalog rows: {id:"claude-opus-5",family:"opus",display_name:"Opus 5",...
CLI_CATALOG = re.compile(rb'\{id:"(claude-[a-z0-9.-]+)",family:"[a-z]+",display_name:"([^"]+)"')
# A path a Windows npm shim runs: "%~dp0\node_modules\@anthropic-ai\claude-code\cli.js"
SHIM_TARGET = re.compile(r'"?%~dp0\\?([^"\s]+\.(?:js|exe))"?', re.I)
DATED = re.compile(r"-\d{8}$")


def base_id(model_id: str) -> str:
    """`claude-haiku-4-5-20251001` and `claude-haiku-4-5` are one model."""
    return DATED.sub("", model_id)


def label_for(display_name: str, model_id: str) -> str:
    name = (display_name or "").strip() or model_id
    return name if name.lower().startswith("claude") else "Claude " + name


# ---- source 1: the claude binary ----

def cli_binary() -> str:
    """The file that holds Claude Code's catalog: the native executable, or the cli.js an
    npm shim runs. "" when there is no CLI or the shim cannot be followed."""
    cli = claude_cli.find_cli()
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


def claude_config_dir() -> str:
    """Where Claude Code keeps its state: CLAUDE_CONFIG_DIR, else ~/.claude."""
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def read_cached_catalog(config_dir: str = "") -> List[Dict[str, str]]:
    """The picker rows from the catalog Claude Code last fetched, newest file first; []
    when it has not fetched one or the shape is not the expected one."""
    folder = os.path.join(config_dir or claude_config_dir(), CATALOG_CACHE)
    try:
        files = sorted((os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".json")),
                       key=os.path.getmtime, reverse=True)
    except OSError:
        return []
    for path in files:
        try:
            doc = read_json(path)
        except (OSError, ValueError):
            continue
        config = ((doc.get("catalog") or {}).get("config") or {}) if isinstance(doc, dict) else {}
        rows = config.get("models") if isinstance(config, dict) else None
        offered = [{"id": str(r["id"]), "label": label_for(str(r.get("name") or ""), str(r["id"]))}
                   for r in (rows or []) if isinstance(r, dict) and r.get("id")]
        if offered:
            return offered
    return []


_cli_cache: Dict[str, Any] = {"key": None, "value": None}


def read_cli_catalog(path: str = "") -> Dict[str, Any]:
    """{ok, path, offered: [{id, label}], known: {id: label}, error}. Cached per file
    version, so the daily check and the settings page do not re-read 200 MB each time."""
    path = path or cli_binary()
    if not path:
        return {"ok": False, "path": "", "offered": [], "known": {},
                "error": "Claude Code is not on this PATH."}
    try:
        stat = os.stat(path)
    except OSError as exc:
        return {"ok": False, "path": path, "offered": [], "known": {}, "error": str(exc)}
    key = (path, stat.st_mtime, stat.st_size)
    if _cli_cache["key"] == key:
        return dict(_cli_cache["value"])
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        return {"ok": False, "path": path, "offered": [], "known": {}, "error": str(exc)}
    result = parse_cli_catalog(data)
    result["path"] = path
    cached = read_cached_catalog()
    if cached:
        result["offered"] = cached
        result["offeredFrom"] = "cache"
    _cli_cache["key"], _cli_cache["value"] = key, dict(result)
    return result


def parse_cli_catalog(data: bytes) -> Dict[str, Any]:
    """The two tables out of the binary's bytes. Nothing found means the shape changed."""
    known: Dict[str, str] = {}
    for model_id, name in CLI_CATALOG.findall(data):
        known.setdefault(model_id.decode(), label_for(name.decode(), model_id.decode()))
    offered: List[Dict[str, str]] = []
    seen = set()
    for model_id, name in CLI_SELECTOR.findall(data):
        mid = model_id.decode()
        if mid not in seen:
            seen.add(mid)
            offered.append({"id": mid, "label": label_for(name.decode(), mid)})
    if not known:
        return {"ok": False, "offered": [], "known": {},
                "error": "no model catalog found in this Claude Code build"}
    return {"ok": True, "offered": offered, "known": known, "error": "", "offeredFrom": "binary"}


# ---- source 2: Anthropic's model list ----

def api_key() -> str:
    return str(SETTINGS.get("anthropic.apiKey") or "").strip()


def read_api_catalog(key: str = "", url: str = "", timeout: int = TIMEOUT) -> Dict[str, Any]:
    """{ok, models: [{id, label, created}], error}. Every page of `GET /v1/models`."""
    key = key or api_key()
    url = url or str(SETTINGS.get("anthropic.modelsUrl"))
    if not key:
        return {"ok": False, "models": [], "error": "no API key configured"}
    found: List[Dict[str, str]] = []
    after = ""
    try:
        for _ in range(20):                                     # never loop on a bad server
            page = url + "?limit=%d" % API_PAGE + ("&after_id=" + after if after else "")
            req = urllib.request.Request(page, headers={
                "x-api-key": key, "anthropic-version": str(SETTINGS.get("anthropic.apiVersion"))})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            for m in body.get("data") or []:
                if isinstance(m, dict) and m.get("id"):
                    found.append({"id": str(m["id"]), "label": label_for(m.get("display_name", ""), str(m["id"])),
                                  "created": str(m.get("created_at") or "")})
            if not body.get("has_more") or not body.get("last_id"):
                break
            after = str(body["last_id"])
    except urllib.error.HTTPError as exc:
        return {"ok": False, "models": [], "error": "HTTP %s from %s" % (exc.code, url)}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "models": [], "error": str(exc)[:200]}
    return {"ok": True, "models": found, "error": ""}


# ---- the merge rule ----

def plan(current: List[Dict[str, Any]], cli: Dict[str, Any], api: Dict[str, Any],
         today: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(the list with additions, added entries, candidates for removal). Pure: no I/O, no
    clock. A candidate is still in the list; `removals()` decides."""
    present = set()
    for m in current:
        present.add(m["id"])
        present.add(base_id(m["id"]))

    added: List[Dict[str, Any]] = []

    def offer(model_id: str, label: str, source: str) -> None:
        if model_id in present or base_id(model_id) in present:
            return
        present.add(model_id)
        present.add(base_id(model_id))
        added.append({"id": model_id, "label": label,
                      "note": "added automatically on %s from %s; test it before a long run"
                              % (today, source)})

    if cli.get("ok"):
        for m in cli["offered"]:
            offer(m["id"], m["label"], "Claude Code's catalog")
    if api.get("ok"):
        known_dates = [m["created"] for m in api["models"]
                       if m["id"] in present or base_id(m["id"]) in present]
        newest = max(known_dates) if known_dates else ""
        for m in sorted(api["models"], key=lambda x: x["created"]):
            if m["created"] > newest and not DATED.search(m["id"]):
                offer(m["id"], m["label"], "Anthropic's model list")

    def names_known_to(source: Dict[str, Any]) -> set:
        ids = set(source["known"]) if "known" in source else {x["id"] for x in source["models"]}
        return ids | {base_id(i) for i in ids}

    answered = [names_known_to(s) for s in (cli, api) if s.get("ok")]
    candidates = [m for m in current
                  if answered and not any({m["id"], base_id(m["id"])} & known for known in answered)]
    return current + added, added, candidates


def removals(candidates: List[Dict[str, Any]], api_answered: bool, probe,
             keep_one: bool) -> Tuple[List[Dict[str, Any]], Dict[str, bool]]:
    """Which candidates go: all of them when Anthropic's list answered without them; else
    only those one real call refuses. `probe(id)` -> {ok, ...}. Returns (removed, checked)
    where checked records each probe. `keep_one` says the list has nothing but candidates,
    in which case the last one stays."""
    removed: List[Dict[str, Any]] = []
    checked: Dict[str, bool] = {}
    for m in candidates:
        if api_answered:
            removed.append(m)
            continue
        ok = bool(probe(m["id"]).get("ok"))
        checked[m["id"]] = ok
        if not ok:
            removed.append(m)
    if keep_one and len(removed) == len(candidates) and removed:
        removed = removed[:-1]
    return removed, checked


# ---- running it ----

def report_path() -> str:
    return os.path.join(SETTINGS.state_dir, REPORT_NAME)


def run(save: bool = True) -> Dict[str, Any]:
    """Read every source, apply the plan, save the list and the report."""
    started = time.time()
    cli = read_cli_catalog()
    api = read_api_catalog()
    today = time.strftime("%Y-%m-%d")
    current = SETTINGS.models
    with_additions, added, candidates = plan(current, cli, api, today)
    removed, checked = removals(candidates, api["ok"], claude_cli.probe,
                                keep_one=len(candidates) == len(with_additions))
    gone = {m["id"] for m in removed}
    new_list = [m for m in with_additions if m["id"] not in gone]
    changed = bool(added or removed)
    report = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seconds": round(time.time() - started, 1),
        "sources": {
            "cli": {"ok": cli["ok"], "path": cli.get("path", ""), "offered": len(cli["offered"]),
                    "offeredFrom": cli.get("offeredFrom", ""), "known": len(cli["known"]),
                    "error": cli["error"]},
            "api": {"ok": api["ok"], "configured": bool(api_key()), "count": len(api["models"]),
                    "error": api["error"]},
        },
        "added": [m["id"] for m in added],
        "removed": [m["id"] for m in removed],
        "checked": checked,
        "changed": changed,
    }
    if save:
        if changed:
            try:
                models.replace(new_list)
            except ValueError as exc:
                report["error"] = str(exc)
                log.error("model discovery: the new list was refused: %s", exc)
        write_json(report_path(), report)
    if changed:
        log.info("model discovery: added %s, removed %s", ", ".join(report["added"]) or "none",
                 ", ".join(report["removed"]) or "none")
    else:
        log.info("model discovery: nothing new (cli %s, api %s)",
                 "ok" if cli["ok"] else cli["error"], "ok" if api["ok"] else api["error"])
    return report


def status() -> Dict[str, Any]:
    """What the settings page shows: the last report, the schedule, the sources."""
    last: Optional[Dict[str, Any]] = None
    try:
        loaded = read_json(report_path())
        if isinstance(loaded, dict):
            last = loaded
    except (OSError, ValueError):
        pass
    return {"last": last, "hours": HOURS, "apiConfigured": bool(api_key()),
            "cliBinary": cli_binary()}


_thread: Optional[threading.Thread] = None


def schedule() -> bool:
    """Start the background check: once after START_DELAY, then every HOURS. False when
    the schedule is off (`discovery.hours` 0) or already running."""
    global _thread
    if HOURS <= 0 or (_thread is not None and _thread.is_alive()):
        return False

    def loop() -> None:
        time.sleep(START_DELAY)
        while True:
            try:
                run()
            except Exception as exc:  # noqa: BLE001 - a failed check must not kill the schedule
                log.error("model discovery failed: %s", exc)
            time.sleep(HOURS * 3600)

    _thread = threading.Thread(target=loop, name="model-discovery", daemon=True)
    _thread.start()
    return True

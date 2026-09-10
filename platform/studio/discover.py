"""Where new models come from, so the list keeps itself current.

Nobody should have to type a model id the day it ships, or notice by hand that one has gone.
**Every configured provider is asked what it knows** (`Provider.catalog`), and the answers are
merged into `models.list` per provider - a Claude Code build says nothing about what OpenAI
offers, and must not be allowed to.

A source answers `{ok, models, known, error}`: `models` is what it would offer someone, and
`known` is the wider set it recognises, because a picker offers five models and accepts
twenty. A source that cannot answer says so rather than reporting an empty list; the two mean
opposite things here, and a build whose shape changed must never be read as "there are no
models".

`plan()` is the merge rule, a pure function: a model a provider offers and the list lacks is
added under that provider; a model the list has that its own provider does not recognise
becomes a candidate for removal; a dated snapshot (`...-20251001`) and its bare id are one
model. A source whose models carry creation dates - an API listing does, a binary scan does
not - offers only what is newer than the newest already listed, so a first run does not drag
in the whole back catalogue.

`removals()` decides the candidates, and the rule is about who may be believed.
`Provider.catalog_is_complete` says whether a catalogue is the whole picture: an endpoint
listing what an account may use is, so a model missing from it really is gone; bytes scraped
out of a binary are not, because an older build passes an id it has never heard of straight
through and it works. For those, a candidate stays unless one real call (`llm.probe`) is
refused *for being that model* - an account out of quota refuses every id there is, and a
check that ran at three in the morning must not empty the list because of it. No provider's
models are ever all removed.

`run()` applies the result through `models.replace`, so it is validated like a hand edit and
live everywhere at once, and writes a report to `state/models-discovery.json` for the
settings page. `schedule()` runs it `discovery.startDelaySeconds` after Studio starts and
every `discovery.hours` after that; `POST /api/models/discover` runs it on demand.
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from coursekit import llm
from coursekit.failures import MODEL
from coursekit.settings import SETTINGS

from . import models
from .files import read_json, write_json
from .log import log

HOURS = float(SETTINGS.get("discovery.hours") or 0)            # 0 turns the schedule off
START_DELAY = int(SETTINGS.get("discovery.startDelaySeconds"))
TIMEOUT = int(SETTINGS.get("discovery.timeout"))
REPORT_NAME = "models-discovery.json"

DATED = re.compile(r"-\d{8}$")


def base_id(model_id: str) -> str:
    """`claude-haiku-4-5-20251001` and `claude-haiku-4-5` are one model."""
    return DATED.sub("", model_id)


# ---- what every provider says ----

def sources(timeout: int = TIMEOUT) -> Dict[str, Dict[str, Any]]:
    """Every enabled provider, asked what it knows, keyed by provider name. `known` is filled
    in from `models` for a source that draws no distinction, and `complete` records whether
    this one may be believed when it leaves a model out."""
    found: Dict[str, Dict[str, Any]] = {}
    for provider in llm.providers():
        answer = dict(provider.catalog(timeout))
        answer.setdefault("models", [])
        answer.setdefault("error", "")
        if not answer.get("known"):
            answer["known"] = {m["id"]: m.get("label") or m["id"] for m in answer["models"]}
        answer["complete"] = bool(provider.catalog_is_complete)
        answer["label"], answer["kind"] = provider.label, provider.kind
        answer["ready"] = provider.available()
        found[provider.name] = answer
    return found


# ---- the merge rule ----

def offerable(source: Dict[str, Any], listed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Which of a source's models are worth offering.

    A source whose models carry creation dates offers only what is newer than the newest one
    already listed - otherwise the first run against an API drags in the whole back
    catalogue, dated snapshots and all. A source without dates has no way to say what is new,
    so everything it offers is on the table and `plan` drops what is already there."""
    rows = source.get("models") or []
    if not any(r.get("created") for r in rows):
        return rows
    present = {m["id"] for m in listed} | {base_id(m["id"]) for m in listed}
    dates = [r["created"] for r in rows if r["id"] in present or base_id(r["id"]) in present]
    newest = max(dates) if dates else ""
    return [r for r in sorted(rows, key=lambda x: x.get("created", ""))
            if r.get("created", "") > newest and not DATED.search(r["id"])]


def plan(current: List[Dict[str, Any]], found: Dict[str, Dict[str, Any]], today: str
         ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(the list with additions, added entries, candidates for removal). Pure: no I/O, no
    clock. A candidate is still in the list; `removals()` decides.

    Everything is scoped to one provider: a model is offered by, missing from, and removed on
    behalf of the provider that reaches it. A provider whose source could not answer keeps
    every model it has."""
    added: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []

    for name, source in found.items():
        if not source.get("ok"):
            continue
        mine = [m for m in current if m.get("provider") == name]
        present = set()
        for m in mine:
            present.add(m["id"])
            present.add(base_id(m["id"]))
        for row in offerable(source, mine):
            model_id = str(row.get("id") or "")
            if not model_id or model_id in present or base_id(model_id) in present:
                continue
            present.add(model_id)
            present.add(base_id(model_id))
            added.append({
                "provider": name, "id": model_id, "label": row.get("label") or model_id,
                "note": "added automatically on %s from %s; test it before a long run"
                        % (today, source.get("label") or name)})
        known = set(source["known"]) | {base_id(i) for i in source["known"]}
        candidates += [m for m in mine if not {m["id"], base_id(m["id"])} & known]

    return current + added, added, candidates


def removals(candidates: List[Dict[str, Any]], complete: bool, probe,
             keep_one: bool) -> Tuple[List[Dict[str, Any]], Dict[str, bool]]:
    """Which candidates go: all of them when the source was the whole picture and answered
    without them; else only those one real call refuses for being that model. `probe(id)` ->
    {ok, why, ...}; a failure whose `why` is anything but "model" - an exhausted account, a
    signed-out CLI, a dropped connection - would refuse every id on the list, so it removes
    nothing. Returns (removed, checked), where checked records each probe. `keep_one` says
    this provider has nothing but candidates, in which case the last one stays."""
    removed: List[Dict[str, Any]] = []
    checked: Dict[str, bool] = {}
    for m in candidates:
        if complete:
            removed.append(m)
            continue
        answer = probe(m["id"])
        ok = bool(answer.get("ok"))
        checked[m["id"]] = ok
        if not ok and answer.get("why", MODEL) == MODEL:
            removed.append(m)
    if keep_one and len(removed) == len(candidates) and removed:
        removed = removed[:-1]
    return removed, checked


# ---- running it ----

def report_path() -> str:
    return os.path.join(SETTINGS.state_dir, REPORT_NAME)


def run(save: bool = True) -> Dict[str, Any]:
    """Ask every provider, apply the plan, save the list and the report."""
    started = time.time()
    found = sources()
    today = time.strftime("%Y-%m-%d")
    current = SETTINGS.models
    with_additions, added, candidates = plan(current, found, today)
    removed, checked = _removals_per_provider(found, with_additions, candidates)

    gone = {(m["provider"], m["id"]) for m in removed}
    new_list = [m for m in with_additions if (m.get("provider"), m["id"]) not in gone]
    changed = bool(added or removed)
    report = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seconds": round(time.time() - started, 1),
        "sources": {name: {"ok": s["ok"], "label": s["label"], "kind": s["kind"],
                           "ready": s["ready"], "complete": s["complete"],
                           "offered": len(s["models"]), "known": len(s["known"]),
                           "from": s.get("from", ""), "path": s.get("path", ""),
                           "error": s["error"]}
                    for name, s in found.items()},
        "added": [{"provider": m["provider"], "id": m["id"]} for m in added],
        "removed": [{"provider": m["provider"], "id": m["id"]} for m in removed],
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
    _log_result(report, found)
    return report


def _removals_per_provider(found: Dict[str, Dict[str, Any]],
                           with_additions: List[Dict[str, Any]],
                           candidates: List[Dict[str, Any]]
                           ) -> Tuple[List[Dict[str, Any]], Dict[str, bool]]:
    """Each provider judges its own models, with its own probe. No provider's models are all
    removed, whatever its source says."""
    removed: List[Dict[str, Any]] = []
    checked: Dict[str, bool] = {}
    for name, source in found.items():
        mine = [m for m in candidates if m.get("provider") == name]
        if not mine:
            continue
        listed = [m for m in with_additions if m.get("provider") == name]

        def probe(model_id: str, provider: str = name) -> Dict[str, Any]:
            return llm.probe(model_id, name=provider)

        theirs, saw = removals(mine, bool(source["complete"] and source["ok"]), probe,
                               keep_one=len(mine) == len(listed))
        removed += theirs
        checked.update(saw)
    return removed, checked


def _log_result(report: Dict[str, Any], found: Dict[str, Dict[str, Any]]) -> None:
    said = ", ".join("%s %s" % (name, "ok" if s["ok"] else s["error"] or "not read")
                     for name, s in found.items())
    if report["changed"]:
        log.info("model discovery: added %s, removed %s (%s)",
                 ", ".join(m["id"] for m in report["added"]) or "none",
                 ", ".join(m["id"] for m in report["removed"]) or "none", said)
    else:
        log.info("model discovery: nothing new (%s)", said)


def status() -> Dict[str, Any]:
    """What the settings page shows: the last report, the schedule, and every provider that
    would be asked."""
    last: Optional[Dict[str, Any]] = None
    try:
        loaded = read_json(report_path())
        if isinstance(loaded, dict):
            last = loaded
    except (OSError, ValueError):
        pass
    return {"last": last, "hours": HOURS,
            "providers": [{"name": p.name, "label": p.label, "kind": p.kind,
                           "ready": p.available(), "complete": p.catalog_is_complete}
                          for p in llm.providers()]}


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

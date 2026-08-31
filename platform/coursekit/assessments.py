"""Loading the authored study data that sits alongside the prose.

Two kinds, both keyed by module id:

  assessments/*.json   list of  {id, predict, quiz[], cards[], elaborate[], transfer{}}
  suggestions/*.json   object of {moduleId: [[q, q, q], ...]}  — one triple per section

They are separate files from the markdown because they are generated in a later pass than
the prose, and because a broken quiz should not stop you from reading the module.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .config import CourseConfig
from .errors import DataError

ASSESS_KEYS = ("predict", "quiz", "cards", "elaborate", "transfer")


def _read_json_dir(directory: str, label: str) -> List[Any]:
    if not os.path.isdir(directory):
        raise DataError("No %s directory at %s." % (label, directory))
    payloads = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, encoding="utf-8") as fh:
                payloads.append(json.load(fh))
        except json.JSONDecodeError as exc:
            raise DataError("%s is not valid JSON: %s" % (path, exc)) from exc
    if not payloads:
        raise DataError("%s holds no .json files." % directory)
    return payloads


def load_assessments(cfg: CourseConfig) -> Dict[str, Dict[str, Any]]:
    """Merge every assessment file into one {moduleId: assessment} map."""
    out: Dict[str, Dict[str, Any]] = {}
    for payload in _read_json_dir(cfg.path(cfg.data["assessments"]), "assessments"):
        if not isinstance(payload, list):
            raise DataError("An assessment file must hold a JSON list of module objects.")
        for entry in payload:
            if "id" not in entry:
                raise DataError("An assessment entry has no 'id'.")
            if entry["id"] in out:
                raise DataError("Two assessments claim module '%s'." % entry["id"])
            out[entry["id"]] = entry
    return out


def load_suggestions(cfg: CourseConfig) -> Dict[str, List[Any]]:
    """Merge every suggestion file into one {moduleId: [per-section question sets]} map."""
    out: Dict[str, List[Any]] = {}
    for payload in _read_json_dir(cfg.path(cfg.data["suggestions"]), "suggestions"):
        if not isinstance(payload, dict):
            raise DataError("A suggestion file must hold a JSON object keyed by module id.")
        for key, rows in payload.items():
            if key in out:
                raise DataError("Two suggestion files claim module '%s'." % key)
            out[key] = rows
    return out


def attach(modules, assessments, suggestions) -> None:
    """Hang the study data off each module, dropping the bookkeeping fields."""
    for module in modules:
        entry = assessments[module.id]
        module.assess = {k: entry[k] for k in ASSESS_KEYS}
        module.suggest = suggestions.get(module.id, [])

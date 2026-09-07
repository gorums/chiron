"""Course operations that need no model: settings, removing a module, trashing a course.

These are the things that used to mean opening a text editor or a shell. Each one changes
the course folder directly and leaves it in a state `build.py check` accepts, or says why not.

Two rules carried over from the rest of the platform:

- **The course id never changes here.** It is the reader's storage key; renaming it would
  orphan their progress. Settings edits touch presentation only.
- **Nothing is deleted outright.** A removed module's file and a trashed course are moved
  under `state/trash/`, where a person can get them back.
"""

from __future__ import annotations

import os
import re
import shutil
from typing import Any, Dict, List

from coursekit import config as ck_config
from coursekit import figures as ck_figures
from coursekit import loader as ck_loader
from coursekit import notebooks as ck_notebooks
from coursekit.errors import CourseError

from .files import read_json, stamp, write_json
from .ids import is_module_id

# The fields the settings form may change, with a small validator for each.
_TEXT = lambda v, n: str(v or "").strip()[:n]  # noqa: E731
SETTINGS = {
    "title": lambda v: _TEXT(v, 120),
    "tagline": lambda v: _TEXT(v, 200),
    "audience": lambda v: _TEXT(v, 200),
    "practitioner": lambda v: _TEXT(v, 60),
    "tutorPersona": lambda v: _TEXT(v, 600),
}
# The reader's own case (`anchor` in course.json): four short texts, all optional.
ANCHOR_KEYS = ("label", "prompt", "placeholder", "noun")

# --------------------------------------------------------------------------- settings


def settings(root: str) -> Dict[str, Any]:
    """The editable subset of course.json, as the form shows it."""
    manifest = read_json(os.path.join(root, "course.json"))
    out = {k: manifest.get(k, "") for k in SETTINGS}
    out["id"] = manifest.get("id", "")
    out["hours"] = manifest.get("hours", 0)
    anchor = manifest.get("anchor") if isinstance(manifest.get("anchor"), dict) else {}
    out["anchor"] = {k: str(anchor.get(k, "") or "") for k in ANCHOR_KEYS}
    out["notebooks"] = ck_config.notebooks_setting(manifest.get("notebooks")) or None
    out["milestones"] = [m for m in (manifest.get("milestones") or [])
                         if isinstance(m, dict) and "text" in m]
    out["parts"] = [{"id": p.get("id"), "name": p.get("name"), "hours": p.get("hours"),
                     "blurb": p.get("blurb", "")} for p in manifest.get("parts") or []]
    return out


def update_settings(root: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a settings form. Returns what is now stored. Raises CourseError on bad input."""
    path = os.path.join(root, "course.json")
    manifest = read_json(path)
    if "id" in changes and changes["id"] != manifest.get("id"):
        raise CourseError("A course's id cannot change: it is the key the reader's progress is stored under.")

    for key, clean in SETTINGS.items():
        if key in changes:
            value = clean(changes[key])
            if key == "title" and not value:
                raise CourseError("A course needs a title.")
            if key == "tutorPersona" and value and not value.endswith("."):
                value += "."
            manifest[key] = value

    if "milestones" in changes:
        manifest["milestones"] = _clean_milestones(changes["milestones"])

    if isinstance(changes.get("anchor"), dict):
        anchor = {k: _TEXT(changes["anchor"].get(k), 300) for k in ANCHOR_KEYS}
        manifest["anchor"] = {k: v for k, v in anchor.items() if v}

    # Notebooks: null turns them off; the form sends the packages as one comma-separated line.
    if "notebooks" in changes:
        raw = changes["notebooks"]
        if isinstance(raw, dict) and isinstance(raw.get("packages"), str):
            raw = dict(raw, packages=[p for p in re.split(r"[,\s]+", raw["packages"]) if p])
        runtime = ck_config.notebooks_setting(raw)
        if runtime:
            manifest["notebooks"] = runtime
        else:
            manifest.pop("notebooks", None)

    if "parts" in changes:
        by_id = {p.get("id"): p for p in (changes["parts"] or []) if isinstance(p, dict)}
        for part in manifest.get("parts") or []:
            edit = by_id.get(part.get("id"))
            if not edit:
                continue
            name = _TEXT(edit.get("name"), 80)
            if name:
                part["name"] = name
            if "blurb" in edit:
                part["blurb"] = _TEXT(edit.get("blurb"), 300)
            if "hours" in edit:
                try:
                    part["hours"] = _tidy(float(edit["hours"]))
                except (TypeError, ValueError):
                    raise CourseError("Part hours must be a number.")
        manifest["hours"] = _tidy(sum(float(p.get("hours") or 0) for p in manifest["parts"]))

    write_json(path, manifest)
    ck_config.load(root)          # it must still be a valid manifest
    return settings(root)


def _clean_milestones(raw: Any) -> List[Dict[str, Any]]:
    out = []
    for m in raw if isinstance(raw, list) else []:
        if not isinstance(m, dict):
            continue
        text = _TEXT(m.get("text"), 600)
        try:
            after = max(0, int(m.get("after") or 0))
        except (TypeError, ValueError):
            after = 0
        if text:
            out.append({"after": after, "text": text})
    return sorted(out, key=lambda m: m["after"])


def _tidy(value: float):
    return int(value) if float(value).is_integer() else round(float(value), 2)


# --------------------------------------------------------------------------- moving a module


def move_module(root: str, mid: str, part_id: str = "", index: int = -1) -> Dict[str, Any]:
    """Put one module somewhere else in the reading order, optionally in another part.

    The file moves folders when the part changes; the order is written to `order` in
    course.json as the full list of ids, which is what the loader sorts by. Progress is keyed
    by id and does not notice. Returns the new order.
    """
    if not is_module_id(mid):
        raise CourseError("Bad module id.")
    cfg = ck_config.load(root)
    modules = ck_loader.load_modules(cfg)
    current = next((m for m in modules if m.id == mid), None)
    if current is None:
        raise CourseError("No module '%s' in this course." % mid)
    part_id = part_id or current.part
    part = next((p for p in cfg.parts if p.id == part_id), None)
    if part is None:
        raise CourseError("No part '%s' in this course." % part_id)

    if part.id != current.part:
        dest_dir = os.path.join(cfg.modules_dir, part.dir)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(current.source))
        if os.path.exists(dest):
            raise CourseError("A file named %s already exists in that part." % os.path.basename(dest))
        shutil.move(current.source, dest)
        # the source folder must keep at least one module or the loader refuses the course
        src_dir = os.path.dirname(current.source)
        if not any(f.endswith(".md") for f in os.listdir(src_dir)):
            shutil.move(dest, current.source)
            raise CourseError("That would leave the part '%s' with no modules." % current.part)

    # rebuild the order: every part's ids in current sequence, with mid re-inserted
    order: List[str] = []
    for p in cfg.parts:
        ids = [m.id for m in modules if m.part == p.id and m.id != mid]
        if p.id == part.id:
            pos = len(ids) if index is None or index < 0 or index > len(ids) else int(index)
            ids.insert(pos, mid)
        order.extend(ids)

    manifest_path = os.path.join(root, "course.json")
    manifest = read_json(manifest_path)
    manifest["order"] = order
    write_json(manifest_path, manifest)
    ck_config.load(root)
    return {"order": order, "part": part.id, "moved": part.id != current.part}


# --------------------------------------------------------------------------- removing a module


def remove_module(root: str, mid: str, trash_dir: str) -> Dict[str, Any]:
    """Take one module out of a course: its file, its figures, its study data, its short title.

    The file goes to the trash rather than being deleted. Progress for the id is left alone in
    the reader's state — harmless, and the id is never reused so it can never be confused.
    """
    if not is_module_id(mid):
        raise CourseError("Bad module id.")
    cfg = ck_config.load(root)

    found = []
    for part in cfg.parts:
        directory = os.path.join(cfg.modules_dir, part.dir)
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if name.endswith(".md") and name.split("-", 1)[0] == mid:
                found.append(os.path.join(directory, name))
    if not found:
        raise CourseError("No module '%s' in this course." % mid)

    dest = os.path.join(trash_dir, "%s-%s-%s" % (cfg.id, mid, stamp()))
    os.makedirs(dest, exist_ok=True)
    for path in found:
        shutil.move(path, os.path.join(dest, os.path.basename(path)))

    removed = {"file": [os.path.relpath(p, root).replace(os.sep, "/") for p in found],
               "assessment": False, "suggestions": False, "figures": 0, "notebooks": 0, "trash": dest}

    for name in ck_figures.names_for(cfg.figures_dir, mid):
        shutil.move(os.path.join(cfg.figures_dir, name), os.path.join(dest, name))
        removed["figures"] += 1
    for name in ck_notebooks.names_for(cfg.notebooks_dir, mid):
        shutil.move(os.path.join(cfg.notebooks_dir, name), os.path.join(dest, name))
        removed["notebooks"] += 1

    assess_dir = cfg.path(cfg.data["assessments"])
    if os.path.isdir(assess_dir):
        for name in sorted(os.listdir(assess_dir)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(assess_dir, name)
            rows = read_json(path)
            if isinstance(rows, list) and any(isinstance(r, dict) and r.get("id") == mid for r in rows):
                kept = [r for r in rows if not (isinstance(r, dict) and r.get("id") == mid)]
                removed["assessment"] = True
                _drop_or_write(path, kept, empty=not kept)

    sugg_dir = cfg.path(cfg.data["suggestions"])
    if os.path.isdir(sugg_dir):
        for name in sorted(os.listdir(sugg_dir)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(sugg_dir, name)
            rows = read_json(path)
            if isinstance(rows, dict) and mid in rows:
                del rows[mid]
                removed["suggestions"] = True
                _drop_or_write(path, rows, empty=not rows)

    manifest_path = os.path.join(root, "course.json")
    manifest = read_json(manifest_path)
    changed = False
    if mid in (manifest.get("shortTitles") or {}):
        del manifest["shortTitles"][mid]
        changed = True
    if mid in (manifest.get("order") or []):
        manifest["order"] = [x for x in manifest["order"] if x != mid]
        changed = True
    if changed:
        write_json(manifest_path, manifest)
    return removed


def _drop_or_write(path: str, rows: Any, empty: bool) -> None:
    """A data file that would be left empty is removed - the loader rejects empty lists
    only when a directory holds nothing at all, but an empty file is noise."""
    if empty:
        os.unlink(path)
    else:
        write_json(path, rows)


# --------------------------------------------------------------------------- trashing a course


def trash_course(courses_dir: str, dist_dir: str, trash_dir: str, course_id: str) -> Dict[str, Any]:
    """Move a course and its build out of the way. Nothing is deleted; `state/trash/` holds it."""
    root = os.path.join(courses_dir, course_id)
    if not os.path.isfile(os.path.join(root, "course.json")):
        raise CourseError("No such course.")
    dest = os.path.join(trash_dir, "%s-%s" % (course_id, stamp()))
    os.makedirs(trash_dir, exist_ok=True)
    shutil.move(root, os.path.join(dest, "course"))
    built = os.path.join(dist_dir, course_id)
    if os.path.isdir(built):
        shutil.move(built, os.path.join(dest, "dist"))
    return {"trash": dest}

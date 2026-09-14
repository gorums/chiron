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

from coursekit.course import config as ck_config
from coursekit.course import figures as ck_figures
from coursekit.course import loader as ck_loader
from coursekit.course import notebooks as ck_notebooks
from coursekit.errors import CourseError

from .authoring import overrides
from .support.files import read_json, stamp, write_json
from .support.ids import is_module_id

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
    """Apply a settings form. Returns what is now stored. Raises CourseError on bad input.

    The scalar fields are `SETTINGS`; each structured section of the form has a function of
    its own in `FORM_SECTIONS`, given the manifest and what the form sent for it."""
    path = os.path.join(root, "course.json")
    manifest = read_json(path)
    if "id" in changes and changes["id"] != manifest.get("id"):
        raise CourseError("A course's id cannot change: it is the key the reader's progress is stored under.")
    for key, clean in SETTINGS.items():
        if key in changes:
            manifest[key] = _scalar(key, clean(changes[key]))
    for key, apply in FORM_SECTIONS.items():
        if key in changes:
            apply(manifest, changes[key])
    write_json(path, manifest)
    ck_config.load(root)          # it must still be a valid manifest
    return settings(root)


def _scalar(key: str, value: str) -> str:
    """The two scalar fields with a rule of their own: a title is required, a persona ends
    in a full stop."""
    if key == "title" and not value:
        raise CourseError("A course needs a title.")
    if key == "tutorPersona" and value and not value.endswith("."):
        value += "."
    return value


# ---- one function per structured section of the settings form -------------------------


def _set_milestones(manifest: Dict[str, Any], raw: Any) -> None:
    manifest["milestones"] = _clean_milestones(raw)


def _set_anchor(manifest: Dict[str, Any], raw: Any) -> None:
    """The four anchor texts, each optional; anything but an object is ignored."""
    if not isinstance(raw, dict):
        return
    anchor = {k: _TEXT(raw.get(k), 300) for k in ANCHOR_KEYS}
    manifest["anchor"] = {k: v for k, v in anchor.items() if v}


def _set_notebooks(manifest: Dict[str, Any], raw: Any) -> None:
    """Null turns them off; the form sends the packages as one comma-separated line."""
    if isinstance(raw, dict) and isinstance(raw.get("packages"), str):
        raw = dict(raw, packages=[p for p in re.split(r"[,\s]+", raw["packages"]) if p])
    runtime = ck_config.notebooks_setting(raw)
    if runtime:
        manifest["notebooks"] = runtime
    else:
        manifest.pop("notebooks", None)


def _set_parts(manifest: Dict[str, Any], raw: Any) -> None:
    """Name, blurb and hours per part, matched by id; the course hours are their sum."""
    by_id = {p.get("id"): p for p in (raw or []) if isinstance(p, dict)}
    for part in manifest.get("parts") or []:
        edit = by_id.get(part.get("id"))
        if edit:
            _edit_part(part, edit)
    manifest["hours"] = _tidy(sum(float(p.get("hours") or 0) for p in manifest["parts"]))


def _edit_part(part: Dict[str, Any], edit: Dict[str, Any]) -> None:
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


# Applied in this order, after the scalar fields.
FORM_SECTIONS = {
    "milestones": _set_milestones, "anchor": _set_anchor,
    "notebooks": _set_notebooks, "parts": _set_parts,
}


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
        _move_file(cfg, current, part)
    order = _reorder(cfg, modules, mid, part.id, index)
    overrides.forget(root, mid)

    manifest_path = os.path.join(root, "course.json")
    manifest = read_json(manifest_path)
    manifest["order"] = order
    write_json(manifest_path, manifest)
    ck_config.load(root)
    return {"order": order, "part": part.id, "moved": part.id != current.part}


def _move_file(cfg, current, part) -> None:
    """The module's file into the part's folder - and back again if that would leave its
    old part empty, because the loader refuses a part with no modules."""
    dest_dir = os.path.join(cfg.modules_dir, part.dir)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(current.source))
    if os.path.exists(dest):
        raise CourseError("A file named %s already exists in that part." % os.path.basename(dest))
    shutil.move(current.source, dest)
    src_dir = os.path.dirname(current.source)
    if not any(f.endswith(".md") for f in os.listdir(src_dir)):
        shutil.move(dest, current.source)
        raise CourseError("That would leave the part '%s' with no modules." % current.part)


def _reorder(cfg, modules, mid: str, part_id: str, index: int) -> List[str]:
    """Every part's ids in their current sequence, with `mid` re-inserted at `index` in its
    part - at the end when the index is missing or out of range."""
    order: List[str] = []
    for p in cfg.parts:
        ids = [m.id for m in modules if m.part == p.id and m.id != mid]
        if p.id == part_id:
            pos = len(ids) if index is None or index < 0 or index > len(ids) else int(index)
            ids.insert(pos, mid)
        order.extend(ids)
    return order


# --------------------------------------------------------------------------- removing a module


def remove_module(root: str, mid: str, trash_dir: str) -> Dict[str, Any]:
    """Take one module out of a course: its file, its figures, its study data, its short title.

    The file goes to the trash rather than being deleted. Progress for the id is left alone in
    the reader's state — harmless, and the id is never reused so it can never be confused.
    """
    if not is_module_id(mid):
        raise CourseError("Bad module id.")
    cfg = ck_config.load(root)
    found = _module_files(cfg, mid)
    if not found:
        raise CourseError("No module '%s' in this course." % mid)

    dest = os.path.join(trash_dir, "%s-%s-%s" % (cfg.id, mid, stamp()))
    os.makedirs(dest, exist_ok=True)
    for path in found:
        shutil.move(path, os.path.join(dest, os.path.basename(path)))

    removed = {"file": [os.path.relpath(p, root).replace(os.sep, "/") for p in found],
               "figures": _trash_media(cfg.figures_dir, ck_figures.names_for(cfg.figures_dir, mid), dest),
               "notebooks": _trash_media(cfg.notebooks_dir,
                                         ck_notebooks.names_for(cfg.notebooks_dir, mid), dest),
               "assessment": _drop_assessment(cfg, mid),
               "suggestions": _drop_suggestions(cfg, mid),
               "trash": dest}
    _forget_in_manifest(root, mid)
    return removed


def _module_files(cfg, mid: str) -> List[str]:
    """Every markdown file in any part whose name starts with the id."""
    found = []
    for part in cfg.parts:
        directory = os.path.join(cfg.modules_dir, part.dir)
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if name.endswith(".md") and name.split("-", 1)[0] == mid:
                found.append(os.path.join(directory, name))
    return found


def _trash_media(directory: str, names: List[str], dest: str) -> int:
    """The module's figures or notebooks into the trash folder; how many went."""
    for name in names:
        shutil.move(os.path.join(directory, name), os.path.join(dest, name))
    return len(names)


def _data_files(cfg, key: str) -> List[str]:
    """The JSON files under one of the course's data folders, in name order."""
    directory = cfg.path(cfg.data[key])
    if not os.path.isdir(directory):
        return []
    return [os.path.join(directory, name) for name in sorted(os.listdir(directory))
            if name.endswith(".json")]


def _drop_assessment(cfg, mid: str) -> bool:
    """The module's entry out of whichever assessment file holds it (a list of rows)."""
    dropped = False
    for path in _data_files(cfg, "assessments"):
        rows = read_json(path)
        if isinstance(rows, list) and any(isinstance(r, dict) and r.get("id") == mid for r in rows):
            kept = [r for r in rows if not (isinstance(r, dict) and r.get("id") == mid)]
            _drop_or_write(path, kept, empty=not kept)
            dropped = True
    return dropped


def _drop_suggestions(cfg, mid: str) -> bool:
    """The module's entry out of whichever suggestions file holds it (a map by id)."""
    dropped = False
    for path in _data_files(cfg, "suggestions"):
        rows = read_json(path)
        if isinstance(rows, dict) and mid in rows:
            del rows[mid]
            _drop_or_write(path, rows, empty=not rows)
            dropped = True
    return dropped


def _forget_in_manifest(root: str, mid: str) -> None:
    """The short title and the `order` entry; the manifest is rewritten only if it changed."""
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

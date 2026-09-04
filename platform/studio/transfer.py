"""Moving a whole course in or out of the library.

A course is a folder of markdown and JSON, usually its own git repository. Three ways to
move one:

    export_zip(root)                 -> bytes        the folder as a zip, without .git
    import_zip(courses_dir, data)    -> {id, ...}    a zip from anywhere, into courses/<id>
    import_git(courses_dir, url)     -> {id, ...}    `git clone` into courses/<id>

Both imports end the same way: the folder is renamed to the id inside its `course.json`,
because every route in Studio treats the folder name as the course id, and the manifest is
loaded once to prove the import is a course at all. Nothing existing is ever overwritten -
an import into a taken id is refused, not merged.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from typing import Any, Dict, Optional

from coursekit import config as ck_config
from coursekit.errors import CourseError

from .ids import is_course_id

# https://host/path or git@host:path. Nothing else: the URL becomes a subprocess argument.
GIT_URL = re.compile(r"^(https?://[\w.\-]+(:\d+)?/[\w.\-/~%]+|git@[\w.\-]+:[\w.\-/~]+)$")
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".claude"}
MAX_MEMBERS = 5000


# --------------------------------------------------------------------------- export


def export_zip(root: str) -> bytes:
    """The course folder as a zip. Hidden and tool directories stay behind; dist/ is not here."""
    if not os.path.isfile(os.path.join(root, "course.json")):
        raise CourseError("No such course.")
    base = os.path.basename(os.path.normpath(root))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            for name in sorted(files):
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                zf.write(full, "%s/%s" % (base, rel))
    return buf.getvalue()


# --------------------------------------------------------------------------- import: zip


def import_zip(courses_dir: str, data: bytes) -> Dict[str, Any]:
    """Unpack a course zip into the library. The zip may hold the files at its root or inside
    one top-level folder; either way the result is `courses/<id>/course.json`."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise CourseError("That file is not a zip archive.")
    names = [n for n in zf.namelist() if not n.endswith("/")]
    if not names:
        raise CourseError("The zip is empty.")
    if len(names) > MAX_MEMBERS:
        raise CourseError("The zip holds too many files to be a course.")
    prefix = _common_folder(names)
    if (prefix + "course.json") not in names:
        raise CourseError("No course.json at the top of the zip - this is not a course.")

    staging = tempfile.mkdtemp(prefix="import-", dir=_staging_parent(courses_dir))
    try:
        for member in zf.infolist():
            if member.is_dir():
                continue
            rel = member.filename[len(prefix):]
            if not rel or _unsafe(rel):
                continue
            target = os.path.join(staging, *rel.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        return _install(courses_dir, staging, source="zip")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _common_folder(names) -> str:
    """'name/' when every member sits under one folder, else ''."""
    heads = {n.split("/", 1)[0] for n in names}
    if len(heads) == 1 and all("/" in n for n in names):
        return heads.pop() + "/"
    return ""


def _unsafe(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    return any(p in ("", ".", "..") for p in parts) or rel.startswith("/") or ":" in parts[0]


# --------------------------------------------------------------------------- import: git


def import_git(courses_dir: str, url: str, timeout: int = 180) -> Dict[str, Any]:
    """Clone a course repository into the library."""
    url = (url or "").strip()
    if not GIT_URL.match(url):
        raise CourseError("Give an https:// or git@ repository URL.")
    git = shutil.which("git")
    if not git:
        raise CourseError("git is not installed on this machine, so nothing can be cloned.")
    staging = tempfile.mkdtemp(prefix="clone-", dir=_staging_parent(courses_dir))
    target = os.path.join(staging, "repo")
    try:
        try:
            proc = subprocess.run([git, "clone", "--depth", "1", "--", url, target],
                                  capture_output=True, text=True, timeout=timeout,
                                  env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
        except subprocess.TimeoutExpired:
            raise CourseError("git clone took longer than %d seconds and was stopped." % timeout)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["unknown error"]
            raise CourseError("git clone failed: %s" % tail[0])
        return _install(courses_dir, target, source="git", keep_git=True, url=url)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


# --------------------------------------------------------------------------- shared


def _staging_parent(courses_dir: str) -> str:
    """Stage beside the destination so the final move is a rename on the same volume."""
    os.makedirs(courses_dir, exist_ok=True)
    return courses_dir


def _install(courses_dir: str, staged: str, *, source: str, keep_git: bool = False,
             url: str = "") -> Dict[str, Any]:
    manifest = os.path.join(staged, "course.json")
    if not os.path.isfile(manifest):
        raise CourseError("The repository has no course.json at its root - this is not a course.")
    cfg = ck_config.load(staged)             # raises ManifestError with the reason if broken
    course_id = cfg.id
    if not is_course_id(course_id):
        raise CourseError("The course id '%s' in course.json is not usable as a folder name." % course_id)
    dest = os.path.join(courses_dir, course_id)
    if os.path.exists(dest):
        raise CourseError("A course with the id '%s' is already in the library. Remove or rename it first." % course_id)
    if not keep_git:
        shutil.rmtree(os.path.join(staged, ".git"), ignore_errors=True)
    shutil.move(staged, dest)
    cfg = ck_config.load(dest)               # paths now point at the final folder
    return {"id": course_id, "title": cfg.title, "root": dest, "source": source, "url": url,
            "modules": _count_modules(cfg)}


def _count_modules(cfg) -> int:
    n = 0
    for part in cfg.parts:
        directory = os.path.join(cfg.modules_dir, part.dir)
        if os.path.isdir(directory):
            n += sum(1 for f in os.listdir(directory) if f.endswith(".md"))
    return n


def is_git_url(text: Optional[str]) -> bool:
    return bool(GIT_URL.match((text or "").strip()))

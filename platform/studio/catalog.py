"""What the API reports about the library: every course, one course in detail, the
reader's calendar, the Studio settings page.

Two levels of cost. `course_summary` counts module *files* and reads the progress record,
cheap enough for the library listing that polls every few seconds; `course_detail` parses
every module and is only asked for by the course page.
"""

from __future__ import annotations

import os
import posixpath
import shutil
import time
from typing import Any, Dict, List

from coursekit.course import config as ck_config
from coursekit import llm
from coursekit.course import loader as ck_loader
from coursekit import settings as ck_settings
from coursekit.errors import CourseError
from coursekit.paths import COURSES_DIR, DIST_DIR, REPO_ROOT
from coursekit.settings import SETTINGS

from .authoring import curriculum, generator, overrides, reviews
from .store import prefs, progress
from . import discover, jupyter, manage, models
from .support import log as logmod
from .support.errors import GenerationError
from .store.runtime import LOG_FILE, PREFS, PROGRESS_DIR, REGISTRY, STATE_ROOT, store

EDITABLE = (".md", ".json", ".svg", ".ipynb")
RECENT_JOBS = int(SETTINGS.get("studio.recentJobs"))


def course_root(course_id: str) -> str:
    return os.path.join(COURSES_DIR, course_id)


def module_ids(cfg) -> List[str]:
    """Module ids in course order, from filenames alone - cheap enough for every listing.
    The order is the loader's (`course.json` `order`, then filename), so it matches the build."""
    ids = []
    for part in cfg.parts:
        if not os.path.isdir(os.path.join(cfg.modules_dir, part.dir)):
            continue
        for name in ck_loader.module_files(cfg, part):
            ids.append(name.split("-", 1)[0])
    return ids


# --------------------------------------------------------------------------- one course


# In the course but never in the page: the approved curriculum and the prompts the course
# sends. Editing either changes what the NEXT run writes, not what the reader can see, so
# neither may make a course look out of date.
NOT_IN_THE_PAGE = (curriculum.PLAN_FILE, overrides.FILE)


def newest_source(root: str) -> float:
    """When the course was last touched. A file newer than the build is what makes a course
    *dirty*, which is the only honest way to tell someone the page they are reading is old."""
    skip = {os.path.normpath(os.path.join(root, rel)) for rel in NOT_IN_THE_PAGE}
    newest = 0.0
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in names:
            path = os.path.join(folder, name)
            if name.endswith(EDITABLE) and os.path.normpath(path) not in skip:
                newest = max(newest, os.path.getmtime(path))
    return newest


def course_summary(course_id: str) -> Dict[str, Any]:
    """The library card: title, counts, progress, whether it is built, the job on it."""
    root = course_root(course_id)
    info: Dict[str, Any] = {"id": course_id, "ok": False, "title": course_id,
                            "modules": 0, "hours": 0, "built": False, "error": ""}
    try:
        cfg = ck_config.load(root)
        ids = module_ids(cfg)
        info.update(ok=True, title=cfg.title, hours=cfg.hours, tagline=cfg.tagline,
                    subject=cfg.subject, parts=len(cfg.parts), modules=len(ids),
                    localFile=cfg.local_file, webFile=cfg.web_file,
                    notebooks=cfg.notebooks or None,
                    progress=store().summary(course_id, ids))
        built = os.path.join(DIST_DIR, cfg.id, cfg.local_file)
        if os.path.isfile(built):
            stamp = os.path.getmtime(built)
            info.update(built=True, builtAt=stamp, dirty=newest_source(root) > stamp + 1)
        info["resumable"] = can_resume(course_id)
    except Exception as exc:  # noqa: BLE001 - a broken course is listed with its error
        info["error"] = str(exc)
    job = REGISTRY.active_for(course_id)
    if job:
        info["job"] = job.summary()
    return info


def course_detail(course_id: str) -> Dict[str, Any]:
    """Everything the course page in Studio shows. Parses the modules, so not for listings."""
    info = course_summary(course_id)
    if not info["ok"]:
        return info
    root = course_root(course_id)
    cfg = ck_config.load(root)
    info["parts"] = [dict(p.public(), dir=p.dir) for p in cfg.parts]
    info["audience"] = cfg.audience
    info["practitioner"] = cfg.practitioner
    info["moduleList"] = []
    own_prompts = overrides.load(root)      # which modules send prompts of the owner's own
    sources: Dict[str, str] = {}
    try:
        for m in ck_loader.load_modules(cfg):
            sources[m.id] = m.source
            info["moduleList"].append({
                "id": m.id, "num": m.num, "part": m.part, "title": m.title, "short": m.short,
                "minutes": m.minutes, "sections": len(m.sections), "figures": len(m.figures),
                "notebooks": len(m.notebooks),
                "path": os.path.relpath(m.source, root).replace(os.sep, "/"),
                "prompts": sorted(own_prompts.get(m.id, {})),
            })
    except CourseError as exc:
        info["error"] = str(exc)
    info["files"] = course_files(root)
    record = store().load(course_id)
    state_obj = record["state"] if record else {}
    info["moduleProgress"] = module_progress(state_obj)
    info["questions"] = open_questions(state_obj, info["moduleList"])
    info["learner"] = learner_view(state_obj, info["moduleList"])
    info["settings"] = manage.settings(root)
    info["notebooks"] = cfg.notebooks or None
    info["order"] = cfg.order
    info["reviews"] = reviews.load_reviews(STATE_ROOT, course_id, sources)
    info["profile"] = PREFS.profile
    return info


def open_questions(state: Dict[str, Any], module_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The passages the reader marked with a question, newest first.

    These are the reader's own record of where the course stopped short - the best brief an
    Add-a-module form can be given.
    """
    titles = {m["id"]: m["title"] for m in module_list}
    out = []
    marks = state.get("marks") if isinstance(state.get("marks"), dict) else {}
    for mid, rows in marks.items():
        for m in rows if isinstance(rows, list) else []:
            if not isinstance(m, dict) or m.get("status") not in ("open", "answered"):
                continue
            out.append({
                "mid": mid, "title": titles.get(mid, mid), "id": m.get("id", ""),
                "sec": m.get("sec"), "text": str(m.get("text") or "")[:400],
                "q": str(m.get("q") or "")[:400], "note": str(m.get("note") or "")[:400],
                "status": m.get("status"), "ts": m.get("ts") or 0,
            })
    return sorted(out, key=lambda q: q["ts"], reverse=True)


def learner_view(state: Dict[str, Any], module_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """What the page's tutor remembers about this reader: the brief and the open gaps.

    The page writes it (see web/js/tutor/learner.js); Studio only shows it, because a gap that
    keeps coming back is the best evidence that a module needs rewriting.
    """
    raw = state.get("learner")
    mem = raw if isinstance(raw, dict) else {}
    titles = {m["id"]: m["title"] for m in module_list}
    closed = mem.get("closed") if isinstance(mem.get("closed"), dict) else {}
    gaps = []
    for g in mem.get("gaps") if isinstance(mem.get("gaps"), list) else []:
        if not isinstance(g, dict) or g.get("status") == "closed" or g.get("id") in closed:
            continue
        gaps.append({
            "id": str(g.get("id") or ""), "mid": str(g.get("mid") or ""),
            "title": titles.get(g.get("mid"), str(g.get("mid") or "")),
            "topic": str(g.get("topic") or "")[:120], "why": str(g.get("why") or "")[:400],
            "ask": str(g.get("ask") or "")[:200],
        })
    return {
        "brief": str(mem.get("brief") or "")[:2000],
        "strengths": [str(s)[:200] for s in mem.get("strengths") or [] if isinstance(s, str)],
        "gaps": gaps,
        "at": mem.get("at") if isinstance(mem.get("at"), (int, float)) else None,
    }


def module_progress(state: Dict[str, Any]) -> Dict[str, Any]:
    """Per module: done, minutes, sections read, quiz finished - the module row's badges."""
    out = {}
    for mid, entry in (state.get("progress") or {}).items():
        if not isinstance(entry, dict):
            continue
        secs = entry.get("secs") or {}
        quiz = entry.get("quiz") if isinstance(entry.get("quiz"), dict) else {}
        out[mid] = {
            "done": bool(entry.get("done")),
            "minutes": int(progress.number(entry.get("time")) // 60),
            "read": sum(1 for v in secs.values() if v) if isinstance(secs, dict) else 0,
            "quiz": bool(quiz.get("finished")),
        }
    return out


def course_files(root: str) -> List[str]:
    """Every markdown, JSON, SVG and notebook file in the course, as course-relative posix paths."""
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if name.endswith(EDITABLE):
                out.append(os.path.relpath(os.path.join(base, name), root).replace(os.sep, "/"))
    return out


def can_resume(course_id: str) -> bool:
    """A course that does not build clean but still has a curriculum to finish from -
    saved in plan/plan.json, or reconstructible from course.json."""
    root = course_root(course_id)
    try:
        curriculum.load_plan(root)
    except (CourseError, GenerationError, ValueError, OSError):
        return False
    try:
        return bool(generator.check_course(root))
    except CourseError:
        return True


def resolve_course_file(root: str, relative: str) -> str:
    """A path inside the course folder, or a ValueError. Only markdown, JSON, SVG and
    notebook files qualify.

    The relative path comes from the browser, so it is normalised and checked to stay
    inside the course.
    """
    clean = posixpath.normpath("/" + (relative or "").replace("\\", "/").lstrip("/")).lstrip("/")
    if not clean or clean == "." or not clean.endswith(EDITABLE):
        raise ValueError("Only .md, .json, .svg and .ipynb files inside the course can be edited.")
    full = os.path.normpath(os.path.join(root, clean))
    if os.path.commonpath([os.path.abspath(root), os.path.abspath(full)]) != os.path.abspath(root):
        raise ValueError("That path is outside the course.")
    return full


# --------------------------------------------------------------------------- the library


def list_courses() -> List[Dict[str, Any]]:
    if not os.path.isdir(COURSES_DIR):
        return []
    ids = sorted(d for d in os.listdir(COURSES_DIR)
                 if os.path.isfile(os.path.join(COURSES_DIR, d, "course.json")))
    return [course_summary(cid) for cid in ids]


def calendar(courses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Study days across every course, for the library's heatmap and the cross-course streak.

    A day counts when any course marked it. The streak is the run of consecutive days ending
    today or yesterday - yesterday, so a reader who has not opened anything yet today does not
    see their streak vanish at breakfast.
    """
    by_day: Dict[str, List[str]] = {}
    for c in courses:
        for day in ((c.get("progress") or {}).get("seen") or []):
            by_day.setdefault(str(int(day)), []).append(c["id"])
    today = int(time.time() // 86400)
    days = {int(k) for k in by_day}
    streak, cursor = 0, today if today in days else today - 1
    while cursor in days:
        streak += 1
        cursor -= 1
    return {"days": by_day, "streak": streak, "today": today, "total": len(days)}


def state() -> Dict[str, Any]:
    """`GET /api/state`: what every screen of the UI needs, cheap enough to poll."""
    courses = list_courses()
    return {
        "courses": courses,
        "llm": llm_view(),
        # The name this block had when there was only ever one provider. A page built or
        # loaded before that changed still looks for it; it goes when nothing does.
        "claude": llm_view(),
        "jobs": [j.summary() for j in REGISTRY.all()[:RECENT_JOBS]],
        "jupyter": jupyter_public(),
        "root": REPO_ROOT,
        "profile": PREFS.profile,
        "profiles": progress.profiles(PROGRESS_DIR),
        "calendar": calendar(courses),
        "git": bool(shutil.which("git")),
    }


def jupyter_public() -> Dict[str, Any]:
    """The Jupyter server as the UI sees it: everything but the token, which only a served
    course page needs (`GET /api/jupyter`)."""
    return {k: v for k, v in jupyter.view().items() if k != "token"}


def profiles_view() -> Dict[str, Any]:
    return {"active": PREFS.profile, "profiles": progress.profiles(PROGRESS_DIR)}


def models_view() -> List[Dict[str, str]]:
    """The models a form may pick from, as the UI shows them: `/api/state` carries the list
    so every writing form can offer it without a second request. `id` is the name a form
    sends (the short alias); `apiId` is the full id a served course page stores and sends;
    `provider` is the row in `providers` that reaches it, and `providerLabel` is that row as
    a person reads it."""
    labels = {name: cfg.get("label") or name for name, cfg in SETTINGS.providers.items()}
    return [{"id": m["name"], "name": m["label"], "note": m["note"],
             "apiId": SETTINGS.model_id(m["name"]), "provider": m["provider"],
             "providerLabel": labels.get(m["provider"], m["provider"])}
            for m in prefs.models()]


def providers_view() -> List[Dict[str, Any]]:
    """Every configured provider, as the settings page shows them: what it is, whether it is
    enabled, whether it can answer right now, and how many models it reaches. The disabled
    ones are here too - a model can be added to a provider before it is switched on, and a
    row nobody can see is a row nobody can enable."""
    counted: Dict[str, int] = {}
    for m in SETTINGS.models:
        counted[m["provider"]] = counted.get(m["provider"], 0) + 1
    enabled = set(SETTINGS.provider_names())
    return [dict(p.describe(), models=counted.get(p.name, 0),
                 enabled=p.name in enabled,
                 isDefault=p.name == SETTINGS.default_provider)
            for p in llm.providers(all_of_them=True)]


def llm_view() -> Dict[str, Any]:
    """`/api/state` and `/api/settings`: what can answer, which model is chosen, and the list
    every form picks from. `available` is about the provider a job would run on - a key for a
    provider nobody writes with must not read as "Studio may write"."""
    default = llm.provider_for(SETTINGS.provider_of(PREFS.model))
    return {"available": default.available(), "provider": default.name,
            "providerLabel": default.label, "hint": getattr(default, "hint", ""),
            "providers": providers_view(), "model": PREFS.model, "models": models_view(),
            "defaultModel": SETTINGS.model_id(PREFS.model)}


def settings_view() -> Dict[str, Any]:
    """`GET /api/settings`: the model, every resolved platform setting with its source, and
    where things are."""
    return {
        "model": PREFS.model,
        "profile": PREFS.profile,
        "models": models_view(),
        "modelList": models.current(),
        "discovery": discover.status(),
        "llm": llm_view(),
        "claude": llm_view(),
        "jupyter": jupyter_public(),
        "paths": {"root": REPO_ROOT, "courses": COURSES_DIR, "dist": DIST_DIR,
                  "state": STATE_ROOT, "log": LOG_FILE, "settings": SETTINGS.path,
                  "overlay": SETTINGS.overlay},
        "platform": SETTINGS.describe(),
        "overrides": dict(SETTINGS.overrides),
        "envKeys": dict(ck_settings.ENV_KEYS),
        "logs": {"maxBytes": logmod.MAX_BYTES, "backups": logmod.BACKUPS},
    }

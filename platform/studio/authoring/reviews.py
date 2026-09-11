"""Reviews: what the model, or the owner, thinks of a module as it is.

A review is an opinion about content, not content, so it lives under `state/reviews/`,
never in the course. One JSON file per module:

    {module, title, verdict, summary, gaps, errors, quiz, rewriteBrief, at, model,
     accepted?, ownerOnly?}

`at` is when the model judged the text; `accepted` is when the owner marked it good. A review
older than the module file is reported `stale`: a rewrite or a hand edit never changes a
verdict, only a new review does.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from coursekit.course import assessments as ck_assess
from coursekit.course import config as ck_config
from coursekit.course import loader as ck_loader
from .. import modelcall
from . import overrides, prompts
from .coerce import fix_review
from .curriculum import plan_from_course
from ..support.errors import GenerationError
from ..support.files import read_json, read_text, write_json
from ..store.jobs import Job


def reviews_dir(state_root: str, course_id: str) -> str:
    return os.path.join(state_root, "reviews", course_id)


def _review_path(state_root: str, course_id: str, mid: str) -> str:
    return os.path.join(reviews_dir(state_root, course_id), "%s.json" % mid)


def _now_ms() -> int:
    return int(time.time() * 1000)


def load_reviews(state_root: str, course_id: str,
                 sources: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Every stored review for a course, keyed by module id.

    With `sources` (module id -> file path) a review older than the module file is marked
    `stale`, with `moduleChangedAt` saying when the file last changed.
    """
    directory = reviews_dir(state_root, course_id)
    out: Dict[str, Any] = {}
    if not os.path.isdir(directory):
        return out
    for name in sorted(os.listdir(directory)):
        if name.endswith(".json"):
            try:
                out[name[:-5]] = read_json(os.path.join(directory, name))
            except (OSError, ValueError):
                continue
    for mid, review in out.items():
        path = (sources or {}).get(mid)
        if not path or not isinstance(review, dict):
            continue
        try:
            changed = int(os.path.getmtime(path) * 1000)     # whole ms, like `at`
        except OSError:
            continue
        # The owner's own "this is good" counts as a verdict on the text of that moment too.
        judged = max(float(review.get("at") or 0), float(review.get("accepted") or 0))
        if changed > judged:
            review["stale"] = True
            review["moduleChangedAt"] = changed
    return out


def accept_module(state_root: str, course_id: str, mid: str, accepted: bool = True) -> Dict[str, Any]:
    """The course owner's own verdict: this module is good as it is.

    It lives in the same file as the model's review, so the row shows one thing. With a review
    present the findings are kept underneath for reference; without one the record says so
    (`ownerOnly`), and withdrawing the mark removes the file again.
    """
    path = _review_path(state_root, course_id, mid)
    record: Dict[str, Any] = {}
    if os.path.isfile(path):
        try:
            loaded = read_json(path)
            record = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            record = {}

    if accepted:
        if not record:
            record = {"module": mid, "verdict": "solid",
                      "summary": "Marked good by the course owner, without a review.",
                      "gaps": [], "errors": [], "quiz": [], "rewriteBrief": "",
                      "at": _now_ms(), "ownerOnly": True}
        record["accepted"] = _now_ms()
        write_json(path, record)
        return record

    if record.get("ownerOnly"):
        try:
            os.unlink(path)
        except OSError:
            pass
        return {}
    if "accepted" in record:
        del record["accepted"]
        write_json(path, record)
    return record


def review_prompt(plan: Dict[str, Any], spec: Dict[str, Any], body: str,
                  assess: Dict[str, Any], root: str = "") -> str:
    """The prompt a module is reviewed against - the course's own where it has one."""
    return overrides.apply(root, spec["id"], "review",
                           prompts.review(plan, plan["modules"], spec, body, assess),
                           body=body, study=prompts.quiz_listing(assess))


def review(job: Job, courses_dir: str, state_root: str, course_id: str, mid: str,
           brief: Dict[str, Any]) -> Dict[str, Any]:
    """Have the model read one module critically and store what it found.

    The UI turns the rewrite brief the review ends with into a Rewrite.
    """
    root = os.path.join(courses_dir, course_id)
    cfg = ck_config.load(root)
    modules = ck_loader.load_modules(cfg)
    current = next((m for m in modules if m.id == mid), None)
    if current is None:
        raise GenerationError("No module '%s' in this course." % mid)
    plan = plan_from_course(cfg, modules)
    spec = next(m for m in plan["modules"] if m["id"] == mid)
    assess = ck_assess.load_assessments(cfg).get(mid) or {}
    model = brief.get("model", "")
    job.meta["course"] = course_id
    job.meta["module"] = mid

    job.progress(1, 2, "Reading %s · %s" % (mid, current.title))
    body = read_text(current.source)
    result = fix_review(modelcall.ask_json(
        review_prompt(plan, spec, body, assess, root), model=model,
        timeout=modelcall.timeout_for("review"), what="a review of %s" % mid))
    result.update(module=mid, title=current.title, at=_now_ms(), model=model or "")
    write_json(_review_path(state_root, course_id, mid), result)
    job.emit("review", id=mid, verdict=result["verdict"], gaps=len(result["gaps"]),
             errors=len(result["errors"]), quiz=len(result["quiz"]))
    job.progress(2, 2, "Done")
    return dict(result, course=course_id, root=root)

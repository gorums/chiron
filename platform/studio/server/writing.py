"""Every route that sets a model writing: a course, a module, its figures, a review.

They are all one shape. Refuse if the provider cannot answer, refuse if the course is
already busy, settle the model, then hand a `jobs.Job` to `authoring/` and answer with its
summary - the browser follows the rest over SSE. Nothing here waits for a model.
"""

from __future__ import annotations

from coursekit.course import config as ck_config
from coursekit.paths import COURSES_DIR, DIST_DIR
from coursekit.settings import SETTINGS

from .. import catalog
from ..authoring import curriculum, editing, generator, overrides, promptview, reviews
from ..store import jobs
from ..store.runtime import STATE_ROOT
from ..support.errors import GenerationError
from ..support.ids import is_course_id
from ..support.log import log
from .base import COURSE, MODULE, route

MIN_HOURS = float(SETTINGS.get("generation.minHours"))
MAX_HOURS = float(SETTINGS.get("generation.maxHours"))


class WritingRoutes:
    # ---- jobs: generation and editing with a model ----

    @route("POST", r"/api/plan/prompt")
    def plan_prompt(self):
        """What one module of a curriculum would be written from, assembled by the writers
        themselves, so what the approval gate shows is what the run will send. The course
        does not exist yet, so the overrides edited there travel in the plan."""
        body = self._body()
        plan = body.get("plan")
        mid = str(body.get("mid") or "").strip().upper()
        if not isinstance(plan, dict) or not isinstance(plan.get("modules"), list):
            return self._fail("Send the plan to preview.")
        ready = curriculum.plan_for_prompt(plan)
        carried = (plan.get("prompts") or {}).get(mid) if isinstance(plan.get("prompts"), dict) else {}
        try:
            stages = promptview.rows(ready, mid, carried=carried if isinstance(carried, dict) else {})
        except KeyError:
            return self._fail("No module %s in this plan." % (mid or "?"), 404)
        except (TypeError, ValueError) as err:
            return self._fail("That plan cannot be turned into a prompt: %s" % err)
        self._json({"module": mid, "stages": stages, "tokens": overrides.TOKENS})

    @route("POST", r"/api/generate")
    def generate(self):
        brief = self._body()
        theme = (brief.get("theme") or "").strip()
        if not theme:
            return self._fail("Give the course a theme.")
        try:
            hours = float(brief.get("hours") or 0)
        except (TypeError, ValueError):
            return self._fail("Hours must be a number.")
        if hours < MIN_HOURS:
            return self._fail("%g hours is the shortest course worth structuring." % MIN_HOURS)
        if hours > MAX_HOURS:
            return self._fail("%g hours is beyond what one course should hold." % MAX_HOURS)
        if not self._provider():
            return
        course_id = (brief.get("id") or "").strip().lower()
        if course_id and not is_course_id(course_id):
            return self._fail("A course id may hold lowercase letters, digits and hyphens only.")
        if course_id and not self._idle(course_id):
            return

        brief.update(theme=theme, hours=hours, id=course_id or None, model=self._model(brief),
                     resume=False)
        log.info("generate: theme=%r hours=%s model=%s", theme, hours, brief["model"])
        job = jobs.Job("generate", {"theme": theme, "hours": hours, "model": brief["model"]})
        self._start_job(job, lambda j: generator.generate(j, COURSES_DIR, DIST_DIR, brief))

    @route("POST", COURSE + r"/resume")
    def resume(self, course_id: str):
        root = catalog.course_root(course_id)
        try:
            curriculum.load_plan(root)
        except (GenerationError, ValueError) as exc:
            return self._fail("Cannot resume: %s" % exc)
        if not catalog.can_resume(course_id):
            return self._fail("Nothing to resume: this course is complete and consistent. Use Build.")
        if not self._provider() or not self._idle(course_id):
            return
        cfg = ck_config.load(root)
        asked = self._body()
        brief = {"id": course_id, "theme": cfg.subject, "hours": cfg.hours, "resume": True,
                 "model": self._model(asked), "figures": asked.get("figures", True) is not False,
                 "notebooks": asked.get("notebooks", True) is not False}
        log.info("resume: course=%s model=%s figures=%s notebooks=%s", course_id, brief["model"],
                 brief["figures"], brief["notebooks"])
        job = jobs.Job("generate", {"theme": cfg.subject, "hours": cfg.hours, "course": course_id,
                                    "resume": True, "model": brief["model"]})
        self._start_job(job, lambda j: generator.generate(j, COURSES_DIR, DIST_DIR, brief))

    @route("POST", COURSE + r"/extend")
    def extend(self, course_id: str):
        brief = self._body()
        if not (brief.get("topic") or "").strip():
            return self._fail("Say what the new module should cover.")
        if not self._provider() or not self._idle(course_id):
            return
        brief["model"] = self._model(brief)
        log.info("extend: course=%s topic=%r model=%s", course_id, brief["topic"], brief["model"])
        job = jobs.Job("extend", {"course": course_id, "topic": brief["topic"]})
        self._start_job(job, lambda j: editing.extend(j, COURSES_DIR, DIST_DIR, course_id, brief))

    @route("POST", MODULE + r"/rewrite")
    def rewrite(self, course_id: str, mid: str):
        brief = self._body()
        if not self._provider() or not self._idle(course_id):
            return
        brief["model"] = self._model(brief)
        mode = "patch" if brief.get("mode") == "patch" else "rewrite"
        log.info("rewrite: course=%s module=%s mode=%s model=%s", course_id, mid, mode, brief["model"])
        job = jobs.Job("rewrite", {"course": course_id, "module": mid, "mode": mode})
        self._start_job(job, lambda j: editing.rewrite(j, COURSES_DIR, DIST_DIR, course_id, mid, brief))

    @route("POST", COURSE + r"/figures")
    def figures_course(self, course_id: str):
        brief = self._body()
        if not self._provider("drawn"):
            return
        if not self._idle(course_id):
            return
        brief["model"] = self._model(brief)
        brief.pop("module", None)
        log.info("figures: course=%s all=%s model=%s", course_id, bool(brief.get("all")), brief["model"])
        job = jobs.Job("figures", {"course": course_id, "all": bool(brief.get("all"))})
        self._start_job(job, lambda j: editing.draw(j, COURSES_DIR, DIST_DIR, course_id, brief))

    @route("POST", MODULE + r"/figures")
    def figures_module(self, course_id: str, mid: str):
        brief = self._body()
        if not self._provider("drawn"):
            return
        if not self._idle(course_id):
            return
        brief["model"] = self._model(brief)
        brief["module"] = mid
        log.info("figures: course=%s module=%s model=%s", course_id, mid, brief["model"])
        job = jobs.Job("figures", {"course": course_id, "module": mid})
        self._start_job(job, lambda j: editing.draw(j, COURSES_DIR, DIST_DIR, course_id, brief))

    @route("POST", COURSE + r"/notebooks")
    def notebooks_course(self, course_id: str):
        brief = self._body()
        if not self._provider():
            return
        if not self._idle(course_id):
            return
        brief["model"] = self._model(brief)
        brief.pop("module", None)
        log.info("notebooks: course=%s all=%s model=%s", course_id, bool(brief.get("all")), brief["model"])
        job = jobs.Job("notebooks", {"course": course_id, "all": bool(brief.get("all"))})
        self._start_job(job, lambda j: editing.notebooks_job(j, COURSES_DIR, DIST_DIR, course_id, brief))

    @route("POST", MODULE + r"/notebooks")
    def notebooks_module(self, course_id: str, mid: str):
        brief = self._body()
        if not self._provider():
            return
        if not self._idle(course_id):
            return
        brief["model"] = self._model(brief)
        brief["module"] = mid
        log.info("notebooks: course=%s module=%s model=%s", course_id, mid, brief["model"])
        job = jobs.Job("notebooks", {"course": course_id, "module": mid})
        self._start_job(job, lambda j: editing.notebooks_job(j, COURSES_DIR, DIST_DIR, course_id, brief))

    @route("POST", MODULE + r"/review")
    def review(self, course_id: str, mid: str):
        if not self._provider("reviewed"):
            return
        if not self._idle(course_id):
            return
        brief = self._body()
        brief["model"] = self._model(brief)
        log.info("review: course=%s module=%s model=%s", course_id, mid, brief["model"])
        job = jobs.Job("review", {"course": course_id, "module": mid})
        self._start_job(job, lambda j: reviews.review(j, COURSES_DIR, STATE_ROOT, course_id, mid, brief))

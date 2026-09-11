"""One module of a course, changed without asking a model.

Removing, moving, the owner's own verdict, and the prompts a course sends instead of the
platform's. Each of these ends by saying what the course's check now makes of the result,
because every one of them can break it.
"""

from __future__ import annotations

from coursekit.course import config as ck_config
from coursekit.course import loader as ck_loader

from .. import catalog, manage
from ..authoring import curriculum, generator, overrides, promptview, reviews
from ..store.runtime import STATE_ROOT, TRASH_DIR
from ..support.log import log
from .base import MODULE, route


class ModuleRoutes:
    # ---- modules of a course, without a model ----

    @route("POST", MODULE + r"/remove")
    def remove_module(self, course_id: str, mid: str):
        if not self._idle(course_id, "That course has a job running; wait for it to finish."):
            return
        root = catalog.course_root(course_id)
        removed = manage.remove_module(root, mid, TRASH_DIR)
        self._json(dict(removed, ok=True, problems=generator.check_course(root)))

    @route("POST", MODULE + r"/move")
    def move_module(self, course_id: str, mid: str):
        if not self._idle(course_id, "That course has a job running; wait for it to finish."):
            return
        root = catalog.course_root(course_id)
        body = self._body()
        try:
            index = int(body.get("index")) if body.get("index") is not None else -1
        except (TypeError, ValueError):
            index = -1
        moved = manage.move_module(root, mid, str(body.get("part") or ""), index)
        log.info("move %s/%s -> part %s index %s", course_id, mid, moved["part"], index)
        self._json(dict(moved, ok=True, problems=generator.check_course(root)))

    @route("GET", MODULE + r"/prompts")
    def module_prompts(self, course_id: str, mid: str):
        """Every prompt this module is written from, as it would be sent."""
        root = catalog.course_root(course_id)
        cfg = ck_config.load(root)
        modules = ck_loader.load_modules(cfg)
        plan = curriculum.plan_from_course(cfg, modules)
        try:
            stages = promptview.rows(plan, mid, root)
        except KeyError:
            return self._fail("No module '%s' in this course." % mid, 404)
        self._json({"module": mid, "stages": stages, "tokens": overrides.TOKENS})

    @route("PUT", MODULE + r"/prompts")
    def set_module_prompt(self, course_id: str, mid: str):
        """Store one stage's prompt, or take the override away with empty text."""
        root = catalog.course_root(course_id)
        body = self._body()
        stage = str(body.get("stage") or "")
        if stage not in overrides.STAGE_IDS:
            return self._fail("There is no %r stage." % stage)
        text = body.get("text")
        if text is not None and not isinstance(text, str):
            return self._fail("A prompt is text.")
        kept = overrides.put(root, mid, stage, text or "")
        log.info("prompt %s/%s stage=%s %s", course_id, mid, stage,
                 "overridden" if stage in kept else "back to the platform's")
        self._json({"ok": True, "overridden": sorted(kept)})

    @route("POST", MODULE + r"/accept")
    def accept_module(self, course_id: str, mid: str):
        """"This is good": the owner's verdict, which the review pill then shows."""
        accepted = bool(self._body().get("accepted", True))
        cfg = ck_config.load(catalog.course_root(course_id))
        sources = {m.id: m.source for m in ck_loader.load_modules(cfg)}
        if mid not in sources:
            return self._fail("No module '%s' in this course." % mid, 404)
        reviews.accept_module(STATE_ROOT, course_id, mid, accepted)
        log.info("accept: course=%s module=%s accepted=%s", course_id, mid, accepted)
        self._json({"ok": True, "accepted": accepted,
                    "review": reviews.load_reviews(STATE_ROOT, course_id, sources).get(mid)})

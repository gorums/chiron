"""The tutor, for a course served from here: same origin, no key, no bridge.

A page opened off disk reaches a model through `tools/bridge/` instead. Both go through
`coursekit.llm`, so the retry policy and the failure kinds are one implementation rather
than two that drift.
"""

from __future__ import annotations

from coursekit.settings import SETTINGS

from .. import catalog, modelcall
from ..support.log import log
from .base import route

ASK_TIMEOUT = int(SETTINGS.get("studio.askTimeout"))


class TutorRoutes:
    # ---- the tutor ----

    @route("POST", r"/api/ask")
    def ask(self):
        """The tutor, for a course served from here: same origin, no key, no bridge."""
        body = self._body()
        messages = body.get("messages") or []
        if not isinstance(messages, list) or not messages:
            return self._fail("No messages to send.")
        if not modelcall.available():
            return self._fail("%s cannot answer, so the tutor is unavailable here."
                              % catalog.llm_view()["providerLabel"], 503)
        prompt = modelcall.chat_prompt(str(body.get("system") or ""), messages)
        try:
            text = modelcall.ask(prompt, model=self._model(body), timeout=ASK_TIMEOUT)
        except modelcall.LLMFailed as exc:
            log.warning("ask: %s (%s) %s", exc, exc.kind, exc.detail)
            return self._fail(str(exc), 502, why=exc.kind, resetsAt=exc.resets_at)
        self._json({"text": text, "mode": "studio"})

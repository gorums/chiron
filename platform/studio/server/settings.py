"""The Settings & logs screen: Studio's own preferences, the model list, the log.

The model list is the one piece of platform configuration a person edits from a browser, so
it is validated here and written to `state/settings.json` - the Studio layer of the settings
- and never to the committed file.
"""

from __future__ import annotations

from .. import catalog, discover, modelcall, models
from ..store.runtime import LOG_FILE, PREFS
from ..support import log as logmod
from ..support.log import log
from .base import route


class SettingsRoutes:
    @route("GET", r"/api/settings")
    def settings_get(self):
        self._json(catalog.settings_view())

    @route("POST", r"/api/settings")
    def settings_post(self):
        try:
            saved = PREFS.save(self._body())
        except ValueError as exc:
            return self._fail(str(exc))
        log.info("settings: model -> %s", saved["model"])
        self._json({"ok": True, "settings": catalog.settings_view()})

    # ---- the model list ----

    @route("GET", r"/api/models")
    def models_get(self):
        self._json(models.current())

    @route("PUT", r"/api/models")
    def models_put(self):
        try:
            saved = models.replace(self._body().get("list"))
        except ValueError as exc:
            return self._fail(str(exc))
        log.info("settings: model list -> %s", ", ".join(m["id"] for m in saved["list"]))
        self._json({"ok": True, "models": saved, "settings": catalog.settings_view()})

    @route("POST", r"/api/models/reset")
    def models_reset(self):
        self._body()
        saved = models.reset()
        log.info("settings: model list back to the platform's")
        self._json({"ok": True, "models": saved, "settings": catalog.settings_view()})

    @route("POST", r"/api/models/discover")
    def models_discover(self):
        self._body()
        report = discover.run()
        self._json({"ok": True, "report": report, "models": models.current(),
                    "settings": catalog.settings_view()})

    @route("POST", r"/api/models/test")
    def models_test(self):
        """One model, on the provider that reaches it. A provider that cannot answer is a
        result to show in that row, not a 400 for the whole page."""
        body = self._body()
        model = str(body.get("model") or "").strip()
        if not models.MODEL_ID.match(model):
            return self._fail("Send the model id to test.")
        self._json(modelcall.probe(model, provider=str(body.get("provider") or "")))

    @route("GET", r"/api/logs")
    def logs(self):
        lines = logmod.recent(limit=int(self._param("limit", "400")),
                              level=self._param("level"), contains=self._param("q"))
        self._json({"lines": lines, "file": LOG_FILE})

    @route("POST", r"/api/logs/clear")
    def logs_clear(self):
        logmod.clear()
        self._json({"ok": True})

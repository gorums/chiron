"""What the whole app is looking at: every course, the search across them, the reader.

`/api/state` is polled by every screen, so it is the one route that has to stay cheap -
`catalog.state()` counts a course's module files rather than parsing them.
"""

from __future__ import annotations

import os
import time

from coursekit.paths import COURSES_DIR
from coursekit.settings import SETTINGS

from .. import catalog, jupyter, search
from ..store import progress
from ..store.runtime import PREFS, PROGRESS_DIR, TRASH_DIR
from ..support.ids import DEFAULT_PROFILE, is_profile
from ..support.log import log
from .base import route

SEARCH_LIMIT = int(SETTINGS.get("studio.searchLimit"))


class StateRoutes:
    @route("GET", r"/api/state")
    def state(self):
        self._json(catalog.state())

    @route("GET", r"/api/jupyter")
    def jupyter_get(self):
        self._json(jupyter.view())

    @route("GET", r"/api/search")
    def search(self):
        self._json(search.search(COURSES_DIR, self._param("q"), SEARCH_LIMIT))

    # ---- reader profiles ----

    @route("GET", r"/api/profile")
    def profile(self):
        self._json({"profile": PREFS.profile})

    @route("GET", r"/api/profiles")
    def profiles_get(self):
        self._json(catalog.profiles_view())

    @route("POST", r"/api/profiles")
    def profiles_post(self):
        body = self._body()
        action = str(body.get("action") or "switch")
        name = str(body.get("name") or "").strip().lower()
        if action in ("switch", "add"):
            try:
                PREFS.save({"profile": name})
            except ValueError as exc:
                return self._fail(str(exc))
            if action == "add":
                os.makedirs(progress.Store(PROGRESS_DIR, name).directory, exist_ok=True)
            log.info("profile -> %s", name)
        elif action == "remove":
            if name == DEFAULT_PROFILE:
                return self._fail("The default profile cannot be removed.")
            if not is_profile(name):
                return self._fail("Bad profile name.")
            directory = progress.Store(PROGRESS_DIR, name).directory
            if os.path.isdir(directory):
                dest = os.path.join(TRASH_DIR, "profile-%s-%s" % (name, time.strftime("%Y%m%d-%H%M%S")))
                os.makedirs(TRASH_DIR, exist_ok=True)
                os.replace(directory, dest)
            if PREFS.profile == name:
                PREFS.save({"profile": DEFAULT_PROFILE})
            log.info("profile %s removed (to trash)", name)
        else:
            return self._fail("Unknown action.")
        self._json(dict(catalog.profiles_view(), ok=True))

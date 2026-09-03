"""Studio-wide preferences: `state/studio.json`.

Tiny by design. Today it holds one thing - the model every generation and tutor call should
ask Claude Code for - because that was the setting whose absence broke a run. Anything
course-specific belongs in `course.json`; anything per-browser belongs in the page.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from coursekit.settings import SETTINGS

from . import claude_cli
from .progress import DEFAULT_PROFILE, SAFE_PROFILE

# (alias, label, note) for every model in settings.json - the only list Settings offers.
MODELS = tuple((m.get("alias") or m["id"], m.get("label") or m["id"], m.get("note", ""))
               for m in SETTINGS.models)
_ALLOWED = {m[0] for m in MODELS}


class Prefs:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        try:
            with open(self.path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            pass
        model = data.get("model") if data.get("model") in _ALLOWED else claude_cli.DEFAULT_MODEL
        profile = str(data.get("profile") or DEFAULT_PROFILE).strip().lower()
        if not SAFE_PROFILE.match(profile):
            profile = DEFAULT_PROFILE
        return {"model": model, "profile": profile}

    def save(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        current = self.load()
        if "model" in changes:
            model = str(changes["model"] or "").strip()
            if model not in _ALLOWED:
                raise ValueError("Unknown model '%s'. Choose one of: %s."
                                 % (model, ", ".join(sorted(_ALLOWED))))
            current["model"] = model
        if "profile" in changes:
            profile = str(changes["profile"] or "").strip().lower()
            if not SAFE_PROFILE.match(profile):
                raise ValueError("A profile name is lowercase letters, digits and hyphens, up to 31 characters.")
            current["profile"] = profile
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(current, fh, indent=1)
        os.replace(tmp, self.path)
        return current

    @property
    def model(self) -> str:
        return self.load()["model"]

    @property
    def profile(self) -> str:
        """The reader whose progress Studio shows and the served pages sync to."""
        return self.load()["profile"]

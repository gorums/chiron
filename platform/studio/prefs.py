"""Studio-wide preferences: `state/studio.json`.

Tiny by design. Today it holds one thing - the model every generation and tutor call should
ask Claude Code for - because that was the setting whose absence broke a run. Anything
course-specific belongs in `course.json`; anything per-browser belongs in the page.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from . import claude_cli

MODELS = (
    ("sonnet", "Claude Sonnet 5", "the sensible default: fast, capable, and always accepted headless"),
    ("opus", "Claude Opus 5", "slower and dearer; for a course where the reasoning has to be best"),
    ("haiku", "Claude Haiku 4.5", "cheap and quick; fine for the tutor, thin for writing modules"),
)
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
        return {"model": model}

    def save(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        current = self.load()
        if "model" in changes:
            model = str(changes["model"] or "").strip()
            if model not in _ALLOWED:
                raise ValueError("Unknown model '%s'. Choose one of: %s."
                                 % (model, ", ".join(sorted(_ALLOWED))))
            current["model"] = model
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(current, fh, indent=1)
        os.replace(tmp, self.path)
        return current

    @property
    def model(self) -> str:
        return self.load()["model"]

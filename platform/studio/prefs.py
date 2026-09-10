"""Studio-wide preferences: `state/studio.json`.

Tiny by design. It holds the model every generation and tutor call should ask Claude Code
for - the setting whose absence once broke a run - and the reader profile. The list that
model is chosen from is not here: it is `SETTINGS.models`, the platform's list under
whatever the settings page saved over it (`studio/models.py`), read live so a model added a
minute ago is already allowed. Anything course-specific belongs in `course.json`; anything
per-browser belongs in the page.
"""

from __future__ import annotations

from typing import Any, Dict

from coursekit.settings import SETTINGS

from . import claude_cli
from .files import read_json, write_json
from .ids import DEFAULT_PROFILE, is_profile



def models() -> tuple:
    """Every model in use - the only list Settings offers - as
    `{name, label, note, provider}`, where `name` is what a form sends. Read on every call,
    not once: the list is editable from the settings page (`studio/models.py`)."""
    return tuple({"name": m.get("alias") or m["id"], "label": m.get("label") or m["id"],
                  "note": m.get("note", ""), "provider": m["provider"]}
                 for m in SETTINGS.models)


def allowed() -> set:
    return {m["name"] for m in models()}


class Prefs:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        try:
            loaded = read_json(self.path)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            pass
        model = data.get("model") if data.get("model") in allowed() else claude_cli.default_model()
        profile = str(data.get("profile") or DEFAULT_PROFILE).strip().lower()
        if not is_profile(profile):
            profile = DEFAULT_PROFILE
        return {"model": model, "profile": profile}

    def save(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        current = self.load()
        if "model" in changes:
            model = str(changes["model"] or "").strip()
            if model not in allowed():
                raise ValueError("Unknown model '%s'. Choose one of: %s."
                                 % (model, ", ".join(sorted(allowed()))))
            current["model"] = model
        if "profile" in changes:
            profile = str(changes["profile"] or "").strip().lower()
            if not is_profile(profile):
                raise ValueError("A profile name is lowercase letters, digits and hyphens, up to 31 characters.")
            current["profile"] = profile
        write_json(self.path, current)
        return current

    @property
    def model(self) -> str:
        return self.load()["model"]

    @property
    def profile(self) -> str:
        """The reader whose progress Studio shows and the served pages sync to."""
        return self.load()["profile"]

"""The model list Studio offers, editable from the settings page.

`models.list` in `platform/settings.json` is the platform's list; when Anthropic ships a model
the owner should not have to edit a committed file to use it. So Studio keeps its own list
in the settings layer it owns - `<state>/settings.json`, read by `coursekit.settings` over
the platform defaults - and this module is the only thing that writes it. Every reader
(`SETTINGS.models`, the pickers in Studio and in a served course page, the CLI's alias table)
sees the change as soon as `SETTINGS.reload()` has run, which `replace` and `reset` do.

The list is validated here, not trusted: an id is what `claude --model` will be given, so it
has to look like one; an alias is a second spelling of the same model; nothing may name the
same model twice, and the list may never be empty, because every call has to name a model.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List

from coursekit import settings as ck_settings
from coursekit.settings import SETTINGS

from .files import read_json, write_json

# What `claude --model` accepts: a lowercase id such as claude-sonnet-5 or claude-haiku-4-5-20251001.
MODEL_ID = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,79}$")
# A short spelling the CLI also takes for the same model: sonnet, opus, haiku, fable.
MODEL_ALIAS = re.compile(r"^[a-z0-9][a-z0-9\-]{0,31}$")
LABEL_CHARS = 60
NOTE_CHARS = 200


def normalise(entries: Any) -> List[Dict[str, str]]:
    """The list a request sent, checked and tidied. Raises ValueError with the reason."""
    if not isinstance(entries, list) or not entries:
        raise ValueError("The model list needs at least one model.")
    out: List[Dict[str, str]] = []
    names: Dict[str, str] = {}      # every id and alias seen -> the label it belongs to
    for n, raw in enumerate(entries, 1):
        if not isinstance(raw, dict):
            raise ValueError("Model %d is not an object." % n)
        model_id = str(raw.get("id") or "").strip()
        if not MODEL_ID.match(model_id):
            raise ValueError("Model %d: '%s' is not a model id (lowercase letters, digits, dots "
                             "and hyphens, like claude-sonnet-5)." % (n, model_id))
        alias = str(raw.get("alias") or "").strip()
        if alias and not MODEL_ALIAS.match(alias):
            raise ValueError("Model %d: alias '%s' may only hold lowercase letters, digits and "
                             "hyphens." % (n, alias))
        label = str(raw.get("label") or "").strip()[:LABEL_CHARS] or model_id
        for name in filter(None, (model_id, alias if alias != model_id else "")):
            if name in names:
                raise ValueError("'%s' names two models (%s and %s)." % (name, names[name], label))
            names[name] = label
        entry = {"id": model_id, "label": label,
                 "note": str(raw.get("note") or "").strip()[:NOTE_CHARS]}
        if alias and alias != model_id:
            entry["alias"] = alias
        out.append(entry)
    return out


def platform_list() -> List[Dict[str, str]]:
    """The list as the platform ships it, without Studio's layer."""
    plain = ck_settings.load(SETTINGS.path, overlay=SETTINGS.overlay, studio_file="")
    return [copy.deepcopy(m) for m in plain.models]


def is_custom() -> bool:
    """True when the list in use is the one Studio saved, not the platform's."""
    return SETTINGS.overrides.get("models.list") == ck_settings.STUDIO_SOURCE


def current() -> Dict[str, Any]:
    """What the settings page shows: the list in use, where it came from, the file."""
    return {"list": [copy.deepcopy(m) for m in SETTINGS.models],
            "default": SETTINGS.default_model,
            "custom": is_custom(),
            "file": SETTINGS.studio_file}


def replace(entries: Any) -> Dict[str, Any]:
    """Save a new list as Studio's own and make it the one in use."""
    if not SETTINGS.studio_file:
        raise ValueError("This Studio has no settings file to write to.")
    data = _studio_data()
    data.setdefault("models", {})["list"] = normalise(entries)
    write_json(SETTINGS.studio_file, data)
    SETTINGS.reload()
    return current()


def reset() -> Dict[str, Any]:
    """Forget Studio's list; the platform's applies again."""
    if SETTINGS.studio_file:
        data = _studio_data()
        models = data.get("models")
        if isinstance(models, dict):
            models.pop("list", None)
            if not models:
                data.pop("models")
        write_json(SETTINGS.studio_file, data)
        SETTINGS.reload()
    return current()


def _studio_data() -> Dict[str, Any]:
    """The Studio settings file as a dict; missing or unreadable means empty."""
    try:
        data = read_json(SETTINGS.studio_file)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


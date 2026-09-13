"""The model list Studio offers, editable from the settings page.

`models.list` in `platform/settings.json` is the platform's list; when Anthropic ships a model
the owner should not have to edit a committed file to use it. So Studio keeps its own list
in the settings layer it owns - `<state>/settings.json`, read by `coursekit.settings` over
the platform defaults - and this module is the only thing that writes it. Every reader
(`SETTINGS.models`, the pickers in Studio and in a served course page, the CLI's alias table)
sees the change as soon as `SETTINGS.reload()` has run, which `replace` and `reset` do.

The list is validated here, not trusted. An id is what a provider will be given - a CLI
argument, or the `model` field of a request - so it has to look like one, and the shapes
differ: `claude-opus-5`, `gpt-5.6`, `models/gemini-flash-3`, `llama3.1:70b`. An id need only
be unique within its provider, because two providers may well offer the same model; an alias
is the short name a person types, so it is unique across the whole list. Every model names a
provider that exists, and the list may never be empty, because every call has to name a model.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List

from coursekit import settings as ck_settings
from coursekit.settings import SETTINGS

from .support.files import read_json, write_json

# What a provider will accept as a model: claude-sonnet-5, gpt-5.6, models/gemini-flash-3,
# llama3.1:70b, us.anthropic.claude-opus-5-v1:0. Lowercase, and never any whitespace or
# quoting - a CLI provider passes this straight into an argument vector.
MODEL_ID = re.compile(r"^[a-z0-9][a-z0-9._:/\-]{0,119}$")
# The short name a person types for it: sonnet, opus, haiku, fable.
MODEL_ALIAS = re.compile(r"^[a-z0-9][a-z0-9\-]{0,31}$")
LABEL_CHARS = 60
NOTE_CHARS = 200


def normalise(entries: Any) -> List[Dict[str, str]]:
    """The list a request sent, checked and tidied. Raises ValueError with the reason."""
    if not isinstance(entries, list) or not entries:
        raise ValueError("The model list needs at least one model.")
    known = SETTINGS.provider_names(all_of_them=True)
    fallback = SETTINGS.default_provider
    out: List[Dict[str, str]] = []
    seen: Dict[str, str] = {}       # "<provider>/<id>" and every alias -> the label it belongs to
    for n, raw in enumerate(entries, 1):
        if not isinstance(raw, dict):
            raise ValueError("Model %d is not an object." % n)
        model_id = str(raw.get("id") or "").strip()
        if not MODEL_ID.match(model_id):
            raise ValueError("Model %d: '%s' is not a model id (lowercase letters, digits and "
                             ". _ : / -, like claude-sonnet-5 or gpt-5.6)." % (n, model_id))
        provider = str(raw.get("provider") or "").strip() or fallback
        if provider not in known:
            raise ValueError("Model %d: there is no provider called '%s'. Configured: %s."
                             % (n, provider, ", ".join(known)))
        alias = str(raw.get("alias") or "").strip()
        if alias and not MODEL_ALIAS.match(alias):
            raise ValueError("Model %d: alias '%s' may only hold lowercase letters, digits and "
                             "hyphens." % (n, alias))
        label = str(raw.get("label") or "").strip()[:LABEL_CHARS] or model_id
        # An id is a model of one provider, so two providers may both offer gpt-4o. An alias
        # is a name a person types, so it has to mean one thing across the whole list.
        for name in filter(None, (provider + "/" + model_id,
                                  alias if alias != model_id else "")):
            if name in seen:
                raise ValueError("'%s' names two models (%s and %s)."
                                 % (name.split("/")[-1], seen[name], label))
            seen[name] = label
        entry = {"provider": provider, "id": model_id, "label": label,
                 "note": str(raw.get("note") or "").strip()[:NOTE_CHARS]}
        if alias and alias != model_id:
            entry["alias"] = alias
        if raw.get("price") is not None:
            entry["price"] = _price(n, raw["price"])
        out.append(entry)
    _check_aliases(out)
    return out


def _price(n: int, raw: Any) -> Dict[str, float]:
    """A model's price, {in, out} in USD per million tokens. The page estimates the tutor's
    cost from it, so a row that carries one keeps it through the settings page."""
    try:
        return {"in": float(raw["in"]), "out": float(raw["out"])}
    except (TypeError, KeyError, ValueError):
        raise ValueError("Model %d: price needs numbers for in and out, USD per million "
                         "tokens." % n) from None


def _check_aliases(entries: List[Dict[str, str]]) -> None:
    """An alias that is another model's id is a name meaning two things: `model_aliases`
    maps ids and aliases into one table, so the pair would silently shadow each other."""
    by_id: Dict[str, str] = {}
    for entry in entries:
        by_id.setdefault(entry["id"], entry["label"])
    for entry in entries:
        alias = entry.get("alias")
        if alias and alias in by_id and alias != entry["id"]:
            raise ValueError("'%s' is the alias of %s and the id of %s."
                             % (alias, entry["label"], by_id[alias]))


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


"""Reaching a model, whoever makes it.

This package is the one place a wire format or a command line appears. Everything above it -
the generator, the editor, the reviewer, the tutor route, the bridge - asks for a completion
and gets text back, and knows nothing about who answered.

It lives in `coursekit` rather than in `studio` because `tools/bridge/` imports it from
outside the package, the way it imports `settings`. That is what keeps one implementation
instead of two. For the same reason it is **standard library only**: `urllib.request` for an
HTTP provider, `subprocess` for a CLI one. A vendor SDK here would cost more than it saves
and would end `markdown` being the platform's only dependency.

The pieces, in dependency order:

| | |
|---|---|
| `failures` | why a call failed, in one word - the kinds every layer branches on |
| `base` | what a provider is: `Provider`, `Request`, `Reply`, `Capabilities`, `LLMFailed` |
| `shape` | flattening a conversation into one prompt; digging JSON out of prose |
| `cli` | a model reached through a headless binary |
| `chain` | retries, model fallback, and telling whoever is watching |

`provider_for(name)` is how a caller gets one. Today there is a single provider, the CLI, and
the name is ignored; the registry exists so that the row in settings.json which selects one
has somewhere to arrive.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .base import (  # noqa: F401  (the package's public surface)
    Capabilities,
    LLMFailed,
    Provider,
    ProviderUnavailable,
    Reply,
    Request,
    failed,
)
from .chain import (  # noqa: F401
    DEFAULT_TIMEOUT,
    JSON_ATTEMPTS,
    Reporter,
    ask,
    ask_json,
    complete,
    default_model,
    model_aliases,
    model_chain,
    set_reporter,
    timeout_for,
)
from .cli import CliProvider
from .shape import CHAT_HISTORY, chat_prompt, slice_json, strip_fence  # noqa: F401

# Built once and kept, because a provider holds no per-call state and finding a binary is a
# PATH walk. `reload()` throws them away, for when the settings underneath them change.
_BUILT: Dict[str, Provider] = {}


def build() -> Dict[str, Provider]:
    """Every configured provider, by name. One for now: the CLI everything already used."""
    return {"claude-code": CliProvider()}


def providers() -> List[Provider]:
    """Every configured provider, in the order settings.json lists them."""
    if not _BUILT:
        _BUILT.update(build())
    return list(_BUILT.values())


def provider_for(name: str = "") -> Provider:
    """The provider to use. An unknown or empty name means the default one."""
    found = providers()
    if name:
        for p in found:
            if p.name == name:
                return p
    return found[0]


def reload() -> None:
    """Forget the built providers; the next call builds them from the settings as they are
    now. `SETTINGS.reload()` is what makes this necessary."""
    _BUILT.clear()


def available(name: str = "") -> bool:
    """Can anything answer right now?"""
    if name:
        return provider_for(name).available()
    return any(p.available() for p in providers())


def probe(model: str, timeout: int = 0, name: str = "") -> dict:
    """One short call with this model only and no fallback."""
    return provider_for(name).probe(model, timeout)


def describe() -> List[dict]:
    """What a status screen should say about every provider."""
    return [p.describe() for p in providers()]

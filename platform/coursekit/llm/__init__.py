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

`provider_for(name)` is how a caller gets one, and the names are the rows of the `providers`
block in settings.json. A row whose `kind` has no adapter yet is skipped rather than being an
error, so the block can describe where the platform is going without breaking what it does
today; a configuration that leaves nothing at all still yields the CLI, because a platform
that can reach no model is worse than one that guesses.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..settings import SETTINGS

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

# Which adapter serves which `kind`. A kind that is not here has no adapter yet.
ADAPTERS = {"cli": CliProvider}


def build(name: str, cfg: Dict[str, Any]) -> Optional[Provider]:
    """One row of the `providers` block, or None when nothing can serve its kind."""
    adapter = ADAPTERS.get(str(cfg.get("kind") or ""))
    return adapter.from_settings(name, cfg) if adapter else None


def providers() -> List[Provider]:
    """Every enabled provider there is an adapter for, in the order settings.json lists them.

    Built per call rather than kept: a provider holds no state, and the list underneath it
    changes whenever `SETTINGS.reload()` runs - which is how a model saved on the settings
    page reaches every module without a restart.
    """
    found = [p for name in SETTINGS.provider_names()
             for p in [build(name, SETTINGS.provider(name))] if p is not None]
    return found or [CliProvider()]


def provider_for(name: str = "") -> Provider:
    """The provider to use. An unknown or empty name means the default one."""
    found = providers()
    if name:
        for p in found:
            if p.name == name:
                return p
        wanted = SETTINGS.default_provider
        for p in found:
            if p.name == wanted:
                return p
    return found[0]


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

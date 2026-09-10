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
| `wire` | a model reached over HTTP: everything but the shape of a request and a reply |
| `anthropic` | Anthropic's Messages API |
| `openai` | OpenAI's Chat Completions - and every server that speaks it |
| `gemini` | Google's generateContent |
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
from .anthropic import AnthropicProvider
from .cli import CliProvider
from .gemini import GeminiProvider
from .openai import OpenAIProvider
from .shape import CHAT_HISTORY, chat_prompt, slice_json, strip_fence  # noqa: F401
from .wire import HttpProvider  # noqa: F401

# Which adapter serves which `kind`. A kind that is not here has no adapter yet.
ADAPTERS = {"cli": CliProvider, "anthropic": AnthropicProvider,
            "openai": OpenAIProvider, "gemini": GeminiProvider}


def build(name: str, cfg: Dict[str, Any]) -> Optional[Provider]:
    """One row of the `providers` block, or None when nothing can serve its kind."""
    adapter = ADAPTERS.get(str(cfg.get("kind") or ""))
    return adapter.from_settings(name, cfg) if adapter else None


def providers(all_of_them: bool = False) -> List[Provider]:
    """Every enabled provider there is an adapter for, in the order settings.json lists them.
    `all_of_them` includes the disabled ones, which are configured but offered nowhere.

    Built per call rather than kept: a provider holds no state, and the list underneath it
    changes whenever `SETTINGS.reload()` runs - which is how a model saved on the settings
    page reaches every module without a restart.
    """
    found = [p for name in SETTINGS.provider_names(all_of_them)
             for p in [build(name, SETTINGS.provider(name))] if p is not None]
    return found or [CliProvider()]


def find(name: str) -> Optional[Provider]:
    """One provider by name, enabled or not - `enabled` governs what is *offered*, not what
    may be addressed, so a row can be tested before it is switched on. None when nothing is
    configured under that name."""
    for p in providers(all_of_them=True):
        if p.name == name:
            return p
    return None


def provider_for(name: str = "") -> Provider:
    """The provider to use. An empty name means the default one; a name nothing answers to
    also falls back, because a caller that guessed wrong should still get an answer rather
    than a crash - `find` is there for a caller that needs to know."""
    if name:
        found = find(name)
        if found is not None:
            return found
    enabled = providers()
    wanted = SETTINGS.default_provider
    for p in enabled:
        if p.name == wanted:
            return p
    return enabled[0]


def available(name: str = "") -> bool:
    """Can anything answer right now?"""
    if name:
        return provider_for(name).available()
    return any(p.available() for p in providers())


def probe(model: str, timeout: int = 0, name: str = "") -> dict:
    """One short call with this model only and no fallback.

    A name nothing is configured under is refused rather than quietly tried somewhere else:
    a settings page asking "does this model work on OpenAI" must not be answered by Claude
    Code saying no.
    """
    if name:
        chosen = find(name)
        if chosen is None:
            said = "There is no provider called '%s'." % name
            return {"ok": False, "seconds": 0, "why": "unknown", "error": said, "advice": said}
        return chosen.probe(model, timeout)
    return provider_for().probe(model, timeout)


def describe() -> List[dict]:
    """What a status screen should say about every provider."""
    return [p.describe() for p in providers()]

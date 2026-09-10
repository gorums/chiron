"""What a provider is: the interface, and nothing that implements it.

A provider is one way to reach a model - a local CLI that is already signed in, or an HTTP
endpoint that takes a key. Everything above this file (the retry policy in `chain`, the JSON
insistence, the job events, every caller in Studio) is written once against these five
methods, so adding a way to reach a model is a new file here and a row in settings.json,
never a change to a caller.

`Capabilities` is what the layers above have to branch on, and it is deliberately short. The
one that matters today is `single_prompt`: a CLI takes one prompt and a chat API takes a
system prompt and a list of turns, which is why `Request` carries both shapes and lets the
provider pick.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .failures import UNKNOWN, describe


@dataclass
class Capabilities:
    """What a provider can be asked for. Defaults describe a headless CLI."""

    single_prompt: bool = True      # takes one prompt, not a system prompt and turns
    system_role: bool = False       # a system prompt travels separately from the messages
    max_tokens: bool = False        # the reply length can be capped
    needs_key: bool = False         # unusable until a key is configured


@dataclass
class Request:
    """One thing to ask for.

    `prompt` is what a caller that has already built its own text sends, and it is used
    verbatim when set - a module prompt is a document, not a conversation, and wrapping it in
    "User:" would change what the model is asked. `system` and `messages` are the chat shape;
    a `single_prompt` provider flattens them itself (`shape.chat_prompt`).

    `what` names the thing being asked for ("the text of M03") so a job screen can say what is
    happening while a call runs for minutes.
    """

    prompt: str = ""
    system: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    model: str = ""                 # "" means the provider's own default
    timeout: int = 0
    max_tokens: int = 0
    what: str = ""


@dataclass
class Reply:
    """One answer, and what it cost to get."""

    text: str
    model: str = ""
    provider: str = ""
    seconds: float = 0.0
    notes: str = ""                 # anything the provider said alongside a good answer


class ProviderUnavailable(RuntimeError):
    """This provider cannot be used at all: no binary on the PATH, or no key configured."""


class LLMFailed(RuntimeError):
    """The provider ran but did not produce usable output.

    The message is the sentence a reader should see; `detail` is what the provider actually
    said, which belongs in the log. `kind` is what the layers above branch on, and
    `resets_at` is the clock time a usage limit named, when it named one.
    """

    def __init__(self, message: str, kind: str = UNKNOWN, detail: str = "",
                 resets_at: str = "", provider: str = ""):
        super().__init__(message)
        self.kind = kind
        self.detail = detail
        self.resets_at = resets_at
        self.provider = provider


def failed(detail: str, kind: str = "", provider: str = "") -> LLMFailed:
    """Everything a provider reports becomes one of these, classified once."""
    message, kind, when = describe(detail, kind)
    return LLMFailed(message, kind=kind, detail=detail, resets_at=when, provider=provider)


class Provider:
    """One way to reach models. Subclasses fill in the five methods below."""

    kind = ""                       # "cli", "anthropic", "openai", "gemini"
    name = ""                       # the settings key: "claude-code", "openai", "local"
    label = ""                      # what a human is shown: "Claude Code", "OpenAI"
    caps = Capabilities()

    def available(self) -> bool:
        """Can this provider be used right now - binary found, or key present?"""
        raise NotImplementedError

    def complete(self, req: Request) -> Reply:
        """One call. Raises `LLMFailed` for anything that is not an answer; never returns
        something empty. Retrying, falling back to another model and reporting progress are
        `chain`'s job, not this one's."""
        raise NotImplementedError

    def probe(self, model: str, timeout: int = 0) -> Dict[str, Any]:
        """One short call with this model only and no fallback, for a settings page that has
        to refuse a typo before a forty-minute run does. Returns {ok, seconds, reply | error};
        never raises for a refused model."""
        raise NotImplementedError

    def catalog(self) -> Dict[str, Any]:
        """The models this provider offers, for discovery: {ok, models, error}. A source that
        cannot answer says so rather than reporting an empty list, because "says nothing" and
        "offers nothing" mean opposite things to the merge."""
        return {"ok": False, "models": [], "error": "this provider has no catalogue"}

    def describe(self) -> Dict[str, Any]:
        """What a status screen should say about this provider."""
        return {"name": self.name, "kind": self.kind, "label": self.label,
                "available": self.available()}

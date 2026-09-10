"""Asking until there is an answer: retries, fallback, and saying what is happening.

Everything here is the platform's policy, not any provider's, which is why it is written
once. A provider runs one call and classifies what came back; this file decides what to do
about it, and tells whoever is watching.

Two kinds of second chance, and they are not the same thing:

- **`transient` is waited out**, on the same model, the wait doubling from `backoffSeconds`
  to `backoffMaxSeconds`. A forty-minute run used to die at module 8 of 9 on a five-second
  outage, which costs far more than the waiting does.
- **`model` moves down the chain** - the model that was asked for, then the default, then
  whatever the provider itself defaults to. Without naming a model at all, a CLI inherits
  whatever the person last picked interactively, and the headless path rejects some of those.

**`quota`, `auth` and `timeout` end it at once.** Every model on the chain draws on the same
account, so trying the next one wastes a minute and then tells the reader the wrong story -
"it refused Opus" when the truth is "this account is out until 3pm".

Progress goes to a `Reporter`, which by default goes nowhere. Studio installs one that
forwards to the job running on the calling thread (`set_reporter`), so `coursekit` never has
to know that jobs exist.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from ..settings import SETTINGS
from .base import LLMFailed, Provider, ProviderUnavailable, Reply, Request, failed
from .failures import AUTH, QUOTA, TIMEOUT, TRANSIENT, UNKNOWN
from .shape import slice_json

log = logging.getLogger("studio.llm")

# Long enough for a full module; short enough that a wedged call cannot stall a job forever.
DEFAULT_TIMEOUT = int(SETTINGS.get("llm.timeout"))
JSON_ATTEMPTS = int(SETTINGS.get("llm.jsonAttempts"))

# How many second chances a call gets when the failure looks like weather, and how long to
# wait between them.
RETRIES = int(SETTINGS.get("llm.retries"))
BACKOFF = float(SETTINGS.get("llm.backoffSeconds"))
BACKOFF_MAX = float(SETTINGS.get("llm.backoffMaxSeconds"))

# Failures no other model on the chain would survive: the account, the login, and a call that
# has already spent its whole timeout.
FINAL = (QUOTA, AUTH, TIMEOUT)

# What the event log calls the last attempt, which names no model at all.
_OWN_DEFAULT = "(provider default)"


# --------------------------------------------------------------------------- who is watching


class Reporter:
    """Where a long call's progress goes. The default is nowhere, which is what the build,
    the bridge and the tests want."""

    def event(self, kind: str, **fields: Any) -> None:
        """A structured event: `call` at the start and the end of every attempt."""

    def say(self, message: str) -> None:
        """A sentence for whoever is watching a run."""


REPORTER = Reporter()


def set_reporter(reporter: Reporter) -> None:
    """Install the thing that hears about calls. Studio forwards to the job on this thread."""
    global REPORTER
    REPORTER = reporter or Reporter()


# --------------------------------------------------------------------------- which models


def timeout_for(step: str) -> int:
    """Seconds allowed for one kind of call: `generation.timeouts.<step>` in settings.json,
    else the general timeout."""
    return int(SETTINGS.get("generation.timeouts." + step, DEFAULT_TIMEOUT))


def model_aliases() -> Dict[str, str]:
    """Every accepted spelling of a model -> the canonical short name. Unknown values are
    dropped rather than passed through. Read per call, not once at import: the list is
    `models.list` in settings.json under whatever Studio's settings page saved over it."""
    return SETTINGS.model_aliases


def default_model() -> str:
    """The model to fall back to: `models.default` in settings.json, overridden by
    STUDIO_MODEL and, per call, by whatever Studio's own preference says."""
    return SETTINGS.default_model


def model_chain(model: str = "", provider_name: str = "") -> List[str]:
    """The models to try, in order: what was asked for, then the default.

    Two rules, and they pull in opposite directions until you say which list is being
    consulted:

    - **The list decides, where it has anything to say.** A model that was taken off it, or
      a name nobody recognises, is not worth a call: `models.list` is what the settings page
      and discovery maintain, and honouring a dead id would undo both. But a provider with
      no models listed yet - a local server, a provider configured before its models were
      added - has nothing to say, and then what was asked for is what is asked for.
    - **A chain never crosses providers.** Falling back from a model one provider refused to
      a model on another account answers a question the caller did not ask, and bills
      someone who did not agree to it. So the default is a fallback only where it is that
      provider's default too.
    """
    listed = SETTINGS.models_for(provider_name) if provider_name else SETTINGS.models
    known = {m["id"] for m in listed} | {m["alias"] for m in listed if m.get("alias")}
    aliases = model_aliases()
    chain: List[str] = []

    asked = (model or "").strip()
    if asked:
        short = aliases.get(asked)
        if short and short in known:
            chain.append(short)
        elif not known:
            chain.append(short or asked)

    fallback = aliases.get(default_model())
    ours = not provider_name or SETTINGS.provider_of(default_model()) == provider_name
    if fallback and ours and fallback not in chain:
        chain.append(fallback)
    return chain


# --------------------------------------------------------------------------- asking


def complete(provider: Provider, req: Request) -> Reply:
    """Ask one provider for one thing, trying every model on the chain and waiting out
    weather. Raises rather than returning something empty."""
    if not provider.available():
        raise ProviderUnavailable(
            "%s is not available. Install it, or sign in, and try again." % provider.label)

    attempts = model_chain(req.model, provider.name) + [""]   # last: its own default model
    last = failed("no output", provider=provider.name)
    for n, model in enumerate(attempts):
        try:
            return _with_retries(provider, req, model)
        except LLMFailed as exc:
            last = exc
            if exc.kind in FINAL:
                REPORTER.say(str(exc))
                break
            if n + 1 < len(attempts):
                nxt = attempts[n + 1]
                REPORTER.say("%s refused %s; trying %s instead." % (
                    provider.label, model or _OWN_DEFAULT, nxt or "its own default model"))

    log.error("%s: giving up (%s): %s", provider.name, last.kind, last.detail or "no output")
    raise last


def _with_retries(provider: Provider, req: Request, model: str) -> Reply:
    """One model, tried again while the failure looks like weather."""
    for attempt in range(RETRIES + 1):
        last_chance = attempt >= RETRIES
        try:
            return _one_call(provider, req, model)
        except LLMFailed as exc:
            if last_chance or exc.kind != TRANSIENT:
                raise
            wait = min(BACKOFF * (2 ** attempt), BACKOFF_MAX)
            log.warning("%s %s: transient failure, trying again in %ds: %s",
                        provider.name, model or _OWN_DEFAULT, round(wait), exc.detail[:160])
            REPORTER.say(
                "%s could not be reached; waiting %ds and trying again, attempt %d of %d."
                % (provider.label, round(wait), attempt + 2, RETRIES + 1))
            time.sleep(wait)
    raise failed("retries is below zero", UNKNOWN)   # a nonsense setting, not a path


def _one_call(provider: Provider, req: Request, model: str) -> Reply:
    """One attempt, bracketed by its two `call` events. Every way out that is not a reply is
    an `LLMFailed` carrying its kind, so no caller has to read stderr a second time."""
    label = model or _OWN_DEFAULT
    size = _size(req)
    started = time.time()
    REPORTER.event("call", phase="start", what=req.what, model=label, chars=size,
                   timeout=req.timeout)
    try:
        reply = provider.complete(_for_model(req, model))
    except LLMFailed as exc:
        took = time.time() - started
        report = log.error if exc.kind == TIMEOUT else log.warning
        report("%s %s: failed in %.1fs, %s, prompt %d chars: %s",
               provider.name, label, took, exc.kind, size, exc.detail or "no output")
        REPORTER.event("call", phase="end", what=req.what, model=label, ok=False,
                       why=exc.kind, seconds=round(took, 1), error=exc.detail)
        raise

    took = reply.seconds or round(time.time() - started, 1)
    log.info("%s %s: ok in %.1fs, prompt %d chars, reply %d chars%s",
             provider.name, label, took, size, len(reply.text),
             (" (notes: %s)" % reply.notes) if reply.notes else "")
    REPORTER.event("call", phase="end", what=req.what, model=label, ok=True,
                   seconds=round(took, 1), reply=len(reply.text))
    return reply


def _for_model(req: Request, model: str) -> Request:
    """The same request, aimed at one model."""
    return Request(prompt=req.prompt, system=req.system, messages=req.messages, model=model,
                   timeout=req.timeout, max_tokens=req.max_tokens, what=req.what)


def _size(req: Request) -> int:
    """How much text one request carries, for the log line and the job event."""
    if req.prompt:
        return len(req.prompt)
    return len(req.system) + sum(len(str((m or {}).get("content", ""))) for m in req.messages)


# --------------------------------------------------------------------------- the two callers use


def ask(prompt: str, *, provider: Optional[Provider] = None, model: str = "",
        timeout: int = 0, what: str = "") -> str:
    """Send one prompt, return the reply text.

    A caller names a model, not a provider: `models.list` already says which provider reaches
    which model, and asking every call site to know as well would be a second place to keep
    right.
    """
    from . import provider_for                       # late: the registry imports this module

    chosen = provider or provider_for(SETTINGS.provider_of(model))
    reply = complete(chosen, Request(prompt=prompt, model=model,
                                     timeout=timeout or DEFAULT_TIMEOUT, what=what))
    return reply.text


def ask_json(prompt: str, *, provider: Optional[Provider] = None, model: str = "",
             timeout: int = 0, attempts: int = JSON_ATTEMPTS, what: str = "",
             asker=None) -> Any:
    """Ask for JSON and insist on getting it.

    A retry re-sends the original prompt with the parse error appended, which recovers a
    truncated or commented-on reply far more often than simply asking again does.

    `asker` is how a caller keeps one seam instead of two: Studio passes its own `ask`, so
    stubbing that one name in a test stubs this as well.
    """
    send = asker or (lambda p, **kw: ask(p, provider=provider, **kw))
    current, last_error = prompt, ""
    for attempt in range(attempts):
        reply = send(current, model=model, timeout=timeout, what=what)
        try:
            return json.loads(slice_json(reply))
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = str(exc)
            if attempt + 1 < attempts:
                REPORTER.say(
                    "The reply%s was not valid JSON (%s); asking again, attempt %d of %d."
                    % ((" for " + what) if what else "", last_error[:120], attempt + 2, attempts))
            current = (
                prompt
                + "\n\nYour previous reply could not be parsed as JSON (%s). "
                "Return only the JSON value, with no prose, no explanation and no code fence."
                % last_error
            )
    raise LLMFailed("Could not get valid JSON after %d attempts: %s" % (attempts, last_error))

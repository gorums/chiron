"""Studio's way in to `coursekit.llm`.

The implementation moved: every wire format and every command line now lives in
`coursekit/llm/`, where `tools/bridge/` can reach it too rather than keeping a second copy.
What stays here is the part that is Studio's and could not move - **the job on the calling
thread hears about every call.** `coursekit` must not import `studio`, so the provider layer
narrates to a `Reporter` and this module installs one that forwards to `jobs.current()`.

The names below are the ones the rest of Studio calls, kept as they were so that a hundred
call sites - and the tests that stub `claude_cli.ask` - did not all have to move at once.
`ask_json` sends through this module's own `ask` for the same reason: stubbing one stubs both.
"""

from __future__ import annotations

import subprocess  # noqa: F401  (tests replace subprocess.run through this name)
from typing import Any, Dict, List, Optional

from coursekit import llm
from coursekit.llm import chain as llm_chain
from coursekit.llm import cli as llm_cli
from coursekit.llm.base import LLMFailed, Provider, ProviderUnavailable

from . import jobs

# The names Studio has always used for these two. `ClaudeFailed` is caught by name in the
# server, the job runner and the tests.
ClaudeFailed = LLMFailed
ClaudeUnavailable = ProviderUnavailable

DEFAULT_TIMEOUT = llm_chain.DEFAULT_TIMEOUT
JSON_ATTEMPTS = llm_chain.JSON_ATTEMPTS
CHAT_HISTORY = llm.CHAT_HISTORY
PROBE_TIMEOUT = llm_cli.PROBE_TIMEOUT
PROBE_PROMPT = llm_cli.PROBE_PROMPT


class _JobReporter(llm_chain.Reporter):
    """Every call, told to the job running on this thread. The tutor route has no job, and
    then this is a no-op - which is why the provider layer asks rather than looking."""

    def event(self, kind: str, **fields: Any) -> None:
        job = jobs.current()
        if job is not None:
            job.emit(kind, **fields)

    def say(self, message: str) -> None:
        job = jobs.current()
        if job is not None:
            job.log(message)


llm_chain.set_reporter(_JobReporter())


# ---- which model, and how long it may take

def model_aliases() -> Dict[str, str]:
    """Every accepted spelling of a model -> the short alias to ask for."""
    return llm_chain.model_aliases()


def default_model() -> str:
    """The model every call falls back to when the request names none."""
    return llm_chain.default_model()


def model_chain(model: str = "") -> List[str]:
    return llm_chain.model_chain(model)


def timeout_for(step: str) -> int:
    """Seconds allowed for one kind of call: `generation.timeouts.<step>`."""
    return llm_chain.timeout_for(step)


# ---- is there anything to call

def find_cli() -> Optional[str]:
    """Where the model runner is on this machine, or None. Only a `cli` provider has one."""
    chosen = _provider()
    return chosen.find() if isinstance(chosen, llm_cli.CliProvider) else None


def available() -> bool:
    """Can the default provider answer? Studio asks this to decide whether it may write, so
    it is about the one that would run, not about any provider being configured."""
    return llm.provider_for().available()


def _provider(name: str = "") -> Provider:
    return llm.provider_for(name)


# ---- asking

def ask(prompt: str, *, model: str = "", timeout: int = DEFAULT_TIMEOUT, what: str = "") -> str:
    """Send one prompt, return the reply text. Raises rather than returning something empty."""
    return llm.ask(prompt, model=model, timeout=timeout, what=what)


def ask_json(prompt: str, *, model: str = "", timeout: int = DEFAULT_TIMEOUT,
             attempts: int = JSON_ATTEMPTS, what: str = "") -> Any:
    """Ask for JSON and insist on getting it."""
    return llm.ask_json(prompt, model=model, timeout=timeout, attempts=attempts, what=what,
                        asker=lambda p, **kw: ask(p, **kw))


def probe(model: str, timeout: int = PROBE_TIMEOUT) -> Dict[str, Any]:
    """Does the runner accept this model? One short call, this model only, no fallback."""
    return llm.probe(model, timeout)


# ---- shaping text on the way in and out

def chat_prompt(system: str, messages) -> str:
    """Flatten a system prompt and a chat transcript into one prompt."""
    return llm.chat_prompt(system, messages)


def strip_fence(text: str) -> str:
    return llm.strip_fence(text)


def slice_json(text: str) -> str:
    return llm.slice_json(text)

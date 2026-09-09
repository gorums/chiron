"""Talking to Claude through the Claude Code CLI.

Why the CLI and not the API: the person running Studio is already signed in to Claude Code,
so there is no key to store and no separate per-token bill. The cost is latency — each call
spawns a process — which is why the generator runs modules one at a time and streams
progress rather than pretending to be instant.

Why stdin and not `-p <prompt>`: a Windows command line caps at 8191 characters, and
`tools/bridge/claude-bridge.py` has to trim prompts to ~5500 to stay clear of it. Course writing
needs prompts an order of magnitude larger than that — the module contract plus the whole
curriculum for context. Passing the prompt on stdin removes the ceiling entirely.

Why failures are classified: the CLI reports an exhausted account, an overloaded server and
a model it does not recognise the same way — a non-zero exit and a line of stderr — and the
right answer to each is different. `coursekit.failures` names the kind, and `ask` acts on
it: wait out weather, swap a model that was refused, and stop at once when the account
itself is the problem, because every model on the chain draws on the same one. The classifier
sits in `coursekit` because the bridge needs it too.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, Optional

from coursekit.failures import AUTH, QUOTA, TIMEOUT, TRANSIENT, UNKNOWN, describe
from coursekit.settings import SETTINGS

from . import jobs
from .log import log

# Long enough for a full module; short enough that a wedged call cannot stall a job forever.
DEFAULT_TIMEOUT = int(SETTINGS.get("claude.timeout"))
JSON_ATTEMPTS = int(SETTINGS.get("claude.jsonAttempts"))
CHAT_HISTORY = int(SETTINGS.get("claude.chatHistory"))

# How many second chances a call gets when the failure looks like weather, and how long to
# wait between them. A run that dies at module 8 of 9 on a five-second outage costs far more
# than the waiting does.
RETRIES = int(SETTINGS.get("claude.retries"))
BACKOFF = float(SETTINGS.get("claude.backoffSeconds"))
BACKOFF_MAX = float(SETTINGS.get("claude.backoffMaxSeconds"))

# One probe call has to answer well inside a job's timeout, or the settings page hangs.
PROBE_TIMEOUT = int(SETTINGS.get("claude.probeTimeout"))
PROBE_PROMPT = "Reply with the single word OK and nothing else."


def model_aliases() -> Dict[str, str]:
    """Every accepted spelling of a model -> the short alias the CLI takes. Unknown values
    are dropped rather than passed through. Read per call, not once at import: the list is
    `models.list` in settings.json under whatever Studio's settings page saved over it."""
    return SETTINGS.model_aliases


def default_model() -> str:
    """Every call names its model. Without `--model` the CLI inherits whatever the person
    last picked interactively - which can be a model the headless SDK path does not accept
    (a `[1m]` context variant, say), and then a run dies mid-module with
    "unrecognized_model". `models.default` in settings.json; STUDIO_MODEL in .env or the
    environment overrides it, and Studio's own preference (state/studio.json) overrides that
    per call."""
    return SETTINGS.default_model


def timeout_for(step: str) -> int:
    """Seconds allowed for one kind of call: `generation.timeouts.<step>` in settings.json,
    else the general `claude.timeout`."""
    return int(SETTINGS.get("generation.timeouts." + step, DEFAULT_TIMEOUT))

_FENCE = re.compile(r"^\s*```(?:json|markdown|md)?\s*\n(.*?)\n\s*```\s*$", re.S)


# Claude Code asks whether to trust the directory it starts in, which would hang a headless
# call — and is worse in a container, where the workspace is a bind mount it has never seen.
# Studio hands the model everything it needs in the prompt and asks it to read nothing, so
# the calls run from an empty scratch directory rather than the repo.
_SCRATCH = SETTINGS.scratch_dir


class ClaudeUnavailable(RuntimeError):
    """The `claude` command is not installed, or not on this PATH."""


class ClaudeFailed(RuntimeError):
    """The CLI ran but did not produce usable output.

    The message is the sentence a reader should see; `detail` is what the CLI actually said,
    which belongs in the log. `kind` is what the layers above branch on, and `resets_at` is
    the clock time a usage limit named, when it named one.
    """

    def __init__(self, message: str, kind: str = UNKNOWN, detail: str = "",
                 resets_at: str = ""):
        super().__init__(message)
        self.kind = kind
        self.detail = detail
        self.resets_at = resets_at


# Failures no other model on the chain would survive: the account, the login, and a call that
# has already spent its whole timeout.
_FINAL = (QUOTA, AUTH, TIMEOUT)


def _failure(detail: str, kind: str = "") -> ClaudeFailed:
    """Everything the CLI reports becomes one of these, classified once."""
    message, kind, when = describe(detail, kind)
    return ClaudeFailed(message, kind=kind, detail=detail, resets_at=when)


def _tell(kind: str, **fields) -> None:
    """Report to the job on this thread, if there is one. The tutor route has none."""
    job = jobs.current()
    if job is not None:
        job.emit(kind, **fields)


def _say(message: str) -> None:
    job = jobs.current()
    if job is not None:
        job.log(message)


def find_cli() -> Optional[str]:
    for name in ("claude", "claude.cmd", "claude.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def available() -> bool:
    return find_cli() is not None


def _argv(cli: str, args) -> list:
    """A .cmd/.bat shim cannot be executed directly on Windows — route it through cmd."""
    if os.name == "nt" and cli.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", cli] + list(args)
    return [cli] + list(args)


def ask(prompt: str, *, model: str = "", timeout: int = DEFAULT_TIMEOUT, what: str = "") -> str:
    """Send one prompt, return the reply text. Raises rather than returning something empty.

    `what` names the thing being asked for ("the text of M03") so the job's event log, and
    the screen watching it, can say what Claude is doing while a call runs for minutes.
    Every attempt emits a `call` event at its start and its end.

    Two kinds of second chance, and they are not the same thing: a transient failure is tried
    again on the same model after a growing wait, and a model that was refused moves to the
    next one in the chain. An exhausted account, a signed-out CLI or a spent timeout ends it
    immediately - the next model would fail the same way, a minute later.
    """
    cli = find_cli()
    if not cli:
        raise ClaudeUnavailable(
            "Claude Code is not on this PATH. Install it, or sign in, and try again."
        )

    os.makedirs(_SCRATCH, exist_ok=True)
    attempts = [_HEADLESS + ["--model", alias] for alias in model_chain(model)]
    attempts.append(list(_HEADLESS))            # last resort: whatever the CLI defaults to

    last = _failure("no output")
    for n, args in enumerate(attempts):
        label = args[args.index("--model") + 1] if "--model" in args else "(cli default)"
        try:
            return _ask_model(cli, args, label, prompt, timeout, what)
        except ClaudeFailed as exc:
            last = exc
            if exc.kind in _FINAL:
                _say(str(exc))
                break
            if n + 1 < len(attempts):
                nxt = attempts[n + 1]
                _say("Claude Code refused %s; trying %s instead." % (
                    label,
                    nxt[nxt.index("--model") + 1] if "--model" in nxt
                    else "the CLI default model"))

    log.error("claude: giving up (%s): %s", last.kind, last.detail or "no output")
    raise last


def _ask_model(cli: str, args: list, label: str, prompt: str, timeout: int, what: str) -> str:
    """One model, tried again while the failure looks like weather. The wait doubles from
    `claude.backoffSeconds` up to `claude.backoffMaxSeconds`, because a run that dies at
    module 8 of 9 on a five-second outage costs far more than the waiting does."""
    for attempt in range(RETRIES + 1):
        last_chance = attempt >= RETRIES
        try:
            return _one_call(cli, args, label, prompt, timeout, what)
        except ClaudeFailed as exc:
            if last_chance or exc.kind != TRANSIENT:
                raise
            wait = min(BACKOFF * (2 ** attempt), BACKOFF_MAX)
            log.warning("claude %s: transient failure, trying again in %ds: %s",
                        label, round(wait), exc.detail[:160])
            _say("Claude could not be reached; waiting %ds and trying again, attempt %d of %d."
                 % (round(wait), attempt + 2, RETRIES + 1))
            time.sleep(wait)
    raise _failure("claude.retries is below zero", UNKNOWN)   # a nonsense setting, not a path


def _one_call(cli: str, args: list, label: str, prompt: str, timeout: int, what: str) -> str:
    """One CLI call, bracketed by its two `call` events. Every way out that is not a reply is
    a ClaudeFailed carrying its kind, so no caller has to read stderr a second time."""
    started = time.time()
    _tell("call", phase="start", what=what, model=label, chars=len(prompt), timeout=timeout)
    try:
        proc = _run(cli, args, prompt, timeout)
    except subprocess.TimeoutExpired as exc:
        detail = "no answer within %ds" % timeout
        log.error("claude %s: %s (prompt %d chars)", label, detail, len(prompt))
        _tell("call", phase="end", what=what, model=label, ok=False, why=TIMEOUT,
              seconds=round(time.time() - started, 1), error=detail)
        raise _failure("Claude Code did not answer within %ds." % timeout, TIMEOUT) from exc
    except Exception as exc:  # noqa: BLE001 - the CLI could not start; the reason is the failure
        detail = str(exc)[:300]
        log.error("claude %s: could not start: %s", label, detail)
        failure = _failure(detail)
        _tell("call", phase="end", what=what, model=label, ok=False, why=failure.kind,
              seconds=round(time.time() - started, 1), error=detail)
        raise failure from exc

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    took = time.time() - started
    if proc.returncode == 0 and out:
        log.info("claude %s: ok in %.1fs, prompt %d chars, reply %d chars%s",
                 label, took, len(prompt), len(out),
                 (" (stderr: %s)" % err[:160]) if err else "")
        _tell("call", phase="end", what=what, model=label, ok=True,
              seconds=round(took, 1), reply=len(out))
        return out

    detail = err[:300] or out[:300] or "exit code %s with no output" % proc.returncode
    failure = _failure(detail)
    log.warning("claude %s: failed in %.1fs, exit %s, %s, prompt %d chars: %s",
                label, took, proc.returncode, failure.kind, len(prompt), err[:600] or "no output")
    _tell("call", phase="end", what=what, model=label, ok=False, why=failure.kind,
          seconds=round(took, 1), error=detail)
    raise failure


def model_chain(model: str = "") -> list:
    """The aliases to try, in order: what was asked for, then Studio's default."""
    chain = []
    aliases = model_aliases()
    for candidate in ((model or "").strip(), default_model()):
        alias = aliases.get(candidate)
        if alias and alias not in chain:
            chain.append(alias)
    return chain


def _refused(detail: str, kind: str, started: float) -> Dict[str, Any]:
    """One failed probe as the settings page wants it: the CLI's own words in `error`, the
    kind in `why`, and the sentence to show in `advice`."""
    message, kind, _when = describe(detail, kind)
    return {"ok": False, "seconds": round(time.time() - started, 1),
            "why": kind, "error": detail, "advice": message}


def probe(model: str, timeout: int = PROBE_TIMEOUT) -> Dict[str, Any]:
    """Does the CLI accept this model? One short call, this model only, no fallback - the
    settings page asks before a model just added is trusted with a forty-minute run.
    Returns {ok, seconds, reply | error}; never raises for a refused model. A failure also
    carries `why` - the kind - so the page can say "the account is out of quota" instead of
    blaming a model that was never tried."""
    cli = find_cli()
    if not cli:
        return {"ok": False, "seconds": 0, "why": UNKNOWN,
                "error": "Claude Code is not on this PATH.",
                "advice": "Claude Code is not on this PATH."}
    os.makedirs(_SCRATCH, exist_ok=True)
    started = time.time()
    try:
        proc = _run(cli, _HEADLESS + ["--model", model], PROBE_PROMPT, timeout)
    except subprocess.TimeoutExpired:
        return _refused("no answer within %ds" % timeout, TIMEOUT, started)
    except Exception as exc:  # noqa: BLE001 - the CLI could not start; the reason is the result
        return _refused(str(exc)[:300], "", started)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    took = round(time.time() - started, 1)
    if proc.returncode == 0 and out:
        log.info("claude probe %s: ok in %.1fs", model, took)
        return {"ok": True, "seconds": took, "reply": out[:80]}
    reason = err[:300] or out[:300] or "exit code %s with no output" % proc.returncode
    log.warning("claude probe %s: refused in %.1fs: %s", model, took, reason)
    return _refused(reason, "", started)


# The headless invocation every call is built on: one prompt on stdin, plain text back.
_HEADLESS = ["-p", "--output-format", "text"]


def _run(cli: str, args: list, prompt: str, timeout: int) -> subprocess.CompletedProcess:
    """One CLI call from the scratch directory, the prompt on stdin."""
    return subprocess.run(
        _argv(cli, args),
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        cwd=_SCRATCH,
    )


def chat_prompt(system: str, messages) -> str:
    """Flatten a system prompt and a chat transcript into one prompt for the CLI.

    The CLI's headless mode takes a single prompt, so the tutor's conversation is rendered as
    a transcript ending in an open "Assistant:" turn. Prompts travel on stdin, so there is no
    size ceiling to trim to - the page already bounds what it sends.
    """
    parts = []
    if system:
        parts.append(str(system))
    for m in list(messages or [])[-CHAT_HISTORY:]:
        who = "User" if (m or {}).get("role") == "user" else "Assistant"
        parts.append("%s: %s" % (who, (m or {}).get("content", "")))
    parts.append("Assistant:")
    return "\n\n".join(parts)


def strip_fence(text: str) -> str:
    """Models wrap structured output in code fences roughly half the time."""
    m = _FENCE.match(text.strip())
    return m.group(1) if m else text.strip()


def _slice_json(text: str) -> str:
    """Pull the outermost JSON value out of a reply that came with commentary around it."""
    text = strip_fence(text)
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        return text
    start = min(starts)
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth, in_string, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def ask_json(prompt: str, *, model: str = "", timeout: int = DEFAULT_TIMEOUT,
             attempts: int = JSON_ATTEMPTS, what: str = "") -> Any:
    """Ask for JSON and insist on getting it.

    A retry re-sends the original prompt with the parse error appended, which recovers a
    truncated or commented-on reply far more often than simply asking again.
    """
    current, last_error = prompt, ""
    for attempt in range(attempts):
        reply = ask(current, model=model, timeout=timeout, what=what)
        try:
            return json.loads(_slice_json(reply))
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = str(exc)
            if attempt + 1 < attempts:
                _say("The reply%s was not valid JSON (%s); asking again, attempt %d of %d."
                     % ((" for " + what) if what else "", last_error[:120], attempt + 2, attempts))
            current = (
                prompt
                + "\n\nYour previous reply could not be parsed as JSON (%s). "
                "Return only the JSON value, with no prose, no explanation and no code fence."
                % last_error
            )
    raise ClaudeFailed("Could not get valid JSON after %d attempts: %s" % (attempts, last_error))

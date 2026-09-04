"""Talking to Claude through the Claude Code CLI.

Why the CLI and not the API: the person running Studio is already signed in to Claude Code,
so there is no key to store and no separate per-token bill. The cost is latency — each call
spawns a process — which is why the generator runs modules one at a time and streams
progress rather than pretending to be instant.

Why stdin and not `-p <prompt>`: a Windows command line caps at 8191 characters, and
`tools/bridge/claude-bridge.py` has to trim prompts to ~5500 to stay clear of it. Course writing
needs prompts an order of magnitude larger than that — the module contract plus the whole
curriculum for context. Passing the prompt on stdin removes the ceiling entirely.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from typing import Any, Optional

from coursekit.settings import SETTINGS

from . import jobs
from .log import log

# Long enough for a full module; short enough that a wedged call cannot stall a job forever.
DEFAULT_TIMEOUT = int(SETTINGS.get("claude.timeout"))
JSON_ATTEMPTS = int(SETTINGS.get("claude.jsonAttempts"))
CHAT_HISTORY = int(SETTINGS.get("claude.chatHistory"))

# Every accepted spelling of a model -> the short alias the CLI takes. Unknown values are
# dropped rather than passed through. The list is `models.list` in settings.json.
MODEL_ALIASES = SETTINGS.model_aliases

# Every call names its model. Without `--model` the CLI inherits whatever the person last
# picked interactively - which can be a model the headless SDK path does not accept (a
# `[1m]` context variant, say), and then a run dies mid-module with "unrecognized_model".
# `models.default` in settings.json; STUDIO_MODEL in .env or the environment overrides it,
# and Studio's own preference (state/studio.json) overrides that per call.
DEFAULT_MODEL = SETTINGS.default_model


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
    """The CLI ran but did not produce usable output."""


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
    """
    cli = find_cli()
    if not cli:
        raise ClaudeUnavailable(
            "Claude Code is not on this PATH. Install it, or sign in, and try again."
        )

    os.makedirs(_SCRATCH, exist_ok=True)
    base = ["-p", "--output-format", "text"]
    attempts = []
    for alias in model_chain(model):
        attempts.append(base + ["--model", alias])
    attempts.append(base)                       # last resort: whatever the CLI defaults to

    last = ""
    for n, args in enumerate(attempts):
        label = args[args.index("--model") + 1] if "--model" in args else "(cli default)"
        started = time.time()
        _tell("call", phase="start", what=what, model=label, chars=len(prompt), timeout=timeout)
        try:
            proc = subprocess.run(
                _argv(cli, args),
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                cwd=_SCRATCH,
            )
        except subprocess.TimeoutExpired:
            log.error("claude %s: no answer within %ds (prompt %d chars)", label, timeout, len(prompt))
            _tell("call", phase="end", what=what, model=label, ok=False,
                  seconds=round(time.time() - started, 1), error="no answer within %ds" % timeout)
            raise ClaudeFailed("Claude Code did not answer within %ds." % timeout)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user as a job failure
            last = str(exc)[:300]
            log.error("claude %s: could not start: %s", label, last)
            _tell("call", phase="end", what=what, model=label, ok=False,
                  seconds=round(time.time() - started, 1), error=last)
            continue

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
        last = err[:300] or "exit code %s with no output" % proc.returncode
        log.warning("claude %s: failed in %.1fs, exit %s, prompt %d chars: %s",
                    label, took, proc.returncode, len(prompt), err[:600] or "no output")
        _tell("call", phase="end", what=what, model=label, ok=False,
              seconds=round(took, 1), error=last)
        if n + 1 < len(attempts):
            nxt = attempts[n + 1]
            _say("Claude Code refused %s; trying %s instead." % (
                label, nxt[nxt.index("--model") + 1] if "--model" in nxt else "the CLI default model"))

    log.error("claude: every attempt failed: %s", last or "no output")
    raise ClaudeFailed("Claude Code failed: " + (last or "no output"))


def model_chain(model: str = "") -> list:
    """The aliases to try, in order: what was asked for, then Studio's default."""
    chain = []
    for candidate in ((model or "").strip(), DEFAULT_MODEL):
        alias = MODEL_ALIASES.get(candidate)
        if alias and alias not in chain:
            chain.append(alias)
    return chain


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

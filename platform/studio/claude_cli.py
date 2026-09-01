"""Talking to Claude through the Claude Code CLI.

Why the CLI and not the API: the person running Studio is already signed in to Claude Code,
so there is no key to store and no separate per-token bill. The cost is latency — each call
spawns a process — which is why the generator runs modules one at a time and streams
progress rather than pretending to be instant.

Why stdin and not `-p <prompt>`: a Windows command line caps at 8191 characters, and
`bridge/claude-bridge.py` has to trim prompts to ~5500 to stay clear of it. Course writing
needs prompts an order of magnitude larger than that — the module contract plus the whole
curriculum for context. Passing the prompt on stdin removes the ceiling entirely.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Optional

# Long enough for a full module; short enough that a wedged call cannot stall a job forever.
DEFAULT_TIMEOUT = 600

# Short aliases the CLI accepts. Unknown values are dropped rather than passed through.
MODEL_ALIASES = {
    "opus": "opus",
    "sonnet": "sonnet",
    "haiku": "haiku",
    "claude-opus-5": "opus",
    "claude-sonnet-5": "sonnet",
    "claude-haiku-4-5-20251001": "haiku",
}

_FENCE = re.compile(r"^\s*```(?:json|markdown|md)?\s*\n(.*?)\n\s*```\s*$", re.S)


# Claude Code asks whether to trust the directory it starts in, which would hang a headless
# call — and is worse in a container, where the workspace is a bind mount it has never seen.
# Studio hands the model everything it needs in the prompt and asks it to read nothing, so
# the calls run from an empty scratch directory rather than the repo.
_SCRATCH = os.path.join(tempfile.gettempdir(), "coursekit-claude")


class ClaudeUnavailable(RuntimeError):
    """The `claude` command is not installed, or not on this PATH."""


class ClaudeFailed(RuntimeError):
    """The CLI ran but did not produce usable output."""


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


def ask(prompt: str, *, model: str = "", timeout: int = DEFAULT_TIMEOUT) -> str:
    """Send one prompt, return the reply text. Raises rather than returning something empty."""
    cli = find_cli()
    if not cli:
        raise ClaudeUnavailable(
            "Claude Code is not on this PATH. Install it, or sign in, and try again."
        )

    os.makedirs(_SCRATCH, exist_ok=True)
    base = ["-p", "--output-format", "text"]
    attempts = []
    alias = MODEL_ALIASES.get((model or "").strip())
    if alias:
        attempts.append(base + ["--model", alias])
    attempts.append(base)

    last = ""
    for args in attempts:
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
            raise ClaudeFailed("Claude Code did not answer within %ds." % timeout)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user as a job failure
            last = str(exc)[:300]
            continue

        out = (proc.stdout or "").strip()
        if proc.returncode == 0 and out:
            return out
        last = (proc.stderr or "").strip()[:300] or "exit code %s with no output" % proc.returncode

    raise ClaudeFailed("Claude Code failed: " + (last or "no output"))


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
             attempts: int = 3) -> Any:
    """Ask for JSON and insist on getting it.

    A retry re-sends the original prompt with the parse error appended, which recovers a
    truncated or commented-on reply far more often than simply asking again.
    """
    current, last_error = prompt, ""
    for attempt in range(attempts):
        reply = ask(current, model=model, timeout=timeout)
        try:
            return json.loads(_slice_json(reply))
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = str(exc)
            current = (
                prompt
                + "\n\nYour previous reply could not be parsed as JSON (%s). "
                "Return only the JSON value, with no prose, no explanation and no code fence."
                % last_error
            )
    raise ClaudeFailed("Could not get valid JSON after %d attempts: %s" % (attempts, last_error))

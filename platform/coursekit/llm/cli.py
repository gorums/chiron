"""A model reached through a headless command-line tool.

Why a CLI at all: the person running Studio is already signed in to one, so there is no key
to store and no separate per-token bill. The cost is latency - each call spawns a process -
which is why the generator runs modules one at a time and streams progress rather than
pretending to be instant.

Why the prompt goes in on stdin and never as an argument: a Windows command line caps at
8191 characters, and a module prompt is an order of magnitude larger than that. stdin removes
the ceiling entirely.

Why the call runs from an empty scratch directory: a CLI prompts to trust the directory it
starts in, which would hang a headless call - worse in a container, where the workspace is a
bind mount it has never seen. Everything the model needs is in the prompt, so it needs no
filesystem context.

This file executes and classifies. It does not retry, fall back or narrate: that is `chain`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from ..settings import SETTINGS
from . import claude_code, shape
from .base import Capabilities, LLMFailed, Provider, Reply, Request, failed
from .failures import TIMEOUT, UNKNOWN, describe

# One probe call has to answer well inside a job's timeout, or the settings page hangs.
PROBE_TIMEOUT = int(SETTINGS.get("llm.probeTimeout"))
PROBE_PROMPT = "Reply with the single word OK and nothing else."

# The headless invocation every call is built on: one prompt on stdin, plain text back.
HEADLESS = ("-p", "--output-format", "text")

# The names the binary might go by on this machine, in order.
COMMANDS = ("claude", "claude.cmd", "claude.exe")


def find_cli(commands=COMMANDS) -> Optional[str]:
    for name in commands:
        found = shutil.which(name)
        if found:
            return found
    return None


def argv(cli: str, args) -> List[str]:
    """A .cmd/.bat shim cannot be executed directly on Windows - route it through cmd."""
    if os.name == "nt" and cli.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", cli] + list(args)
    return [cli] + list(args)


class CliProvider(Provider):
    """Any headless binary that takes a prompt on stdin and prints the reply."""

    kind = "cli"
    caps = Capabilities(single_prompt=True, system_role=False, max_tokens=False, needs_key=False)

    def __init__(self, name: str = "claude-code", label: str = "Claude Code",
                 commands=COMMANDS, args=HEADLESS, model_flag: str = "--model",
                 prompt_on: str = "stdin", hint: str = "", scratch: str = ""):
        self.name = name
        self.label = label
        self.commands = tuple(commands)
        self.args = list(args)
        self.model_flag = model_flag
        self.prompt_on = prompt_on      # "stdin", or "arg" for a tool that wants it there
        self.hint = hint                # what to do when it is there but will not answer
        self.scratch = scratch or SETTINGS.scratch_dir

    @classmethod
    def from_settings(cls, name: str, cfg: Dict[str, Any]) -> "CliProvider":
        """One row of the `providers` block. Everything about the command line is a setting,
        so a second headless tool is a row rather than a file."""
        return cls(name=name,
                   label=str(cfg.get("label") or name),
                   commands=tuple(cfg.get("command") or COMMANDS),
                   args=list(cfg.get("args") or HEADLESS),
                   model_flag=str(cfg.get("modelFlag") or "--model"),
                   prompt_on=str(cfg.get("promptOn") or "stdin"),
                   hint=str(cfg.get("signinHint") or ""))

    # ---- what it is

    def find(self) -> Optional[str]:
        return find_cli(self.commands)

    def available(self) -> bool:
        return self.find() is not None

    def describe(self) -> Dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "label": self.label,
                "available": self.available(), "path": self.find() or "", "hint": self.hint}

    def catalog(self, timeout: int = 0) -> Dict[str, Any]:
        """What this binary knows about, read out of the binary - there is no endpoint to
        ask. Only Claude Code is understood (`claude_code.py`), and anything else reads as
        "could not be read", which is exactly right: nothing here knows what it accepts."""
        return claude_code.read(claude_code.binary(self.find() or ""))

    # ---- one call

    def complete(self, req: Request) -> Reply:
        cli = self.find()
        if not cli:
            raise LLMFailed("%s is not on this PATH." % self.label, UNKNOWN, provider=self.name)
        prompt = req.prompt or shape.chat_prompt(req.system, req.messages)
        started = time.time()
        try:
            proc = self._run(cli, self._args_for(req.model), prompt, req.timeout)
        except subprocess.TimeoutExpired as exc:
            raise LLMFailed("%s did not answer within %ds." % (self.label, req.timeout),
                            TIMEOUT, detail="no answer within %ds" % req.timeout,
                            provider=self.name) from exc
        except Exception as exc:  # noqa: BLE001 - the CLI could not start; the reason is the failure
            raise failed(str(exc)[:300], provider=self.name) from exc

        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        if proc.returncode == 0 and out:
            return Reply(text=out, model=req.model, provider=self.name,
                         seconds=round(time.time() - started, 1), notes=err[:160])
        detail = err[:300] or out[:300] or "exit code %s with no output" % proc.returncode
        raise failed(detail, provider=self.name)

    def probe(self, model: str, timeout: int = 0) -> Dict[str, Any]:
        cli = self.find()
        if not cli:
            gone = "%s is not on this PATH." % self.label
            return {"ok": False, "seconds": 0, "why": UNKNOWN, "error": gone, "advice": gone}
        started = time.time()
        try:
            proc = self._run(cli, self._args_for(model), PROBE_PROMPT, timeout or PROBE_TIMEOUT)
        except subprocess.TimeoutExpired:
            return self._refused("no answer within %ds" % (timeout or PROBE_TIMEOUT),
                                 TIMEOUT, started)
        except Exception as exc:  # noqa: BLE001 - the CLI could not start; the reason is the result
            return self._refused(str(exc)[:300], "", started)
        out = (proc.stdout or "").strip()
        took = round(time.time() - started, 1)
        if proc.returncode == 0 and out:
            return {"ok": True, "seconds": took, "reply": out[:80]}
        err = (proc.stderr or "").strip()
        return self._refused(err[:300] or out[:300] or
                             "exit code %s with no output" % proc.returncode, "", started)

    # ---- the mechanics

    def _args_for(self, model: str) -> List[str]:
        """The argument vector for one call. No model named means the binary's own default,
        which is the last resort at the end of the chain."""
        return self.args + ([self.model_flag, model] if model else [])

    def _run(self, cli: str, args: List[str], prompt: str, timeout: int
             ) -> subprocess.CompletedProcess:
        """One call from the scratch directory. The argument vector is a list and there is no
        shell, so neither a model id nor a prompt can ever be read as a command.

        `promptOn: "arg"` is for a tool that will not read stdin. It is not the default and
        should not be: a Windows command line caps at 8191 characters, which a module prompt
        passes an order of magnitude ago."""
        os.makedirs(self.scratch, exist_ok=True)
        on_stdin = self.prompt_on != "arg"
        return subprocess.run(
            argv(cli, args if on_stdin else args + [prompt]),
            input=prompt if on_stdin else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            cwd=self.scratch,
        )

    def _refused(self, detail: str, kind: str, started: float) -> Dict[str, Any]:
        """One failed probe as a settings page wants it: the CLI's own words in `error`, the
        kind in `why`, and the sentence to show in `advice`."""
        message, kind, _when = describe(detail, kind)
        return {"ok": False, "seconds": round(time.time() - started, 1),
                "why": kind, "error": detail, "advice": message}

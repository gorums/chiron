"""Turning text into what a provider takes, and a reply back into what a caller wanted.

Two jobs, both provider-shaped rather than vendor-shaped:

- **Flattening.** A headless CLI takes one prompt, so a conversation has to be rendered as a
  transcript ending in an open "Assistant:" turn. A chat API does not need this; that is why
  it lives here and not in a caller.
- **Digging structure out of prose.** Models wrap JSON in a code fence roughly half the time
  and put a sentence in front of it about as often, so a reply is fenced-stripped and then
  scanned for its outermost JSON value before it is parsed.

Nothing here calls anything. It is pure text, which is what lets `cli` and `chain` both use
it without importing each other.
"""

from __future__ import annotations

import re

from ..settings import SETTINGS

# How many turns of a conversation travel with a question. The page bounds what it sends;
# this is the backstop.
CHAT_HISTORY = int(SETTINGS.get("claude.chatHistory"))

_FENCE = re.compile(r"^\s*```(?:json|markdown|md)?\s*\n(.*?)\n\s*```\s*$", re.S)


def chat_prompt(system: str, messages, history: int = 0) -> str:
    """Flatten a system prompt and a chat transcript into one prompt.

    Prompts travel on stdin, so there is no size ceiling to trim to - the caller already
    bounds what it sends.
    """
    parts = []
    if system:
        parts.append(str(system))
    for m in list(messages or [])[-(history or CHAT_HISTORY):]:
        who = "User" if (m or {}).get("role") == "user" else "Assistant"
        parts.append("%s: %s" % (who, (m or {}).get("content", "")))
    parts.append("Assistant:")
    return "\n\n".join(parts)


def strip_fence(text: str) -> str:
    """Models wrap structured output in code fences roughly half the time."""
    m = _FENCE.match(text.strip())
    return m.group(1) if m else text.strip()


def slice_json(text: str) -> str:
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

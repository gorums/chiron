"""Why a call to Claude failed, in one word.

Claude Code reports an exhausted account, an overloaded server and a model it does not
recognise in exactly the same way — a non-zero exit and a line of stderr — and the right
answer to each is different: wait out weather, swap a model that was refused, and stop at
once when the account itself is the problem. Naming the kind once is what lets every caller
decide without reading stderr again, and what lets a job screen and a chat bubble say
something the reader can act on instead of quoting a stack of CLI output at them.

It lives in the build package because that is the one place both sides can reach:
`studio/claude_cli.py` imports it as part of the package, and `tools/bridge/claude-bridge.py`
imports it from outside, the way it imports `settings`. Like `settings`, and for the same
reason, it is standard library only.
"""

from __future__ import annotations

import re

# The kinds of failure, which is to say the kinds of answer. Trying the next model on an
# exhausted account wastes a minute and then tells the reader the wrong story ("Claude Code
# refused Opus" when the truth is "this account is out until 3pm"), which is the whole
# reason these are told apart.
QUOTA = "quota"
AUTH = "auth"
MODEL = "model"
TRANSIENT = "transient"
TIMEOUT = "timeout"
UNKNOWN = "unknown"

# Matched in order, first fit wins, so the distinctive wordings come before the loose ones.
_SIGNS = (
    (QUOTA, re.compile(
        r"usage limit|rate.?limit|too many requests|\b429\b|quota|"
        r"out of credit|credit balance|insufficient", re.I)),
    (AUTH, re.compile(
        r"not logged in|please (?:log|sign) in|invalid api key|unauthorized|"
        r"authentication|permission_error|\b401\b|\b403\b", re.I)),
    (MODEL, re.compile(
        r"unrecognized_model|unknown model|invalid model|model not found|"
        r"not_found_error|not a valid model|model catalog|\b404\b", re.I)),
    (TRANSIENT, re.compile(
        r"overloaded|\b5(?:00|02|03|29)\b|internal server error|bad gateway|"
        r"service unavailable|fetch failed|socket hang up|connection (?:reset|refused|closed)|"
        r"network|ECONNRESET|ETIMEDOUT|ENOTFOUND|EAI_AGAIN", re.I)),
)

# "Your limit will reset at 3pm (America/New_York)" — worth repeating back, because it turns
# "it failed" into "come back at three". The parenthetical timezone is left out: it is the
# machine's own zone, which is the one the reader is already in.
_RESETS_AT = re.compile(r"resets?(?:\s+\w+){0,2}\s+at\s+([^.\n(]{1,40})", re.I)


def classify(text: str) -> str:
    """Which kind of failure this stderr describes. `unknown` when nothing fits, and unknown
    is treated as permanent everywhere: retrying something we cannot name is how a run burns
    an hour to arrive at the same error."""
    for kind, sign in _SIGNS:
        if sign.search(text or ""):
            return kind
    return UNKNOWN


def resets_at(text: str) -> str:
    """The clock time a usage-limit message named, or "" when it named none."""
    found = _RESETS_AT.search(text or "")
    return found.group(1).strip(" ,;") if found else ""


def explain(kind: str, detail: str = "", when: str = "") -> str:
    """One sentence someone can act on. The CLI's own words go to the log; this is what a job
    screen and a chat bubble show, so it says what happened and what to do about it."""
    if kind == QUOTA:
        return ("This Claude account has reached its usage limit%s. Nothing written so far "
                "is lost." % ((", which resets at " + when) if when else ""))
    if kind == AUTH:
        return ("Claude Code is not signed in. Run `claude` once in a terminal, sign in, and "
                "try again.")
    if kind == TRANSIENT:
        return "Claude could not be reached just now. It is usually back within a minute."
    if kind == MODEL:
        return "Claude Code would not accept that model."
    if kind == TIMEOUT:
        return detail or "Claude Code did not answer in time."
    return "Claude Code failed: " + (detail or "no output")


# An HTTP status from Anthropic says the same things, in numbers. Anything else is unknown
# rather than transient: a status nobody planned for is not something to retry blindly.
_BY_STATUS = {401: AUTH, 403: AUTH, 404: MODEL, 429: QUOTA,
              500: TRANSIENT, 502: TRANSIENT, 503: TRANSIENT, 504: TRANSIENT, 529: TRANSIENT}


def from_status(code: int) -> str:
    """Which kind an Anthropic HTTP status describes."""
    return _BY_STATUS.get(int(code or 0), UNKNOWN)


def describe(detail: str, kind: str = "") -> tuple:
    """(sentence, kind, when) for one line of stderr — the whole classification in one call,
    which is what both callers actually want."""
    kind = kind or classify(detail)
    when = resets_at(detail) if kind == QUOTA else ""
    return explain(kind, detail, when), kind, when

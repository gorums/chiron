"""A provider reached over HTTP: everything except the shape of a request and a reply.

Three wire formats meet here — Anthropic's Messages, OpenAI's Chat Completions and Google's
generateContent — and they differ in about forty lines each: where the system prompt goes,
what the reply field is called, which header carries the key. Everything else is the same
work, so it is written once and each adapter fills in four hooks:

    url_for(req)     where this request goes (Google puts the model in the path)
    headers()        how the key travels
    body_for(req)    the request as that API wants it
    text_of(answer)  the reply, dug out of whatever it came wrapped in

Errors are the fifth thing, and the only subtle one. The HTTP status is always there and
already says which of the six kinds this is (`failures.from_status`), so it decides; the
body says it again in words, which is what the log and the reader want to see, and which
catches the case where a provider returns 400 for something that is really a missing model.

Standard library only, like everything in this package: `urllib.request`, because the bridge
imports it from outside the package and installs nothing.
"""

from __future__ import annotations

import copy
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

from .base import Capabilities, LLMFailed, Provider, Reply, Request, failed
from .failures import AUTH, TIMEOUT, UNKNOWN, describe, from_status

PROBE_PROMPT = "Reply with the single word OK and nothing else."
PROBE_TOKENS = 4
PROBE_TIMEOUT = 30

# A catalogue request is a listing, not a completion; it should answer in seconds or not
# at all.
CATALOG_TIMEOUT = 30


class HttpProvider(Provider):
    """A model reached over HTTP with a key. Subclasses fill in the four hooks above."""

    kind = ""
    caps = Capabilities(single_prompt=False, system_role=True, max_tokens=True, needs_key=True)

    def __init__(self, name: str = "", label: str = "", api_url: str = "",
                 models_url: str = "", key: str = "", hint: str = "",
                 max_tokens_field: str = "max_tokens"):
        self.name = name or self.kind
        self.label = label or self.name
        self.api_url = api_url
        self.models_url = models_url
        self.key = (key or "").strip()
        self.hint = hint
        self.max_tokens_field = max_tokens_field

    @classmethod
    def from_settings(cls, name: str, cfg: Dict[str, Any]) -> "HttpProvider":
        return cls(name=name,
                   label=str(cfg.get("label") or name),
                   api_url=str(cfg.get("apiUrl") or ""),
                   models_url=str(cfg.get("modelsUrl") or ""),
                   key=str(cfg.get("apiKey") or ""),
                   hint=str(cfg.get("signinHint") or ""),
                   max_tokens_field=str(cfg.get("maxTokensField") or "max_tokens"))

    def with_key(self, key: str) -> "HttpProvider":
        """The same provider, using a key the caller found for itself - the bridge, which
        hunts for one, or a page that supplies the reader's. A key never travels on a
        `Request`, so it cannot end up in a job event or a log line."""
        mine = copy.copy(self)
        mine.key = (key or "").strip()
        return mine

    # ---- what it is

    def available(self) -> bool:
        return bool(self.key and self.api_url)

    def describe(self) -> Dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "label": self.label,
                "available": self.available(), "hasKey": bool(self.key),
                "url": self.api_url, "hint": self.hint}

    # ---- one call

    def complete(self, req: Request) -> Reply:
        if not self.key:
            raise LLMFailed("%s needs an API key." % self.label, AUTH, provider=self.name)
        started = time.time()
        answer = self.post(self.url_for(req), self.body_for(req), req.timeout)
        text = self.text_of(answer)
        if not text:
            raise failed("the reply carried no text", provider=self.name)
        return Reply(text=text, model=req.model, provider=self.name,
                     seconds=round(time.time() - started, 1), notes=self.notes_of(answer))

    def probe(self, model: str, timeout: int = 0) -> Dict[str, Any]:
        started = time.time()
        if not self.key:
            gone = "%s has no API key configured." % self.label
            return {"ok": False, "seconds": 0, "why": AUTH, "error": gone, "advice": gone}
        try:
            reply = self.complete(Request(prompt=PROBE_PROMPT, model=model,
                                          timeout=timeout or PROBE_TIMEOUT,
                                          max_tokens=PROBE_TOKENS))
        except LLMFailed as exc:
            said = exc.detail or str(exc)
            message, kind, _when = describe(said, exc.kind)
            return {"ok": False, "seconds": round(time.time() - started, 1), "why": kind,
                    "error": said, "advice": message}
        return {"ok": True, "seconds": reply.seconds, "reply": reply.text[:80]}

    # ---- the four hooks

    def url_for(self, req: Request) -> str:
        """Where one completion goes. Most APIs have one endpoint; Google puts the model and
        the verb in the path."""
        return self.api_url

    def headers(self) -> Dict[str, str]:
        raise NotImplementedError

    def body_for(self, req: Request) -> Dict[str, Any]:
        raise NotImplementedError

    def text_of(self, answer: Dict[str, Any]) -> str:
        raise NotImplementedError

    def notes_of(self, answer: Dict[str, Any]) -> str:
        """Anything worth a line in the log beside a good answer - a hit token cap, say."""
        return ""

    # ---- shared shaping

    @staticmethod
    def turns(req: Request) -> List[Dict[str, str]]:
        """The conversation as plain {role, content} pairs. A caller that built its own text
        is not holding a conversation: `prompt` becomes the one turn, verbatim."""
        if req.prompt:
            return [{"role": "user", "content": req.prompt}]
        return [{"role": str(m.get("role") or "user"), "content": str(m.get("content") or "")}
                for m in (req.messages or [])]

    # ---- the wire

    def post(self, url: str, body: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        request = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers=self.headers(), method="POST")
        return self.send(request, timeout)

    def get(self, url: str, timeout: int = 0) -> Dict[str, Any]:
        request = urllib.request.Request(url, headers=self.headers())
        return self.send(request, timeout or CATALOG_TIMEOUT)

    def send(self, request: urllib.request.Request, timeout: int) -> Dict[str, Any]:
        """Every way out that is not a parsed body is an `LLMFailed` carrying its kind, so no
        caller has to read an HTTP status a second time."""
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail, kind = self.error_of(exc)
            raise failed(detail, kind, provider=self.name) from exc
        except TimeoutError as exc:
            raise LLMFailed("%s did not answer within %ds." % (self.label, timeout),
                            TIMEOUT, detail="no answer within %ds" % timeout,
                            provider=self.name) from exc
        except Exception as exc:  # noqa: BLE001 - the request never landed; the reason is the failure
            raise failed(str(exc)[:300], provider=self.name) from exc

    # What an error body calls the fields that say what went wrong. Every one of these three
    # APIs nests them under "error"; they disagree only on the names.
    ERROR_FIELDS = ("type", "status", "code", "message")

    def error_of(self, exc: urllib.error.HTTPError) -> tuple:
        """(what went wrong, which kind). The status decides the kind because it is always
        there; the words are kept because they are what a reader can act on, and because a
        provider that answers 400 for a missing model is only findable in them."""
        kind = from_status(exc.code)
        try:
            raw = json.loads(exc.read().decode("utf-8"))
            error = raw.get("error") if isinstance(raw.get("error"), dict) else raw
            said = " ".join(str(error.get(f) or "") for f in self.ERROR_FIELDS).strip()
        except Exception:  # noqa: BLE001 - an error with no body is still an error
            said = ""
        detail = ("HTTP %s %s" % (exc.code, said)).strip()
        return detail, (kind if kind != UNKNOWN else "")

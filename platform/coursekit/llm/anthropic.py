"""A model reached through Anthropic's Messages API.

The second provider, and the one that proves the interface: it takes a key rather than a
signed-in binary, it wants the system prompt separately from the turns, and it reports
trouble as an HTTP status with a JSON body instead of an exit code and a line of stderr.
None of that reaches a caller - `chain` retries and falls back exactly as it does for the
CLI, because the difference is all in here.

Why `urllib` and not the SDK: this package is imported by `tools/bridge/` from outside the
package and must stay standard library only. The wire format is four fields and a version
header; an SDK would cost more than it saves.

The key is on the provider, not on the request, so a caller that has its own - the bridge,
which hunts for one in half a dozen places, or a page that supplies the reader's - builds an
instance with `with_key` rather than threading a secret through every layer.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from ..settings import SETTINGS
from .base import Capabilities, LLMFailed, Provider, Reply, Request, failed
from .failures import TIMEOUT, UNKNOWN, describe, from_status

# The reply length asked for when a caller names none. The page's tutor budget is the only
# number the platform has for "one answer".
DEFAULT_MAX_TOKENS = int(SETTINGS.get("page.tutor.maxTokens"))
PROBE_PROMPT = "Reply with the single word OK and nothing else."
PROBE_TOKENS = 4

# `GET /v1/models` is paged; twenty pages of a hundred is far more than exists, and is there
# so a server that keeps saying "more" cannot spin forever.
CATALOG_PAGE = int(SETTINGS.get("discovery.apiPage"))
CATALOG_PAGES = 20


class AnthropicProvider(Provider):
    """The Messages API. Needs a key; everything else has a default."""

    kind = "anthropic"
    caps = Capabilities(single_prompt=False, system_role=True, max_tokens=True, needs_key=True)

    def __init__(self, name: str = "anthropic", label: str = "Anthropic API",
                 api_url: str = "", models_url: str = "", api_version: str = "",
                 key: str = "", hint: str = ""):
        self.name = name
        self.label = label
        self.api_url = api_url
        self.models_url = models_url
        self.api_version = api_version
        self.key = (key or "").strip()
        self.hint = hint

    @classmethod
    def from_settings(cls, name: str, cfg: Dict[str, Any]) -> "AnthropicProvider":
        return cls(name=name,
                   label=str(cfg.get("label") or name),
                   api_url=str(cfg.get("apiUrl") or ""),
                   models_url=str(cfg.get("modelsUrl") or ""),
                   api_version=str(cfg.get("apiVersion") or ""),
                   key=str(cfg.get("apiKey") or ""),
                   hint=str(cfg.get("signinHint") or ""))

    def with_key(self, key: str) -> "AnthropicProvider":
        """The same provider, using a key the caller found for itself."""
        return AnthropicProvider(self.name, self.label, self.api_url, self.models_url,
                                 self.api_version, key, self.hint)

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
            raise LLMFailed("%s needs an API key." % self.label, "auth", provider=self.name)
        started = time.time()
        body = self._body(req)
        answer = self._post(self.api_url, body, req.timeout)
        text = "".join(part.get("text", "") for part in (answer.get("content") or [])
                       if part.get("type") == "text").strip()
        if not text:
            raise failed("the reply carried no text", provider=self.name)
        # "end_turn" is the model finishing; anything else - a hit token cap, a stop
        # sequence - is worth a line in the log beside an answer that may be cut short.
        stopped = str(answer.get("stop_reason") or "")
        return Reply(text=text, model=req.model, provider=self.name,
                     seconds=round(time.time() - started, 1),
                     notes="" if stopped in ("", "end_turn") else "stopped: " + stopped)

    def probe(self, model: str, timeout: int = 0) -> Dict[str, Any]:
        started = time.time()
        if not self.key:
            gone = "%s has no API key configured." % self.label
            return {"ok": False, "seconds": 0, "why": "auth", "error": gone, "advice": gone}
        req = Request(prompt=PROBE_PROMPT, model=model, timeout=timeout or 30,
                      max_tokens=PROBE_TOKENS)
        try:
            reply = self.complete(req)
        except LLMFailed as exc:
            message, kind, _when = describe(exc.detail or str(exc), exc.kind)
            return {"ok": False, "seconds": round(time.time() - started, 1), "why": kind,
                    "error": exc.detail or str(exc), "advice": message}
        return {"ok": True, "seconds": reply.seconds, "reply": reply.text[:80]}

    # ---- what it offers

    def catalog(self, timeout: int = 0) -> Dict[str, Any]:
        """`GET /v1/models`, every page. Each model carries a creation date, which is what
        lets discovery add only what is newer than the newest one already listed."""
        if not self.key or not self.models_url:
            return {"ok": False, "models": [], "error": "no API key configured"}
        found: List[Dict[str, str]] = []
        after = ""
        try:
            for _ in range(CATALOG_PAGES):
                page = self.models_url + "?limit=%d" % CATALOG_PAGE + (
                    "&after_id=" + after if after else "")
                body = self._get(page, timeout)
                for m in body.get("data") or []:
                    if m.get("id"):
                        found.append({"id": str(m["id"]),
                                      "label": str(m.get("display_name") or m["id"]),
                                      "created": str(m.get("created_at") or "")})
                if not body.get("has_more") or not body.get("last_id"):
                    break
                after = str(body["last_id"])
        except Exception as exc:  # noqa: BLE001 - a source that cannot answer says so
            return {"ok": False, "models": [], "error": str(exc)[:200]}
        return {"ok": True, "models": found, "error": ""}

    # ---- the wire

    def _body(self, req: Request) -> Dict[str, Any]:
        """The request as the Messages API wants it: the system prompt separate from the
        turns, and a reply length that is required rather than optional."""
        messages = [{"role": str(m.get("role") or "user"),
                     "content": str(m.get("content") or "")} for m in (req.messages or [])]
        if req.prompt:
            messages = [{"role": "user", "content": req.prompt}]
        body: Dict[str, Any] = {
            "model": req.model,
            "max_tokens": int(req.max_tokens or DEFAULT_MAX_TOKENS),
            "messages": messages,
        }
        if req.system:
            body["system"] = str(req.system)
        return body

    def _headers(self) -> Dict[str, str]:
        return {"content-type": "application/json", "x-api-key": self.key,
                "anthropic-version": self.api_version}

    def _post(self, url: str, body: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        request = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers=self._headers(), method="POST")
        return self._send(request, timeout)

    def _get(self, url: str, timeout: int = 0) -> Dict[str, Any]:
        return self._send(urllib.request.Request(url, headers=self._headers()), timeout or 30)

    def _send(self, request: urllib.request.Request, timeout: int) -> Dict[str, Any]:
        """Every way out that is not a parsed body is an `LLMFailed` carrying its kind, so no
        caller has to read an HTTP status a second time."""
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail, kind = _error_of(exc)
            raise failed(detail, kind, provider=self.name) from exc
        except TimeoutError as exc:
            raise LLMFailed("%s did not answer within %ds." % (self.label, timeout),
                            TIMEOUT, detail="no answer within %ds" % timeout,
                            provider=self.name) from exc
        except Exception as exc:  # noqa: BLE001 - the request never landed; the reason is the failure
            raise failed(str(exc)[:300], provider=self.name) from exc


def _error_of(exc: urllib.error.HTTPError) -> tuple:
    """(what went wrong, which kind) from an Anthropic error body. The status decides the
    kind, because it is always there; the body says it again in words, which is what the log
    and the reader want to see."""
    said, kind = "", from_status(exc.code)
    try:
        raw = json.loads(exc.read().decode("utf-8"))
        error = raw.get("error") or {}
        said = " ".join(str(error.get(f) or "") for f in ("type", "message")).strip()
    except Exception:  # noqa: BLE001 - an error with no body is still an error
        said = ""
    detail = ("HTTP %s %s" % (exc.code, said)).strip()
    return detail, (kind if kind != UNKNOWN else "")

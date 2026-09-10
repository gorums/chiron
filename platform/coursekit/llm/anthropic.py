"""A model reached through Anthropic's Messages API.

What is particular to this wire format, and all that is: the key travels as `x-api-key`
beside a dated `anthropic-version`; the system prompt is a top-level field rather than a
turn; `max_tokens` is required rather than optional; the reply is a list of content blocks,
of which the text ones are joined. Everything else - the socket, the retries, the failure
kinds, the probe - is `wire.HttpProvider` and `chain`.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..settings import SETTINGS
from .base import Request
from .wire import CATALOG_TIMEOUT, HttpProvider

# The reply length asked for when a caller names none. The page's tutor budget is the only
# number the platform has for "one answer", and this API will not take "as much as it needs".
DEFAULT_MAX_TOKENS = int(SETTINGS.get("page.tutor.maxTokens"))

# `GET /v1/models` is paged; twenty pages of a hundred is far more than exists, and is there
# so a server that keeps saying "more" cannot spin forever.
CATALOG_PAGE = int(SETTINGS.get("discovery.apiPage"))
CATALOG_PAGES = 20


class AnthropicProvider(HttpProvider):
    """The Messages API. Needs a key; everything else has a default."""

    kind = "anthropic"

    def __init__(self, name: str = "anthropic", label: str = "Anthropic API",
                 api_url: str = "", models_url: str = "", api_version: str = "",
                 key: str = "", hint: str = "", max_tokens_field: str = "max_tokens"):
        HttpProvider.__init__(self, name, label, api_url, models_url, key, hint,
                              max_tokens_field)
        self.api_version = api_version

    @classmethod
    def from_settings(cls, name: str, cfg: Dict[str, Any]) -> "AnthropicProvider":
        return cls(name=name,
                   label=str(cfg.get("label") or name),
                   api_url=str(cfg.get("apiUrl") or ""),
                   models_url=str(cfg.get("modelsUrl") or ""),
                   api_version=str(cfg.get("apiVersion") or ""),
                   key=str(cfg.get("apiKey") or ""),
                   hint=str(cfg.get("signinHint") or ""))

    # ---- the four hooks

    def headers(self) -> Dict[str, str]:
        return {"content-type": "application/json", "x-api-key": self.key,
                "anthropic-version": self.api_version}

    def body_for(self, req: Request) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": req.model,
            "max_tokens": int(req.max_tokens or DEFAULT_MAX_TOKENS),
            "messages": self.turns(req),
        }
        if req.system:
            body["system"] = str(req.system)
        return body

    def text_of(self, answer: Dict[str, Any]) -> str:
        return "".join(part.get("text", "") for part in (answer.get("content") or [])
                       if part.get("type") == "text").strip()

    def notes_of(self, answer: Dict[str, Any]) -> str:
        # "end_turn" is the model finishing; anything else - a hit token cap, a stop
        # sequence - is worth a line beside an answer that may be cut short.
        stopped = str(answer.get("stop_reason") or "")
        return "" if stopped in ("", "end_turn") else "stopped: " + stopped

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
                body = self.get(page, timeout or CATALOG_TIMEOUT)
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

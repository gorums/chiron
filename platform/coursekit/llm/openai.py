"""A model reached through an OpenAI-shaped Chat Completions endpoint.

This is the one adapter that is worth more than the API it is named after. Chat Completions
is the lingua franca: Ollama, LM Studio, vLLM, OpenRouter, Groq, DeepSeek, Mistral, xAI and
Azure all speak it. So the base URL is a setting rather than a constant, and one file serves
every local server and every aggregator - `local` in `settings.json` is this adapter pointed
at a machine of your own.

What is particular to the format: the key is a bearer token; the system prompt is a turn
with the role `system` rather than a field beside the turns; the reply is
`choices[0].message.content`. And the token cap has two names - `max_tokens` on everything
older, `max_completion_tokens` on the newer reasoning models, which reject the old one - so
which to send is `maxTokensField` on the provider, not a guess made here.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import Request
from .wire import CATALOG_TIMEOUT, HttpProvider


class OpenAIProvider(HttpProvider):
    """Chat Completions, wherever it is being served from."""

    kind = "openai"

    # ---- the four hooks

    def headers(self) -> Dict[str, str]:
        return {"content-type": "application/json", "authorization": "Bearer " + self.key}

    def body_for(self, req: Request) -> Dict[str, Any]:
        messages = self.turns(req)
        if req.system:
            messages = [{"role": "system", "content": str(req.system)}] + messages
        body: Dict[str, Any] = {"model": req.model, "messages": messages}
        if req.max_tokens:
            body[self.max_tokens_field] = int(req.max_tokens)
        return body

    def text_of(self, answer: Dict[str, Any]) -> str:
        choices = answer.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        return str(message.get("content") or "").strip()

    def notes_of(self, answer: Dict[str, Any]) -> str:
        choices = answer.get("choices") or []
        why = str((choices[0].get("finish_reason") or "") if choices else "")
        return "" if why in ("", "stop") else "stopped: " + why

    # ---- what it offers

    def catalog(self, timeout: int = 0) -> Dict[str, Any]:
        """`GET /v1/models`. One page, no dates - which is all this format promises, and all
        the merge needs from a source that only has to say what exists."""
        if not self.key or not self.models_url:
            return {"ok": False, "models": [], "error": "no API key configured"}
        try:
            body = self.get(self.models_url, timeout or CATALOG_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 - a source that cannot answer says so
            return {"ok": False, "models": [], "error": str(exc)[:200]}
        found: List[Dict[str, str]] = []
        for m in body.get("data") or []:
            if isinstance(m, dict) and m.get("id"):
                found.append({"id": str(m["id"]), "label": str(m.get("id")), "created": ""})
        return {"ok": True, "models": found, "error": ""}

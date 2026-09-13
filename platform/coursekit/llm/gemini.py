"""A model reached through Google's generateContent.

The odd one of the three, in four ways, and they are the whole file: the model goes in the
path rather than the body, so `apiUrl` here is a base and not an endpoint; a turn is
`{role, parts: [{text}]}` rather than `{role, content}`; the assistant is called `model`;
and the system prompt is `systemInstruction`, shaped like a turn but without a role. The key
travels as `x-goog-api-key`, which keeps it out of the URL and therefore out of any log that
records one.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import Request
from .wire import CATALOG_TIMEOUT, HttpProvider


class GeminiProvider(HttpProvider):
    """generateContent. `apiUrl` is the API base, e.g. .../v1beta."""

    kind = "gemini"

    # ---- the four hooks

    def url_for(self, req: Request) -> str:
        """`<base>/models/<model>:generateContent`. A model id may already be written as the
        resource path Google prints (`models/gemini-flash-3`); do not repeat the prefix."""
        model = str(req.model or "")
        if not model.startswith("models/"):
            model = "models/" + model
        return "%s/%s:generateContent" % (self.api_url.rstrip("/"), model)

    def headers(self) -> Dict[str, str]:
        return {"content-type": "application/json", "x-goog-api-key": self.key}

    def body_for(self, req: Request) -> Dict[str, Any]:
        contents = [{"role": "model" if t["role"] == "assistant" else "user",
                     "parts": [{"text": t["content"]}]} for t in self.turns(req)]
        body: Dict[str, Any] = {"contents": contents}
        if req.system:
            body["systemInstruction"] = {"parts": [{"text": str(req.system)}]}
        if req.max_tokens:
            body["generationConfig"] = {"maxOutputTokens": int(req.max_tokens)}
        return body

    def text_of(self, answer: Dict[str, Any]) -> str:
        candidates = answer.get("candidates") or []
        parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        return "".join(str(p.get("text") or "") for p in parts).strip()

    def usage_of(self, answer: Dict[str, Any]):
        usage = answer.get("usageMetadata") or {}
        return self.tokens(usage.get("promptTokenCount"), usage.get("candidatesTokenCount"))

    def notes_of(self, answer: Dict[str, Any]) -> str:
        candidates = answer.get("candidates") or []
        why = str((candidates[0].get("finishReason") or "") if candidates else "")
        return "" if why in ("", "STOP") else "stopped: " + why

    # ---- what it offers

    def catalog(self, timeout: int = 0) -> Dict[str, Any]:
        """`GET <base>/models`. The id is the resource path, which is also what the model
        field takes, so it is kept as it comes."""
        if not self.key or not self.api_url:
            return {"ok": False, "models": [], "error": "no API key configured"}
        url = (self.models_url or self.api_url.rstrip("/") + "/models")
        try:
            body = self.get(url, timeout or CATALOG_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 - a source that cannot answer says so
            return {"ok": False, "models": [], "error": str(exc)[:200]}
        found: List[Dict[str, str]] = []
        for m in body.get("models") or []:
            if isinstance(m, dict) and m.get("name"):
                found.append({"id": str(m["name"]),
                              "label": str(m.get("displayName") or m["name"]),
                              "created": ""})
        return {"ok": True, "models": found, "error": ""}

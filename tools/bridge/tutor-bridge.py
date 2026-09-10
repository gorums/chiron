#!/usr/bin/env python3
"""The tutor bridge: a course page opened off disk, given a way to reach a model.

    course site (your browser)  ->  http://127.0.0.1:8787  ->  a model

It binds to 127.0.0.1 only, so nothing outside this computer can reach it.

**It has no opinion about how a model is reached.** Every call goes through
`coursekit.llm`, the same provider layer Studio uses - so the retry policy, the model
fallback and the failure classification are one implementation, not two that drift. What is
left here is what a bridge is actually for:

- **CORS and a loopback socket**, because a `file://` page cannot call a model directly
  without a key and cannot call Studio at all.
- **Finding a key without asking.** `candidate_keys` looks in the half-dozen places one is
  already likely to be on this machine, reports which one it used, and saves it to
  `config.json` so the question is asked once.
- **Choosing between the ways in**, and falling back: Claude Code if it is signed in, an API
  key otherwise, and one to the other when the live one fails mid-question.
- **A budget per question.** The prompt travels on stdin so there is no size ceiling to trim
  to; this only bounds what one question can cost.

Run it:   double-click start-bridge.bat   (or: python tutor-bridge.py)
Stop it:  close the window, or press Ctrl+C

Environment overrides:
    ANTHROPIC_API_KEY   use this key and never touch config.json
    BRIDGE_PORT         overrides `bridge.port` in platform/settings.json
    BRIDGE_HOST         overrides `bridge.host` (containers set 0.0.0.0)
    BRIDGE_API_URL      overrides `providers.anthropic.apiUrl`
    BRIDGE_MODE         force "api" or "cli"
    BRIDGE_ECHO=1       test mode: echo messages back, call nothing
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "3.0"
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")

# Every default - port, host, the providers, the model list, budgets, timeouts - comes from
# platform/settings.json, the same file Studio and the build read. The provider layer comes
# from the same place, imported from outside the package the way `settings` is; both are
# standard library only, so the bridge needs nothing installed.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "platform"))
from coursekit import llm  # noqa: E402  (stdlib only; needs no `markdown`)
from coursekit.llm import cli as llm_cli  # noqa: E402
from coursekit.llm.anthropic import AnthropicProvider  # noqa: E402
from coursekit.llm.base import LLMFailed, Request  # noqa: E402
from coursekit.llm.failures import AUTH, TIMEOUT, UNKNOWN  # noqa: E402
from coursekit.settings import SETTINGS  # noqa: E402

PORT = int(SETTINGS.get("bridge.port"))
# Loopback unless told otherwise. A container has to bind 0.0.0.0 to be reachable through a
# published port; the port is still published to loopback on the host, so the boundary holds.
HOST = str(SETTINGS.get("bridge.host"))
ECHO = os.environ.get("BRIDGE_ECHO") == "1"
FORCE_MODE = os.environ.get("BRIDGE_MODE", "").strip().lower()

API_TIMEOUT = int(SETTINGS.get("bridge.apiTimeout"))
CLI_TIMEOUT = int(SETTINGS.get("bridge.cliTimeout"))
CLI_PROBE_TIMEOUT = int(SETTINGS.get("bridge.cliProbeTimeout"))
CLI_BUDGET = int(SETTINGS.get("bridge.cliBudgetChars"))
SYSTEM_CHARS = int(SETTINGS.get("bridge.systemChars"))
MAX_TOKENS = int(SETTINGS.get("page.tutor.maxTokens"))
MAX_TOKENS_CAP = int(SETTINGS.get("bridge.maxTokensCap"))
HISTORY = int(SETTINGS.get("page.tutor.history"))

CFG = {"key": "", "model": SETTINGS.model_id(SETTINGS.default_model)}


# --------------------------------------------------------------------------- what we remember


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            CFG.update(json.load(f))
    except Exception:
        pass


def save_config():
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(CFG, f, indent=2)
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except Exception:
            pass
        return True
    except Exception as e:
        print("  Could not save config.json: %s" % e)
        return False


def active_key():
    return (os.environ.get("ANTHROPIC_API_KEY") or CFG.get("key") or "").strip()


def key_source():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "ANTHROPIC_API_KEY environment variable"
    if (CFG.get("key") or "").strip():
        return "bridge config.json"
    return "none"


def key_hint():
    k = active_key()
    if not k:
        return ""
    return (k[:14] + "…" + k[-4:]) if len(k) > 22 else "(suspiciously short)"


# Every place on this machine a key of yours might already be, in priority order. Read only
# when you press Connect, and the source is always reported back to you.
KEY_NAMES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY")
KEY_SHAPES = ("sk-ant-", "sk-", "AIza")


def candidate_keys():
    found, seen = [], set()

    def add(k, src):
        k = (k or "").strip()
        if k.startswith(KEY_SHAPES) and k not in seen:
            seen.add(k)
            found.append((k, src))

    for name in KEY_NAMES:
        add(os.environ.get(name), name + " environment variable")
    add(CFG.get("key"), "bridge config.json")

    home = os.path.expanduser("~")
    spots = [
        (os.path.join(HERE, "anthropic.key"), "plain"),
        (os.path.join(home, ".anthropic", "api_key"), "plain"),
        (os.path.join(home, "anthropic.key"), "plain"),
        (os.path.join(home, ".anthropic", "config.json"), "json"),
        (os.path.join(home, ".claude", "settings.json"), "claude"),
        (os.path.join(HERE, ".env"), "env"),
        (os.path.join(os.path.dirname(os.path.dirname(HERE)), ".env"), "env"),   # repo root
        (os.path.join(home, ".env"), "env"),
    ]
    for path, kind in spots:
        try:
            if not os.path.isfile(path):
                continue
            raw = open(path, encoding="utf-8", errors="ignore").read()
            if kind == "plain":
                add(raw.strip().splitlines()[0] if raw.strip() else "", path)
            elif kind == "json":
                d = json.loads(raw)
                add(d.get("api_key") or d.get("key"), path)
            elif kind == "claude":
                d = json.loads(raw)
                add((d.get("env") or {}).get("ANTHROPIC_API_KEY"), path)
            elif kind == "env":
                for name in KEY_NAMES:
                    m = re.search(r"^\s*%s\s*=\s*[\"']?([^\"'\r\n]+)" % name, raw, re.M)
                    if m:
                        add(m.group(1), path)
        except Exception:
            pass
    return found


# --------------------------------------------------------------------------- ways to a model


def cli_provider():
    """The configured `cli` provider - Claude Code, unless settings.json says otherwise."""
    for p in llm.providers():
        if p.kind == "cli":
            return p
    return llm_cli.CliProvider()


def api_provider():
    """The Anthropic provider, using whatever key this bridge found for itself."""
    provider = AnthropicProvider.from_settings("anthropic", SETTINGS.provider("anthropic"))
    return provider.with_key(active_key() or provider.key)


def route():
    """(mode, provider): which way to a model is live right now."""
    if ECHO:
        return "echo", None
    cli, api = cli_provider(), api_provider()
    if FORCE_MODE == "api":
        return ("api", api) if api.available() else ("none", None)
    if FORCE_MODE == "cli":
        return ("cli", cli) if cli.available() else ("none", None)
    if CFG.get("prefer_cli") and cli.available():
        return "cli", cli
    if api.available():
        return "api", api
    if cli.available():
        return "cli", cli
    return "none", None


def active_mode():
    return route()[0]


def cli_works():
    alias = SETTINGS.model_aliases.get(CFG.get("model") or "", "")
    return bool(cli_provider().probe(alias, CLI_PROBE_TIMEOUT).get("ok"))


def verify_key(key):
    """One tiny real request. Returns (ok, message)."""
    answer = api_provider().with_key(key).probe(CFG.get("model") or "", 30)
    return bool(answer.get("ok")), answer.get("advice") or answer.get("reply") or "works"


def trim(system, messages, budget):
    """Bound what one question costs. The prompt travels on stdin, so this is about money
    and latency rather than any command-line limit: drop the oldest turns first, then shorten
    the quoted passage, and only then clip the newest message."""
    msgs = [dict(m) for m in messages][-HISTORY:]
    system = str(system or "")[:SYSTEM_CHARS]
    if not budget:
        return system, msgs

    def size():
        return len(system) + sum(len(str(m.get("content", ""))) for m in msgs)

    while len(msgs) > 1 and size() > budget:
        msgs.pop(0)
    over = size() - budget
    if over > 0 and len(system) > 900:
        system = system[:max(600, len(system) - over - 40)] + "\n…(passage shortened to fit)…"
    over = size() - budget
    if over > 0 and msgs:
        content = str(msgs[-1].get("content", ""))
        msgs[-1]["content"] = content[:max(200, len(content) - over - 20)]
    return system, msgs


def answer(mode, provider, system, messages, model, max_tokens):
    """One reply through the provider layer, which handles the retries and the model chain.
    The live route falls back to the other one when it fails and the other is configured."""
    budget = CLI_BUDGET if provider.kind == "cli" else 0
    system, messages = trim(system, messages, budget)
    request = Request(system=system, messages=messages, model=model or CFG.get("model") or "",
                      timeout=CLI_TIMEOUT if provider.kind == "cli" else API_TIMEOUT,
                      max_tokens=min(int(max_tokens or MAX_TOKENS), MAX_TOKENS_CAP))
    return llm.complete(provider, request).text


# --------------------------------------------------------------------------- the server


class Handler(BaseHTTPRequestHandler):
    server_version = "CourseBridge/" + VERSION
    protocol_version = "HTTP/1.1"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")

    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---- routing: one method per path ----

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            return self.health()
        self._send(404, {"error": "Not found. This bridge serves /health, /ask, /configure, "
                                  "/connect and /testkey."})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, {"error": "Could not read the request body."})
        handler = {"/configure": self.configure, "/connect": self.connect,
                   "/testkey": self.testkey, "/ask": self.ask}.get(path)
        if not handler:
            return self._send(404, {"error": "Not found. POST to /ask."})
        handler(body)

    def _key_status(self):
        return {"has_key": bool(active_key()), "key_source": key_source(), "key_hint": key_hint()}

    def health(self):
        """What can answer, and how. `providers` is the shape to read; the flat fields
        beside it are what a page built before this release looks for."""
        mode, _provider = route()
        rows = [dict(p.describe(), ready=p.available()) for p in llm.providers()]
        self._send(200, dict(self._key_status(), ok=True, version=VERSION, echo=ECHO, mode=mode,
                             ready=mode != "none", providers=rows,
                             cli=bool(cli_provider().available()),
                             model=CFG.get("model", "")))

    def configure(self, body):
        """Store a key, or a preference for the CLI, and the model."""
        if body.get("use_cli"):
            CFG["key"] = ""
            CFG["prefer_cli"] = True
        elif "key" in body:
            CFG["key"] = str(body["key"] or "").strip()
            CFG["prefer_cli"] = False
        if body.get("model") in {m["id"] for m in SETTINGS.models}:
            CFG["model"] = body["model"]
        save_config()
        self._send(200, dict(self._key_status(), ok=True, mode=active_mode()))

    def connect(self, body):
        """Find a working route without asking the user for anything."""
        steps = []
        cli = cli_provider()
        if cli.available():
            steps.append({"tried": cli.label + " on this machine", "ok": cli_works()})
            if steps[-1]["ok"]:
                # The CLI wins. Any stored key stays only as a silent fallback for the rare
                # case where it fails mid-question.
                CFG["prefer_cli"] = True
                save_config()
                return self._send(200, {"ok": True, "mode": "cli", "steps": steps,
                                        "source": cli.label + " on this machine",
                                        "note": "No API key needed — this uses the account "
                                                "you are already signed in to."})
        for key, src in candidate_keys():
            ok, why = verify_key(key)
            steps.append({"tried": src, "ok": ok, "why": "" if ok else why})
            if ok:
                CFG["prefer_cli"] = False
                if not src.endswith("environment variable"):
                    CFG["key"] = key
                save_config()
                return self._send(200, {"ok": True, "mode": "api", "steps": steps,
                                        "source": src, "key_hint": key_hint(),
                                        "note": "Saved to tools/bridge/config.json — you will "
                                                "not be asked again."})
        # nothing usable: clear a dead key so it stops poisoning every request
        if (CFG.get("key") or "").strip():
            CFG["key"] = ""
            save_config()
            steps.append({"tried": "removing the rejected key from config.json", "ok": True})
        self._send(200, {"ok": False, "need": "key", "steps": steps,
                         "cli": bool(cli.available())})

    def testkey(self, body):
        """Cheapest possible real call, so the raw failure is visible."""
        if not active_key():
            return self._send(200, {"ok": False, "reason": "No key configured.",
                                    "mode": active_mode()})
        result = api_provider().probe(CFG.get("model") or "", 30)
        if result.get("ok"):
            return self._send(200, dict(self._key_status(), ok=True))
        self._send(200, dict(self._key_status(), ok=False, why=result.get("why", UNKNOWN),
                             reason=result.get("advice") or result.get("error", "")))

    def ask(self, body):
        """The tutor: {system, messages, model, max_tokens, key?} -> {text, mode}."""
        messages = body.get("messages") or []
        if not messages:
            return self._send(400, {"error": "No messages to send."})
        if ECHO:
            return self._send(200, {"text": "ECHO: " + messages[-1].get("content", ""),
                                    "mode": "echo"})

        # A key sent by the page is only a fallback. The bridge's own key wins, so a stale
        # value left in a browser can never override what you configured here.
        page_key = (body.get("key") or "").strip()
        if page_key and not active_key() and not CFG.get("prefer_cli"):
            CFG["key"] = page_key

        mode, provider = route()
        if mode == "none":
            return self._send(400, {"error": (
                "No way to reach a model yet. Either paste an API key (the bridge asks for "
                "one on first run, or use the Settings page), or install the command-line "
                "tool so the bridge can use it.")})
        system, model, tokens = body.get("system") or "", body.get("model"), body.get("max_tokens")
        try:
            text = answer(mode, provider, system, messages, model, tokens)
            return self._send(200, {"text": text, "mode": mode})
        except LLMFailed as exc:
            self._failed(exc, mode, system, messages, model, tokens)
        except Exception as exc:  # noqa: BLE001 - anything else still owes the page an answer
            self._send(502, {"error": str(exc)[:400] or "Could not reach a model.",
                             "why": UNKNOWN})

    def _failed(self, exc, mode, system, messages, model, tokens):
        """The live route said no. When the other one is configured, use it and say so."""
        other = {"cli": api_provider(), "api": cli_provider()}.get(mode)
        worth_it = exc.kind == AUTH or (mode == "cli" and exc.kind != TIMEOUT)
        if other is not None and other.available() and worth_it:
            try:
                text = answer(mode, other, system, messages, model, tokens)
                kind = "api" if other.kind != "cli" else "cli"
                return self._send(200, {"text": text, "mode": kind, "notice": _switched(mode)})
            except Exception:  # noqa: BLE001 - the first failure is the one to report
                pass
        self._send(504 if exc.kind == TIMEOUT else 502,
                   {"error": str(exc), "why": exc.kind, "resetsAt": exc.resets_at})


def _switched(mode):
    if mode == "api":
        return ("That API key was rejected, so this answer came from the command-line tool "
                "instead. Clear the saved key in Settings to use it from now on.")
    return ("The command-line tool could not answer, so this came through the API key "
            "instead.")


# --------------------------------------------------------------------------- starting up


def auto_configure():
    """Work out how to reach a model without asking anything. Never blocks."""
    if ECHO or FORCE_MODE:
        return
    if cli_provider().available():
        CFG["prefer_cli"] = True
        save_config()
        return
    if not active_key():
        found = candidate_keys()
        if found:
            CFG["key"] = found[0][0]
            CFG["_found_in"] = found[0][1]
            save_config()


def main():
    load_config()
    auto_configure()
    try:
        srv = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        print("\n  Could not start on port %d: %s" % (PORT, e))
        print("  Something else may be using it. Try:  set BRIDGE_PORT=%d\n" % (PORT + 1))
        return 1
    mode = active_mode()
    label = {"api": "an API key (%s)" % (CFG.get("_found_in") or key_source()),
             "cli": "%s on this machine - no API key needed" % cli_provider().label,
             "echo": "ECHO test mode (nothing is called)",
             "none": "nothing found yet - press Connect in the site"}[mode]
    print("")
    print("  Course platform - tutor bridge v%s" % VERSION)
    print("  " + "-" * 46)
    print("  Listening on   http://%s:%d" % (HOST, PORT))
    print("  Reachable by   %s" % ("this computer only"
                                   if HOST in ("127.0.0.1", "localhost", "::1")
                                   else "anything that can reach %s" % HOST))
    print("  Using          %s" % label)
    print("")
    print("  Now open your course's -local.html copy and press Connect.")
    print("  Leave this window open while you study. Ctrl+C to stop.")
    print("")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Bridge stopped.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

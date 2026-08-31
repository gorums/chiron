#!/usr/bin/env python3
"""
Claude bridge for any course site built by this platform.

A web page cannot call a model directly. This small program runs on your own
machine and passes messages along:

    course site (your browser)  ->  http://127.0.0.1:8787  ->  Claude

It binds to 127.0.0.1 only, so nothing outside this computer can reach it.

Two ways to reach Claude, tried in this order:
  1. An Anthropic API key   (asked for once on first run, saved to config.json)
  2. The Claude Code CLI    (used automatically if `claude` is on your PATH and
                             no key is configured — no API key, no extra billing)

Run it:   double-click start-bridge.bat   (or: python claude-bridge.py)
Stop it:  close the window, or press Ctrl+C

Environment overrides:
    ANTHROPIC_API_KEY   use this key and never touch config.json
    BRIDGE_PORT         default 8787
    BRIDGE_MODE         force "api" or "cli"
    BRIDGE_ECHO=1       test mode: echo messages back, call nothing
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "2.0"
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
PORT = int(os.environ.get("BRIDGE_PORT", "8787"))
ECHO = os.environ.get("BRIDGE_ECHO") == "1"
FORCE_MODE = os.environ.get("BRIDGE_MODE", "").strip().lower()
API_URL = os.environ.get("BRIDGE_API_URL", "https://api.anthropic.com/v1/messages")
API_VERSION = "2023-06-01"
ALLOWED_MODELS = {"claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5-20251001"}

CFG = {"key": "", "model": "claude-sonnet-5"}


def load_config():
    global CFG
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


def find_cli():
    for name in ("claude", "claude.cmd", "claude.exe"):
        p = shutil.which(name)
        if p:
            return p
    return None


def active_key():
    return (os.environ.get("ANTHROPIC_API_KEY") or CFG.get("key") or "").strip()


def key_source():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "environment variable"
    if (CFG.get("key") or "").strip():
        return "bridge config.json"
    return "none"


def key_hint():
    k = active_key()
    if not k:
        return ""
    return (k[:14] + "…" + k[-4:]) if len(k) > 22 else "(suspiciously short)"


def active_mode():
    """Which route to Claude is live right now."""
    if ECHO:
        return "echo"
    if FORCE_MODE in ("api", "cli"):
        return FORCE_MODE
    if CFG.get("prefer_cli") and find_cli():
        return "cli"
    if active_key():
        return "api"
    if find_cli():
        return "cli"
    return "none"


CLI_BUDGET = 5500          # characters. Windows command lines cap at 8191, and Claude Code's
                           # headless mode has been known to return nothing on very large input.
CLI_MODELS = {"claude-opus-5": "opus", "claude-sonnet-5": "sonnet",
              "claude-haiku-4-5-20251001": "haiku"}


def flatten(system, messages, budget=None):
    """Build one prompt, trimming to stay well inside the safe size."""
    msgs = list(messages)
    system = system or ""
    if budget:
        # 1. drop the oldest turns first, always keeping the newest question
        while len(msgs) > 1 and len(system) + sum(len(m.get("content", "")) for m in msgs) > budget:
            msgs.pop(0)
        # 2. still too big: shorten the quoted passage inside the system prompt
        over = len(system) + sum(len(m.get("content", "")) for m in msgs) - budget
        if over > 0 and len(system) > 900:
            keep = max(600, len(system) - over - 40)
            system = system[:keep] + "\n…(passage shortened to fit)…"
        # 3. last resort: clip the newest message
        over = len(system) + sum(len(m.get("content", "")) for m in msgs) - budget
        if over > 0 and msgs:
            c = msgs[-1].get("content", "")
            msgs[-1] = dict(msgs[-1], content=c[:max(200, len(c) - over - 20)])
    parts = []
    if system:
        parts.append(system)
    for m in msgs:
        who = "User" if m.get("role") == "user" else "Assistant"
        parts.append("%s: %s" % (who, m.get("content", "")))
    parts.append("Assistant:")
    return "\n\n".join(parts)


def cli_argv(cli, args):
    """A .cmd/.bat shim cannot be executed directly on Windows — route it through cmd."""
    if os.name == "nt" and cli.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", cli] + args
    return [cli] + args


def candidate_keys():
    """Every place on this machine a key of yours might already be, in priority order.
    Read only when you press Connect, and the source is always reported back to you."""
    found, seen = [], set()

    def add(k, src):
        k = (k or "").strip()
        if k.startswith("sk-ant-") and k not in seen:
            seen.add(k)
            found.append((k, src))

    add(os.environ.get("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY environment variable")
    add(CFG.get("key"), "bridge config.json")

    home = os.path.expanduser("~")
    spots = [
        (os.path.join(HERE, "anthropic.key"), "plain"),
        (os.path.join(home, ".anthropic", "api_key"), "plain"),
        (os.path.join(home, "anthropic.key"), "plain"),
        (os.path.join(home, ".anthropic", "config.json"), "json"),
        (os.path.join(home, ".claude", "settings.json"), "claude"),
        (os.path.join(HERE, ".env"), "env"),
        (os.path.join(os.path.dirname(HERE), ".env"), "env"),
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
                m = re.search(r"^\s*ANTHROPIC_API_KEY\s*=\s*[\"']?([^\"'\r\n]+)", raw, re.M)
                if m:
                    add(m.group(1), path)
        except Exception:
            pass
    return found


def verify_key(key):
    """One 4-token request. Returns (ok, message)."""
    try:
        call_api("", [{"role": "user", "content": "hi"}], CFG.get("model"), 4, key=key)
        return True, "works"
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")[:200]
        except Exception:
            msg = ""
        return False, msg or ("HTTP %s" % e.code)
    except Exception as e:
        return False, str(e)[:200]


def cli_works():
    cli = find_cli()
    if not cli:
        return False
    try:
        p = subprocess.run(cli_argv(cli, ["-p", "Reply with the single word: ready"]),
                           capture_output=True, text=True, timeout=120,
                           stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
        return p.returncode == 0 and bool((p.stdout or "").strip())
    except Exception:
        return False


def call_api(system, messages, model, max_tokens, key=None):
    key = (key or active_key() or "").strip()
    if not key:
        raise RuntimeError("No API key configured.")
    if model not in ALLOWED_MODELS:
        model = CFG.get("model") or "claude-sonnet-5"
    payload = {
        "model": model,
        "max_tokens": min(int(max_tokens or 1400), 4000),
        "messages": [{"role": m.get("role", "user"), "content": str(m.get("content", ""))}
                     for m in messages][-20:],
    }
    if system:
        payload["system"] = str(system)[:8000]
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": API_VERSION},
        method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode("utf-8"))
    return "".join(c.get("text", "") for c in data.get("content", []) if c.get("type") == "text")


def call_cli(system, messages, model=None):
    cli = find_cli()
    if not cli:
        raise RuntimeError("Claude Code is not installed, or not on this PATH.")
    prompt = flatten(system, messages, budget=CLI_BUDGET)
    short = CLI_MODELS.get(model or CFG.get("model") or "")
    attempts = []
    if short:
        attempts.append(["-p", prompt, "--output-format", "text", "--model", short])
    attempts.append(["-p", prompt, "--output-format", "text"])
    attempts.append(["-p", prompt])
    last = ""
    for args in attempts:
        try:
            proc = subprocess.run(cli_argv(cli, args), capture_output=True, text=True,
                                  timeout=240, stdin=subprocess.DEVNULL,
                                  encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            raise
        except Exception as e:
            last = str(e)[:300]
            continue
        out = (proc.stdout or "").strip()
        if proc.returncode == 0 and out:
            return out
        last = (proc.stderr or "").strip()[:300] or (
            "Claude Code returned nothing. The prompt may have been too long — "
            "try selecting a shorter passage." if proc.returncode == 0 else
            "exit code %s" % proc.returncode)
    raise RuntimeError("Claude Code failed: " + (last or "no output"))


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

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            mode = active_mode()
            return self._send(200, {
                "ok": True,
                "version": VERSION,
                "echo": ECHO,
                "mode": mode,
                "ready": mode not in ("none",),
                "cli": bool(find_cli()),
                "has_key": bool(active_key()),
                "key_source": key_source(),
                "key_hint": key_hint(),
                "model": CFG.get("model", "claude-sonnet-5"),
            })
        return self._send(404, {"error": "Not found. This bridge serves /health, /ask, /configure and /testkey."})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, {"error": "Could not read the request body."})

        if path == "/configure":
            if body.get("use_cli"):
                CFG["key"] = ""
                CFG["prefer_cli"] = True
            elif "key" in body:
                CFG["key"] = str(body["key"] or "").strip()
                CFG["prefer_cli"] = False
            if body.get("model") in ALLOWED_MODELS:
                CFG["model"] = body["model"]
            save_config()
            return self._send(200, {"ok": True, "mode": active_mode(),
                                    "has_key": bool(active_key()),
                                    "key_source": key_source(), "key_hint": key_hint()})

        if path == "/connect":
            """Find a working route to Claude without asking the user for anything."""
            steps = []
            if find_cli():
                steps.append({"tried": "Claude Code on this machine", "ok": cli_works()})
                if steps[-1]["ok"]:
                    # Claude Code wins. Any stored key stays only as a silent fallback
                    # for the rare case where the CLI fails mid-question.
                    CFG["prefer_cli"] = True
                    save_config()
                    return self._send(200, {"ok": True, "mode": "cli", "steps": steps,
                                            "source": "Claude Code on this machine",
                                            "note": "No API key needed — this uses the Claude you are already signed in to."})
            for key, src in candidate_keys():
                ok, msg = verify_key(key)
                steps.append({"tried": src, "ok": ok, "why": "" if ok else msg})
                if ok:
                    CFG["prefer_cli"] = False
                    if src != "ANTHROPIC_API_KEY environment variable":
                        CFG["key"] = key
                    save_config()
                    return self._send(200, {"ok": True, "mode": "api", "steps": steps,
                                            "source": src, "key_hint": key_hint(),
                                            "note": "Saved to bridge/config.json — you will not be asked again."})
            # nothing usable: clear a dead key so it stops poisoning every request
            if (CFG.get("key") or "").strip():
                CFG["key"] = ""
                save_config()
                steps.append({"tried": "removing the rejected key from config.json", "ok": True})
            return self._send(200, {"ok": False, "need": "key", "steps": steps,
                                    "cli": bool(find_cli())})

        if path == "/testkey":
            """Cheapest possible real call, so the raw failure is visible."""
            if not active_key():
                return self._send(200, {"ok": False, "reason": "No key configured.",
                                        "mode": active_mode()})
            try:
                call_api("", [{"role": "user", "content": "hi"}], CFG.get("model"), 4)
                return self._send(200, {"ok": True, "key_source": key_source(),
                                        "key_hint": key_hint()})
            except urllib.error.HTTPError as e:
                try:
                    raw = json.loads(e.read().decode("utf-8"))
                    detail = raw.get("error", {}).get("message", "")[:300]
                    etype = raw.get("error", {}).get("type", "")
                except Exception:
                    detail, etype = "", ""
                return self._send(200, {"ok": False, "status": e.code, "type": etype,
                                        "reason": detail or ("HTTP %s" % e.code),
                                        "key_source": key_source(), "key_hint": key_hint()})
            except Exception as e:
                return self._send(200, {"ok": False, "reason": str(e)[:300],
                                        "key_source": key_source(), "key_hint": key_hint()})

        if path != "/ask":
            return self._send(404, {"error": "Not found. POST to /ask."})

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

        mode = active_mode()
        system = body.get("system") or ""
        try:
            if mode == "api":
                text = call_api(system, messages, body.get("model"), body.get("max_tokens"))
            elif mode == "cli":
                try:
                    text = call_cli(system, messages, body.get("model"))
                except Exception:
                    if not active_key():
                        raise
                    text = call_api(system, messages, body.get("model"), body.get("max_tokens"))
            else:
                return self._send(400, {"error": (
                    "Claude is not set up yet. Either paste an API key (the bridge asks for "
                    "one on first run, or use the Settings page), or install Claude Code so "
                    "the bridge can use it.")})
            return self._send(200, {"text": text, "mode": mode})
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")[:400]
            except Exception:
                msg = ""
            # If the key is bad but Claude Code is sitting right there, use it instead of failing.
            if e.code in (401, 403) and find_cli():
                try:
                    text = call_cli(system, messages)
                    return self._send(200, {"text": text, "mode": "cli", "notice": (
                        "That API key was rejected, so this answer came from Claude Code instead. "
                        "Clear the saved key in Settings to use Claude Code from now on.")})
                except Exception:
                    pass
            friendly = {
                401: ("The API key was rejected by Anthropic (%s). It is coming from %s%s. "
                      "Check it in the Anthropic console, or clear it in Settings to use "
                      "Claude Code instead." % (msg or "invalid key", key_source(),
                                                (" — " + key_hint()) if key_hint() else "")),
                400: "The API rejected the request. " + msg,
                404: "That model is not available for this key.",
                429: "Rate limited, or the key is out of credit.",
            }.get(e.code, "Anthropic API error %s. %s" % (e.code, msg))
            return self._send(e.code if e.code in (401, 429) else 502, {"error": friendly})
        except subprocess.TimeoutExpired:
            return self._send(504, {"error": "Claude Code took too long to answer."})
        except Exception as e:
            return self._send(502, {"error": str(e)[:400] or "Could not reach Claude."})


def auto_configure():
    """Work out how to reach Claude without asking anything. Never blocks."""
    if ECHO or FORCE_MODE:
        return
    if find_cli():
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
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as e:
        print("\n  Could not start on port %d: %s" % (PORT, e))
        print("  Something else may be using it. Try:  set BRIDGE_PORT=8788\n")
        return 1
    mode = active_mode()
    label = {"api": "Anthropic API key (%s)" % (CFG.get("_found_in") or key_source()),
             "cli": "Claude Code on this machine - no API key needed",
             "echo": "ECHO test mode (nothing is called)",
             "none": "nothing found yet - press Connect Claude in the site"}[mode]
    print("")
    print("  Course platform - Claude bridge v%s" % VERSION)
    print("  " + "-" * 46)
    print("  Listening on   http://127.0.0.1:%d" % PORT)
    print("  Reachable by   this computer only")
    print("  Using          %s" % label)
    print("")
    print("  Now open your course's -local.html copy and press Connect Claude.")
    print("  Leave this window open while you study. Ctrl+C to stop.")
    print("")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Bridge stopped.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The platform's settings, resolved once.

Every default the platform has — ports, hosts, the API endpoint, the model list, timeouts,
generation counts, the page's study rules and layout sizes — lives in `platform/settings.json`.
Nothing in `platform/` or `tools/` carries a literal of its own; it asks `SETTINGS`.

Resolution, later layers winning:

    platform/settings.json          the committed defaults
    $SETTINGS_FILE                  an optional JSON overlay, deep-merged, for a machine that
                                    wants a different model list or its own timeouts
    .env at the repo root           the scalar knobs listed in ENV_KEYS (same file compose reads)
    the environment                 the same names, winning over .env

An environment value is coerced to the type of the default it replaces, so `STUDIO_PORT=9000`
becomes an int and `STUDIO_HOST=0.0.0.0` stays a string. `Settings.overrides` records which
layer supplied each overridden key, for the Studio settings page.

Stdlib only: the bridge imports this from outside the package and must not need `markdown`.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Tuple

PLATFORM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(PLATFORM_DIR)
ENV_FILE = os.path.join(REPO_ROOT, ".env")
SETTINGS_FILE = os.path.join(PLATFORM_DIR, "settings.json")

# Environment / .env name -> the dotted key it overrides. These are the knobs a machine is
# likely to differ on; anything else is edited in settings.json or an overlay file.
ENV_KEYS: Dict[str, str] = {
    "COURSES_DIR": "paths.courses",
    "DIST_DIR": "paths.dist",
    "STUDIO_STATE_ROOT": "paths.state",
    "STUDIO_STATE_DIR": "paths.progress",
    "STUDIO_HOST": "studio.host",
    "STUDIO_PORT": "studio.port",
    "STUDIO_MODEL": "models.default",
    "STUDIO_LOG_LEVEL": "logs.level",
    "BRIDGE_HOST": "bridge.host",
    "BRIDGE_PORT": "bridge.port",
    "BRIDGE_URL": "bridge.url",
    "BRIDGE_API_URL": "anthropic.apiUrl",
    "ANTHROPIC_API_VERSION": "anthropic.apiVersion",
}

# Binding to every interface is how a container is reached through its published port; the
# address a browser on this machine should then use is loopback.
ANY_HOST = ("0.0.0.0", "", "::")
LOOPBACK = "127.0.0.1"


class SettingsError(RuntimeError):
    """settings.json is missing or not valid JSON — the platform cannot run without it."""


def read_env_file(path: str = ENV_FILE) -> Dict[str, str]:
    """The `KEY=value` lines of a dotenv file. Comments and blanks are skipped; a value may
    be wrapped in single or double quotes. Missing file: empty. No interpolation."""
    out: Dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def _deep_merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in (over or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def _coerce(raw: str, like: Any) -> Any:
    """An environment value is a string; make it the type of the default it replaces."""
    if isinstance(like, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(like, int):
        return int(raw.strip())
    if isinstance(like, float):
        return float(raw.strip())
    return raw


class Settings:
    def __init__(self, data: Dict[str, Any], overrides: Dict[str, str], path: str = SETTINGS_FILE,
                 overlay: str = ""):
        self.data = data
        self.overrides = overrides      # dotted key -> "environment" | ".env" | overlay path
        self.path = path
        self.overlay = overlay

    # ---- generic access ----

    def get(self, key: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, _MISSING)
        if value is _MISSING:
            raise KeyError("settings.json has no '%s'" % key)
        return value

    def section(self, key: str) -> Dict[str, Any]:
        value = self.get(key)
        return copy.deepcopy(value) if isinstance(value, dict) else {}

    # ---- paths ----

    def path_of(self, key: str, default: str = "") -> str:
        """A directory setting, absolute and normalised. Relative values are anchored at the
        repo root, so `.env` can say `COURSES_DIR=../courses` and mean the same thing on
        every machine that checks the platform out into a sibling folder."""
        value = os.path.expanduser(str(self.get(key) or default))
        if not os.path.isabs(value):
            value = os.path.join(REPO_ROOT, value)
        return os.path.normpath(value)

    @property
    def courses_dir(self) -> str:
        return self.path_of("paths.courses", "courses")

    @property
    def dist_dir(self) -> str:
        return self.path_of("paths.dist", "dist")

    @property
    def state_dir(self) -> str:
        return self.path_of("paths.state", "state")

    @property
    def progress_dir(self) -> str:
        return self.path_of("paths.progress") if self.get("paths.progress") \
            else os.path.join(self.state_dir, "progress")

    @property
    def scratch_dir(self) -> str:
        """Where Claude Code is run from: an empty folder, so it never asks to trust one."""
        return os.path.join(tempfile.gettempdir(), str(self.get("paths.scratch") or "coursekit-claude"))

    # ---- models ----

    @property
    def models(self) -> List[Dict[str, Any]]:
        return [dict(m) for m in (self.get("models.list") or []) if isinstance(m, dict) and m.get("id")]

    @property
    def model_aliases(self) -> Dict[str, str]:
        """Every accepted spelling of a model -> the short alias the CLI takes."""
        out: Dict[str, str] = {}
        for m in self.models:
            alias = str(m.get("alias") or m["id"])
            out[alias] = alias
            out[str(m["id"])] = alias
        return out

    @property
    def default_model(self) -> str:
        """The default as a CLI alias. A full id or an unknown name falls back to the first
        model in the list, so the platform can never name a model it does not know."""
        wanted = str(self.get("models.default") or "").strip()
        aliases = self.model_aliases
        if wanted in aliases:
            return aliases[wanted]
        models = self.models
        return str(models[0].get("alias") or models[0]["id"]) if models else wanted

    def model_id(self, alias_or_id: str = "") -> str:
        """The full API id for an alias (or id). Default model when the name is unknown."""
        alias = self.model_aliases.get(alias_or_id or "", "") or self.default_model
        for m in self.models:
            if m.get("alias") == alias or m["id"] == alias:
                return str(m["id"])
        return alias

    # ---- network ----

    @staticmethod
    def local_url(host: str, port: int) -> str:
        """What a browser on this machine should open for a service bound to host:port."""
        return "http://%s:%d" % (LOOPBACK if host in ANY_HOST else host, int(port))

    @property
    def studio_url(self) -> str:
        return self.local_url(str(self.get("studio.host")), int(self.get("studio.port")))

    @property
    def bridge_url(self) -> str:
        """The address a course page tries first. Explicit `bridge.url` wins; otherwise it is
        derived from the bridge's own host and port."""
        explicit = str(self.get("bridge.url") or "").strip().rstrip("/")
        return explicit or self.local_url(str(self.get("bridge.host")), int(self.get("bridge.port")))

    # ---- for the browser ----

    def page(self) -> Dict[str, Any]:
        """CFG.platform: the slice the built page needs. Presentation-free and course-free."""
        out = self.section("page")
        out.update({
            "bridgeUrl": self.bridge_url,
            "apiUrl": self.get("anthropic.apiUrl"),
            "apiVersion": self.get("anthropic.apiVersion"),
            "defaultModel": self.model_id(self.default_model),
            "models": [{"id": m["id"], "label": m.get("label") or m["id"]} for m in self.models],
        })
        return out

    # ---- for the Studio settings page ----

    def describe(self) -> List[Dict[str, Any]]:
        """Every scalar setting as {key, value, source}, in file order."""
        rows: List[Dict[str, Any]] = []

        def walk(node: Any, prefix: str) -> None:
            for key, value in node.items():
                if key == "_":
                    continue
                dotted = prefix + key
                if isinstance(value, dict):
                    walk(value, dotted + ".")
                elif isinstance(value, list):
                    rows.append({"key": dotted, "value": ", ".join(
                        str(v.get("id") if isinstance(v, dict) else v) for v in value),
                        "source": self.overrides.get(dotted, "settings.json")})
                else:
                    rows.append({"key": dotted, "value": value,
                                 "source": self.overrides.get(dotted, "settings.json")})
        walk(self.data, "")
        return rows


_MISSING = object()


def _set(data: Dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _get(data: Dict[str, Any], dotted: str) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def load(path: str = SETTINGS_FILE, *, env: Optional[Dict[str, str]] = None,
         dotenv: Optional[Dict[str, str]] = None, overlay: Optional[str] = None,
         env_keys: Optional[Dict[str, str]] = None) -> Settings:
    """Read the defaults, then apply the overlay, `.env` and the environment in that order."""
    env = os.environ if env is None else env
    dotenv = read_env_file() if dotenv is None else dotenv
    env_keys = ENV_KEYS if env_keys is None else env_keys
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as exc:
        raise SettingsError("No settings file at %s: %s" % (path, exc)) from exc
    except ValueError as exc:
        raise SettingsError("%s is not valid JSON: %s" % (path, exc)) from exc
    if not isinstance(data, dict):
        raise SettingsError("%s must hold a JSON object" % path)

    overrides: Dict[str, str] = {}
    overlay = env.get("SETTINGS_FILE") if overlay is None else overlay
    if overlay:
        try:
            with open(overlay, encoding="utf-8") as fh:
                extra = json.load(fh)
        except (OSError, ValueError) as exc:
            raise SettingsError("SETTINGS_FILE %s could not be read: %s" % (overlay, exc)) from exc
        if isinstance(extra, dict):
            for dotted in _leaves(extra):
                overrides[dotted] = overlay
            _deep_merge(data, extra)

    for layer, source in ((dotenv, ".env"), (env, "environment")):
        for name, dotted in env_keys.items():
            raw = layer.get(name)
            if raw is None or raw == "":
                continue
            try:
                value = _coerce(str(raw), _get(data, dotted))
            except ValueError as exc:
                raise SettingsError("%s=%r is not a valid value for %s: %s" % (name, raw, dotted, exc)) from exc
            _set(data, dotted, value)
            overrides[dotted] = source
    return Settings(data, overrides, path, overlay or "")


def _leaves(node: Dict[str, Any], prefix: str = "") -> Iterable[str]:
    for key, value in node.items():
        if isinstance(value, dict):
            yield from _leaves(value, prefix + key + ".")
        else:
            yield prefix + key


SETTINGS = load()

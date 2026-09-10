"""The platform's settings, resolved once.

Every default the platform has — ports, hosts, the API endpoint, the model list, timeouts,
generation counts, the page's study rules and layout sizes — lives in `platform/settings.json`.
Nothing in `platform/` or `tools/` carries a literal of its own; it asks `SETTINGS`.

Resolution, later layers winning:

    platform/settings.json          the committed defaults
    $SETTINGS_FILE                  an optional JSON overlay, deep-merged, for a machine that
                                    wants a different model list or its own timeouts
    <state>/settings.json           what Studio's settings page changed - today the model
                                    list; deep-merged like the overlay, written only by Studio
    .env at the repo root           the scalar knobs listed in ENV_KEYS (same file compose reads)
    the environment                 the same names, winning over .env

The Studio layer sits under the state directory because it is personal and generated, like
progress; `paths.state` may itself come from the environment, so the file is located after
the environment has been read once and the environment is applied again over it.
`Settings.reload()` re-reads every layer in place, so a list Studio just saved reaches every
module that holds the `SETTINGS` object without a restart.

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
from typing import Any, Dict, Iterable, List, Optional

PLATFORM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(PLATFORM_DIR)
ENV_FILE = os.path.join(REPO_ROOT, ".env")
SETTINGS_FILE = os.path.join(PLATFORM_DIR, "settings.json")
STUDIO_SETTINGS_NAME = "settings.json"      # under the state directory
STUDIO_SOURCE = "Studio"                    # what `overrides` says for that layer

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
    "JUPYTER_HOST": "jupyter.host",
    "JUPYTER_PORT": "jupyter.port",
    "JUPYTER_URL": "jupyter.url",
    "JUPYTER_INTERNAL_URL": "jupyter.internalUrl",
    "JUPYTER_TOKEN": "jupyter.token",
    "BRIDGE_API_URL": "providers.anthropic.apiUrl",
    "ANTHROPIC_API_KEY": "providers.anthropic.apiKey",
    "ANTHROPIC_API_VERSION": "providers.anthropic.apiVersion",
    "OPENAI_API_KEY": "providers.openai.apiKey",
    "GOOGLE_API_KEY": "providers.google.apiKey",
    "LLM_DEFAULT_PROVIDER": "llm.defaultProvider",
}

# Where a setting used to live -> where it is read now. A block below is only present if
# something deliberately set it - an overlay, Studio's file, or a settings.json older than
# the providers block - so when it is present it wins, and then it is absorbed and dropped.
# This is what keeps an existing .env or overlay working across the rename.
LEGACY_KEYS: Dict[str, str] = {
    "claude.timeout": "llm.timeout",
    "claude.jsonAttempts": "llm.jsonAttempts",
    "claude.chatHistory": "llm.chatHistory",
    "claude.probeTimeout": "llm.probeTimeout",
    "claude.retries": "llm.retries",
    "claude.backoffSeconds": "llm.backoffSeconds",
    "claude.backoffMaxSeconds": "llm.backoffMaxSeconds",
    "anthropic.apiUrl": "providers.anthropic.apiUrl",
    "anthropic.modelsUrl": "providers.anthropic.modelsUrl",
    "anthropic.apiVersion": "providers.anthropic.apiVersion",
    "anthropic.apiKey": "providers.anthropic.apiKey",
}
LEGACY_BLOCKS = ("claude", "anthropic")

# Settings that are secrets: shown as set or empty, never by value. A key belongs to a
# provider and a provider can be added from the settings page, so this is a rule rather than
# a list of names.
SECRET_KEYS = ("jupyter.token",)
SECRET_SUFFIXES = (".apiKey",)


def is_secret(dotted: str) -> bool:
    """Is this setting a secret? Every provider key, and the Jupyter token."""
    return dotted in SECRET_KEYS or dotted.endswith(SECRET_SUFFIXES)

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
                 overlay: str = "", studio_file: str = "",
                 env: Optional[Dict[str, str]] = None, dotenv: Optional[Dict[str, str]] = None):
        self.data = data
        self.overrides = overrides      # dotted key -> "environment" | ".env" | STUDIO_SOURCE | overlay path
        self.path = path
        self.overlay = overlay
        self.studio_file = studio_file  # the layer Studio writes; "" when that layer is off
        self.env = env                  # the environment and .env this was loaded from, for reload()
        self.dotenv = dotenv

    def reload(self) -> None:
        """Re-read every layer into this same object, so every module holding `SETTINGS`
        sees what Studio just wrote."""
        fresh = load(self.path, env=self.env, dotenv=self.dotenv, overlay=self.overlay,
                     studio_file=self.studio_file)
        self.data = fresh.data
        self.overrides = fresh.overrides

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

    # ---- providers ----

    @property
    def providers(self) -> Dict[str, Dict[str, Any]]:
        """Every configured provider, by name, in the order the file lists them. A provider
        with `enabled: false` keeps its configuration and is offered nowhere."""
        out: Dict[str, Dict[str, Any]] = {}
        for name, cfg in self.section("providers").items():
            if name != "_" and isinstance(cfg, dict):
                out[name] = cfg
        return out

    def provider_names(self, all_of_them: bool = False) -> List[str]:
        """The providers on offer, in file order. `all_of_them` includes the disabled ones,
        which the settings page still has to show."""
        return [name for name, cfg in self.providers.items()
                if all_of_them or cfg.get("enabled", True)]

    def provider(self, name: str) -> Dict[str, Any]:
        """One provider configuration, or an empty dict when there is no such row."""
        return dict(self.providers.get(name) or {})

    @property
    def default_provider(self) -> str:
        """The provider a model that names none belongs to. An unknown name falls back to the
        first enabled provider, so the platform can never point at a row that is not there."""
        wanted = str(self.get("llm.defaultProvider") or "").strip()
        offered = self.provider_names()
        if wanted in offered:
            return wanted
        return offered[0] if offered else wanted

    # ---- models ----

    @property
    def models(self) -> List[Dict[str, Any]]:
        """Every model on offer. A row that names no provider belongs to the default one,
        which is what lets a model list saved before providers existed keep working."""
        fallback = self.default_provider
        out: List[Dict[str, Any]] = []
        for m in (self.get("models.list") or []):
            if isinstance(m, dict) and m.get("id"):
                entry = dict(m)
                entry["provider"] = str(entry.get("provider") or fallback)
                out.append(entry)
        return out

    def models_for(self, provider: str) -> List[Dict[str, Any]]:
        """The models one provider reaches."""
        return [m for m in self.models if m["provider"] == provider]

    def provider_of(self, alias_or_id: str = "") -> str:
        """Which provider reaches this model. An unknown name means the default model, and
        so the provider that reaches it."""
        alias = self.model_aliases.get(alias_or_id or "", "") or self.default_model
        for m in self.models:
            if m.get("alias") == alias or m["id"] == alias:
                return m["provider"]
        return self.default_provider

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

    @property
    def jupyter_url(self) -> str:
        """Where a browser on this machine finds the Jupyter server that runs a course's
        notebooks. Explicit `jupyter.url` wins; otherwise host and port."""
        explicit = str(self.get("jupyter.url") or "").strip().rstrip("/")
        return explicit or self.local_url(str(self.get("jupyter.host")), int(self.get("jupyter.port")))

    @property
    def jupyter_internal_url(self) -> str:
        """Where Studio itself reaches that server: the same address, unless the two run
        in separate containers and `jupyter.internalUrl` names the service."""
        explicit = str(self.get("jupyter.internalUrl") or "").strip().rstrip("/")
        return explicit or self.jupyter_url

    # ---- for the browser ----

    def page_providers(self) -> List[Dict[str, Any]]:
        """The providers a browser may call itself: enabled, and speaking a wire format
        rather than running a binary. **Never a key** - a built page is a file anyone may be
        given, so the reader supplies their own in Settings.

        `standsInFor` lists the providers whose models this one also serves. A browser cannot
        spawn a process, so a model reached through a local tool would otherwise be
        unreachable from a page opened off disk - even though the same model sits behind an
        API. Which API is a setting (`apiProvider` on the tool's row), not a guess made from
        the model's name.
        """
        twins: Dict[str, List[str]] = {}
        for name, cfg in self.providers.items():
            api = str(cfg.get("apiProvider") or "")
            if api:
                twins.setdefault(api, []).append(name)
        out: List[Dict[str, Any]] = []
        for name, cfg in self.providers.items():
            if not cfg.get("enabled", True) or cfg.get("kind") == "cli":
                continue
            row = {"name": name, "kind": str(cfg.get("kind") or ""),
                   "label": str(cfg.get("label") or name),
                   "apiUrl": str(cfg.get("apiUrl") or ""), "needsKey": True,
                   "standsInFor": twins.get(name, [])}
            if cfg.get("apiVersion"):
                row["apiVersion"] = str(cfg["apiVersion"])
            if cfg.get("maxTokensField"):
                row["maxTokensField"] = str(cfg["maxTokensField"])
            out.append(row)
        return out

    def page(self) -> Dict[str, Any]:
        """CFG.platform: the slice the built page needs. Presentation-free and course-free."""
        out = self.section("page")
        out.update({
            "bridgeUrl": self.bridge_url,
            "providers": self.page_providers(),
            "defaultModel": self.model_id(self.default_model),
            "models": [{"id": m["id"], "label": m.get("label") or m["id"],
                        "provider": m["provider"]} for m in self.models],
        })
        return out

    # ---- for the Studio settings page ----

    def describe(self) -> List[Dict[str, Any]]:
        """Every scalar setting as {key, value, source}, in file order; a secret's value
        is replaced by whether it is set."""
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
                    shown = ("(set)" if value else "") if is_secret(dotted) else value
                    rows.append({"key": dotted, "value": shown,
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


def _apply_env(data: Dict[str, Any], overrides: Dict[str, str], dotenv: Dict[str, str],
               env: Dict[str, str], env_keys: Dict[str, str]) -> None:
    """`.env`, then the environment, over `data`: the scalar knobs in `env_keys`, typed."""
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


def _merge_file(data: Dict[str, Any], overrides: Dict[str, str], path: str, source: str,
                what: str) -> None:
    """One JSON layer over `data`, every key it sets recorded under `source`."""
    try:
        with open(path, encoding="utf-8") as fh:
            extra = json.load(fh)
    except (OSError, ValueError) as exc:
        raise SettingsError("%s %s could not be read: %s" % (what, path, exc)) from exc
    if isinstance(extra, dict):
        for dotted in _leaves(extra):
            overrides[dotted] = source
        _deep_merge(data, extra)


def load(path: str = SETTINGS_FILE, *, env: Optional[Dict[str, str]] = None,
         dotenv: Optional[Dict[str, str]] = None, overlay: Optional[str] = None,
         studio_file: Optional[str] = None,
         env_keys: Optional[Dict[str, str]] = None) -> Settings:
    """Read the defaults, then apply the overlay, Studio's file, `.env` and the environment in
    that order. `studio_file=None` means the default place under the state directory;
    `""` turns that layer off (tests)."""
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
        _merge_file(data, overrides, overlay, overlay, "SETTINGS_FILE")

    # The environment is read once to learn where the state directory is, and again after
    # Studio's file so that it still wins over what Studio wrote.
    _apply_env(data, overrides, dotenv, env, env_keys)
    if studio_file is None:
        studio_file = os.path.join(Settings(data, {}).state_dir, STUDIO_SETTINGS_NAME)
    if studio_file and os.path.isfile(studio_file):
        _merge_file(data, overrides, studio_file, STUDIO_SOURCE, "Studio's settings file")
        _apply_env(data, overrides, dotenv, env, env_keys)
    _absorb_legacy(data, overrides)
    return Settings(data, overrides, path, overlay or "", studio_file or "", env, dotenv)


def _absorb_legacy(data: Dict[str, Any], overrides: Dict[str, str]) -> None:
    """Move a setting written under its older name to where it is read now, then drop the
    older name so there is one place to look. Present at all means deliberately set, so it
    wins over the default it lands on; where it came from is carried across, because that is
    what the settings page shows."""
    for old, new in LEGACY_KEYS.items():
        value = _get(data, old)
        if value is None:
            continue
        _set(data, new, value)
        overrides[new] = overrides.get(old) or ("the older %s" % old)
        overrides.pop(old, None)
    for block in LEGACY_BLOCKS:
        data.pop(block, None)


def _leaves(node: Dict[str, Any], prefix: str = "") -> Iterable[str]:
    for key, value in node.items():
        if isinstance(value, dict):
            yield from _leaves(value, prefix + key + ".")
        else:
            yield prefix + key


SETTINGS = load()

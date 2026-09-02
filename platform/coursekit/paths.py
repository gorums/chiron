"""Where courses and builds live.

The platform is one repository; courses are not part of it. Each course is its own folder -
usually its own git repository - and the platform only needs to know the directory that
holds them. That directory is resolved once, here, and every entry point (the CLI, Studio)
reads it from this module so the rule lives in one place.

Resolution, first match wins:

    COURSES_DIR   environment variable
    COURSES_DIR   line in `.env` at the platform root (the same file compose reads)
    <platform root>/courses            gitignored - a place for course clones

`DIST_DIR` resolves the same way and defaults to `<platform root>/dist`. A relative value in
either place is taken relative to the platform root, so `.env` can say `COURSES_DIR=../courses`
and mean the same thing on every machine that checks the platform out into a sibling folder.

Inside the container both variables are set in the image (see docker/Dockerfile), so a host
path written in `.env` never leaks in: compose mounts the host directory to a fixed path and
the environment points at that.
"""

from __future__ import annotations

import os
from typing import Dict

PLATFORM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(PLATFORM_DIR)
ENV_FILE = os.path.join(REPO_ROOT, ".env")


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


def resolve(name: str, default: str, *, env: Dict[str, str] = None,
            dotenv: Dict[str, str] = None, base: str = REPO_ROOT) -> str:
    """One directory setting: environment, then `.env`, then the default. Relative values are
    anchored at `base`. Always absolute and normalised."""
    env = os.environ if env is None else env
    dotenv = read_env_file() if dotenv is None else dotenv
    value = env.get(name) or dotenv.get(name) or default
    value = os.path.expanduser(value)
    if not os.path.isabs(value):
        value = os.path.join(base, value)
    return os.path.normpath(value)


COURSES_DIR = resolve("COURSES_DIR", os.path.join(REPO_ROOT, "courses"))
DIST_DIR = resolve("DIST_DIR", os.path.join(REPO_ROOT, "dist"))

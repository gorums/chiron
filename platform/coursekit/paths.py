"""Where courses and builds live.

The platform is one repository; courses are not part of it. Each course is its own folder -
usually its own git repository - and the platform only needs to know the directory that
holds them. That directory is resolved once, here, and every entry point (the CLI, Studio)
reads it from this module so the rule lives in one place.

The defaults are `paths.courses` and `paths.dist` in `platform/settings.json`; `COURSES_DIR`
and `DIST_DIR` in the environment or in `.env` at the platform root (the same file compose
reads) override them - see `coursekit.settings`. A relative value in any of those places is
taken relative to the platform root, so `.env` can say `COURSES_DIR=../courses` and mean the
same thing on every machine that checks the platform out into a sibling folder.

Inside the container both variables are set in the image (see docker/Dockerfile), so a host
path written in `.env` never leaks in: compose mounts the host directory to a fixed path and
the environment points at that.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

from .settings import ENV_FILE, PLATFORM_DIR, REPO_ROOT, SETTINGS, read_env_file  # noqa: F401

__all__ = ["PLATFORM_DIR", "REPO_ROOT", "ENV_FILE", "read_env_file", "resolve",
           "COURSES_DIR", "DIST_DIR"]


def resolve(name: str, default: str, *, env: Optional[Dict[str, str]] = None,
            dotenv: Optional[Dict[str, str]] = None, base: str = REPO_ROOT) -> str:
    """One directory setting: environment, then `.env`, then the default. Relative values are
    anchored at `base`. Always absolute and normalised."""
    env = os.environ if env is None else env
    dotenv = read_env_file() if dotenv is None else dotenv
    value = env.get(name) or dotenv.get(name) or default
    value = os.path.expanduser(value)
    if not os.path.isabs(value):
        value = os.path.join(base, value)
    return os.path.normpath(value)


COURSES_DIR = SETTINGS.courses_dir
DIST_DIR = SETTINGS.dist_dir

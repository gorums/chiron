"""The Jupyter server a course's notebooks run on: is it up, and where a page finds it.

Studio runs no kernels itself. A separate Jupyter server - the `jupyter` service in
compose.yaml, or `build.py jupyter` on a machine without Docker - serves the courses
directory, so `courses/<id>/notebooks/<mid>-<n>.ipynb` opens at
`<jupyter>/notebooks/<id>/notebooks/<mid>-<n>.ipynb`. The course page embeds that in a
frame (`web/js/07e-notebooks.js`); this module answers two questions: is the server
reachable, and what should the browser be told (`GET /api/jupyter`).

Both routes share one configuration, `tools/jupyter/jupyter_server_config.py`, which
reads the same settings as everything else (`jupyter.*` in settings.json, overridden by
JUPYTER_PORT, JUPYTER_TOKEN, ...) - so the port Studio tells the page, the port the server
binds, and the origin the server lets frame it never disagree.

The probe is cached for `jupyter.probeCacheSeconds`: `/api/state` is polled, and a dead
server would otherwise cost a timeout per poll. The token reaches the page through
Studio, which binds to loopback, and never through the built HTML - a published copy
must not carry it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request
from typing import Any, Dict, Optional

from coursekit.paths import COURSES_DIR
from coursekit.settings import REPO_ROOT, SETTINGS

from .log import log

PROBE_TIMEOUT = float(SETTINGS.get("jupyter.probeTimeout"))
PROBE_CACHE = float(SETTINGS.get("jupyter.probeCacheSeconds"))
CONFIG_FILE = os.path.join(REPO_ROOT, "tools", "jupyter", "jupyter_server_config.py")

# The last probe: when it ran, and the server version it found (None: not reachable).
_probe = {"at": 0.0, "version": None}


def probe(force: bool = False) -> Optional[str]:
    """The server's version when it answers `/api/` (the one endpoint that needs no
    token), else None. Cached, unless `force`."""
    now = time.time()
    if not force and now - _probe["at"] < PROBE_CACHE:
        return _probe["version"]
    version: Optional[str] = None
    try:
        with urllib.request.urlopen(SETTINGS.jupyter_internal_url + "/api/", timeout=PROBE_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        version = str((data or {}).get("version") or "?")
    except Exception as exc:  # noqa: BLE001 - any failure means "not reachable", which is the answer
        if _probe["version"] is not None:
            log.info("jupyter: no longer reachable at %s (%s)", SETTINGS.jupyter_internal_url, exc)
    if version is not None and _probe["version"] is None:
        log.info("jupyter: %s reachable at %s", version, SETTINGS.jupyter_internal_url)
    _probe.update(at=now, version=version)
    return version


def available() -> bool:
    return probe() is not None


def view() -> Dict[str, Any]:
    """`GET /api/jupyter`: what a served course page needs to embed a notebook, and what
    the Settings page shows."""
    version = probe()
    return {
        "available": version is not None,
        "version": version or "",
        "url": SETTINGS.jupyter_url,
        "internalUrl": SETTINGS.jupyter_internal_url,
        "token": str(SETTINGS.get("jupyter.token") or ""),
        "config": CONFIG_FILE,
        "installed": installed(),
    }


def installed() -> bool:
    """Whether the `notebook` package is importable here - what `build.py jupyter` needs."""
    return importlib.util.find_spec("notebook") is not None


def run() -> int:
    """`build.py jupyter`: start a Jupyter Notebook server on this machine with the
    platform's configuration, serving the courses directory. Blocks until it exits."""
    if not installed():
        print("The notebook package is not installed here. Run:  pip install notebook",
              file=sys.stderr)
        return 1
    env = dict(os.environ, COURSES_DIR=COURSES_DIR)
    argv = [sys.executable, "-m", "notebook", "--config=%s" % CONFIG_FILE, "--no-browser"]
    print("Jupyter for the course platform: %s  (notebooks under %s)"
          % (SETTINGS.jupyter_url, COURSES_DIR))
    print("Open a course from Studio and press \"Run it here\" on a notebook. Ctrl+C stops it.")
    try:
        return subprocess.call(argv, env=env, cwd=REPO_ROOT)
    except KeyboardInterrupt:
        return 0

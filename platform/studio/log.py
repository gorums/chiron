"""Studio's log: what happened, readable from the UI.

A generation run is minutes of subprocess calls, and when one fails the job's event list
says *that* it failed but rarely *why* - the CLI's stderr, the model that was asked for, how
long the call took. This module keeps that record in two places:

- a rotating file under `state/logs/`, so it survives a restart and can be attached to a
  bug report;
- a ring buffer in memory, so the Settings page can show the last few hundred lines without
  reading the file back.

Use the module-level `log` (a standard `logging.Logger`) everywhere in Studio. Nothing here
knows about courses or Claude; it is plumbing.
"""

from __future__ import annotations

import collections
import logging
import logging.handlers
import os
import threading
import time
from typing import Any, Dict, List, Optional

from coursekit.settings import SETTINGS

log = logging.getLogger("studio")

RING_LINES = int(SETTINGS.get("logs.ring"))
PAGE_LINES = int(SETTINGS.get("logs.pageLines"))
MAX_BYTES = int(SETTINGS.get("logs.maxBytes"))
BACKUPS = int(SETTINGS.get("logs.backups"))
DEFAULT_LEVEL = str(SETTINGS.get("logs.level") or "INFO")

_RING = collections.deque(maxlen=RING_LINES)
_LOCK = threading.Lock()
_configured = False


class _Ring(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = {
                "t": record.created,
                "level": record.levelname,
                "where": record.name.split(".")[-1],
                "msg": self.format(record),
            }
        except Exception:  # noqa: BLE001
            return
        with _LOCK:
            _RING.append(line)


def configure(directory: str = "", level: str = "") -> str:
    """Set up file + ring handlers once. Returns the log file path ('' if none)."""
    global _configured
    if _configured:
        return _path(directory)
    _configured = True
    log.setLevel(getattr(logging, (level or DEFAULT_LEVEL).upper(), logging.INFO))
    log.propagate = False

    plain = logging.Formatter("%(message)s")
    ring = _Ring()
    ring.setFormatter(plain)
    log.addHandler(ring)

    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("  %(asctime)s %(levelname)-5s %(message)s", "%H:%M:%S"))
    stream.setLevel(logging.INFO)
    log.addHandler(stream)

    path = _path(directory)
    if path:
        try:
            os.makedirs(directory, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUPS,
                                                      encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s %(name)s %(message)s"))
            log.addHandler(fh)
        except OSError as exc:
            log.warning("Could not open the log file %s: %s", path, exc)
            return ""
    return path


def _path(directory: str) -> str:
    return os.path.join(directory, "studio.log") if directory else ""


def recent(limit: int = 0, level: str = "", contains: str = "") -> List[Dict[str, Any]]:
    """The newest lines, oldest first, optionally filtered."""
    threshold = getattr(logging, (level or "DEBUG").upper(), logging.DEBUG)
    needle = (contains or "").lower()
    with _LOCK:
        rows = list(_RING)
    out = [r for r in rows
           if getattr(logging, r["level"], 0) >= threshold and (not needle or needle in r["msg"].lower())]
    return out[-max(1, min(int(limit or PAGE_LINES), RING_LINES)):]


def clear() -> None:
    with _LOCK:
        _RING.clear()


class Timer:
    """`with Timer() as t: ...; t.ms` - for logging how long a call took."""

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *exc):
        self.ms = int((time.time() - self.start) * 1000)
        return False

    @property
    def elapsed(self) -> str:
        return "%.1fs" % (time.time() - self.start)

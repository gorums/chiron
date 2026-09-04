"""What one running Studio shares between requests: where state lives, the job registry,
the preferences file, the log.

Reader progress, jobs, reviews and trash are kept apart from both the course (which is
content) and `dist/` (which is regenerated). `paths.state` / `paths.progress` in
settings.json name the folders; STUDIO_STATE_ROOT and STUDIO_STATE_DIR override them so a
container can point at a volume of its own.
"""

from __future__ import annotations

import os

from coursekit.settings import SETTINGS

from . import jobs, prefs, progress
from . import log as logmod

STATE_ROOT = SETTINGS.state_dir
PROGRESS_DIR = SETTINGS.progress_dir
JOBS_DIR = os.path.join(STATE_ROOT, "jobs")       # finished jobs, replayable after a restart
TRASH_DIR = os.path.join(STATE_ROOT, "trash")     # removed modules and courses, never deleted
LOGS_DIR = os.path.join(STATE_ROOT, "logs")       # studio.log, rotating
PREFS_PATH = os.path.join(STATE_ROOT, "studio.json")

REGISTRY = jobs.Registry(JOBS_DIR)
PREFS = prefs.Prefs(PREFS_PATH)
LOG_FILE = logmod.configure(LOGS_DIR)


def store() -> progress.Store:
    """The progress store of the active reader profile. Resolved per request, so switching
    profiles in Studio takes effect without a restart."""
    return progress.Store(PROGRESS_DIR, PREFS.profile)

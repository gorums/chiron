"""The shapes of the identifiers Studio puts in paths and URLs.

A course id is also its folder name and the reader's storage key, a module id keys progress
and study data, a profile name is a folder under `state/progress/`. All three become path
segments, so each is checked against one pattern before it goes anywhere near the disk.
"""

from __future__ import annotations

import re

COURSE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}$")
MODULE_ID = re.compile(r"^M\d{2,3}$")
PROFILE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")

DEFAULT_PROFILE = "default"


def is_course_id(value: str) -> bool:
    return bool(COURSE_ID.match(value or ""))


def is_module_id(value: str) -> bool:
    return bool(MODULE_ID.match(value or ""))


def is_profile(value: str) -> bool:
    return bool(PROFILE.match(value or ""))

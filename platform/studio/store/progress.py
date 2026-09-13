"""Server-side copy of a reader's progress.

A built course keeps everything the reader does in the browser's localStorage. That is the
right default for a file opened off disk, but it hides progress from the platform: Studio
cannot say "you are 40% through, continue at M07" if it cannot see the state.

So a course served by Studio syncs its state here. The browser stays the source of truth
while a page is open; this is the durable, platform-visible copy. One JSON file per course
under `state/progress/`, outside `courses/` because progress is the reader's, not the
course's, and outside `dist/` because a rebuild must not erase it.

Device-specific settings (the API key, bridge address) are stripped before storage — they
describe a browser, not a reader, and a key does not belong in a file that may be backed up.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from ..support.files import read_json, write_json
from ..support.ids import DEFAULT_PROFILE, is_course_id, is_profile

# Keys in the page's state object that describe the browser, not the reader.
DEVICE_KEYS = ("bridge", "ui", "theme", "usage")


class Store:
    """The progress files of one reader profile.

    The default profile keeps the original layout, `state/progress/<course>.json`, so nothing
    moves for a platform that has only ever had one reader. Every other profile gets a folder
    of its own under the same directory.
    """

    def __init__(self, directory: str, profile: str = DEFAULT_PROFILE):
        profile = (profile or DEFAULT_PROFILE).strip().lower()
        if not is_profile(profile):
            raise ValueError("Bad profile name.")
        self.root = directory
        self.profile = profile
        self.directory = directory if profile == DEFAULT_PROFILE else os.path.join(directory, profile)

    def path(self, course_id: str) -> str:
        if not is_course_id(course_id):
            raise ValueError("Bad course id.")
        return os.path.join(self.directory, "%s.json" % course_id)

    def delete_everywhere(self, course_id: str) -> int:
        """Forget a course for every profile - used when the course itself is trashed."""
        n = 0
        for prof in profiles(self.root):
            if Store(self.root, prof).delete(course_id):
                n += 1
        return n

    def load(self, course_id: str) -> Optional[Dict[str, Any]]:
        """The stored record: {course, updatedAt, receivedAt, state} — or None."""
        path = self.path(course_id)
        if not os.path.isfile(path):
            return None
        try:
            record = read_json(path)
        except (OSError, ValueError):
            return None
        if not isinstance(record, dict) or not isinstance(record.get("state"), dict):
            return None
        return record

    def save(self, course_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Store a page's state. Returns the record written."""
        if not isinstance(state, dict):
            raise ValueError("State must be a JSON object.")
        clean = {k: v for k, v in state.items() if k not in DEVICE_KEYS}
        record = {
            "course": course_id,
            "updatedAt": number(clean.get("updatedAt")) or int(time.time() * 1000),
            "receivedAt": int(time.time() * 1000),
            "state": clean,
        }
        write_json(self.path(course_id), record, indent=None)
        return record

    def delete(self, course_id: str) -> bool:
        path = self.path(course_id)
        if os.path.isfile(path):
            os.unlink(path)
            return True
        return False

    def summary(self, course_id: str, module_ids) -> Dict[str, Any]:
        """What the library card shows: how far along, and where to pick up."""
        record = self.load(course_id)
        ids = list(module_ids)
        out: Dict[str, Any] = {
            "modules": len(ids), "done": 0, "started": 0, "pct": 0.0,
            "minutes": 0, "cards": 0, "due": 0, "next": ids[0] if ids else None,
            "updatedAt": None,
        }
        if not record:
            return out
        return dict(out, **summarise(record["state"], ids), updatedAt=record["updatedAt"])


def profiles(directory: str) -> list:
    """Every profile that has a folder, plus the default. Sorted, default first."""
    names = set()
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            if is_profile(name) and os.path.isdir(os.path.join(directory, name)):
                names.add(name)
    names.discard(DEFAULT_PROFILE)
    return [DEFAULT_PROFILE] + sorted(names)


def summarise(state: Dict[str, Any], ids) -> Dict[str, Any]:
    """Derive the headline numbers from a page's state, without loading the course."""
    raw = state.get("progress")
    progress = raw if isinstance(raw, dict) else {}
    entry = lambda mid: progress.get(mid) if isinstance(progress.get(mid), dict) else {}  # noqa: E731
    done = [mid for mid in ids if entry(mid).get("done")]
    started = [mid for mid in ids if mid not in done and _touched(entry(mid))]
    seconds = sum(number(entry(mid).get("time")) for mid in ids)
    raw_cards = state.get("cards")
    cards = raw_cards if isinstance(raw_cards, dict) else {}
    today = int(time.time() // 86400)
    due = sum(1 for c in cards.values()
              if isinstance(c, dict) and number(c.get("due")) <= today)
    # Continue where the reader left off: first started module, else first undone one.
    nxt = started[0] if started else next((mid for mid in ids if mid not in done), None)
    streak = state.get("streak") if isinstance(state.get("streak"), dict) else {}
    seen = [int(d) for d in (streak.get("seen") or []) if isinstance(d, (int, float))]
    return {
        "seen": sorted(set(seen))[-400:],
        "done": len(done),
        "started": len(started),
        "pct": (len(done) / len(ids)) if ids else 0.0,
        "minutes": int(seconds // 60),
        "cards": len(cards),
        "due": due,
        "next": nxt,
    }


def _touched(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("time") or entry.get("predict") or entry.get("quiz"):
        return True
    secs = entry.get("secs") or {}
    return isinstance(secs, dict) and any(secs.values())


def number(value: Any) -> float:
    """A float out of whatever the page stored, 0.0 for anything unusable."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0

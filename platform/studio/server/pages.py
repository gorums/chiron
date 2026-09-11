"""Static files: the Studio UI itself, and a built course opened from it.

The design system is served out of `platform/web/` rather than copied into `ui/`, which is
what keeps one `.btn` from meaning two things on the two surfaces.
"""

from __future__ import annotations

import os

from coursekit.paths import DIST_DIR

from .base import route

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(STUDIO_DIR, "ui")

# The design system lives in platform/web/ because the course page inlines it; Studio links
# the same three files at /ui/shared/ rather than keeping a copy that drifts.
_WEB = os.path.join(os.path.dirname(STUDIO_DIR), "web")
SHARED_UI = {
    "tokens.css": os.path.join(_WEB, "css", "tokens.css"),
    "base.css": os.path.join(_WEB, "css", "base.css"),
    "dom.js": os.path.join(_WEB, "js", "core", "dom.js"),
}


class Pages:
    @route("GET", r"/(index\.html)?")
    def ui_index(self):
        self._static(os.path.join(UI_DIR, "index.html"))

    @route("GET", r"/ui/shared/(?P<name>[A-Za-z0-9._-]+)")
    def ui_shared(self, name: str):
        """The tokens, primitives and DOM helpers the course page inlines. Studio links the
        same files, which is what keeps one `.btn` from meaning two things."""
        source = SHARED_UI.get(name)
        if not source:
            return self._fail("Not found", 404)
        self._static(source)

    @route("GET", r"/ui/(?P<path>.+)")
    def ui_file(self, path: str):
        self._static(self._under(UI_DIR, path))

    @route("GET", r"/course/(?P<course_id>[^/]+)/(?P<path>.+)")
    def built_file(self, course_id: str, path: str):
        self._static(self._under(os.path.join(DIST_DIR, course_id), path))

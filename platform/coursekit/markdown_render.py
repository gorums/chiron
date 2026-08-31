"""Markdown to HTML, with the two adjustments a single-file site needs."""

from __future__ import annotations

import re

import markdown

_MD = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "attr_list"])

# Relative links between markdown files cannot resolve inside a one-file site. Keep the
# words, drop the anchor — a dead link is worse than plain text.
_REL_LINK = re.compile(r'<a href="(?!http)[^"]*?"[^>]*>(.*?)</a>', re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def to_html(text: str) -> str:
    _MD.reset()
    return _REL_LINK.sub(r"<em>\1</em>", _MD.convert(text))


def to_text(html: str) -> str:
    """Plain text for search indexing and for the excerpt the tutor is given as context."""
    return _WS.sub(" ", _TAG.sub(" ", html)).strip()


def read_html(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return to_html(fh.read())

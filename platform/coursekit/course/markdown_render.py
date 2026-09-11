"""Markdown to HTML, with the two adjustments a single-file site needs."""

from __future__ import annotations

import re

import markdown

_MD = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "attr_list"])

# Relative links between markdown files cannot resolve inside a one-file site. Keep the
# words, drop the anchor — a dead link is worse than plain text. The one relative link
# that survives is a notebook reference, `notebooks/<name>.ipynb`, which the build turns
# into the notebook itself (see `notebooks.py`).
_REL_LINK = re.compile(r'<a href="(?!http)(?!notebooks/)[^"]*?"[^>]*>(.*?)</a>', re.S)
_TAG = re.compile(r"<[^>]+>")
# A wide table has to scroll sideways in a narrow reading column. Doing that with
# `display:block` on the <table> costs it its own semantics — a screen reader stops
# announcing rows and columns — so the scrolling goes on a wrapper instead.
_TABLE = re.compile(r"<table>(.*?)</table>", re.S)
_WS = re.compile(r"\s+")


def to_html(text: str) -> str:
    _MD.reset()
    html = _REL_LINK.sub(r"<em>\1</em>", _MD.convert(text))
    return _TABLE.sub(r'<div class="tablewrap"><table>\1</table></div>', html)


def to_text(html: str) -> str:
    """Plain text for search indexing and for the excerpt the tutor is given as context."""
    return _WS.sub(" ", _TAG.sub(" ", html)).strip()


def read_html(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return to_html(fh.read())

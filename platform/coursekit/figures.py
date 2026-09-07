"""Figures: an SVG diagram drawn for a section, inlined into the page at build time.

A course cannot ship pictures. It is one HTML file that has to work off disk, so a raster
image would have to travel as a data URI and bloat the page, and a model cannot draw one
anyway. What a model can draw is a diagram - a funnel, a flow, a 2x2, a timeline, a
before/after - as SVG, which is text: small, sharp at any size, themeable, and out of the
way of search. So a figure is an `.svg` under `courses/<id>/figures/`, referenced from
module markdown as an ordinary image on a paragraph of its own:

    ![What the reader should notice](figures/M03-1.svg)

The build replaces that paragraph with the SVG itself inside a `<figure>`. Three things
happen on the way in, and this module is all three:

- **Sanitising.** Model output is trusted for prose and distrusted for structure, and an
  SVG that is inlined into the page runs *inside* the reader's page: `<script>`, event
  attributes, `<foreignObject>`, external references and `<image>` loads are all removed.
  A `<style>` block is removed too - inline SVG styles apply to the whole document, so one
  figure could restyle the page. Colour comes from classes the page's stylesheet defines
  (`fig-1` ... `fig-4`, `fig-soft`, `fig-line`, `fig-muted`) and from `currentColor`.
- **Checking.** A figure that is not well-formed XML, has no `viewBox`, or is larger than
  `build.figureMaxBytes` is reported by `build.py check`, like any other inconsistency.
- **Steps.** Groups marked `<g data-step="1">`, `<g data-step="2">`, ... turn a figure into
  a build-up: the page reveals one step at a time, with Prev / Next and a Play button
  that advances on a timer. That is the animated GIF a course cannot carry, with the
  reader in control of the pace. Everything outside a step group is always visible.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree

from .settings import SETTINGS

FIGURES_DIR = "figures"
MAX_BYTES = int(SETTINGS.get("build.figureMaxBytes"))

# The colour classes the page's stylesheet defines. The authoring prompt and the skill name
# these; anything else a figure carries is left alone, so a hex fill still renders.
COLOUR_CLASSES = ("fig-1", "fig-2", "fig-3", "fig-4", "fig-soft", "fig-line", "fig-muted")

# A figure reference as python-markdown renders `![caption](figures/<name>.svg)`: an <img>
# alone in its paragraph. The name is restricted so a reference can never leave the folder.
FIGURE_NAME = r"[A-Za-z0-9][A-Za-z0-9_.-]*\.svg"
_FIGURE_P = re.compile(
    r"<p>\s*<img\b(?P<attrs>[^>]*?)\bsrc=\"" + FIGURES_DIR + r"/(?P<name>" + FIGURE_NAME + r")\""
    r"(?P<attrs2>[^>]*?)/?>\s*</p>"
)
_ALT = re.compile(r'\balt="([^"]*)"')
_ANY_IMG = re.compile(r"<img\b[^>]*?\bsrc=\"([^\"]*)\"", re.I)

_ATTR_VALUE = r"""(?:"[^"]*"|'[^']*'|[^\s>]+)"""
_XML_DECL = re.compile(r"<\?xml[^>]*\?>|<!DOCTYPE[^>]*>|<!--.*?-->", re.S | re.I)
_DROP_ELEMENTS = re.compile(
    r"<(script|style|foreignObject|image|iframe|object|embed|video|audio)\b.*?</\1\s*>"
    r"|<(script|style|foreignObject|image|iframe|object|embed|video|audio)\b[^>]*/>",
    re.S | re.I,
)
_EVENT_ATTR = re.compile(r"\s+on[a-z]+\s*=\s*" + _ATTR_VALUE, re.I)
_EXTERNAL_HREF = re.compile(r"\s+(?:xlink:)?href\s*=\s*(?:\"(?!#)[^\"]*\"|'(?!#)[^']*')", re.I)
_SVG_ROOT = re.compile(r"<svg\b[^>]*>", re.I)
_VIEWBOX = re.compile(r"\bviewBox\s*=", re.I)
_STEP = re.compile(r"\bdata-step\s*=\s*[\"']?(\d+)")
_ROOT_SIZE = re.compile(r"\s+(?:width|height)\s*=\s*" + _ATTR_VALUE, re.I)


def sanitize(svg: str) -> str:
    """The SVG with everything that could run, load or restyle the page removed.

    Also drops the XML prolog and the root's width/height, so the figure scales to the
    reading column - the `viewBox` carries the aspect ratio.
    """
    text = _XML_DECL.sub("", svg or "").strip()
    text = _DROP_ELEMENTS.sub("", text)
    text = _EVENT_ATTR.sub("", text)
    text = _EXTERNAL_HREF.sub("", text)
    root = _SVG_ROOT.search(text)
    if root:
        head = _ROOT_SIZE.sub("", root.group(0))
        text = text[: root.start()] + head + text[root.end():]
    return text.strip()


def problems(svg: str) -> List[str]:
    """Every reason a figure cannot ship. Empty means it can."""
    out: List[str] = []
    text = (svg or "").strip()
    if not text:
        return ["is empty"]
    root = _SVG_ROOT.search(text)
    if not root or not text.lower().startswith("<svg"):
        return ["does not start with an <svg> element"]
    if not _VIEWBOX.search(root.group(0)):
        out.append("has no viewBox on its <svg> element, so it cannot scale")
    if len(text.encode("utf-8")) > MAX_BYTES:
        out.append("is larger than %d KB" % (MAX_BYTES // 1024))
    try:
        ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        out.append("is not well-formed XML (%s)" % exc)
    return out


def steps_in(svg: str) -> int:
    """How many build-up steps a figure declares: the highest `data-step`, or 0."""
    found = [int(n) for n in _STEP.findall(svg or "")]
    return max(found) if found else 0


def read(figures_dir: str, name: str) -> Dict[str, Any]:
    """One figure off disk: `{name, svg, steps, problem}`. `svg` is sanitised and empty
    when the file is missing or unusable; `problem` says why."""
    path = os.path.join(figures_dir, name)
    if not os.path.isfile(path):
        return {"name": name, "svg": "", "steps": 0, "problem": "is missing from %s/" % FIGURES_DIR}
    with open(path, encoding="utf-8") as fh:
        svg = sanitize(fh.read())
    found = problems(svg)
    if found:
        return {"name": name, "svg": "", "steps": 0, "problem": "; ".join(found)}
    return {"name": name, "svg": svg, "steps": steps_in(svg), "problem": ""}


def markup(fig: Dict[str, Any], caption: str) -> str:
    """The <figure> the page renders, or a visible placeholder for one that cannot ship."""
    if not fig["svg"]:
        return ('<figure class="figure missing"><figcaption>Figure %s/%s %s.</figcaption></figure>'
                % (FIGURES_DIR, fig["name"], fig["problem"]))
    steps = ' data-steps="%d"' % fig["steps"] if fig["steps"] else ""
    cap = "<figcaption>%s</figcaption>" % caption if caption else ""
    return '<figure class="figure" data-fig="%s"%s>%s%s</figure>' % (fig["name"], steps, fig["svg"], cap)


def inline(html: str, figures_dir: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Replace every figure reference in rendered HTML with the figure itself.

    Returns the new HTML and the list of figures it referred to, each with its `problem`
    (empty when fine) so the validator can report what a reader would otherwise see as a
    broken image. Any other <img> is reported too: a one-file site has nothing to load it
    from.
    """
    refs: List[Dict[str, Any]] = []

    def swap(m: "re.Match[str]") -> str:
        fig = read(figures_dir, m.group("name"))
        alt = _ALT.search(m.group("attrs") + m.group("attrs2"))
        refs.append({"name": fig["name"], "steps": fig["steps"], "problem": fig["problem"]})
        return markup(fig, alt.group(1) if alt else "")

    out = _FIGURE_P.sub(swap, html)
    for src in _ANY_IMG.findall(out):
        refs.append({"name": src, "steps": 0,
                     "problem": "is not a figures/<name>.svg reference - the only image a "
                                "one-file site can carry"})
    return out, refs


def names_for(figures_dir: str, mid: str) -> List[str]:
    """The figure files a module owns, `<mid>-<n>.svg`, in numeric order."""
    if not os.path.isdir(figures_dir):
        return []
    prefix = mid + "-"
    owned = [n for n in os.listdir(figures_dir)
             if n.startswith(prefix) and n.endswith(".svg") and n[len(prefix):-4].isdigit()]
    return sorted(owned, key=lambda n: int(n[len(prefix):-4]))


def first_problem(svg: str) -> Optional[str]:
    """The first thing wrong with a figure as a model returned it, or None when it is fine."""
    found = problems(sanitize(svg))
    return found[0] if found else None

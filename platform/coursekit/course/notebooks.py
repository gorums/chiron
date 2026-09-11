"""Notebooks: a Jupyter notebook that belongs to a section, shown in the page and run there.

A course that teaches something the reader learns by running code - a language, data
analysis, statistics, a numerical method - wants the notebook next to the prose, not a
link out to one. A course cannot ship a kernel, but it can ship the notebook: `.ipynb` is
JSON, so `courses/<id>/notebooks/<mid>-<n>.ipynb` is text like everything else in a
course. A module refers to it on a paragraph of its own, as an ordinary link:

    [Try it: fit the line yourself](notebooks/M03-1.ipynb)

The build replaces that paragraph with a `<div class="notebook">` holding a read-only
rendering of every cell - the markdown, the code, and the outputs saved in the file - so
the notebook reads well off disk and in a published copy. When the page is served by
Studio and a Jupyter server is running (`studio/jupyter.py`), the page swaps that
rendering for the live notebook in a frame, where the reader runs and edits it. The file
is the same one, so what they save is what the course carries.

Only a course whose `course.json` declares `notebooks` may refer to one: the runtime is
a course-level decision (which kernel, which packages), and a reference in a course
without it is a `check` failure, not a silent dead link.

Three things happen on the way in, as with a figure:

- **Reading.** The file must be JSON in nbformat 4 with a list of cells, under
  `build.notebookMaxBytes`. Nothing else is trusted: an unknown cell type is skipped.
- **Rendering.** Markdown cells go through the module's own renderer. Code and text
  outputs are escaped. An image output (`image/png`, `image/jpeg`) becomes a data URI -
  the one image a one-file site can carry besides an SVG figure. Anything that could run
  (`text/html`, `application/javascript`) is dropped: a notebook is model output too,
  and it would render inside the reader's page.
- **The excerpt.** The tutor is given the code of a section's notebooks separately
  (`code` on each reference, capped at `build.notebookPromptChars`), so it can talk about
  the cell the reader is stuck on.
"""

from __future__ import annotations

import html as htmlmod
import json
import os
import re
from typing import Any, Dict, List, Tuple

from .markdown_render import to_html, to_text
from ..settings import SETTINGS

NOTEBOOKS_DIR = "notebooks"
MAX_BYTES = int(SETTINGS.get("build.notebookMaxBytes"))
OUTPUT_CHARS = int(SETTINGS.get("build.notebookOutputChars"))
PROMPT_CHARS = int(SETTINGS.get("build.notebookPromptChars"))

NBFORMAT = 4
# What a reference looks like once python-markdown has rendered `[caption](notebooks/x.ipynb)`:
# an <a> alone in its paragraph. The name is restricted so a reference can never leave the
# folder. `markdown_render` leaves exactly these links alone (every other relative link is
# reduced to its words, because a one-file site cannot resolve it).
NOTEBOOK_NAME = r"[A-Za-z0-9][A-Za-z0-9_.-]*\.ipynb"
_NOTEBOOK_P = re.compile(
    r"<p>\s*<a\b[^>]*?\bhref=\"" + NOTEBOOKS_DIR + r"/(?P<name>" + NOTEBOOK_NAME + r")\"[^>]*>"
    r"(?P<caption>.*?)</a>\s*</p>",
    re.S,
)
_IMAGE_TYPES = ("image/png", "image/jpeg")
NO_RUNTIME = ('is referred to, but course.json declares no notebooks runtime - add '
              '"notebooks": {"kernel": "python3"} to the manifest')


def _escape(text: str) -> str:
    return htmlmod.escape(text, quote=False)


def _joined(value: Any) -> str:
    """nbformat stores text as a string or a list of lines; either way, one string."""
    if isinstance(value, list):
        return "".join(str(v) for v in value)
    return str(value or "")


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + "\n…"


def problems(text: str) -> List[str]:
    """Every reason a notebook cannot ship. Empty means it can."""
    raw = (text or "").strip()
    if not raw:
        return ["is empty"]
    if len(raw.encode("utf-8")) > MAX_BYTES:
        return ["is larger than %d KB" % (MAX_BYTES // 1024)]
    try:
        nb = json.loads(raw)
    except ValueError as exc:
        return ["is not valid JSON (%s)" % exc]
    if not isinstance(nb, dict) or nb.get("nbformat") != NBFORMAT:
        return ["is not an nbformat %d notebook" % NBFORMAT]
    if not isinstance(nb.get("cells"), list):
        return ["has no cells list"]
    if not nb["cells"]:
        return ["has no cells"]
    return []


def cells_of(nb: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The cells worth rendering: `{type, source, outputs, count}`, unknown types skipped."""
    out: List[Dict[str, Any]] = []
    for cell in nb.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        kind = cell.get("cell_type")
        if kind not in ("markdown", "code"):
            continue
        source = _joined(cell.get("source")).strip("\n")
        if not source.strip():
            continue
        outputs = cell.get("outputs") if isinstance(cell.get("outputs"), list) else []
        out.append({"type": kind, "source": source, "outputs": outputs,
                    "count": cell.get("execution_count")})
    return out


def code_of(nb: Dict[str, Any]) -> str:
    """The code cells, one after another, for the tutor's context."""
    parts = [c["source"] for c in cells_of(nb) if c["type"] == "code"]
    return _clip("\n\n".join(parts), PROMPT_CHARS)


def _output_html(output: Any) -> str:
    if not isinstance(output, dict):
        return ""
    kind = output.get("output_type")
    if kind == "stream":
        return '<pre class="nb-out">%s</pre>' % _escape(_clip(_joined(output.get("text")), OUTPUT_CHARS))
    if kind == "error":
        line = "%s: %s" % (output.get("ename", "Error"), output.get("evalue", ""))
        return '<pre class="nb-out nb-err">%s</pre>' % _escape(_clip(line, OUTPUT_CHARS))
    if kind in ("execute_result", "display_data"):
        data = output.get("data") if isinstance(output.get("data"), dict) else {}
        for mime in _IMAGE_TYPES:
            if mime in data:
                b64 = re.sub(r"\s+", "", _joined(data[mime]))
                return '<img class="nb-img" alt="Output" src="data:%s;base64,%s">' % (mime, b64)
        if "text/plain" in data:
            return '<pre class="nb-out">%s</pre>' % _escape(_clip(_joined(data["text/plain"]), OUTPUT_CHARS))
    return ""


def static_html(nb: Dict[str, Any]) -> str:
    """The read-only rendering of every cell, for a page with no kernel to run them."""
    parts: List[str] = []
    for cell in cells_of(nb):
        if cell["type"] == "markdown":
            parts.append('<div class="nb-md">%s</div>' % to_html(cell["source"]))
            continue
        count = cell["count"]
        label = "In [%s]" % (count if isinstance(count, int) else " ")
        outputs = "".join(_output_html(o) for o in cell["outputs"])
        parts.append('<div class="nb-cell"><span class="nb-n">%s</span>'
                     '<pre class="nb-code"><code>%s</code></pre>%s</div>'
                     % (label, _escape(cell["source"]), outputs))
    return "".join(parts)


def read(notebooks_dir: str, name: str) -> Dict[str, Any]:
    """One notebook off disk: `{name, cells, code, html, problem}`. `html` is empty and
    `problem` says why when the file is missing or unusable."""
    empty = {"name": name, "cells": 0, "code": "", "html": ""}
    path = os.path.join(notebooks_dir, name)
    if not os.path.isfile(path):
        return dict(empty, problem="is missing from %s/" % NOTEBOOKS_DIR)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    found = problems(text)
    if found:
        return dict(empty, problem="; ".join(found))
    nb = json.loads(text)
    cells = cells_of(nb)
    return {"name": name, "cells": len(cells), "code": code_of(nb), "html": static_html(nb),
            "problem": ""}


def markup(rec: Dict[str, Any], caption: str) -> str:
    """The block the page renders, or a visible placeholder for one that cannot ship."""
    if rec.get("problem"):
        return ('<div class="notebook missing"><div class="nb-head"><span class="nb-title">'
                'Notebook %s/%s %s.</span></div></div>' % (NOTEBOOKS_DIR, rec["name"], rec["problem"]))
    title = _escape(caption) if caption else rec["name"]
    return ('<div class="notebook" data-nb="%s" data-cells="%d">'
            '<div class="nb-head"><span class="nb-title">%s</span><span class="nb-tools"></span></div>'
            '<div class="nb-static">%s</div></div>'
            % (rec["name"], rec["cells"], title, rec["html"]))


def inline(html: str, notebooks_dir: str, allowed: bool) -> Tuple[str, List[Dict[str, Any]]]:
    """Replace every notebook reference in rendered HTML with the notebook's rendering.

    Returns the new HTML and the references, each `{name, cells, code, problem}` (the
    problem empty when fine) so the validator can report what a reader would otherwise
    see as a broken block. With `allowed` false - a course whose manifest declares no
    notebooks - every reference is a problem.
    """
    refs: List[Dict[str, Any]] = []

    def swap(m: "re.Match[str]") -> str:
        name = m.group("name")
        caption = to_text(m.group("caption"))
        rec = read(notebooks_dir, name) if allowed else {"name": name, "cells": 0, "code": "",
                                                          "html": "", "problem": NO_RUNTIME}
        refs.append({"name": name, "cells": rec["cells"], "code": rec["code"],
                     "problem": rec["problem"]})
        return markup(rec, caption)

    return _NOTEBOOK_P.sub(swap, html), refs


def names_for(notebooks_dir: str, mid: str) -> List[str]:
    """The notebook files a module owns, `<mid>-<n>.ipynb`, in numeric order."""
    if not os.path.isdir(notebooks_dir):
        return []
    prefix = mid + "-"
    owned = [n for n in os.listdir(notebooks_dir)
             if n.startswith(prefix) and n.endswith(".ipynb") and n[len(prefix):-6].isdigit()]
    return sorted(owned, key=lambda n: int(n[len(prefix):-6]))


def first_problem(text: str) -> str:
    """The first thing wrong with a notebook as a file, or an empty string when it is fine."""
    found = problems(text)
    return found[0] if found else ""

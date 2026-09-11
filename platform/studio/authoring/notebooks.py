"""Notebooks for one module: ask the model for them, keep the usable ones, put them in the text.

A notebook is `courses/<id>/notebooks/<mid>-<n>.ipynb`, referenced from the module
markdown on a paragraph of its own (`coursekit.course.notebooks` explains the contract the
build enforces). This module is the writer, the twin of `figures.py`: it asks for a
notebook or two that belong to named sections, drops any that would not pass the build,
replaces whatever notebooks the module had before, and inserts one reference line at the
end of each named section. Only a course whose manifest declares `notebooks` gets any.

The reply is not JSON. Code inside a JSON string means escaping every quote and newline
of a dozen cells, and one slip costs the call; a delimited text format (`=== NOTEBOOK`,
two header lines, then `--- markdown` / `--- code` cells) parses notebook by notebook and
cell by cell. The `.ipynb` is assembled here, from cells the model never had to quote.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from coursekit.course import loader as ck_loader
from coursekit.course import notebooks as ck_notebooks
from coursekit.course.config import DEFAULT_KERNEL
from coursekit.settings import SETTINGS

from .. import modelcall
from . import overrides, prompts
from .coerce import fix_notebooks
from .figures import insert_reference
from ..support.files import write_json
from ..support.files import write_text
from ..store.jobs import Job

NOTEBOOKS_PER_MODULE = int(SETTINGS.get("generation.notebooksPerModule"))
NOTEBOOK_CELLS = int(SETTINGS.get("generation.notebookCells"))

_BLOCK = re.compile(r"^=== NOTEBOOK\s*$", re.M)
_HEADER = re.compile(r"^(section|caption)\s*:\s*(.*)$", re.I)
_CELL = re.compile(r"^--- (markdown|code)\s*$", re.M)
_REFERENCE = re.compile(
    r"^\[[^\]\n]*\]\(" + ck_notebooks.NOTEBOOKS_DIR + r"/(?P<name>[^)\s]+)\)\s*$", re.M)

# What nbformat wants to know about the kernel, for the ones a course is likely to name.
_LANGUAGES = {"python": "python", "ir": "R", "julia": "julia", "bash": "bash"}


def enabled() -> bool:
    """Notebooks are written during generation when settings ask for at least one per module."""
    return NOTEBOOKS_PER_MODULE > 0


def parse_reply(text: str) -> List[Dict[str, Any]]:
    """The raw notebooks out of a delimited reply: `{section, caption, cells}` each, with
    `cells` as `{type, source}`, untrusted."""
    out: List[Dict[str, Any]] = []
    for chunk in _BLOCK.split(modelcall.strip_fence(text or ""))[1:]:
        nb: Dict[str, Any] = {"section": "", "caption": "", "cells": []}
        lines = chunk.strip("\n").split("\n")
        while lines:
            head = _HEADER.match(lines[0].strip())
            if not head:
                break
            nb[head.group(1).lower()] = head.group(2).strip()
            lines.pop(0)
        pieces = _CELL.split("\n".join(lines))
        # pieces: [preamble, type, body, type, body, ...]
        for kind, body in zip(pieces[1::2], pieces[2::2]):
            source = body.strip("\n").rstrip()
            if source.strip():
                nb["cells"].append({"type": kind, "source": source})
        if nb["cells"]:
            out.append(nb)
    return out


def make_notebook(cells: List[Dict[str, str]], kernel: str = DEFAULT_KERNEL) -> Dict[str, Any]:
    """An nbformat 4 notebook holding `cells`, with no outputs - the reader makes those."""
    language = next((lang for key, lang in _LANGUAGES.items() if kernel.lower().startswith(key)),
                    kernel)
    rows = []
    for n, cell in enumerate(cells, start=1):
        row: Dict[str, Any] = {"id": "cell-%d" % n, "cell_type": cell["type"], "metadata": {},
                               "source": cell["source"]}
        if cell["type"] == "code":
            row.update(outputs=[], execution_count=None)
        rows.append(row)
    return {
        "nbformat": ck_notebooks.NBFORMAT,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"name": kernel, "display_name": kernel, "language": language},
            "language_info": {"name": language},
        },
        "cells": rows,
    }


def strip_references(body: str, mid: str) -> str:
    """The module text without any reference to this module's own notebooks."""
    prefix = mid + "-"

    def keep(m: "re.Match[str]") -> str:
        return "" if m.group("name").startswith(prefix) else m.group(0)

    text = _REFERENCE.sub(keep, body)
    return re.sub(r"\n{3,}", "\n\n", text)


def references_in(body: str, mid: str) -> List[str]:
    prefix = mid + "-"
    return [m.group("name") for m in _REFERENCE.finditer(body) if m.group("name").startswith(prefix)]


def notebooks_prompt(plan: Dict[str, Any], mod: Dict[str, Any], body: str,
                     headings: List[str], count: int = 0, root: str = "") -> str:
    """The prompt this module's notebooks are written from - the course's own where it has
    one. The kernel and packages come from the course, so an override that names them freezes
    what the settings tab can change."""
    runtime = plan.get("notebooks") or {}
    count = count or NOTEBOOKS_PER_MODULE
    default = prompts.notebooks(plan, mod, body, headings, count, NOTEBOOK_CELLS,
                                str(runtime.get("kernel") or DEFAULT_KERNEL),
                                list(runtime.get("packages") or []))
    return overrides.apply(root, mod["id"], "notebooks", default, body=body)


def write_notebooks(job: Job, root: str, plan: Dict[str, Any], mod: Dict[str, Any], body: str,
                    path: str, model: str = "", count: int = 0) -> str:
    """Ask for this module's notebooks, write the files, put the references in, save the text.

    Whatever notebooks the module had are replaced: their files are removed and their
    reference lines dropped before the new ones go in. Returns the new body, which is
    also what is now on disk at `path`. `plan["notebooks"]` names the kernel and packages.
    """
    mid = mod["id"]
    count = count or NOTEBOOKS_PER_MODULE
    runtime = plan.get("notebooks") or {}
    kernel = str(runtime.get("kernel") or DEFAULT_KERNEL)
    headings = [s.heading for s in ck_loader.parse_sections(body)]
    reply = modelcall.ask(
        notebooks_prompt(plan, mod, body, headings, count, root),
        model=model, timeout=modelcall.timeout_for("notebooks"),
        what="the notebooks for %s" % mid)
    fixed = fix_notebooks(parse_reply(reply), headings, count, NOTEBOOK_CELLS)

    notebooks_dir = os.path.join(root, ck_notebooks.NOTEBOOKS_DIR)
    for name in ck_notebooks.names_for(notebooks_dir, mid):
        os.remove(os.path.join(notebooks_dir, name))
    text = strip_references(body, mid)
    for n, nb in enumerate(fixed, start=1):
        name = "%s-%d.ipynb" % (mid, n)
        write_json(os.path.join(notebooks_dir, name), make_notebook(nb["cells"], kernel))
        text = insert_reference(text, nb["section"],
                                "[%s](%s/%s)" % (nb["caption"], ck_notebooks.NOTEBOOKS_DIR, name))
    write_text(path, text)
    job.emit("notebooks", id=mid, count=len(fixed),
             cells=sum(len(nb["cells"]) for nb in fixed), sections=[nb["section"] for nb in fixed])
    return text

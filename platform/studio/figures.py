"""Figures for one module: ask the model for them, keep the usable ones, put them in the text.

A figure is an SVG under `courses/<id>/figures/<mid>-<n>.svg`, referenced from the module
markdown on a paragraph of its own (`coursekit.figures` explains the contract the build
enforces). This module is the writer: it asks for a few diagrams that belong to named
sections, drops any that would not pass the build, replaces whatever figures the module
had before, and inserts one reference line at the end of each named section.

The reply is not JSON. An SVG is XML, and asking a model to escape every quote of a
2 KB document inside a JSON string is asking for a parse failure; a delimited text format
(`=== FIGURE`, two header lines, the SVG) parses figure by figure, so one broken drawing
costs one figure and not the call.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from coursekit import figures as ck_figures
from coursekit import loader as ck_loader
from coursekit.settings import SETTINGS

from . import modelcall, overrides, prompts
from .coerce import fix_figures
from .files import write_text
from .jobs import Job

FIGURES_PER_MODULE = int(SETTINGS.get("generation.figuresPerModule"))
FIGURE_STEPS = int(SETTINGS.get("generation.figureSteps"))

_BLOCK = re.compile(r"^=== FIGURE\s*$", re.M)
_HEADER = re.compile(r"^(section|caption)\s*:\s*(.*)$", re.I)
_REFERENCE = re.compile(r"^!\[[^\]\n]*\]\(" + ck_figures.FIGURES_DIR + r"/(?P<name>[^)\s]+)\)\s*$", re.M)


def enabled() -> bool:
    """Figures are drawn during generation when settings ask for at least one per module."""
    return FIGURES_PER_MODULE > 0


def parse_reply(text: str) -> List[Dict[str, str]]:
    """The raw figures out of a delimited reply: `{section, caption, svg}` each, untrusted."""
    out: List[Dict[str, str]] = []
    for chunk in _BLOCK.split(modelcall.strip_fence(text or ""))[1:]:
        fig = {"section": "", "caption": "", "svg": ""}
        lines = chunk.strip("\n").split("\n")
        while lines:
            head = _HEADER.match(lines[0].strip())
            if not head:
                break
            fig[head.group(1).lower()] = head.group(2).strip()
            lines.pop(0)
        fig["svg"] = "\n".join(lines).strip()
        if fig["svg"]:
            out.append(fig)
    return out


def strip_references(body: str, mid: str) -> str:
    """The module text without any reference to this module's own figures."""
    prefix = mid + "-"

    def keep(m: "re.Match[str]") -> str:
        return "" if m.group("name").startswith(prefix) else m.group(0)

    text = _REFERENCE.sub(keep, body)
    return re.sub(r"\n{3,}", "\n\n", text)


def insert_reference(body: str, heading: str, line: str) -> str:
    """`line` appended to the body of the `##` section called `heading`, before its trailing
    rule; the text is returned unchanged when no such section exists."""
    parts = body.split("\n## ")
    for i, chunk in enumerate(parts[1:], start=1):
        name = chunk.split("\n", 1)[0].strip()
        if name != heading:
            continue
        text = chunk.rstrip()
        tail = ""
        rule = re.search(r"\n---\s*$", text)
        if rule:
            text, tail = text[: rule.start()].rstrip(), "\n\n---"
        parts[i] = text + "\n\n" + line + tail + "\n"
        return "\n## ".join(parts)
    return body


def references_in(body: str, mid: str) -> List[str]:
    prefix = mid + "-"
    return [m.group("name") for m in _REFERENCE.finditer(body) if m.group("name").startswith(prefix)]


def figures_prompt(plan: Dict[str, Any], mod: Dict[str, Any], body: str,
                   headings: List[str], count: int = 0, root: str = "") -> str:
    """The prompt this module's figures are drawn from - the course's own where it has one."""
    count = count or FIGURES_PER_MODULE
    return overrides.apply(root, mod["id"], "figures",
                           prompts.figures(plan, mod, body, headings, count, FIGURE_STEPS),
                           body=body)


def write_figures(job: Job, root: str, plan: Dict[str, Any], mod: Dict[str, Any], body: str,
                  path: str, model: str = "", count: int = 0) -> str:
    """Ask for this module's figures, write the files, put the references in, save the text.

    Whatever figures the module had are replaced: their files are removed and their
    reference lines dropped before the new ones go in. Returns the new body, which is also
    what is now on disk at `path`.
    """
    mid = mod["id"]
    count = count or FIGURES_PER_MODULE
    headings = [s.heading for s in ck_loader.parse_sections(body)]
    reply = modelcall.ask(figures_prompt(plan, mod, body, headings, count, root),
                           model=model, timeout=modelcall.timeout_for("figures"),
                           what="the figures for %s" % mid)
    fixed = fix_figures(parse_reply(reply), headings, count)

    figures_dir = os.path.join(root, ck_figures.FIGURES_DIR)
    for name in ck_figures.names_for(figures_dir, mid):
        os.remove(os.path.join(figures_dir, name))
    text = strip_references(body, mid)
    for n, fig in enumerate(fixed, start=1):
        name = "%s-%d.svg" % (mid, n)
        write_text(os.path.join(figures_dir, name), fig["svg"])
        text = insert_reference(text, fig["section"],
                                "![%s](%s/%s)" % (fig["caption"], ck_figures.FIGURES_DIR, name))
    write_text(path, text)
    job.emit("figures", id=mid, count=len(fixed), steps=sum(1 for f in fixed if f["steps"]),
             sections=[f["section"] for f in fixed])
    return text

"""Figures and notebooks: the two things a course carries that are not prose.

Both come back in a delimited text format rather than JSON. An SVG inside a JSON string,
or a cell of Python, is a parse failure waiting to happen - and a model that has to escape
its own output writes worse output.
"""

from __future__ import annotations

from typing import Any, Dict, List


FIGURES_FORMAT = """=== FIGURE
section: <one of the module's `##` headings, verbatim>
caption: <one sentence: what the reader should notice in it>
<svg viewBox='0 0 800 450'> ... </svg>"""


def figures(cfg: Dict[str, Any], spec: Dict[str, Any], body: str, headings: List[str],
            count: int, max_steps: int) -> str:
    """Diagrams for a module, as SVG the build can inline (see `coursekit.course.figures`).

    A picture earns its place when it shows a structure the prose can only list: a flow,
    a funnel, a 2x2, a timeline, a before/after, the parts of a thing and how they touch.
    Colour comes from the page's classes so the figure reads in both themes; a build-up
    with `data-step` groups is the moving picture a one-file course can carry.
    """
    listing = "\n".join("  - " + h for h in headings)
    return f"""Draw up to {count} figures for module {spec['id']}, "{spec['title']}", of "{cfg['title']}",
a course on {cfg['subject']} for {cfg['audience']}.

A figure earns its place only where a picture shows something the prose can only list: a
flow or sequence, a funnel, a 2x2, a timeline, a before/after, the parts of a thing and how
they connect, a quantity that dwarfs another. Do not draw a decoration, a list in boxes, or
anything a sentence says just as well. Fewer good figures beat {count} weak ones; zero is a
valid answer for a module that has nothing to draw.

Where a figure goes is part of what makes it stick:
- "Core concepts": one figure of the module's mental model - a picture and its words are
  stored twice and recalled either way. It lands right after the paragraph that
  introduces the structure.
- "How it works in practice": a build-up (steps, below) for a sequence, with a caption
  that tells the reader to guess the next stage before pressing Next - a guess corrected
  on the spot is remembered; a diagram scanned is not.
- "Common mistakes": a wrong/right or before/after contrast in ONE frame.
- Never "Why this matters", "2026 reality check" or "If you remember one thing": the last
  is retrieval, and a picture there hands over the answer the reader should be recalling.
- The caption says what to notice, or asks it ("Which stage would you cut?") - never the
  title again. A figure that restates its paragraph in boxes is redundancy, and redundant
  material is read less carefully, not more.

The module's sections, one of which each figure belongs to (spell the name exactly):
{listing}

Each figure is a single SVG element, written to these rules - the build rejects a figure
that breaks them:
- Start with `<svg viewBox='0 0 800 450'>` (or a taller box up to 800x600). No width or
  height attributes, no xmlns needed, no XML declaration.
- Use SINGLE quotes for every attribute value.
- Colour comes only from these class names, which the page defines for light and dark
  themes: `fig-1` `fig-2` `fig-3` `fig-4` (four strong fills, in that order of importance),
  `fig-soft` (a quiet fill for boxes and bands), `fig-line` (a stroke for connectors and
  frames; it sets fill to none), `fig-muted` (secondary text). Text and arrows are
  `fill='currentColor'` / `stroke='currentColor'`. Never a hex colour, never `<style>`.
- Text: `<text>` elements only, font-size 15 to 24, at most 40 words in the whole figure,
  no line longer than the space it sits in. Every label must be legible at half size.
- No `<script>`, `<image>`, `<foreignObject>`, links, or external references. Only the
  entities &amp; &lt; &gt; - write an arrow as a path, not a character.
- Keep each under 8 KB. Simple shapes, generous spacing, one idea per figure.
- Give the SVG a `<title>` as its first child: the caption, for screen readers.

A figure that builds up in steps is stronger for a sequence or a cause-and-effect: wrap
each stage in `<g data-step='1'>`, `<g data-step='2'>`, ... up to {max_steps}, in the order
they should appear. The page reveals them one at a time, with the reader in control, and
can play them like a short animation. Anything outside a step group is always visible -
put the frame and the axis there, and the moving parts in the steps. Use steps only where
the order itself teaches something.

The module:
\"\"\"
{body[:20000]}
\"\"\"

Return the figures one after another in exactly this format, nothing before the first
`=== FIGURE` and nothing after the last SVG. No code fence, no commentary:
{FIGURES_FORMAT}"""


NOTEBOOKS_FORMAT = """=== NOTEBOOK
section: <the section heading, spelled exactly>
caption: <one line: what the reader will do or find out, under 15 words>
--- markdown
<a short cell of markdown: what to do, what to look at>
--- code
<a code cell>
--- code
<another code cell>
=== NOTEBOOK
..."""


def notebooks(cfg: Dict[str, Any], spec: Dict[str, Any], body: str, headings: List[str],
              count: int, max_cells: int, kernel: str, packages: List[str]) -> str:
    """Jupyter notebooks for a module, as delimited cells the writer assembles into
    `.ipynb` files (see `studio/notebooks.py`).

    A notebook earns its place where the reader learns by running and changing code: the
    worked example made live, the exercise with its data set up, the claim the reader
    can test. It is written cell by cell, never as JSON, so a stray quote costs nothing.
    """
    listing = "\n".join("  - " + h for h in headings)
    stack = ", ".join(packages) if packages else "the standard library only"
    return f"""Write up to {count} Jupyter notebooks for module {spec['id']}, "{spec['title']}", of
"{cfg['title']}", a course on {cfg['subject']} for {cfg['audience']}. The reader runs and
edits them inside the module, next to the prose, on the `{kernel}` kernel with {stack}
available.

A notebook earns its place where running the code teaches what reading cannot: the
worked example made live, so the reader changes a number and sees what moves; the
exercise with its data already set up, so the reader writes only the part that matters;
a claim the module makes that the reader can test. Do not write a notebook that only
prints what the prose already said. Fewer good notebooks beat {count} weak ones; zero is
a valid answer for a module with nothing to run.

Where a notebook goes is part of what makes it stick:
- "Exercise" is the home: the exercise with its data set up and the part that matters left
  as `# your turn`, producing a number, a plot or a working function the reader keeps.
- "Core concepts" only as the worked example made live: the whole thing running, then the
  same cell with one step removed for the reader to fill in.
- "Common mistakes": a cell that raises, or returns the plausible wrong number, and a line
  asking why - fixing a broken thing is remembered longer than reading about the mistake.
- Never "Why this matters", "2026 reality check" or "If you remember one thing".

The module's sections, one of which each notebook belongs to (spell the name exactly):
{listing}

Rules for each notebook:
- At most {max_cells} cells. Open with one markdown cell saying what to do, what to
  notice, and asking the reader to predict what the first code cell will print or plot
  BEFORE they run it - predict, run, compare is what makes the result stick. Then code
  cells that run top to bottom without input, each small enough to read at a glance, with
  a comment where the reader should change something.
- Every code cell must run as written on {kernel} with {stack}: no files that do not
  exist, no network, no packages beyond those. Make the data inline or generate it.
- Leave one clearly marked cell for the reader to complete (`# your turn`), with the
  scaffolding around it already working.
- End with a markdown cell that asks the question the run should have answered, to be
  written down in a sentence - explaining the result is what turns a run into knowledge.
- Plain Python (or the kernel's language), no notebook magics, no shell escapes.

The module:
\"\"\"
{body[:20000]}
\"\"\"

Return the notebooks one after another in exactly this format, nothing before the first
`=== NOTEBOOK` and nothing after the last cell. No code fence around the whole reply, no
commentary:
{NOTEBOOKS_FORMAT}"""

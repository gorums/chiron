"""Writing one module's text: from a brief, from a topic, or as a patch of what is there.

`module` is the prompt a run sends per module. `patch_module` is its opposite number: the
module as it stands goes in and comes back with only the notes applied, because a full
rewrite regenerates every sentence and creates new findings while fixing the last ones.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .common import VOICE, course_context


def module(cfg: Dict[str, Any], modules: List[Dict[str, Any]], spec: Dict[str, Any]) -> str:
    sections = "\n".join("## " + s for s in spec["sections"])
    requires = [r for r in (spec.get("requires") or []) if r != spec["id"]]
    requires_line = ("**Requires:** " + ", ".join(requires) + "\n") if requires else ""
    return f"""Write module {spec['id']} of this course, in full.

{course_context(cfg, modules)}

The module to write:
  id:       {spec['id']}
  title:    {spec['title']}
  minutes:  {spec['minutes']}
  intent:   {spec.get('summary', '')}
  builds on: {", ".join(requires) if requires else "nothing in particular"}

{VOICE}

Output format - a single markdown document, exactly this shape:

# {spec['id']} — {spec['title']}

**Time:** {spec['minutes']} minutes (read · exercise · recall)
{requires_line}
---

{sections}

Hard requirements:
- The first line is exactly `# {spec['id']} — {spec['title']}` with an em dash.
- The `**Time:**` line must be present and start with the number {spec['minutes']}.
{"- Keep the `**Requires:**` line exactly as shown, directly under the time line." if requires else ""}
- Use exactly the `##` headings listed above, in that order, spelled identically. Do not add,
  remove, rename or reorder them. Every one must have real content under it - an empty
  heading is dropped by the build and breaks the course.
- Use `###` subheadings inside "Core concepts" to separate ideas.
- Aim for {max(900, int(spec['minutes']) * 20)}-{int(spec['minutes']) * 33} words overall.

What each section is for:
- Why this matters: the 30-second case. Name the specific mistake this module prevents.
- Core concepts: the actual teaching. Definitions, the arithmetic, worked examples with
  real numbers. Use a blockquote for any definition worth memorising.
- How it works in practice: the Tuesday-afternoon version. Sequence, tools, what it looks
  like on a real screen.
- 2026 reality check: what changed recently that older material gets wrong. Date the claim.
  If this subject genuinely moves slowly, say so and explain what people wrongly believe
  has changed.
- Common mistakes: 3-6 traps. For each, what it looks like, why it is tempting, what to do
  instead.
- Exercise: bounded in time, producing a concrete deliverable, applied to the one real
  subject the reader chose in module 01 (their business, team, or project). Not answerable
  by re-reading the module.
- If you remember one thing: a single paragraph. The sentence that survives when the rest fades.

Markdown tables, blockquotes and fenced code are available. Do not write links between
modules - they cannot resolve in the built site. Do not add a "Next" line.

Return only the markdown document. No preamble, no code fence around it."""


def module_first(cfg: Dict[str, Any]) -> str:
    """Extra instruction for M01, which has to establish the running example."""
    return f"""

This is the FIRST module, so it carries one extra job. Somewhere in it - most naturally in
the Exercise - have the reader choose ONE real, concrete thing they will apply every
subsequent exercise to: their own {cfg['subject']} situation, their employer, their project,
or something they genuinely care about. Say plainly why this matters: {cfg['subject']}
learned in the abstract evaporates. Every later module's exercise refers back to this choice."""


def direction(notes: str) -> str:
    """Extra instruction appended to a module prompt when the person asked for something."""
    notes = (notes or "").strip()
    if not notes:
        return ""
    return f"""

Direction from the person who owns this course, which overrides the defaults above where
they conflict:
{notes}"""


MODULE_SPEC_SCHEMA = """{
  "title": str,        // the module's full title
  "short": str,        // sidebar label, 3-5 words
  "minutes": number,   // 30-120
  "summary": str,      // two sentences on what it teaches and why it sits here
  "sections": [str],   // the seven standard section headings, verbatim, in order
  "requires": [str]    // ids of the 0-3 existing modules it builds on
}"""


def patch_module(cfg: Dict[str, Any], modules: List[Dict[str, Any]], spec: Dict[str, Any],
                 body: str, notes: str) -> str:
    """The rewrite that changes only what was asked.

    A full rewrite regenerates every sentence, so each pass fixes the last review's findings
    and creates new ones. A patch hands the model the module as it is and forbids touching
    anything the notes do not name, which is what a review's brief actually calls for.
    """
    return f"""Edit module {spec['id']}, "{spec['title']}", of this course. Change only what the notes
below ask for, and keep everything else word for word.

{course_context(cfg, modules)}

{VOICE}

The notes - what must change:
{(notes or '').strip() or '(nothing specific: fix only clear errors, typos and muddled sentences)'}

Rules:
- Return the whole module as markdown with the notes applied and nothing else altered. A
  sentence the notes do not concern must come back identical: same words, same punctuation,
  same order. Do not tighten, restyle or "improve" passages the notes do not mention.
- Keep the title line, the `**Time:**` line, any `**Requires:**` line and every `##` heading
  exactly as they are, in the same order. Adding, removing or renaming a `##` heading breaks
  the reader's progress and the quiz mapping.
- Where a note asks for a source you do not have, hedge the claim honestly rather than
  inventing a citation.
- A line of the form `![...](figures/...)` is a figure the build inlines, and one of the
  form `[...](notebooks/...)` a notebook. Keep every one exactly where it is unless a note
  names it.
- A note about the quiz, the flashcards or the prompts is handled separately; ignore it here.

The module as it stands:
\"\"\"
{body[:30000]}
\"\"\"

Return only the edited markdown document. No preamble, no commentary, no code fence."""


def module_spec(cfg: Dict[str, Any], modules: List[Dict[str, Any]], topic: str,
                part_name: str, minutes: int, notes: str = "") -> str:
    """Design one new module that fits an existing course - used when a course is extended."""
    return f"""A reader working through "{cfg['title']}" wants the course to go further on:

  {topic}

{course_context(cfg, modules)}

Design ONE new module on that topic to be appended to the part called "{part_name}". It must
teach something the existing modules do not - build on them, refer to them where useful, and
do not repeat them. Plan it at about {minutes} minutes.

Every module has exactly these sections, in this order, and you must list them in
"sections" verbatim:
  "Why this matters", "Core concepts", "How it works in practice",
  "2026 reality check", "Common mistakes", "Exercise", "If you remember one thing"
{direction(notes)}

Return ONLY a JSON object of this shape, no prose and no code fence:
{MODULE_SPEC_SCHEMA}"""

"""The course's reference material: glossary, mental models, resources, worksheets, plan pages.

All of it is optional to a course and none of it is per module, which is why it is written
once at the end of a run from the corpus the modules turned out to be.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .common import VOICE


def glossary(cfg: Dict[str, Any], modules: List[Dict[str, Any]], corpus: str) -> str:
    return f"""Write the glossary for "{cfg['title']}", a {cfg['hours']}-hour course on
{cfg['subject']}.

Cover every term and acronym the course uses that a beginner would not already know. Define
in plain language - the reader uses this during real conversations long after finishing, so
a definition that needs its own glossary is a failed definition.

Course text to draw the terms from:
{corpus}

{VOICE}

Format - a markdown document. After a `# Glossary` heading and one short intro line, one
term per line, exactly:

**Term** — plain-language definition, one or two sentences.

Prefix the term with a literal \\* for the ones worth memorising first, like:
**\\*Term** — definition.

Alphabetical. Aim for 60-160 terms depending on how much vocabulary this subject carries.
Return only the markdown document."""


def mental_models(cfg: Dict[str, Any], corpus: str) -> str:
    return f"""Write the mental models document for "{cfg['title']}", a course on
{cfg['subject']}.

These are the ideas that survive after the details fade - the ones the reader should be able
to apply years later having forgotten every specific technique.

Course text:
{corpus}

{VOICE}

Format - a markdown document:
- `# Mental models` heading, then a short intro under a `## How to use this` heading.
- Then one `## N. Name of the model` heading per model, numbered from 1, each followed by
  2-5 short paragraphs: what it says, why it is true, and when it stops being true.
- 20 models if this subject genuinely carries twenty load-bearing ideas. If it does not,
  write 12 good ones rather than padding to a round number.

Return only the markdown document."""


def resources(cfg: Dict[str, Any]) -> str:
    return f"""Write the recommended-resources document for "{cfg['title']}", a
{cfg['hours']}-hour course on {cfg['subject']} for {cfg['audience']}.

{VOICE}

A short, opinionated list - not everything that exists. For each entry say what it is, who
it is for, and why it earns its place. Say plainly where something is overrated, dated, or
only worth one chapter. Group by kind (books, sites, newsletters, tools, communities,
courses) with `##` headings.

Be honest about currency: it is 2026, and recommend accordingly. If you are not confident a
specific title exists, describe the kind of resource to look for and what makes a good one
instead of inventing a name or a URL. Never fabricate an author, title, or link.

Return only the markdown document, starting with `# Resources`."""


def worksheet(cfg: Dict[str, Any], name: str, purpose: str) -> str:
    return f"""Write one reusable worksheet for "{cfg['title']}", a course on {cfg['subject']}.

Worksheet: {name}
Purpose:   {purpose}

{VOICE}

This is a fill-in artefact the reader reuses for years, so it must be usable on its own by
someone who has forgotten which module it came from.

Format - a markdown document:
- `# {name}` as the first line.
- One line saying when to use it and what you get out of it.
- Then the worksheet: markdown tables with empty cells, prompts with blank lines under them,
  checklists. Include a short filled-in example clearly marked as an example.
- End with a `## How to tell if you did this well` section: 3-5 checks.

Return only the markdown document."""


def plan_docs(cfg: Dict[str, Any], modules: List[Dict[str, Any]], kind: str) -> str:
    listing = "\n".join(
        "  %s - %s (%s min)" % (m["id"], m["title"], m["minutes"]) for m in modules
    )
    common = f"""For "{cfg['title']}", a {cfg['hours']}-hour course on {cfg['subject']} for
{cfg['audience']}.

The modules:
{listing}

{VOICE}
"""
    if kind == "curriculum":
        return common + """
Write the curriculum document: the whole map, part by part and module by module, with the
time budget. For each module give one line on what it covers and one on why it sits where it
does in the order. Open with the total shape - parts, hours, module count - so the reader can
see the whole thing at once.

Return only the markdown document, starting with `# Curriculum`."""
    if kind == "how":
        return common + """
Write the "how to study" document. This is read before module 01 and its job is to protect
the reader's remaining hours. Be concrete and specific to this subject:
- how to space the sessions, and why massed reading fails;
- what to do when stuck;
- why the exercises are the part that matters, and what happens if they are skipped;
- how to use the flashcards and the quizzes honestly, including rating confidence;
- what to skip if short on time, named explicitly;
- the trap where knowing the vocabulary feels like competence.

Return only the markdown document, starting with `# How to study`."""
    return common + f"""
Write the "path to expert" document. Say plainly what {cfg['hours']} hours does and does not
buy - roughly the level of a junior {cfg['practitioner']} with unusually good instincts, not
an expert. Then map what comes after: what the next few hundred hours of real practice look
like, in what order, what to seek out, how to tell you are improving rather than just
accumulating time, and the failure modes of self-taught people in this field.

Do not soften it. A reader who trusts this document will trust the rest of the course.

Return only the markdown document, starting with `# After the last module`."""


WORKSHEET_PLAN_SCHEMA = """[ { "slug": "kebab-case-name", "name": str, "purpose": str } ]"""


def worksheet_plan(cfg: Dict[str, Any], modules: List[Dict[str, Any]]) -> str:
    listing = "\n".join("  %s - %s" % (m["id"], m["title"]) for m in modules)
    return f"""For "{cfg['title']}", a course on {cfg['subject']}, decide which reusable
fill-in worksheets it should ship.

The modules:
{listing}

Pick 6-10 worksheets that the reader will genuinely reuse after finishing - the lasting
artefacts of the course. Each should serve a recurring real task in this field, and should be
the natural output of at least one module's exercise. Do not propose a worksheet that is just
a summary of a module.

"slug" is a kebab-case filename with no extension. "purpose" is one sentence on when it is used.

Return ONLY a JSON array of this shape, no prose and no code fence:
{WORKSHEET_PLAN_SCHEMA}"""

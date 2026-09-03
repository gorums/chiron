"""The prompts Studio sends.

These are the machine-driven twin of `.claude/skills/course-author/`. The skill guides a
model that can read files and iterate; these run unattended, so they carry their contract
inline and state the output format exactly. When the module format or a JSON schema changes,
both have to change — the skill's `references/` remain the human-readable source of truth.

Kept in one module so the whole voice of a generated course can be read in one sitting.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

# The house style, prepended to every content call so nineteen modules sound like one course.
VOICE = """\
Voice rules, which matter as much as the content:
- Second person, present tense. "You will notice", not "One might observe".
- Short declaratives. State the thing, then qualify it — never the reverse.
- Name the mistake. "Most people think X. That belief is why Y is wasted." A course that
  never says anyone is wrong gives the reader nothing to correct.
- Numbers over adjectives. "Roughly the last 10%" beats "a small part".
- No throat-clearing. Never open with "In this module we will explore". Start with content.
- Earn the hedge: "it depends" is only useful with the "on what" attached.
- Be honest about what the time budget does not buy. Do not flatter the reader.
Write nothing that could be produced by someone who had not thought about this subject."""

PLAN_SCHEMA = """{
  "title": str,               // e.g. "Negotiation Mastery" - a real name, not a description
  "tagline": str,             // e.g. "20 hours - beginner to practitioner"
  "practitioner": str,        // what a competent person is called, singular: "negotiator"
  "audience": str,            // e.g. "a complete beginner"
  "tutorPersona": str,        // one sentence, starts "You are", ends with a period
  "anchor": {                 // the one real thing of the reader's that every exercise is applied to
    "label": str,             //   e.g. "Your business" / "Your kitchen" / "Your next negotiation"
    "prompt": str,            //   one or two sentences asking the reader to name it
    "placeholder": str,       //   e.g. "e.g. my sister's physiotherapy clinic"
    "noun": str               //   how a question refers to it: "my business", "my kitchen"
  },
  "parts": [
    { "id": "p1", "name": str, "hours": number, "dir": str, "blurb": str }
  ],
  "modules": [
    { "id": "M01", "part": "p1", "title": str, "short": str, "minutes": number,
      "summary": str, "sections": [str], "requires": ["M01"] }
  ],
  "milestones": [ { "after": number, "text": str } ]
}"""


def plan(theme: str, hours: float, audience: str, practitioner: str,
         part_hint: List[Dict[str, Any]], notes: str = "") -> str:
    return f"""You are designing a complete study course on **{theme}** for {audience}, to be
studied in {hours} focused hours. Design the whole curriculum before any of it is written.

{VOICE}

How to structure it:
- Work at roughly 60 minutes per module. A 90 or 120 minute module is fine where the
  material earns it.
- Part 1 is what does not expire: definitions, the mental model, the arithmetic. If every
  tool in this field were replaced tomorrow, this part would still stand.
- Part 2 is the working middle - the actual doing. Most hours belong here.
- Part 3 is judgement: the calls a senior person makes that a junior does not know exist.
  Not "advanced tactics" - the reasoning behind choosing between tactics.
- The final module is a capstone: one end-to-end deliverable that consumes everything before it.
- Order by dependency, not by interest. A reader cannot judge a technique before they have
  the means to tell whether it worked.

A reasonable hour split for this budget is {json.dumps(part_hint)} - change the names, count
and budgets if this subject wants a different shape.

Every module needs exactly these sections, in this order, and you must list them in
"sections" verbatim as the headings you will write:
  "Why this matters", "Core concepts", "How it works in practice",
  "2026 reality check", "Common mistakes", "Exercise", "If you remember one thing"

Rules:
- Module ids run M01, M02, ... sequentially across the WHOLE course, never restarting per part.
- "short" is the sidebar label: 3-5 words.
- "dir" is a folder name: "01-foundations", "02-core", "03-expert-layer".
- Part "hours" must sum to exactly {hours}.
- "milestones" is the honest-read line on the stats page: 4-6 entries keyed on how many
  modules are complete, including one with "after": 0 and one for the full module count.
  Same voice as the course. Say plainly what the reader has and has not earned.
- "requires" lists the 0-3 EARLIER modules this one genuinely builds on - the ones a reader
  must have understood, not merely read before. The page warns when a prerequisite is weak.
  Leave it empty for a module that stands alone.
{("- Additional direction from the person requesting the course: " + notes) if notes else ""}

Return ONLY a JSON object of this shape, no prose and no code fence:
{PLAN_SCHEMA}"""


def _course_context(cfg: Dict[str, Any], modules: List[Dict[str, Any]]) -> str:
    listing = "\n".join(
        "  %s (%s) - %s" % (m["id"], m["part"], m["title"]) for m in modules
    )
    return f"""This module belongs to "{cfg['title']}", a {cfg['hours']}-hour course on
{cfg['subject']} for {cfg['audience']}. A competent person in this field is called
a {cfg['practitioner']}.

The full curriculum, so you can build on earlier modules and leave later ones alone:
{listing}"""


def module(cfg: Dict[str, Any], modules: List[Dict[str, Any]], spec: Dict[str, Any]) -> str:
    sections = "\n".join("## " + s for s in spec["sections"])
    requires = [r for r in (spec.get("requires") or []) if r != spec["id"]]
    requires_line = ("**Requires:** " + ", ".join(requires) + "\n") if requires else ""
    return f"""Write module {spec['id']} of this course, in full.

{_course_context(cfg, modules)}

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


def module_spec(cfg: Dict[str, Any], modules: List[Dict[str, Any]], topic: str,
                part_name: str, minutes: int, notes: str = "") -> str:
    """Design one new module that fits an existing course - used when a course is extended."""
    return f"""A reader working through "{cfg['title']}" wants the course to go further on:

  {topic}

{_course_context(cfg, modules)}

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


ASSESS_SCHEMA = """{
  "id": "M01",
  "predict": str,
  "quiz": [
    { "type": "single", "q": str, "options": [str, str, str, str], "answer": int,
      "feedback": [str, str, str, str], "hints": [str], "why": str },
    { "type": "multi",   "q": str, "options": [str, ...], "answer": [int, ...], "why": str },
    { "type": "tf",      "q": str, "answer": bool, "feedback": [str, str], "why": str },
    { "type": "numeric", "q": str, "answer": number, "tolerance": number, "unit": str, "why": str },
    { "type": "order",   "q": str, "options": [str, ...], "why": str },
    { "type": "match",   "q": str, "pairs": [[str, str], ...], "why": str },
    { "type": "cloze",   "q": "text with a ___ blank", "answer": [str, ...], "why": str },
    { "type": "short",   "q": str, "model": str, "why": str }
  ],
  "cards": [ { "front": str, "back": str } ],
  "elaborate": [str, str],
  "transfer": { "scenario": str, "prompt": str, "model": str },
  "roleplay": { "persona": str, "situation": str, "goal": str, "rubric": [str, str, str] }
}"""


def assessment(cfg: Dict[str, Any], spec: Dict[str, Any], body: str) -> str:
    return f"""Write the study data for module {spec['id']} of "{cfg['title']}", a course on
{cfg['subject']}. Base every item strictly on the module text below - never on general
knowledge the module does not teach.

--- MODULE TEXT ---
{body}
--- END MODULE TEXT ---

Produce:

"predict" - one question asked BEFORE reading, answerable by guessing. The point is
committing to a guess so the correction lands, not being right.

"quiz" - exactly 6 questions. Test whether the reader can USE the idea, not whether they
saw the sentence. The weak form is "Which of these is the definition of X?"; the strong form
gives a situation and asks what follows from it. "why" is required on every question and is
where the teaching happens: say why the right answer is right AND why the most tempting
wrong one is tempting.

Question types - use the one the material calls for, at least 3 different types across
the six:
- "single": 4 plausible options, "answer" is the ZERO-BASED index of the right one. Vary the
  position. Add "feedback": one short line per option saying why THAT option is right or
  wrong - the reader who picked the tempting wrong answer should get a different sentence
  from the one who guessed. Add "hints": 1-2 nudges that narrow it without giving it away.
- "multi": several options apply; "answer" is the list of correct indexes.
- "tf": a statement; "answer" is true or false; "feedback" has two entries.
- "numeric": the reader computes a figure from the module's arithmetic; "answer" is the
  number, "tolerance" the absolute slack, "unit" a short label like "%" or "EUR".
- "order": "options" listed in the CORRECT order; the page shuffles them.
- "match": "pairs" of [term, its match]; the page shuffles the right-hand side.
- "cloze": a sentence with ONE blank written as ___; "answer" lists every acceptable fill.
- "short": a one-or-two-sentence free answer; "model" is what a good answer contains.
Every type may carry "hints".

"cards" - exactly 6 flashcards for spaced repetition. "front" is a question or prompt,
"back" is the answer. Test recall of the load-bearing ideas, not trivia.

"elaborate" - exactly 2 prompts that force the reader to explain in their own words. At
least one applied to the real thing they chose in module 01.

"transfer" - a situation the module never discussed, with enough concrete detail (numbers,
constraints, a stated wrong instinct) to reason about. "prompt" says what to produce.
"model" is the answer they see after committing to theirs.

"roleplay" - a live conversation that practises this module, played by the tutor in the
page. "persona" is who the tutor plays, written as an instruction to the tutor ("You are the
owner of a 12-room hotel who thinks ads are a waste of money..."), with a stated wrong
belief or pressure so the reader has to work. "situation" is the setup the reader sees.
"goal" is what the reader must achieve in the conversation. "rubric" lists 3-4 things a
good performance shows. Omit "roleplay" only if this module has no conversation worth
practising.

Return ONLY a JSON object of this shape, no prose and no code fence:
{ASSESS_SCHEMA}"""


def suggestions(cfg: Dict[str, Any], mid: str, headings: List[str], body: str) -> str:
    numbered = "\n".join("  %d. %s" % (i + 1, h) for i, h in enumerate(headings))
    return f"""For module {mid} of "{cfg['title']}", write the one-tap questions that appear
in the chat sidebar while the reader is looking at each section.

The module has exactly {len(headings)} sections, in this order:
{numbered}

--- MODULE TEXT ---
{body}
--- END MODULE TEXT ---

Return a JSON array of exactly {len(headings)} arrays, in that same order - element N is for
section N. Each inner array holds exactly 3 questions.

Each question must be:
- under 70 characters, because they render as small buttons;
- specific to that section's actual content - "Tell me more" is wasted;
- written as the reader would ask it, in first person where natural.

Mix the three kinds within each set: one that clarifies the idea, one that asks for it made
concrete or worked through, one that applies it to the reader's own situation.

Return ONLY the JSON array of {len(headings)} arrays. No prose, no code fence, no object
wrapper, no module id."""


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

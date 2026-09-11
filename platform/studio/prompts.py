"""The prompts Studio sends.

These are the machine-driven twin of `common/skills/course-author/`. The skill guides a
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
  "notebooks": null | {       // ONLY for a subject the reader learns by running code; null otherwise
    "kernel": "python3",      //   the Jupyter kernel: python3 unless the subject is another language
    "packages": [str]         //   the packages the notebooks import beyond the standard library
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
         part_hint: List[Dict[str, Any]], notes: str = "", notebooks: str = "auto") -> str:
    notebooks_rule = {
        "yes": "The person asked for notebooks: set \"notebooks\" with the kernel and packages "
               "this subject needs.",
        "no": "The person asked for no notebooks: \"notebooks\" is null.",
    }.get(notebooks, "")
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
- "notebooks": a course carries Jupyter notebooks the reader runs and edits inside each
  module ONLY when the subject is learned by running code - a programming language, data
  analysis, statistics, machine learning, scientific computing, SQL through a driver. Then
  name the kernel and the packages the notebooks will import. For every other subject -
  and most subjects are every other subject - it is null. {notebooks_rule}
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


def patch_module(cfg: Dict[str, Any], modules: List[Dict[str, Any]], spec: Dict[str, Any],
                 body: str, notes: str) -> str:
    """The rewrite that changes only what was asked.

    A full rewrite regenerates every sentence, so each pass fixes the last review's findings
    and creates new ones. A patch hands the model the module as it is and forbids touching
    anything the notes do not name, which is what a review's brief actually calls for.
    """
    return f"""Edit module {spec['id']}, "{spec['title']}", of this course. Change only what the notes
below ask for, and keep everything else word for word.

{_course_context(cfg, modules)}

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


def patch_assessment(cfg: Dict[str, Any], spec: Dict[str, Any], assess: Dict[str, Any],
                     notes: str, body: str) -> str:
    """The study-data half of a patch: the same object back, with only the flagged items new."""
    import json
    return f"""Edit the study data for module {spec['id']}, "{spec['title']}", of the course
"{cfg.get('title', '')}". Change only what the notes below require.

The notes:
{(notes or '').strip() or '(nothing specific)'}

Rules:
- Return the complete JSON object in the same shape, with only the items the notes concern
  changed. Every other quiz item, card, elaborate prompt and transfer scenario must come
  back identical.
- A replaced quiz item tests the idea, not the module's wording, and its key must be
  answerable from the module text below. Keep the item's type unless the note asks otherwise.
- If the notes say nothing about the quiz, the cards or the prompts, return the object
  unchanged.

The module text, for reference:
\"\"\"
{body[:20000]}
\"\"\"

The study data as it stands:
{json.dumps(assess, ensure_ascii=False, indent=1)}

Return ONLY the JSON object, no prose and no code fence. Its shape:
{ASSESS_SCHEMA}"""


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


FIGURES_FORMAT = """=== FIGURE
section: <one of the module's `##` headings, verbatim>
caption: <one sentence: what the reader should notice in it>
<svg viewBox='0 0 800 450'> ... </svg>"""


def figures(cfg: Dict[str, Any], spec: Dict[str, Any], body: str, headings: List[str],
            count: int, max_steps: int) -> str:
    """Diagrams for a module, as SVG the build can inline (see `coursekit.figures`).

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


REVIEW_SCHEMA = """{
  "verdict": "solid" | "needs work" | "rewrite",
  "summary": str,                 // two or three sentences a course owner can act on
  "gaps": [ { "where": str, "issue": str, "fix": str } ],      // what the module should teach and does not
  "errors": [ { "where": str, "issue": str, "fix": str } ],    // things stated that are false, muddled or dated
  "quiz": [ { "item": str, "issue": str, "fix": str } ],       // questions that test the wrong thing or have a broken key
  "rewriteBrief": str             // the direction you would hand a writer to fix all of the above, under 120 words
}"""


def quiz_listing(assess: Any) -> str:
    """The quiz as the review prompt shows it. Public because an overridden review prompt
    carries `{{study_data}}` where this block goes, and the two must render alike. A string
    is already that block - which is how a preview puts the token there instead."""
    if isinstance(assess, str):
        return assess
    return "\n".join(
        "  - [%s] %s" % (q.get("type", "single"), q.get("q", ""))
        for q in (assess.get("quiz") or [])
    ) or "  (none)"


def review(cfg: Dict[str, Any], modules: List[Dict[str, Any]], spec: Dict[str, Any],
           body: str, assess: Dict[str, Any]) -> str:
    """Read one finished module the way a demanding reader would, before that reader does.

    The checklist is the pedagogy the authoring skill works to, compressed: a module earns its
    place by what the reader can do afterwards, teaches with the mistake named, carries real
    numbers, and is tested by questions that need the idea rather than the wording.
    """
    quiz = quiz_listing(assess)
    return f"""You are reviewing module {spec['id']}, "{spec['title']}", before its reader finds the gap.

{_course_context(cfg, modules)}

Judge it against this standard, which is what every module in this course is written to:
- Purpose: the reader can DO something afterwards that they could not before, and the module
  says what. A module that only informs has failed.
- Sequence: it builds on the modules before it and does not quietly re-teach them, and it does
  not depend on anything taught later.
- Honesty: it names the mistake most people make, gives real numbers and thresholds rather
  than adjectives, says where the simplification breaks, and does not flatter the reader.
- Currency: nothing stated is out of date for {cfg.get('year', '2026')} or wrong in this field.
- Practice: the Exercise produces something concrete that applies to the reader's own case,
  and the quiz below tests understanding of the idea, not recall of the module's phrasing,
  with a defensible answer key.
- Length: it fits its {spec.get('minutes', 60)}-minute budget - neither padded nor rushed.
- Placement: a figure (`![...](figures/...)`) or notebook (`[...](notebooks/...)`) sits where
  it aids retention - the mental model in Core concepts, a build-up or a live example where
  the sequence is taught, a contrast or a failing cell under Common mistakes, the exercise
  as a notebook - and never in Why this matters, the reality check or If you remember one
  thing, where it hands over what the reader should recall.

Be exact and brief. Every finding names WHERE (a section heading or a quoted phrase), WHAT is
wrong, and the FIX. Do not list what is fine. An empty list is a valid answer for a category
with nothing wrong.

The verdict says whether the module can be published, not whether it is perfect:
- "solid": publishable as it stands. Minor findings - a typo, a hedge worth adding, one more
  example, a claim that could carry a source - still go in the lists, but they do not lower
  the verdict. A well-made module lands here even with a few of them.
- "needs work": at least one finding would mislead the reader or break the practice: a false
  or dated claim, a number stated with invented precision, a quiz key that is wrong or not
  answerable from the text, a required section missing or empty, an exercise that produces
  nothing.
- "rewrite": the purpose or the structure fails, and the fixes amount to writing it again.
Do not lower the verdict for polish, and do not invent findings to justify one.

The module text:
\"\"\"
{body[:24000]}
\"\"\"

Its quiz:
{quiz}

Return ONLY a JSON object of this shape, no prose and no code fence:
{REVIEW_SCHEMA}"""

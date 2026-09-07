---
name: course-author
description: Write a complete study course from scratch for any subject and any hour budget — folder structure, module markdown, glossary, worksheets, quizzes, flashcards and suggested questions — then build it into the interactive site. Use when the user asks for a course, tutorial, curriculum or learning path on a theme ("build me a 20-hour course on negotiation"), or wants to extend, rewrite or re-generate an existing course in courses/.
---

# Authoring a course

You are writing a real course that someone will spend their evenings on. The platform in
`platform/` renders whatever you produce and never checks whether it is any good — only
whether it is consistent. Quality is entirely on you.

Read `references/pedagogy.md` before writing any prose. It is what separates this from a
generated outline with paragraphs under it.

## The brief

Get four things before starting. Ask only for what is genuinely missing; infer the rest and
say what you inferred.

| | | |
|---|---|---|
| **theme** | the subject | `"negotiation"` |
| **hours** | total study budget | `20` |
| **practitioner** | what a competent person in this field is called | `"negotiator"` |
| **audience** | who is studying | `"a complete beginner"` |

If the user gives only a theme and hours, that is enough — pick a sensible practitioner noun
and assume a motivated beginner.

## Phase 1 — scaffold

```
python platform/build.py new --theme "<theme>" --hours <n>
```

This creates `<id>/` inside the courses directory (`python platform/build.py where` prints
it; `courses/` by default) with the folder tree, a filled-in `course.json`, a `README.md`
and stub plan documents. The folder is meant to become its own git repository; the platform
repository ignores it. It prints the hour split and how many modules each part should hold. Treat that
as the starting proposal, not a constraint — reshape it in the next phase if the subject
wants a different division.

## Phase 2 — design the curriculum, then commit it to `course.json`

Decide the module list *whole* before writing any of it. A course designed module-by-module
drifts, repeats itself, and buries the important ideas in module 14.

Work at roughly **60 minutes per module**. Rules that hold across subjects:

- **Part 1 is what does not expire.** Definitions, the mental model, the arithmetic. If the
  subject's tools were all replaced tomorrow, this part still stands.
- **Part 2 is the working middle** — the actual doing, and where most hours belong.
- **Part 3 is judgement.** The calls a senior person makes that a junior does not know exist.
  Not "advanced tactics" — the reasoning behind choosing between tactics.
- **The last module is a capstone**: one end-to-end deliverable that uses everything.

Then edit the course's `course.json`:

- `parts` — rename, re-budget or re-split if the subject wants a different shape. `dir` must
  match a real folder under `modules/`.
- `shortTitles` — `{"M01": "…"}` for every module. These are the sidebar labels: 3–5 words.
- `tagline`, `practitioner`, `audience`, `tutorPersona` — the tutor persona is a system
  prompt fragment and must end with a period.
- `anchor` — the one real thing of the reader's that every exercise is applied to:
  `{"label": "Your business", "prompt": "…", "placeholder": "e.g. …", "noun": "my business"}`.
  The page prints these four strings wherever it asks the reader to bring their own case, so
  make them fit the subject: a baking course says kitchen, a negotiation course says the next
  negotiation. Omit it and the page says "Your own case".
- `milestones` — leave until Phase 7.

## Phase 3 — the plan documents

Three short files in `plan/`, all of which the reader sees before module 1:

- `curriculum.md` — the whole map, session by session, with the time budget.
- `how-to-study.md` — how not to waste the hours. Concrete: spacing, what to skip, what to
  do when stuck, how to use the exercises.
- `path-to-expert.md` — honest account of what these hours do and do not buy, and what the
  next few hundred hours look like. Say the uncomfortable thing plainly.

## Phase 4 — write the modules

**Read `references/module-format.md` first — the format is a contract the build enforces.**

One file per module, `modules/<part-dir>/M01-kebab-title.md`, ids sequential *across the
whole course* (M01…M19, not restarting per part). Under the `**Time:**` line, a
`**Requires:** M03, M05` line names the 0–3 earlier modules this one genuinely builds on;
the page warns the reader when one of them is weak.

Every module has the same seven sections, in this order:

1. `## Why this matters` — the 30-second case for reading on
2. `## Core concepts` — the actual teaching, with `###` subheadings
3. `## How it works in practice` — what a competent person does on a Tuesday
4. `## <Year> reality check` — what changed recently that most guides get wrong
5. `## Common mistakes` — the traps, and why each is tempting
6. `## Exercise` — applied to the one real subject the reader picked in module 1
7. `## If you remember one thing` — a single paragraph

Write one module at a time, completely, before starting the next. Do not draft all nineteen
outlines and fill them in — the fill-in pass is where courses go generic.

Where a picture shows what the prose can only list — a flow, a funnel, a 2x2, a sequence
that builds up — draw it as an SVG in `figures/<ID>-<n>.svg` and refer to it from the
section with `![caption](figures/<ID>-<n>.svg)`. The rules (colour classes, steps, size)
are in `references/module-format.md` under "Figures"; the build enforces them. One or two
per module where they earn their place; none where they do not.

The **one rule** that makes a course stick: every exercise applies to a single concrete
thing the reader chooses in module 1 — their business, their team, their project. Establish
that choice in M01 and refer back to it in every subsequent exercise.

## Phase 5 — reference shelf

- `reference/glossary.md` — every term the course uses. One per line, exactly:
  `**Term** — plain-language definition.` Prefix with `\*` the terms worth memorising first.
- `reference/mental-models.md` — the ideas worth keeping after the details fade. Numbered
  `## 1. Name` headings; anything under a non-numbered heading becomes the intro note.
- `reference/resources.md` — a short, opinionated list. Say why each one earns its place.
- `templates/*.md` — fill-in worksheets the reader reuses. First line `# Title`, then a
  `**Use with:** M07 — …` line naming the modules whose exercise it serves, then the
  worksheet. Runs of underscores, empty table cells, `- [ ]` items and ```` ```answer ````
  blocks become real inputs on the page (see `references/module-format.md`). These are the
  course's lasting artefact.

## Phase 6 — study data

**Read `references/data-schemas.md`.** Two JSON families, and one invariant that the build
will reject you for breaking:

> **A module's suggestion list must have exactly one entry per `##` section.**
> They are matched by position, not by name.

Count the sections in the finished markdown — do not count the sections you planned.

- `data/assessments/partN.json` — a JSON **list**, one object per module: `predict`, `quiz`
  (6 questions, mixing at least three of the eight types — `numeric` for the arithmetic,
  `order` for a real sequence, `cloze` for a term the reader must produce — with per-option
  `feedback` and `hints` where they earn their place), `cards` (6 flashcards), `elaborate`,
  `transfer`, and a `roleplay` wherever the module has a conversation worth practising.
- `data/suggestions/partN.json` — a JSON **object** keyed by module id, each value a list of
  3-question sets, one set per section.

Write these per part, after that part's modules are finished, so the questions are drawn
from the text that actually exists.

## Phase 7 — milestones

Add `milestones` to `course.json`: 4–6 entries of `{"after": <modules completed>, "text": …}`.
The highest matching `after` wins, so include an `after: 0` and one for the full count. This
is the "honest read" line on the stats page — write it in the same voice as the rest.

## Phase 8 — build

```
python platform/build.py check <id>     # every inconsistency at once
python platform/build.py build <id>     # writes dist/<id>/
```

`check` reports all problems in one pass. Fix them all, re-check, then build. Never hand
over a course that only builds with `check` failing.

Tell the user to open `dist/<id>/<output>-local.html` — that copy is the one allowed to
reach Anthropic, so it is the one where the tutor works.

## Working order

Content before data, part by part:

```
scaffold → curriculum → plan docs
  → part 1 modules → part 1 assessments + suggestions
  → part 2 modules → part 2 assessments + suggestions
  → part 3 modules → part 3 assessments + suggestions
  → reference + templates → milestones → check → build
```

Checking after each part costs seconds and stops a section-count mismatch from propagating
through eighteen more modules.

## What makes this fail

- **Outlining everything, then filling in.** Produces uniform, forgettable prose.
- **Section counts drifting from suggestion counts.** Count the file, not the plan.
- **A module that only defines terms.** Every module needs something the reader *does*.
- **Hedged writing.** "It depends" is only useful with the *on what* attached.
- **Flattering the reader about what the hours buy.** Say what the budget does not cover.

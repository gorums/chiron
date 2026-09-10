# How to write a course someone finishes

The platform can render anything. These are the choices that decide whether the reader is
competent at the end or merely well-read. They are derived from the marketing course in
the marketing course (its own repository; clone it into the courses directory), which is
worth reading a module of before you write your own.

## The learning cycle each module runs

The seven sections and the study data are not decoration; together they run a specific
sequence, and each piece has a job:

| Step | Mechanism | Where it lives |
|---|---|---|
| Predict | Committing to a guess before reading makes the correction stick | `predict` |
| Read | The teaching | the `##` sections |
| Retrieve | Answering from memory, not recognition | `quiz`, `cards` |
| Elaborate | Explaining in your own words exposes what you only half-know | `elaborate` |
| Transfer | Applying it to a situation the module never mentioned | `transfer` |
| Space | Returning days later, at increasing intervals | the flashcard scheduler |

If you write the prose and skimp on the data, you have built a book. The data is what makes
it a course.

## Be honest about the budget

State early and plainly what the hours do and do not buy. A 20-hour course does not produce
an expert, and saying so is not modesty — it is the thing that makes the reader trust the
rest of your claims. Put the honest version in `path-to-expert.md` and do not soften it.

> Anyone selling you "expert in 30 hours" is doing marketing on you. Notice that.

## One real subject, all the way through

Have the reader choose one concrete thing in module 1 — their business, their team, their
project, the negotiation they actually have coming up — and aim every exercise at it. Skills
learned in the abstract evaporate. This single decision does more for retention than any
other choice in the course.

## Voice

- **Second person, present tense.** "You will notice…" not "One might observe…".
- **Short declaratives.** State the thing, then qualify it. Not the reverse.
- **Name the mistake.** "Most people think X. That belief is why Y is wasted." A course that
  never says anyone is wrong never gives the reader anything to correct.
- **Numbers over adjectives.** "Roughly the last 10%" beats "a small part".
- **No throat-clearing.** Delete "In this module we will explore…". Start with the content.
- **Earn the hedge.** "It depends" is only useful with the *on what* attached.

## Sequencing

Order by dependency, not by importance. A reader cannot evaluate a tactic before they have
the arithmetic that says whether it worked, so the arithmetic comes first even though the
tactic is more interesting.

Put the confidence trap where it happens. Around the middle of most courses the reader
learns the vocabulary and mistakes it for competence. Name that out loud when it arrives —
it is one of the most useful sentences in the whole course.

## The reality-check section

Every module has one, dated to the current year. It exists because most material on any
subject is quietly two to five years stale, and the reader has no way to tell. Say what
changed, say roughly when, and say what advice it invalidates. This section is the main
thing that dates the course — which is the point.

## Practice that produces, not recognises

A four-option question tests recognition; the page can test production. Spend the six
questions accordingly: a `numeric` for the module's arithmetic, a `cloze` for the term the
reader must be able to say, an `order` where sequence carries meaning, a `short` for the one
idea that only a sentence can hold. Write per-option `feedback` on the `single` questions
whose distractors are real beliefs — the reader who picked the tempting wrong answer
deserves a different sentence from the one who guessed.

Give every module a `roleplay` if it has a conversation in it: a pitch, a pushback, a
client who is wrong. The tutor plays the other side and grades the transcript against your
rubric. Nothing else in the course tests whether the reader can *do* it under pressure.

Weeks later, the page asks the module's questions again, mixed with every other module's,
and drops a module's mastery when it misses. Write questions that survive that: ones that
cannot be answered by remembering which module you are in.

## Exercises that work

- **Bounded.** "Twenty minutes" not "spend some time".
- **A deliverable.** Something that exists at the end: a filled-in worksheet, a written
  paragraph, a number. If nothing is produced, it will be skipped.
- **Uses the worksheet.** Point at the template in `templates/`. Reusable artefacts are what
  the reader still has a year later.
- **Not a lookup.** If it can be answered by re-reading the section, it is a quiz question,
  not an exercise.

## Figures and notebooks: where they earn retention

A figure or a notebook is a claim on the reader's attention. Each earns it only in the
place where it does something the prose cannot, and each place maps to a mechanism. The
section names below are the seven every module has.

**Figures** (SVG diagrams; `module-format.md`, "Figures")

- **Core concepts: one figure of the module's mental model.** Words and a picture of the
  same structure are stored twice and recalled either way (dual coding). Put the reference
  right after the paragraph that introduces the structure, never a screen away from it: a
  picture the reader has to scroll back to is not read with the text.
- **How it works in practice: a build-up for a sequence.** Reveal one stage per step. The
  reader who guesses what comes next before pressing Next is generating, not reading, and
  the reveal corrects the guess on the spot. The caption should tell them to guess.
- **Common mistakes: a wrong/right or before/after contrast in one frame.** The contrast
  is what is remembered; two separate pictures lose it.
- **Never in "Why this matters", the reality check, or "If you remember one thing".** The
  first is a hook, the second is dated prose, the last is retrieval, and a picture there
  hands the reader the answer they should be recalling.
- **The caption says what to notice, or asks it.** "Where most of the loss happens" or
  "Which stage would you cut?", not the title again. A figure that restates its paragraph
  in boxes is redundancy, and redundant material is read less carefully, not more.
- One figure per idea, one or two per module. Every extra picture splits attention.

**Notebooks** (Jupyter; `module-format.md`, "Notebooks")

- **Exercise is the home.** An exercise that produces a number, a plot or a working
  function is the deliverable this file asks for, and the kernel checks it in a way no
  worksheet can. Set the data up; leave the part that matters as `# your turn`.
- **Core concepts, only as the worked example made live.** A novice learns a method from a
  complete working example before from a problem. Show the whole thing running, then fade
  it: the next cell is the same with one step removed for the reader to fill in.
- **Open with a prediction.** The first markdown cell asks what the reader expects the
  next cell to print or plot, before they run it. Predict, run, compare is the module's own
  Predict step in miniature, and the surprise is what sticks.
- **Common mistakes, as a cell that fails.** A cell that raises, or gives the plausible
  wrong number, and a line asking why. Fixing a broken thing is remembered longer than
  reading about the mistake.
- **Close with the question the run answered**, to be answered in words: the reader
  writes a sentence in a markdown cell. Explaining the result is what turns a run into
  knowledge.
- **Never in "Why this matters", the reality check, or "If you remember one thing"**, for
  the same reasons as figures. One notebook per module; a second is the sign that the
  exercise should have been longer, not that the module needs two.

The later steps should lean on them: a quiz question asks for the number the notebook
produced or the stage the build-up revealed, and an Elaborate prompt asks the reader to
explain the figure without looking at it.

## The capstone

The final module puts it all together into one end-to-end deliverable — the thing the reader
would actually be asked to produce on the job. It should be genuinely hard and take longer
than an hour, and it should make earlier modules' worksheets into its inputs.

## Reference material

The glossary is not an appendix; it is the thing the reader uses during real conversations
long after finishing. Define every acronym in plain language, and star the ones worth
memorising. The mental models file is the twenty ideas that survive after the details fade —
if you cannot get to twenty that are genuinely load-bearing, write twelve good ones.

"""The study data a module is judged by: its quiz, its flashcards, its suggested questions.

The schemas are stated exactly because `coerce` has to be able to repair what comes back,
and `coursekit.course.validate` is the authority on what is finally acceptable.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List


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

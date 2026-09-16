"""Proposing the curriculum: the one call made before a course exists.

Everything downstream is written from what this returns, and a person approves it first,
so the schema is stated exactly and the brief per module is the part that matters - not
the title.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .common import VOICE


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


def asked_for(notes: str) -> str:
    """The person's own direction, stated above the structure rules rather than below them.

    It used to be the last bullet of a long rule list, which is where a planner has stopped
    reading: a course asked for a named topic came back with no module covering it. Putting
    it first is not enough on its own - the rules under it are prescriptive enough to win a
    disagreement, so they are named as defaults that yield.
    """
    notes = (notes or "").strip()
    if not notes:
        return ""
    return """What the person asked for, in their own words. This is the brief. Everything
below it is a default, and a default yields where the two disagree:

%s

Before you return the JSON, read that again against the modules you have written, and check
that every topic it names is the "summary" of some module. A topic asked for and missing
from the curriculum is the one failure this step can make that nothing later can repair.

""" % notes


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

{asked_for(notes)}How to structure it:
- Work at roughly 60 minutes per module. A 90 or 120 minute module is fine where the
  material earns it.
- Part 1 is what does not expire: definitions, the mental model, the arithmetic. If every
  tool in this field were replaced tomorrow, this part would still stand.
- Part 2 is the working middle - the actual doing. Most hours belong here.
- Part 3 is judgement: the calls a senior person makes that a junior does not know exist.
  Not "advanced tactics" - the reasoning behind choosing between tactics.
- The final module is a capstone: one end-to-end deliverable that consumes everything
  before it - unless the brief above says what the course should end on.
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

Return ONLY a JSON object of this shape, no prose and no code fence:
{PLAN_SCHEMA}"""

"""Reading a finished module critically, against the pedagogy the course claims to follow.

The verdict scale is calibrated in the prompt itself: "solid" means publishable, and minor
findings do not lower it. Without that, every module comes back needing work.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .common import course_context


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

{course_context(cfg, modules)}

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

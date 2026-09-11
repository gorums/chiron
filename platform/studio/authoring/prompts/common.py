"""What every prompt in this package is built on: the house style, and where the module sits.

Both are here because every stage needs them and none of them owns them. `VOICE` is
prepended to every content call so nineteen modules sound like one course, and
`course_context` is what tells the model which module it is writing and what the reader
has already been told.
"""

from __future__ import annotations

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


def course_context(cfg: Dict[str, Any], modules: List[Dict[str, Any]]) -> str:
    listing = "\n".join(
        "  %s (%s) - %s" % (m["id"], m["part"], m["title"]) for m in modules
    )
    return f"""This module belongs to "{cfg['title']}", a {cfg['hours']}-hour course on
{cfg['subject']} for {cfg['audience']}. A competent person in this field is called
a {cfg['practitioner']}.

The full curriculum, so you can build on earlier modules and leave later ones alone:
{listing}"""

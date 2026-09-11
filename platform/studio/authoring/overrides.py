"""The prompts a course overrides, module by module.

Studio's prompts are the platform's opinion about how a module should be written. A course
owner may disagree - about the voice, the section balance, how many quiz items a subject
needs, what a figure is for here - and the only honest place to say so is the prompt itself.
So every per-module call has a stage name (`module`, `assessment`, `suggestions`, `figures`,
`notebooks`, `review`), and a course may carry its own text for any of them.

They live in the course, at `plan/prompts.json`, because they are authoring intent: they
belong to the course the way its curriculum does, they travel with a zip or a clone, and a
rewrite eight months later writes to the same instructions the first run did.

    {"M03": {"assessment": "Write the study data for M03 ... {{module_text}} ..."}}

An override is sent **verbatim**, with two exceptions - the values that cannot be known when
it is written, and would freeze into a lie if they were:

    {{module_text}}   the module's text as it is at the moment of the call
    {{study_data}}    the quiz and flashcards, for the review stage

`apply` is the whole contract, and every builder that assembles a per-module prompt goes
through it (`generator.module_prompt`, `generator.assessment_prompt`, ...), so no call site
can forget to honour an override and no preview can show something other than what is sent.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple

from ..support.files import read_json, write_json

FILE = "plan/prompts.json"

BODY = "{{module_text}}"        # the module's own text, inserted at the moment of the call
STUDY = "{{study_data}}"        # its quiz and flashcards, for the review stage

# Every per-module call, in the order a run makes them. The label is what a person reads;
# the note says what the stage is for, so a prompt is edited knowing what depends on it.
STAGES: Tuple[Tuple[str, str, str], ...] = (
    ("module", "The module text",
     "The markdown of the module itself: the headings, the teaching, the exercise."),
    ("figures", "Figures",
     "The SVG diagrams drawn for it. Skipped when a run is asked for no figures."),
    ("notebooks", "Notebooks",
     "The Jupyter notebooks, for a course that declares the runtime."),
    ("assessment", "Quiz and flashcards",
     "The study data: quiz items, flashcards, elaborate and apply prompts, the role-play."),
    ("suggestions", "Suggested questions",
     "The one-tap questions in the chat rail - one set per section."),
    ("review", "Review",
     "What the model is asked when it reads the module critically."),
)

STAGE_IDS = tuple(stage for stage, _, _ in STAGES)

# What a person may write in an override that is filled in when the call is made. Sent to
# both surfaces, so the editor lists them without knowing what they are.
TOKENS: Tuple[Dict[str, str], ...] = (
    {"token": BODY, "what": "the module's own text, as it is when the call is made"},
    {"token": STUDY, "what": "its quiz, as a list - the review stage only"},
)

_MID = re.compile(r"^M\d{2,3}$")


def path(root: str) -> str:
    """Where a course keeps its overrides."""
    return os.path.join(root, FILE)


def load(root: str) -> Dict[str, Dict[str, str]]:
    """Every override this course carries, `{mid: {stage: prompt}}`, repaired on the way in.

    A hand-edited file is model-free but not fool-free: an unknown stage or a prompt that is
    not a string is dropped rather than failing a run forty minutes in.
    """
    clean: Dict[str, Dict[str, str]] = {}
    try:
        raw = read_json(path(root))
    except (OSError, ValueError):        # no file yet, or one edited into nonsense
        return clean
    if not isinstance(raw, dict):
        return clean
    for mid, stages in raw.items():
        if not isinstance(stages, dict) or not _MID.match(str(mid).upper()):
            continue
        kept = {stage: text for stage, text in stages.items()
                if stage in STAGE_IDS and isinstance(text, str) and text.strip()}
        if kept:
            clean[str(mid).upper()] = kept
    return clean


def save(root: str, data: Dict[str, Dict[str, str]]) -> None:
    """Write the whole set. A course that overrides nothing carries no file at all, rather
    than an empty one: a course is a repository, and an empty file is a thing to explain."""
    keep = {mid: stages for mid, stages in sorted(data.items()) if stages}
    if keep:
        write_json(path(root), keep)
    elif os.path.exists(path(root)):
        os.remove(path(root))


def get(root: str, mid: str, stage: str) -> str:
    """The override for one stage of one module, or ''."""
    return load(root).get(str(mid).upper(), {}).get(stage, "")


def put(root: str, mid: str, stage: str, text: str) -> Dict[str, str]:
    """Store one stage's prompt; empty text takes the override away. Returns what that
    module now overrides."""
    if stage not in STAGE_IDS:
        raise ValueError("There is no %r stage." % stage)
    data = load(root)
    mid = str(mid).upper()
    stages = dict(data.get(mid, {}))
    if str(text).strip():
        stages[stage] = str(text)
    else:
        stages.pop(stage, None)
    if stages:
        data[mid] = stages
    else:
        data.pop(mid, None)
    save(root, data)
    return stages


def forget(root: str, mid: str) -> None:
    """Drop every override for a module - it is being removed from the course."""
    data = load(root)
    if data.pop(str(mid).upper(), None) is not None:
        save(root, data)


def merge(root: str, incoming: Any) -> None:
    """Add overrides written before the course existed - the approval gate edits them while
    there is still nothing on disk. What is already in the course wins nothing: the plan is
    the later decision."""
    if not isinstance(incoming, dict) or not incoming:
        return
    data = load(root)
    for mid, stages in incoming.items():
        if not isinstance(stages, dict) or not _MID.match(str(mid).upper()):
            continue
        kept = {stage: text for stage, text in stages.items()
                if stage in STAGE_IDS and isinstance(text, str) and text.strip()}
        if kept:
            data[str(mid).upper()] = dict(data.get(str(mid).upper(), {}), **kept)
    save(root, data)


def apply(root: str, mid: str, stage: str, default: str, body: str = "",
          study: str = "") -> str:
    """The prompt to send: the course's own text where it has one, else the platform's.

    `root` may be empty - a preview of a course that does not exist yet, or a caller that
    deliberately wants the platform's prompt - and then the default is what comes back.
    """
    override = get(root, mid, stage) if root else ""
    if not override:
        return default
    return override.replace(BODY, body).replace(STUDY, study)


def overridden(root: str, mid: str) -> List[str]:
    """Which stages of this module the course has its own prompt for."""
    stages = load(root).get(str(mid).upper(), {})
    return [stage for stage in STAGE_IDS if stage in stages]

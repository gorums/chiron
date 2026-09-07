"""Every cross-file consistency check, in one place.

These run before anything is written. The failures they catch — a quiz whose answer index
points past its options, a module with four sections but three sets of follow-up questions —
are all silent at runtime: the page renders, and something is quietly missing or wrong.
Collecting them means one build tells you everything to fix, not the first thing.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .errors import DataError

ASSESS_KEYS = ("predict", "quiz", "cards", "elaborate", "transfer")

# Every question type the page can render. `single` is the default when `type` is absent,
# so every course written before types existed still validates unchanged.
QUIZ_TYPES = ("single", "multi", "tf", "numeric", "order", "match", "cloze", "short")

# Types whose answer is chosen from `options`, and may therefore carry per-option feedback.
OPTION_TYPES = ("single", "multi", "tf")

ROLEPLAY_KEYS = ("persona", "situation", "goal")


def check(modules, assessments: Dict[str, Any], suggestions: Dict[str, Any]) -> List[str]:
    """Return every problem found. Empty list means the course is coherent."""
    problems: List[str] = []
    problems += _check_ids(modules)
    problems += _check_requires(modules)
    problems += _check_figures(modules)
    problems += _check_notebooks(modules)
    problems += _check_assessments(modules, assessments)
    problems += _check_suggestions(modules, suggestions)
    return problems


def _check_ids(modules) -> List[str]:
    seen, problems = {}, []
    for m in modules:
        if m.id in seen:
            problems.append("Duplicate module id '%s': %s and %s" % (m.id, seen[m.id], m.source))
        seen[m.id] = m.source
    return problems


def _check_requires(modules) -> List[str]:
    """A `**Requires:**` line may only name modules that exist."""
    ids = {m.id for m in modules}
    problems = []
    for m in modules:
        for rid in getattr(m, "requires", []) or []:
            if rid not in ids:
                problems.append("%s requires '%s', which is not a module in this course." % (m.id, rid))
    return problems


def _check_figures(modules) -> List[str]:
    """Every figure a module refers to is on disk and usable (see `figures.py`)."""
    problems = []
    for m in modules:
        for fig in getattr(m, "figures", []) or []:
            if fig.get("problem"):
                problems.append("%s: figure %s %s." % (m.id, fig["name"], fig["problem"]))
    return problems


def _check_notebooks(modules) -> List[str]:
    """Every notebook a module refers to is on disk, usable, and allowed by the manifest
    (see `notebooks.py`)."""
    problems = []
    for m in modules:
        for nb in getattr(m, "notebooks", []) or []:
            if nb.get("problem"):
                problems.append("%s: notebook %s %s." % (m.id, nb["name"], nb["problem"]))
    return problems


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(s, str) and s.strip() for s in value)


def quiz_item_problems(q: Any, label: str) -> List[str]:
    """Every problem with one quiz item. Public so Studio can lean on the same rules."""
    problems: List[str] = []
    if not isinstance(q, dict):
        return ["%s is not an object." % label]
    kind = q.get("type") or "single"
    if kind not in QUIZ_TYPES:
        return ["%s has unknown type %r. Known types: %s." % (label, kind, ", ".join(QUIZ_TYPES))]
    if not isinstance(q.get("q"), str) or not q["q"].strip():
        problems.append("%s has no question text ('q')." % label)
    options = q.get("options") if isinstance(q.get("options"), list) else []
    answer = q.get("answer")

    if kind == "single":
        if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer < len(options):
            problems.append("%s: answer %r is not a valid index into %d options." % (label, answer, len(options)))
    elif kind == "multi":
        if len(options) < 2:
            problems.append("%s: a multi-select question needs at least 2 options." % label)
        if (not isinstance(answer, list) or not answer
                or any(not isinstance(a, int) or isinstance(a, bool) or not 0 <= a < len(options) for a in answer)):
            problems.append("%s: answer must be a non-empty list of option indexes." % label)
    elif kind == "tf":
        if not isinstance(answer, bool):
            problems.append("%s: a true/false question needs answer true or false." % label)
    elif kind == "numeric":
        if not _is_number(answer):
            problems.append("%s: a numeric question needs a number as its answer." % label)
        tol = q.get("tolerance", 0)
        if not _is_number(tol) or tol < 0:
            problems.append("%s: tolerance must be a number >= 0." % label)
    elif kind == "order":
        if len(options) < 2:
            problems.append("%s: an ordering question needs at least 2 options, listed in the correct order." % label)
    elif kind == "match":
        pairs = q.get("pairs")
        ok = (isinstance(pairs, list) and len(pairs) >= 2
              and all(isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) and x.strip() for x in p)
                      for p in pairs))
        if not ok:
            problems.append("%s: a matching question needs 'pairs', a list of at least 2 [left, right] strings." % label)
    elif kind == "cloze":
        if "___" not in str(q.get("q", "")):
            problems.append("%s: a cloze question needs a blank written as ___ in its text." % label)
        if not ((isinstance(answer, str) and answer.strip()) or _strings(answer)):
            problems.append("%s: a cloze answer is a string, or a list of acceptable strings." % label)
    elif kind == "short":
        if not isinstance(q.get("model"), str) or not q["model"].strip():
            problems.append("%s: a short-answer question needs a 'model' answer to compare against." % label)

    if not q.get("why"):
        problems.append("%s has no 'why' explanation." % label)
    feedback = q.get("feedback")
    if feedback is not None:
        expected = 2 if kind == "tf" else len(options)
        if kind not in OPTION_TYPES:
            problems.append("%s: per-option 'feedback' only applies to single, multi and tf questions." % label)
        elif not isinstance(feedback, list) or len(feedback) != expected:
            problems.append("%s: 'feedback' must have one entry per option (%d)." % (label, expected))
    hints = q.get("hints")
    if hints is not None and not (isinstance(hints, list) and all(isinstance(h, str) for h in hints)):
        problems.append("%s: 'hints' must be a list of strings." % label)
    return problems


def roleplay_problems(rp: Any, label: str) -> List[str]:
    if not isinstance(rp, dict):
        return ["%s roleplay must be an object." % label]
    problems = []
    for key in ROLEPLAY_KEYS:
        if not isinstance(rp.get(key), str) or not rp[key].strip():
            problems.append("%s roleplay is missing '%s'." % (label, key))
    if not _strings(rp.get("rubric")):
        problems.append("%s roleplay needs a 'rubric': a list of things the reader is judged on." % label)
    return problems


def _check_assessments(modules, assessments) -> List[str]:
    problems = []
    for m in modules:
        entry = assessments.get(m.id)
        if entry is None:
            problems.append("%s has no assessment. Add an entry with id '%s'." % (m.id, m.id))
            continue
        for key in ASSESS_KEYS:
            if key not in entry:
                problems.append("%s assessment is missing '%s'." % (m.id, key))
        for i, q in enumerate(entry.get("quiz", [])):
            problems += quiz_item_problems(q, "%s quiz[%d]" % (m.id, i))
        for i, c in enumerate(entry.get("cards", [])):
            if not c.get("front") or not c.get("back"):
                problems.append("%s cards[%d] needs both 'front' and 'back'." % (m.id, i))
        if entry.get("roleplay"):
            problems += roleplay_problems(entry["roleplay"], m.id)

    orphans = sorted(set(assessments) - {m.id for m in modules})
    for o in orphans:
        problems.append("Assessment for '%s' matches no module." % o)
    return problems


def _check_suggestions(modules, suggestions) -> List[str]:
    """One set of follow-up questions per section — the rail indexes them positionally."""
    problems = []
    for m in modules:
        rows = suggestions.get(m.id)
        if rows is None:
            problems.append("%s has no suggested questions." % m.id)
            continue
        if len(rows) != len(m.sections):
            problems.append(
                "%s has %d sections but %d sets of suggested questions — they are matched by "
                "position, so the counts must agree." % (m.id, len(m.sections), len(rows))
            )
    orphans = sorted(set(suggestions) - {m.id for m in modules})
    for o in orphans:
        problems.append("Suggested questions for '%s' match no module." % o)
    return problems


def raise_if_broken(problems: List[str]) -> None:
    if problems:
        raise DataError(
            "This course is not consistent:\n  - " + "\n  - ".join(problems)
        )

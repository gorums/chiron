"""Every cross-file consistency check, in one place.

These run before anything is written. The failures they catch — a quiz whose answer index
points past its options, a module with four sections but three sets of follow-up questions —
are all silent at runtime: the page renders, and something is quietly missing or wrong.
Collecting them means one build tells you everything to fix, not the first thing.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..errors import DataError

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


def _is_index(value: Any, options: list) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(options)


def _options(q: Dict[str, Any]) -> list:
    return q.get("options") if isinstance(q.get("options"), list) else []


# ---- one checker per quiz type: what its answer has to look like -----------------------


def _single_problems(q: Dict[str, Any], label: str) -> List[str]:
    options, answer = _options(q), q.get("answer")
    if not _is_index(answer, options):
        return ["%s: answer %r is not a valid index into %d options." % (label, answer, len(options))]
    return []


def _multi_problems(q: Dict[str, Any], label: str) -> List[str]:
    options, answer = _options(q), q.get("answer")
    problems = []
    if len(options) < 2:
        problems.append("%s: a multi-select question needs at least 2 options." % label)
    if not isinstance(answer, list) or not answer or not all(_is_index(a, options) for a in answer):
        problems.append("%s: answer must be a non-empty list of option indexes." % label)
    return problems


def _tf_problems(q: Dict[str, Any], label: str) -> List[str]:
    if not isinstance(q.get("answer"), bool):
        return ["%s: a true/false question needs answer true or false." % label]
    return []


def _numeric_problems(q: Dict[str, Any], label: str) -> List[str]:
    problems = []
    if not _is_number(q.get("answer")):
        problems.append("%s: a numeric question needs a number as its answer." % label)
    tol = q.get("tolerance", 0)
    if not _is_number(tol) or tol < 0:
        problems.append("%s: tolerance must be a number >= 0." % label)
    return problems


def _order_problems(q: Dict[str, Any], label: str) -> List[str]:
    if len(_options(q)) < 2:
        return ["%s: an ordering question needs at least 2 options, listed in the correct order." % label]
    return []


def _match_problems(q: Dict[str, Any], label: str) -> List[str]:
    pairs = q.get("pairs")
    ok = (isinstance(pairs, list) and len(pairs) >= 2
          and all(isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) and x.strip() for x in p)
                  for p in pairs))
    if not ok:
        return ["%s: a matching question needs 'pairs', a list of at least 2 [left, right] strings." % label]
    return []


def _cloze_problems(q: Dict[str, Any], label: str) -> List[str]:
    answer = q.get("answer")
    problems = []
    if "___" not in str(q.get("q", "")):
        problems.append("%s: a cloze question needs a blank written as ___ in its text." % label)
    if not ((isinstance(answer, str) and answer.strip()) or _strings(answer)):
        problems.append("%s: a cloze answer is a string, or a list of acceptable strings." % label)
    return problems


def _short_problems(q: Dict[str, Any], label: str) -> List[str]:
    if not isinstance(q.get("model"), str) or not q["model"].strip():
        return ["%s: a short-answer question needs a 'model' answer to compare against." % label]
    return []


# The one place a type is matched to its rules. Keyed by QUIZ_TYPES, and checked to be.
ANSWER_CHECKS = {
    "single": _single_problems, "multi": _multi_problems, "tf": _tf_problems,
    "numeric": _numeric_problems, "order": _order_problems, "match": _match_problems,
    "cloze": _cloze_problems, "short": _short_problems,
}
assert set(ANSWER_CHECKS) == set(QUIZ_TYPES), "every quiz type needs an answer check"


def _feedback_problems(q: Dict[str, Any], kind: str, label: str) -> List[str]:
    """Per-option feedback: only for types whose answer is picked from options, one per option."""
    feedback = q.get("feedback")
    if feedback is None:
        return []
    if kind not in OPTION_TYPES:
        return ["%s: per-option 'feedback' only applies to single, multi and tf questions." % label]
    expected = 2 if kind == "tf" else len(_options(q))
    if not isinstance(feedback, list) or len(feedback) != expected:
        return ["%s: 'feedback' must have one entry per option (%d)." % (label, expected)]
    return []


def _hints_problems(q: Dict[str, Any], label: str) -> List[str]:
    hints = q.get("hints")
    if hints is not None and not (isinstance(hints, list) and all(isinstance(h, str) for h in hints)):
        return ["%s: 'hints' must be a list of strings." % label]
    return []


def quiz_item_problems(q: Any, label: str) -> List[str]:
    """Every problem with one quiz item. Public so Studio can lean on the same rules.

    The shape every type shares is checked here; what each type's answer must look like is
    one function per type in `ANSWER_CHECKS`."""
    if not isinstance(q, dict):
        return ["%s is not an object." % label]
    kind = q.get("type") or "single"
    if kind not in QUIZ_TYPES:
        return ["%s has unknown type %r. Known types: %s." % (label, kind, ", ".join(QUIZ_TYPES))]
    problems: List[str] = []
    if not isinstance(q.get("q"), str) or not q["q"].strip():
        problems.append("%s has no question text ('q')." % label)
    problems += ANSWER_CHECKS[kind](q, label)
    if not q.get("why"):
        problems.append("%s has no 'why' explanation." % label)
    problems += _feedback_problems(q, kind, label)
    problems += _hints_problems(q, label)
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

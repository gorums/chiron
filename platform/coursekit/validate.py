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


def check(modules, assessments: Dict[str, Any], suggestions: Dict[str, Any]) -> List[str]:
    """Return every problem found. Empty list means the course is coherent."""
    problems: List[str] = []
    problems += _check_ids(modules)
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
            options = q.get("options") or []
            answer = q.get("answer")
            if not isinstance(answer, int) or not 0 <= answer < len(options):
                problems.append(
                    "%s quiz[%d]: answer %r is not a valid index into %d options."
                    % (m.id, i, answer, len(options))
                )
            if not q.get("why"):
                problems.append("%s quiz[%d] has no 'why' explanation." % (m.id, i))
        for i, c in enumerate(entry.get("cards", [])):
            if not c.get("front") or not c.get("back"):
                problems.append("%s cards[%d] needs both 'front' and 'back'." % (m.id, i))

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

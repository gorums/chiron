"""Model output into the shapes the build accepts.

Model output is trusted for prose and distrusted for structure. Every JSON reply that ends
up in a course's data files passes through one of these: a quiz item gets the fields its
type demands or is dropped, a flashcard missing a side is dropped, the suggestion list is
padded or trimmed to one entry per section. What cannot be repaired raises
`GenerationError` so a run fails loudly instead of shipping an empty quiz.

`coursekit.validate` is the authority on what is valid; these functions only coerce
towards it, and `test_studio.py` checks their output passes the real validator.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from coursekit import validate as ck_validate
from coursekit.settings import SETTINGS

from .curriculum import DEFAULT_SECTIONS
from .errors import GenerationError

# All from the `generation` block of settings.json.
QUIZ_ITEMS = int(SETTINGS.get("generation.quizItems"))
CARD_ITEMS = int(SETTINGS.get("generation.cardItems"))
QUESTIONS_PER_SECTION = int(SETTINGS.get("generation.questionsPerSection"))

FALLBACK_QUESTIONS = ("Why does this matter?",
                      "Can you show me an example?",
                      "How does this apply to my situation?")
REVIEW_VERDICTS = ("solid", "needs work", "rewrite")


def strings(value: Any, cap: int = 12) -> List[str]:
    """A list of non-empty strings out of a string, a list, or anything else (-> [])."""
    if isinstance(value, str):
        value = [value]
    items = value if isinstance(value, list) else []
    return [str(v).strip() for v in items if str(v).strip()][:cap]


def number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- quiz items


def fix_quiz_item(q: Any) -> Optional[Dict[str, Any]]:
    """One quiz item into a shape `validate.quiz_item_problems` accepts, or None to drop it."""
    if not isinstance(q, dict):
        return None
    kind = str(q.get("type") or "single").strip().lower()
    if kind not in ck_validate.QUIZ_TYPES:
        kind = "single"
    out: Dict[str, Any] = {
        "type": kind,
        "q": str(q.get("q") or "").strip() or "Which statement follows from this module?",
        "why": str(q.get("why") or "").strip() or "See the module section this draws on.",
    }
    body = _QUIZ_BODIES[kind](q, out)
    if body is None:
        return None
    out.update(body)

    feedback = strings(q.get("feedback"), 8)
    expected = 2 if kind == "tf" else len(out.get("options", []))
    if kind in ck_validate.OPTION_TYPES and feedback and len(feedback) == expected:
        out["feedback"] = feedback
    hints = strings(q.get("hints"), 3)
    if hints:
        out["hints"] = hints
    return out


# One function per question type: the type-specific fields, or None when unrepairable.

def _single(q, out):
    options = strings(q.get("options"), 8)
    if len(options) < 2:
        return None
    idx = number(q.get("answer"))
    idx = int(idx) if idx is not None else 0
    return {"options": options, "answer": max(0, min(idx, len(options) - 1))}


def _multi(q, out):
    options = strings(q.get("options"), 8)
    if len(options) < 2:
        return None
    answer = q.get("answer")
    picks = answer if isinstance(answer, list) else [answer]
    idxs = sorted({int(number(a)) for a in picks
                   if number(a) is not None and 0 <= int(number(a)) < len(options)})
    if not idxs:
        return None
    return {"options": options, "answer": idxs}


def _tf(q, out):
    answer = q.get("answer")
    if isinstance(answer, bool):
        return {"answer": answer}
    if isinstance(answer, str) and answer.strip().lower() in ("true", "false"):
        return {"answer": answer.strip().lower() == "true"}
    return None


def _numeric(q, out):
    value = number(q.get("answer"))
    if value is None:
        return None
    fields: Dict[str, Any] = {"answer": int(value) if value == int(value) else value}
    tol = number(q.get("tolerance"))
    fields["tolerance"] = abs(tol) if tol is not None else 0
    if q.get("unit"):
        fields["unit"] = str(q["unit"]).strip()[:12]
    return fields


def _order(q, out):
    options = strings(q.get("options"), 8)
    return {"options": options} if len(options) >= 2 else None


def _match(q, out):
    pairs = []
    for pair in (q.get("pairs") if isinstance(q.get("pairs"), list) else []):
        if isinstance(pair, dict):
            pair = [pair.get("left") or pair.get("term"), pair.get("right") or pair.get("match")]
        if isinstance(pair, list) and len(pair) == 2 and all(str(x).strip() for x in pair):
            pairs.append([str(pair[0]).strip(), str(pair[1]).strip()])
    return {"pairs": pairs[:6]} if len(pairs) >= 2 else None


def _cloze(q, out):
    text = out["q"]
    if "___" not in text:
        if "____" in text or "[blank]" in text.lower():
            text = re.sub(r"_{2,}|\[blank\]", "___", text, flags=re.I)
        else:
            return None
    fills = strings(q.get("answer"), 8)
    return {"q": text, "answer": fills} if fills else None


def _short(q, out):
    model = str(q.get("model") or q.get("answer") or "").strip()
    return {"model": model} if model else None


_QUIZ_BODIES = {
    "single": _single, "multi": _multi, "tf": _tf, "numeric": _numeric,
    "order": _order, "match": _match, "cloze": _cloze, "short": _short,
}
assert set(_QUIZ_BODIES) == set(ck_validate.QUIZ_TYPES), "every quiz type needs a coercer"


# --------------------------------------------------------------------------- study data


def fix_roleplay(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    out = {k: str(raw.get(k) or "").strip() for k in ck_validate.ROLEPLAY_KEYS}
    if not all(out.values()):
        return None
    out["rubric"] = strings(raw.get("rubric"), 5) or [
        "Reached the goal without giving ground on the essentials."]
    return out


def fix_assessment(raw: Any, mid: str) -> Dict[str, Any]:
    """A module's assessment into something the validator will accept, or fail loudly."""
    if not isinstance(raw, dict):
        raise GenerationError("%s assessment was not a JSON object." % mid)
    out: Dict[str, Any] = {"id": mid}
    out["predict"] = str(raw.get("predict") or "Before reading: what do you expect this to say?")

    quiz = [item for item in (fix_quiz_item(q) for q in (raw.get("quiz") or [])[:QUIZ_ITEMS]) if item]
    if not quiz:
        raise GenerationError("%s assessment produced no usable quiz questions." % mid)
    out["quiz"] = quiz

    cards = [{"front": str(c.get("front") or "").strip(), "back": str(c.get("back") or "").strip()}
             for c in (raw.get("cards") or [])[:CARD_ITEMS] if isinstance(c, dict)]
    cards = [c for c in cards if c["front"] and c["back"]]
    if not cards:
        raise GenerationError("%s assessment produced no usable flashcards." % mid)
    out["cards"] = cards

    out["elaborate"] = strings(raw.get("elaborate"), 12) or [
        "Explain this module's main idea in your own words."]

    transfer = raw.get("transfer") or {}
    out["transfer"] = {
        "scenario": str(transfer.get("scenario") or "").strip(),
        "prompt": str(transfer.get("prompt") or "Apply this module to the situation above.").strip(),
        "model": str(transfer.get("model") or "").strip(),
    }
    roleplay = fix_roleplay(raw.get("roleplay"))
    if roleplay:
        out["roleplay"] = roleplay
    return out


def fix_suggestions(raw: Any, headings: List[str]) -> List[List[str]]:
    """Force one list of `QUESTIONS_PER_SECTION` questions per heading. Not negotiable."""
    rows = raw if isinstance(raw, list) else []
    if rows and isinstance(rows[0], str):        # a flat list of questions: regroup it
        rows = [rows[i:i + QUESTIONS_PER_SECTION]
                for i in range(0, len(rows), QUESTIONS_PER_SECTION)]
    fixed: List[List[str]] = []
    for i, _heading in enumerate(headings):
        row = rows[i] if i < len(rows) and isinstance(rows[i], list) else []
        questions = strings(row, QUESTIONS_PER_SECTION)
        while len(questions) < QUESTIONS_PER_SECTION:
            questions.append(FALLBACK_QUESTIONS[len(questions) % len(FALLBACK_QUESTIONS)])
        fixed.append(questions)
    return fixed


# --------------------------------------------------------------------------- module specs


def fix_spec(raw: Any, mid: str, part_id: str, topic: str, minutes: int,
             known_ids=()) -> Dict[str, Any]:
    """A designed module spec (from `prompts.module_spec`) into the shape the writer needs."""
    raw = raw if isinstance(raw, dict) else {}
    spec = {
        "id": mid,
        "part": part_id,
        "title": (str(raw.get("title") or topic).strip() or topic)[:120],
        "short": (str(raw.get("short") or topic).strip() or topic)[:60],
        "summary": str(raw.get("summary") or "").strip(),
    }
    try:
        spec["minutes"] = max(15, min(240, int(raw.get("minutes") or minutes)))
    except (TypeError, ValueError):
        spec["minutes"] = minutes
    spec["sections"] = strings(raw.get("sections"), 20) or list(DEFAULT_SECTIONS)
    known = set(known_ids)
    spec["requires"] = [r for r in strings(raw.get("requires"), 10)
                        if r in known and r != mid][:3]
    return spec


# --------------------------------------------------------------------------- reviews


def fix_review(raw: Any) -> Dict[str, Any]:
    """A review reply into the shape the UI renders."""
    raw = raw if isinstance(raw, dict) else {}
    verdict = str(raw.get("verdict") or "").strip().lower()
    if verdict not in REVIEW_VERDICTS:
        verdict = "needs work"
    return {
        "verdict": verdict,
        "summary": str(raw.get("summary") or "").strip()[:1200],
        "gaps": _findings(raw.get("gaps"), "where"),
        "errors": _findings(raw.get("errors"), "where"),
        "quiz": _findings(raw.get("quiz"), "item"),
        "rewriteBrief": str(raw.get("rewriteBrief") or "").strip()[:1500],
    }


def _findings(raw: Any, first: str) -> List[Dict[str, str]]:
    """Review findings as {<first>, issue, fix} rows; a bare string is an issue."""
    out = []
    for row in raw if isinstance(raw, list) else []:
        if isinstance(row, str) and row.strip():
            out.append({first: "", "issue": row.strip()[:600], "fix": ""})
        elif isinstance(row, dict):
            issue = str(row.get("issue") or "").strip()
            if issue:
                out.append({first: str(row.get(first) or "").strip()[:200],
                            "issue": issue[:600], "fix": str(row.get("fix") or "").strip()[:600]})
    return out[:12]

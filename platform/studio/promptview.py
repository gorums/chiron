"""Every prompt one module is written from, gathered for reading and editing.

The approval gate and the course page both show a module's prompts and let the owner replace
any of them (`overrides`). This is the one place that knows how to assemble the set: which
stages exist for this course, what each one's prompt currently is, and what the platform's
own text would be if the override were taken away.

Two rules make the screen honest:

**A row is built by the same function the run calls** - `generator.module_prompt`,
`figures.figures_prompt`, ... - so what is shown cannot drift from what is sent.

**The volatile values are shown as their tokens.** A module's text does not exist when its
prompt is written, and would be stale by the next rewrite if it did, so the prompt shown
carries `{{module_text}}` where the text goes and `{{study_data}}` where the quiz goes;
`overrides.apply` puts the real values in at the moment of the call.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import figures, generator, notebooks, overrides, reviews


def rows(plan: Dict[str, Any], mid: str, root: str = "",
         carried: Dict[str, str] = None) -> List[Dict[str, Any]]:
    """Every stage of one module: what would be sent, and what the platform would send.

    `root` is the course on disk, "" for a course that does not exist yet - and then
    `carried` holds the overrides edited at the approval gate, which are saved into the
    course once it is laid down.
    """
    spec = next((m for m in plan.get("modules") or [] if m.get("id") == mid), None)
    if not spec:
        raise KeyError(mid)
    carried = carried or {}
    headings = [str(s) for s in (spec.get("sections") or []) if str(s).strip()]
    out = []
    for stage, label, note in overrides.STAGES:
        if not _applies(stage, plan):
            continue
        default = _default(stage, plan, spec, headings)
        override = carried.get(stage) or (overrides.get(root, mid, stage) if root else "")
        out.append({
            "stage": stage,
            "label": label,
            "note": note,
            "default": default,
            "prompt": override or default,
            "overridden": bool(override),
        })
    return out


def _applies(stage: str, plan: Dict[str, Any]) -> bool:
    """A stage nobody can run is a prompt nobody can edit: no notebooks in a course without
    the runtime, no figures where the platform draws none."""
    if stage == "notebooks":
        return bool(plan.get("notebooks")) and notebooks.enabled()
    if stage == "figures":
        return figures.enabled()
    return True


def _default(stage: str, plan: Dict[str, Any], spec: Dict[str, Any],
             headings: List[str]) -> str:
    """The platform's own prompt for one stage, with the tokens standing in for what is only
    known at the moment of the call."""
    mid = spec["id"]
    if stage == "module":
        return generator.module_prompt(plan, spec)
    if stage == "assessment":
        return generator.assessment_prompt(plan, spec, overrides.BODY)
    if stage == "suggestions":
        return generator.suggestions_prompt(plan, spec, headings, overrides.BODY)
    if stage == "figures":
        return figures.figures_prompt(plan, spec, overrides.BODY, headings)
    if stage == "notebooks":
        return notebooks.notebooks_prompt(plan, spec, overrides.BODY, headings)
    if stage == "review":
        return reviews.review_prompt(plan, spec, overrides.BODY, overrides.STUDY)
    raise ValueError("There is no %r stage of %s." % (stage, mid))

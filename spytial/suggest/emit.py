"""Render a :class:`SpecDraft` three ways: source, registry dict, or live decoration.

All three go through the same enabled-suggestion filter and ordering so what you
read is what gets applied.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..annotations import CONSTRAINT_TYPES
from ._model import SpecDraft, Suggestion

# Preferred order *within* a section. Which section a form belongs to is not
# restated here -- it is read from the tables, so a form that moves between
# sections upstream (`size` and `hideAtom` did, in spytial-core 4.3) moves here
# too instead of leaving this list quietly contradicting its own comment. A
# form missing from this list sorts to the end of its own section rather than
# the end of everything; test_spec_tables.py keeps the list complete.
_PREFERRED = [
    "orientation",
    "cyclic",
    "align",
    "group",
    "size",
    "hideAtom",
    "atomStyle",
    "atomColor",  # legacy alias of atomStyle; user heuristics may still emit it
    "icon",
    "edgeStyle",
    "edgeColor",  # legacy alias of edgeStyle
    "attribute",
    "hideField",
    "inferredEdge",
    "tag",
    "projection",
    "flag",
]
# Kwargs render in this order when present; everything else follows.
_KW_ORDER = [
    "selector",
    "field",
    "name",
    "directions",
    "direction",
    "value",
    "fillStyle",
    "borderStyle",
    "lineStyle",
    "textStyle",
]


def _is_constraint(directive: str) -> bool:
    return directive in CONSTRAINT_TYPES


def _rank(directive: str) -> tuple:
    """Constraints (geometry) before directives (drawing), then by preference.

    Matches how the gold-standard hand-written specs stack, and matches the
    order ``to_registry`` puts them in, so reading ``to_source`` tells you which
    section each rule lands in.
    """
    section = 0 if _is_constraint(directive) else 1
    within = _PREFERRED.index(directive) if directive in _PREFERRED else len(_PREFERRED)
    return (section, within)


def _selected(draft: SpecDraft, enabled_only: bool) -> List[Suggestion]:
    items = [s for s in draft.suggestions if s.enabled_by_default or not enabled_only]
    return sorted(items, key=lambda s: _rank(s.directive))


def _order_kwargs(kwargs: Dict[str, Any]) -> List[tuple]:
    def rank(k: str) -> int:
        return _KW_ORDER.index(k) if k in _KW_ORDER else len(_KW_ORDER)

    return sorted(kwargs.items(), key=lambda kv: rank(kv[0]))


def to_source(
    draft: SpecDraft, enabled_only: bool = True, with_comments: bool = True
) -> str:
    lines: List[str] = []
    for s in _selected(draft, enabled_only):
        if s.directive == "flag":
            rendered = f"name={s.kwargs.get('name')!r}"
        else:
            rendered = ", ".join(f"{k}={v!r}" for k, v in _order_kwargs(s.kwargs))
        comment = f"  # {s.rationale}" if with_comments and s.rationale else ""
        lines.append(f"@spytial.{s.directive}({rendered}){comment}")
    return "\n".join(lines)


def to_registry(draft: SpecDraft, enabled_only: bool = True) -> Dict[str, list]:
    constraints: List[dict] = []
    directives: List[dict] = []
    for s in _selected(draft, enabled_only):
        if s.directive == "flag":
            entry = {"flag": s.kwargs.get("name")}
        else:
            entry = {s.directive: dict(s.kwargs)}
        (constraints if _is_constraint(s.directive) else directives).append(entry)
    return {"constraints": constraints, "directives": directives}


def apply(draft: SpecDraft, enabled_only: bool = True) -> type:
    import spytial  # local import: suggest is not imported by spytial/__init__

    cls = draft.cls
    # Decorators stack bottom-up; reverse so the visual order matches to_source().
    for s in reversed(_selected(draft, enabled_only)):
        factory = getattr(spytial, s.directive)
        if s.directive == "flag":
            cls = factory(name=s.kwargs.get("name"))(cls)
        else:
            cls = factory(**s.kwargs)(cls)
    return cls

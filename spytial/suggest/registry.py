"""The heuristic registry and the draft-building engine.

Deliberately mirrors the relationalizer registry (``provider_system.py``):
priority-ordered, highest-first, with the 0-99 band reserved for built-ins.
A heuristic is just a function — built-ins are registered the same way a user
would register their own.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, List, Optional, Tuple

from ._model import ClassInfo, SpecDraft, Suggestion

# Directives where at most one may apply to a given field. If several land on the
# same field, the best wins and the rest become toggled-off alternatives. Others
# (e.g. atomColor, one per enum member) are additive and all kept.
EXCLUSIVE_DIRECTIVES = {"orientation", "cyclic", "align", "attribute", "hideField"}


class HeuristicRegistry:
    """An ordered collection of heuristics.

    Use the default registry for global rules, or construct one for an isolated
    rule set passed to :func:`suggest`.
    """

    def __init__(self) -> None:
        # (priority, scope, fn), kept sorted highest-priority-first.
        self._heuristics: List[Tuple[int, str, Callable]] = []

    def register(
        self, fn: Callable, *, scope: str = "field", priority: int = 0
    ) -> Callable:
        if scope not in ("field", "class"):
            raise ValueError(f"scope must be 'field' or 'class', got {scope!r}")
        self._heuristics.append((priority, scope, fn))
        self._heuristics.sort(key=lambda x: x[0], reverse=True)
        return fn

    def heuristic(
        self, fn: Optional[Callable] = None, *, scope: str = "field", priority: int = 0
    ):
        """Decorator form of :meth:`register`."""

        def deco(f: Callable) -> Callable:
            return self.register(f, scope=scope, priority=priority)

        return deco(fn) if fn is not None else deco

    def run(self, class_info: ClassInfo) -> List[Tuple[int, Suggestion]]:
        """Invoke every heuristic; return ``(priority, suggestion)`` pairs."""
        out: List[Tuple[int, Suggestion]] = []
        for priority, scope, fn in self._heuristics:
            if scope == "class":
                results = fn(class_info) or []
            else:
                results = []
                for fi in class_info.fields:
                    results.extend(fn(fi, class_info) or [])
            for s in results:
                out.append((priority, s))
        return out

    def list_heuristics(self) -> List[Tuple[int, str, str]]:
        return [(p, s, getattr(f, "__name__", repr(f))) for p, s, f in self._heuristics]

    def copy(self) -> "HeuristicRegistry":
        """A new registry seeded with this one's heuristics (e.g. the built-ins)."""
        clone = HeuristicRegistry()
        clone._heuristics = list(self._heuristics)
        return clone


#: The registry the built-in rules and bare ``@heuristic`` register into.
DEFAULT_REGISTRY = HeuristicRegistry()


def heuristic(
    fn: Optional[Callable] = None, *, scope: str = "field", priority: int = 0
):
    """Register a heuristic into the default registry.

    Works bare (``@heuristic``) or parameterized (``@heuristic(scope='class')``).
    """

    def deco(f: Callable) -> Callable:
        DEFAULT_REGISTRY.register(f, scope=scope, priority=priority)
        return f

    return deco(fn) if fn is not None else deco


def _sort_key(priority: int, suggestion: Suggestion) -> Tuple[int, int]:
    return (priority, suggestion.rank)


def build_draft(class_info: ClassInfo, registry: HeuristicRegistry) -> SpecDraft:
    """Run the registry over a class and resolve conflicts into a draft."""
    raw = registry.run(class_info)

    # 1. De-duplicate identical (directive, kwargs), keeping the strongest.
    best: dict = {}
    for priority, s in raw:
        k = s.dedup_key()
        key_rank = _sort_key(priority, s)
        if k not in best or key_rank > best[k][0]:
            best[k] = (key_rank, s)
    items = list(best.values())  # [((priority, rank), Suggestion)]

    # 2. Resolve same-field conflicts among mutually-exclusive directives.
    suggestions: List[Suggestion] = []
    alternatives: List[Suggestion] = []
    by_field: dict = defaultdict(list)
    standalone: List[Tuple[tuple, Suggestion]] = []
    for key_rank, s in items:
        if s.source_field is None:
            standalone.append((key_rank, s))
        else:
            by_field[s.source_field].append((key_rank, s))

    for _field_name, group in by_field.items():
        exclusive = [(r, s) for r, s in group if s.directive in EXCLUSIVE_DIRECTIVES]
        additive = [(r, s) for r, s in group if s.directive not in EXCLUSIVE_DIRECTIVES]
        if len(exclusive) > 1:
            exclusive.sort(key=lambda x: x[0], reverse=True)
            suggestions.append(exclusive[0][1])
            for _r, loser in exclusive[1:]:
                loser.enabled_by_default = False
                alternatives.append(loser)
        else:
            suggestions.extend(s for _r, s in exclusive)
        suggestions.extend(s for _r, s in additive)

    suggestions.extend(s for _r, s in standalone)

    return SpecDraft(
        cls=class_info.cls,
        suggestions=suggestions,
        alternatives=alternatives,
        notes=_build_notes(class_info),
    )


def _build_notes(class_info: ClassInfo) -> List[str]:
    notes: List[str] = []
    private = [f.name for f in class_info.fields if f.is_private]
    if private:
        notes.append(
            f"{len(private)} private field(s) ({', '.join(private)}) are already "
            "hidden by the relationalizers — no directive needed."
        )
    if not class_info.fields:
        notes.append(
            "No fields discovered; pass instance=... so the analyzer can sample one."
        )
    elif not any(f.is_self_ref for f in class_info.fields):
        notes.append(
            "No self-referential fields found — structure could not be inferred "
            "statically (array/index-encoded structures need a custom heuristic)."
        )
    return notes

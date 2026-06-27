"""``spytial.suggest`` — scaffold a SpyTial spec from class analysis.

A lightweight, deterministic starting point you then edit::

    from spytial.suggest import suggest

    draft = suggest(TreeNode)                 # static analysis only
    print(draft.to_source())                  # paste-able @spytial.* stack
    draft.apply()                             # or decorate the class live
    draft                                     # rich panel in Jupyter

Pass ``instance=`` when a plain class can't be read statically (e.g. children
default to ``None``), and ``registry=`` to run an isolated set of heuristics.
Extend the rules with the :func:`heuristic` decorator.

This subpackage is intentionally *not* imported by ``spytial`` itself: it adds
no dependencies and stays dormant until you reach for it.
"""

from __future__ import annotations

from typing import Any, Optional

from . import rules  # noqa: F401  (import for the side effect of registering built-ins)
from ._model import ClassInfo, FieldInfo, SpecDraft, Suggestion
from .introspect import build_class_info
from .registry import DEFAULT_REGISTRY, HeuristicRegistry, build_draft, heuristic

__all__ = [
    "suggest",
    "heuristic",
    "HeuristicRegistry",
    "DEFAULT_REGISTRY",
    "Suggestion",
    "SpecDraft",
    "FieldInfo",
    "ClassInfo",
    "build_class_info",
]


def suggest(
    target: Any,
    *,
    instance: Any = None,
    registry: Optional[HeuristicRegistry] = None,
    enrich: bool = False,
) -> SpecDraft:
    """Analyze a class and return a :class:`SpecDraft` of proposed directives.

    Args:
        target: the class to analyze, or an instance (its class is used and the
            instance is sampled).
        instance: an optional example object to sample for types static reading
            can't recover.
        registry: an alternate :class:`HeuristicRegistry`; defaults to the global
            one populated with the built-in rules.
        enrich: reserved for the optional LLM enrichment layer (semantic palettes,
            unfamiliar domain naming). Not yet implemented.
    """
    if enrich:
        raise NotImplementedError(
            "LLM enrichment is not implemented yet. The static analyzer needs no "
            "extra dependencies; when enrichment lands it will live behind the "
            "'spytial_diagramming[suggest-llm]' extra."
        )
    if isinstance(target, type):
        cls = target
    else:
        # An instance was passed directly — infer the class and sample it.
        instance = target if instance is None else instance
        cls = type(target)

    reg = registry if registry is not None else DEFAULT_REGISTRY
    class_info = build_class_info(cls, instance=instance)
    return build_draft(class_info, reg)

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
    enrich_model: Optional[str] = None,
) -> SpecDraft:
    """Analyze a class and return a :class:`SpecDraft` of proposed directives.

    Args:
        target: the class to analyze, or an instance (its class is used and the
            instance is sampled).
        instance: an optional example object to sample for types static reading
            can't recover.
        registry: an alternate :class:`HeuristicRegistry`; defaults to the global
            one populated with the built-in rules.
        enrich: opt into the optional LLM enrichment layer (the ``[suggest-llm]``
            extra). It only *fills values* into selectors the deterministic rules
            already generated — today, semantic colors for enum members in place of
            the arbitrary built-in palette. The model never writes a selector;
            enriched rows are tagged ``source="llm"`` and stay off by default, so
            they are candidates you pick. Degrades to the static draft (with a note)
            if ``llm`` isn't installed or no model is configured — never raises.
        enrich_model: an ``llm`` model id (e.g. ``"claude-sonnet-4-6"``); defaults
            to your configured ``llm`` default model. Ignored unless ``enrich``.
    """
    if isinstance(target, type):
        cls = target
    else:
        # An instance was passed directly — infer the class and sample it.
        instance = target if instance is None else instance
        cls = type(target)

    reg = registry if registry is not None else DEFAULT_REGISTRY
    class_info = build_class_info(cls, instance=instance)
    draft = build_draft(class_info, reg)
    if enrich:
        from ._enrich import enrich_draft

        draft = enrich_draft(draft, class_info, model=enrich_model)
    return draft

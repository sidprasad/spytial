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

from typing import Any, List, Optional

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


def _coerce_examples(examples: Any, instance: Any) -> List[Any]:
    """Normalize the example set used to validate model-authored selectors.

    ``examples`` is a list/tuple of instances; a bare object counts as one example.
    When omitted, fall back to the single sampled ``instance`` so the common
    ``suggest(obj, enrich=True)`` validates against ``obj``. ``None`` entries drop.
    """
    if examples is None:
        return [instance] if instance is not None else []
    if isinstance(examples, (list, tuple)):
        return [e for e in examples if e is not None]
    return [examples]


def suggest(
    target: Any,
    *,
    instance: Any = None,
    examples: Optional[List[Any]] = None,
    registry: Optional[HeuristicRegistry] = None,
    enrich: bool = False,
    enrich_model: Optional[str] = None,
) -> SpecDraft:
    """Analyze a class and return a :class:`SpecDraft` of proposed directives.

    Args:
        target: the class to analyze, or an instance (its class is used and the
            instance is sampled).
        instance: an optional example object to sample for types static reading
            can't recover. Also the default example for selector validation (see
            ``examples``).
        examples: a list of example instances to validate model-authored selectors
            against (the ``enrich`` selector tier). A selector is admitted only if it
            resolves on *every* example, so several instances narrow the gap toward
            "correct on all data". Defaults to ``[instance]`` (or the instance form of
            ``target``); pass more for the instance-set form. Ignored unless ``enrich``.
        registry: an alternate :class:`HeuristicRegistry`; defaults to the global
            one populated with the built-in rules.
        enrich: opt into the optional LLM enrichment layer (the ``[suggest-llm]``
            extra). It suggests the *spatial shape* of the structure — orientation
            directions per structural field, ``cyclic`` for ring-like links, and
            ``group`` for collections — filling the gap where the deterministic rules
            fall back to a flat ``below`` for fields outside their name vocabulary.
            The model only chooses the shape; spytial supplies the (render-verified)
            selector from the field, so this stays schema-level and needs no
            instance. Enriched rows are tagged ``source="llm"`` and stay off by
            default — candidates you pick. Degrades to the static draft (with a note)
            if ``llm`` isn't installed or no model is configured — never raises.
            When examples are available, enrichment additionally authors *selectors*
            for relational cases the shape tier can't express, validating each by
            evaluating it over every example (these too are off-by-default
            ``source="llm"`` candidates).
        enrich_model: an ``llm`` model id (e.g. ``"claude-sonnet-4-6"``); defaults
            to your configured ``llm`` default model. Ignored unless ``enrich``.
    """
    if isinstance(target, type):
        cls = target
    else:
        # An instance was passed directly — infer the class and sample it.
        instance = target if instance is None else instance
        cls = type(target)

    # The example set drives selector validation (tier-2). Default it to the sampled
    # instance so suggest(obj, enrich=True) just works; an explicit examples= list is
    # the instance-set form. The introspection sample falls back to the first example.
    example_objs = _coerce_examples(examples, instance)
    sample = (
        instance
        if instance is not None
        else (example_objs[0] if example_objs else None)
    )

    reg = registry if registry is not None else DEFAULT_REGISTRY
    class_info = build_class_info(cls, instance=sample)
    draft = build_draft(class_info, reg)
    if enrich:
        from ._enrich import enrich_draft

        draft = enrich_draft(
            draft, class_info, model=enrich_model, examples=example_objs
        )
    return draft

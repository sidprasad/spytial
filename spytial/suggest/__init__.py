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
from .providers import (
    ClaudeCode,
    Codex,
    EnrichError,
    EnrichProvider,
    LlmModel,
    as_provider,
)
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
    "EnrichProvider",
    "EnrichError",
    "LlmModel",
    "ClaudeCode",
    "Codex",
]


def _coerce_examples(examples: Any, instance: Any) -> List[Any]:
    """Normalize the example set used to validate model-authored selectors.

    ``examples`` is a list/tuple of instances; a bare object counts as one example.
    When omitted, fall back to the single sampled ``instance`` so the common
    ``suggest(obj, enrich=...)`` validates against ``obj``. ``None`` entries drop.
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
    enrich: Any = None,
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
        enrich: turn on the optional LLM enrichment layer by saying *what* to enrich
            with — there is no ambient default. Either a model-id **string** resolved
            through the ``llm`` library (e.g. ``enrich="llama3.2"``, ``"gpt-4o"``; the
            ``[suggest-llm]`` extra), or any **callable provider** with the signature
            ``(prompt, *, schema) -> dict`` — a function, or a built-in like
            :class:`~spytial.suggest.ClaudeCode` / :class:`~spytial.suggest.Codex` to
            enrich from a subscription instead of a metered key. ``None`` (default)
            or ``False`` leaves the draft static. Enrichment suggests the
            *spatial shape* of the structure (orientation directions per field,
            ``cyclic`` for ring-like links, ``group`` for collections). In this mode the
            model is the *primary* shape author — even for fields the built-in rules
            already name: its choice wins and is enabled, and the rule it beats is
            demoted to a backup alternative (kept, off, one toggle away). The
            deterministic shape returns as the active default only if the whole provider
            call fails. The model only chooses the shape; spytial supplies the
            render-verified selector. Enriched rows are tagged ``source="llm"``.
            When examples are available it additionally authors *selectors* for
            relational cases the shape tier can't express, validating each by
            evaluating it over every example. A spec that can't be resolved (``llm``
            missing, unknown id) degrades to the static draft with a note — never
            raises.
    """
    if isinstance(target, type):
        cls = target
    else:
        # An instance was passed directly — infer the class and sample it.
        instance = target if instance is None else instance
        cls = type(target)

    # The example set drives selector validation (tier-2). Default it to the sampled
    # instance so suggest(obj, enrich=...) just works; an explicit examples= list is
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
    # ``None``/``False`` mean "no enrichment"; everything else is a provider spec.
    # Use identity checks, not truthiness — a callable provider whose ``__bool__``
    # (or ``__len__``) is falsy must still resolve, since the contract accepts *any*
    # callable.
    if enrich is not None and enrich is not False:
        # Resolve the provider up front: a bad spec (no llm / unknown id / wrong
        # type) degrades to the static draft with a note rather than raising.
        try:
            provider = as_provider(enrich)
        except EnrichError as exc:
            draft.notes.append(f"enrich skipped: {exc}")
            return draft

        from ._enrich import enrich_draft

        draft = enrich_draft(
            draft, class_info, provider=provider, examples=example_objs
        )
    return draft

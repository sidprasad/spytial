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

This subpackage is intentionally *not* imported by ``spytial`` itself: the
ordinary static path adds no dependencies and stays dormant until you reach for
it.  Class-only ``ask=`` calls lazily use Hypothesis to derive a concrete
witness; pass ``examples=`` or ``strategy=`` to control that witness set.
"""

from __future__ import annotations

import sys as _sys
import types as _types
from typing import Any, List, Optional

from . import rules  # noqa: F401  (import for the side effect of registering built-ins)
from ._ask import AskError
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
    "AskError",
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
    strategy: Any = None,
    registry: Optional[HeuristicRegistry] = None,
    enrich: Any = None,
    ask: Optional[str] = None,
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
        strategy: an optional Hypothesis strategy that supplies one generated witness
            in addition to any fixed ``examples``. Pass ``"auto"`` to derive it with
            ``hypothesis.strategies.from_type(target)``. If ``ask=`` is used with a
            class and no instance/examples/strategy, ``"auto"`` is implied, so
            ``suggest(TreeNode, ask=..., enrich=...)`` works directly for a type
            Hypothesis can construct. Generation is bounded and provides a concrete
            vocabulary for selector validation; it is not a proof over the whole
            strategy. Requires the optional ``[suggest-search]`` extra. A failed
            strategy degrades to a static-draft note unless ``ask=`` makes the witness
            mandatory, in which case it raises :class:`AskError`.
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
        ask: a natural-language layout request to translate into directive(s) —
            e.g. ``ask="all binary tree children should be below their parents"``.
            Uses the same provider as ``enrich`` (which is therefore required), and
            admits a translation only after it passes the full gauntlet: known
            directive kind with in-vocabulary kwargs, selector evaluated at the
            right arity on *every* example, and the same authoring-time validation
            the ``@spytial.*`` decorators run. Admitted rows are enabled by default
            and tagged ``source="llm"``; a translation that matches an existing row
            enables that row instead of duplicating it. The ask is authoritative on
            the ground it covers: an admitted orientation/cyclic/align row demotes
            every enabled geometric row whose selector overlaps its own (checked by
            evaluating the intersection over the examples) to ``draft.alternatives``.
            Unlike enrichment, ``ask`` fails **loudly**: a missing provider, no
            buildable fixed or generated witness, no headless evaluator, or a
            translation that can't be validated raises
            :class:`AskError` with the reasons.
    """
    if ask is not None:
        if not isinstance(ask, str) or not ask.strip():
            raise AskError(
                "ask= must be a natural-language request (a non-empty string)."
            )
        ask = ask.strip()
        if enrich is None or enrich is False:
            raise AskError(
                "ask= needs a model: also pass enrich= — a model-id string, a "
                "callable provider, or a built-in like ClaudeCode() / Codex()."
            )

    if isinstance(target, type):
        cls = target
    else:
        # An instance was passed directly — infer the class and sample it.
        instance = target if instance is None else instance
        cls = type(target)

    # Fixed examples drive selector validation (tier-2). Default to the sampled
    # instance so suggest(obj, enrich=...) just works; an explicit examples= list is
    # the instance-set form. A strategy adds one generated witness. Class-only ask
    # implies strategy="auto": its selector translation needs a concrete datum even
    # though the caller only named a type.
    example_objs = _coerce_examples(examples, instance)
    strategy_note: Optional[str] = None
    effective_strategy = strategy
    if ask is not None and not example_objs and effective_strategy is None:
        effective_strategy = "auto"
    if effective_strategy is not None:
        from ._strategy import StrategyError, find_witness

        static_info = build_class_info(cls)
        try:
            witness = find_witness(cls, static_info, effective_strategy)
        except StrategyError as exc:
            if ask is not None:
                raise AskError(f"ask: {exc}") from exc
            strategy_note = f"strategy skipped: {exc}"
        else:
            example_objs.append(witness)
            origin = (
                "auto-derived"
                if isinstance(effective_strategy, str) and effective_strategy == "auto"
                else "supplied"
            )
            strategy_note = (
                f"strategy: added one Hypothesis witness from the {origin} strategy."
            )
    sample = (
        instance
        if instance is not None
        else (example_objs[0] if example_objs else None)
    )

    reg = registry if registry is not None else DEFAULT_REGISTRY
    class_info = build_class_info(cls, instance=sample)
    draft = build_draft(class_info, reg)
    if strategy_note:
        draft.notes.append(strategy_note)
    # ``None``/``False`` mean "no enrichment"; everything else is a provider spec.
    # Use identity checks, not truthiness — a callable provider whose ``__bool__``
    # (or ``__len__``) is falsy must still resolve, since the contract accepts *any*
    # callable.
    if enrich is not None and enrich is not False:
        # Resolve the provider up front: a bad spec (no llm / unknown id / wrong
        # type) degrades to the static draft with a note rather than raising —
        # unless the user asked, in which case the ask can't be honored: loud.
        try:
            provider = as_provider(enrich)
        except EnrichError as exc:
            if ask is not None:
                raise AskError(
                    f"ask: cannot resolve the enrich= provider ({exc})."
                ) from exc
            draft.notes.append(f"enrich skipped: {exc}")
            return draft

        from ._enrich import enrich_draft

        draft = enrich_draft(
            draft, class_info, provider=provider, examples=example_objs
        )
        if ask is not None:
            from ._ask import ask_draft

            ask_draft(draft, class_info, ask, provider=provider, examples=example_objs)
    return draft


class _CallableModule(_types.ModuleType):
    """Let ``spytial.suggest(...)`` be the call itself.

    The natural spelling — ``spytial.suggest(tree, ask=..., enrich=...)`` — treats
    this subpackage as the function. Swapping the module's class (the PEP 562-era
    idiom; ``__class__`` assignment on modules is supported for exactly this) makes
    the module callable while leaving every other access — ``from spytial.suggest
    import suggest``, ``spytial.suggest.SpecDraft`` — untouched.
    """

    def __call__(self, *args, **kwargs):
        return suggest(*args, **kwargs)


_sys.modules[__name__].__class__ = _CallableModule

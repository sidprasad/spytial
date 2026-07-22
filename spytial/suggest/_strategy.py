"""Hypothesis-backed witness generation for :mod:`spytial.suggest`.

This module is deliberately lazy.  The ordinary static ``suggest(Cls)`` path
does not import Hypothesis (and the package does not require it); only an
explicit ``strategy=`` or class-only ``ask=`` reaches this file's imports.

A strategy supplies a *witness*, not a proof.  The witness gives selector
authoring a concrete relational vocabulary to work over.  User-provided
``examples=`` retain the stronger, fixed-regression-case meaning: every one is
validated.  In particular, we do not mistake bounded generation for a claim
about every inhabitant of the type.
"""

from __future__ import annotations

import sys
from typing import Any, Callable, List, Optional, Set

from ..provider_system import CnDDataInstanceBuilder
from ._model import ClassInfo, FieldInfo
from .introspect import _looks_node_like, _referenced_names


class StrategyError(RuntimeError):
    """A Hypothesis strategy could not supply a usable witness."""


_MAX_EXAMPLES = 100


class _BuildTracker:
    """Tell 'no witness matched' apart from 'the builder is broken'.

    ``find`` calls the buildable predicate many times.  If ``build_instance``
    returns even once, the builder works and an exhausted search genuinely means
    nothing matched the predicate.  If it raised on *every* value, the failure is
    a builder bug, not an empty search — and we surface that instead of the
    misleading 'within the search budget' message (which would send the user off
    to write ``examples=`` for a witness the builder could never have accepted).
    """

    def __init__(self) -> None:
        self.ever_built = False
        self.last_error: Optional[Exception] = None


def find_witness(cls: type, ci: ClassInfo, strategy: Any) -> Any:
    """Return one buildable ``cls`` instance drawn from ``strategy``.

    ``strategy="auto"`` asks Hypothesis to derive ``from_type(cls)``.  For a
    recursive class, first try to populate every recursive root field, then
    search for any nontrivial object (at least two atoms of the root type).  This
    keeps a generated binary tree from shrinking to a leaf or a one-sided tree
    whose child relations cannot all be validated.  If the type genuinely has
    no nontrivial inhabitant under the strategy, fall back to any buildable one.

    ``hypothesis.find`` is used rather than ``SearchStrategy.example()``: it is
    the public API for bounded search and gives us deterministic shrinking.
    """
    find, settings, strategies, no_such_example = _hypothesis_api()

    if isinstance(strategy, str):
        if strategy != "auto":
            raise StrategyError(
                f"unknown strategy={strategy!r}; use 'auto' or pass a Hypothesis "
                "strategy."
            )
        try:
            source = strategies.from_type(cls)
        except Exception as exc:  # noqa: BLE001 — normalize Hypothesis diagnostics
            raise StrategyError(
                f"could not derive a Hypothesis strategy for {cls.__name__}: {exc}. "
                "Pass strategy=<a Hypothesis strategy> or examples=[...]."
            ) from exc
    else:
        source = strategy

    search_settings = settings(
        max_examples=_MAX_EXAMPLES,
        database=None,
        deadline=None,
        derandomize=True,
    )
    tracker = _BuildTracker()
    buildable = _buildable_predicate(cls, tracker)
    # The atom types that count as structural *nodes* of this graph — the root
    # class plus any sibling node-like type its self-ref fields point at, matching
    # introspect's own is_self_ref rule. Both witness-quality tiers key off this
    # so a heterogeneous graph (root -> a different node type) is judged by the
    # same rule that marked the field self-ref, not a root-only check.
    node_names = _node_type_names(cls, ci)

    # Recursive schemas need populated structural edges to ground an ask such as
    # "put every child below its parent". Prefer a root that exercises every
    # recursive field (both left and right, for example). Domain invariants may
    # make that impossible, so fall back to any graph containing another node-
    # like atom, then finally any buildable witness.
    if ci.self_ref_fields:
        # The fully-populated tier needs concrete fields to check. Gate it on the
        # SAME non-private self-ref set the predicate uses: a class whose only
        # self-ref field is private (e.g. a linked list linked by ``_next``) would
        # otherwise enter a tier that passes vacuously and hands back a leaf —
        # exactly the degenerate witness the tier exists to avoid. The nontrivial
        # tier still runs for any self-ref class, private field or not.
        populatable = [f for f in ci.fields if f.is_self_ref and not f.is_private]
        if populatable:
            fully_populated = _fully_populated_predicate(
                populatable, node_names, buildable
            )
            try:
                return find(source, fully_populated, settings=search_settings)
            except no_such_example:
                pass
            except Exception as exc:  # invalid strategy, bad generation, etc.
                raise _search_error(cls, exc, tracker) from exc

        nontrivial = _nontrivial_predicate(node_names, buildable)
        try:
            return find(source, nontrivial, settings=search_settings)
        except no_such_example:
            pass
        except Exception as exc:  # invalid strategy, bad generation, etc.
            raise _search_error(cls, exc, tracker) from exc

    try:
        return find(source, buildable, settings=search_settings)
    except Exception as exc:  # noqa: BLE001 — present one stable public error
        raise _search_error(cls, exc, tracker) from exc


def _hypothesis_api():
    """Import the optional dependency only when generation is requested."""
    try:
        from hypothesis import find, settings, strategies
        from hypothesis.errors import NoSuchExample
    except ImportError as exc:
        raise StrategyError(
            "strategy-backed suggestion needs Hypothesis. Install "
            "spytial_diagramming[suggest-search], or pass examples=[...] instead."
        ) from exc
    return find, settings, strategies, NoSuchExample


def _buildable_predicate(cls: type, tracker: _BuildTracker) -> Callable[[Any], bool]:
    def buildable(obj: Any) -> bool:
        if not isinstance(obj, cls):
            return False
        try:
            datum = CnDDataInstanceBuilder().build_instance(obj)
        except Exception as exc:  # noqa: BLE001 — Hypothesis should keep searching
            tracker.last_error = exc
            return False
        tracker.ever_built = True
        return bool(datum.get("atoms"))

    return buildable


def _node_type_names(cls: type, ci: ClassInfo) -> Set[str]:
    """Atom-type names that count as structural *nodes* of ``cls``'s graph.

    Mirrors introspect's ``_is_self_ref`` exactly — the root class, plus any
    sibling class in the same module that a self-ref field names and that itself
    looks node-like — so the witness-quality tiers judge "another node" by the
    same rule that marked the field self-ref. The old root-only check silently
    rejected sibling nodes (a heterogeneous ``Head -> Cell`` graph) and handed
    back a leaf.
    """
    names = {cls.__name__}
    module = sys.modules.get(cls.__module__)
    if module is None:
        return names
    for f in ci.fields:
        if not f.is_self_ref or not f.type_repr:
            continue
        for nm in _referenced_names(f.type_repr):
            obj = getattr(module, nm, None)
            if isinstance(obj, type) and _looks_node_like(obj):
                names.add(obj.__name__)
    return names


def _nontrivial_predicate(
    node_names: Set[str], buildable: Callable[[Any], bool]
) -> Callable[[Any], bool]:
    def nontrivial(obj: Any) -> bool:
        if not buildable(obj):
            return False
        try:
            datum = CnDDataInstanceBuilder().build_instance(obj)
        except Exception:  # pragma: no cover — buildable just established this
            return False
        # >=2 node atoms means at least one structural edge exists, so a self-ref
        # relation the ask names is non-empty. Counting node_names (not just the
        # root type) keeps heterogeneous graphs from being read as leaves.
        return sum(a.get("type") in node_names for a in datum.get("atoms", [])) >= 2

    return nontrivial


def _fully_populated_predicate(
    fields: List[FieldInfo], node_names: Set[str], buildable: Callable[[Any], bool]
) -> Callable[[Any], bool]:
    # ``fields`` is the non-private self-ref set chosen by the caller; keeping the
    # choice in one place (find_witness) avoids the two-definitions-of-self-ref
    # divergence that let a private-only recursive class slip a leaf through here.
    def fully_populated(obj: Any) -> bool:
        if not buildable(obj):
            return False
        for field in fields:
            try:
                value = getattr(obj, field.name)
            except (AttributeError, TypeError):
                return False
            if field.container:
                if not _container_has(value, node_names, set()):
                    return False
            elif value is None:
                # A non-container self-ref field is populated iff it holds a node;
                # any non-None value qualifies (it may be a sibling node type, not
                # the root class), matching how the field was judged self-ref.
                return False
        return True

    return fully_populated


def _container_has(value: Any, node_names: Set[str], seen: set) -> bool:
    """Does a possibly nested built-in container hold a node-like instance?"""
    if type(value).__name__ in node_names:
        return True
    if not isinstance(value, (list, tuple, set, frozenset, dict)):
        return False
    marker = id(value)
    if marker in seen:
        return False
    seen.add(marker)
    items = (
        list(value.keys()) + list(value.values()) if isinstance(value, dict) else value
    )
    return any(_container_has(item, node_names, seen) for item in items)


def _search_error(cls: type, exc: Exception, tracker: _BuildTracker) -> StrategyError:
    # If the builder raised on *every* generated value, this was never an empty
    # search — it is a builder failure wearing a NoSuchExample. Report that, and
    # carry the real exception, rather than telling the user to write examples=
    # for a witness the builder could not have accepted anyway.
    if not tracker.ever_built and tracker.last_error is not None:
        detail = str(tracker.last_error).strip()
        suffix = f" ({detail})" if detail else ""
        return StrategyError(
            f"every generated {cls.__name__} failed to build into a diagram "
            f"instance{suffix}. This is a builder error, not an exhausted search "
            "— check that the type is buildable, or pass examples=[...]."
        )

    # Tell a bad/empty strategy apart from a genuinely exhausted search. find
    # raises InvalidArgument when the argument is not a strategy at all, and
    # Unsatisfiable when the strategy can generate nothing — neither is a "widen
    # the search" situation, so don't send the user off to add more examples.
    from hypothesis.errors import InvalidArgument, Unsatisfiable

    detail = str(exc).strip()
    suffix = f" ({detail})" if detail else ""
    if isinstance(exc, InvalidArgument):
        return StrategyError(
            f"strategy= for {cls.__name__} is not a valid Hypothesis strategy"
            f"{suffix}. Pass a Hypothesis strategy, strategy='auto', or "
            "examples=[...]."
        )
    if isinstance(exc, Unsatisfiable):
        return StrategyError(
            f"the strategy for {cls.__name__} generated no usable values"
            f"{suffix}. Pass a strategy that can build {cls.__name__}, "
            "strategy='auto', or examples=[...]."
        )
    return StrategyError(
        f"strategy could not produce a buildable {cls.__name__} witness within "
        f"the search budget{suffix}. Pass examples=[...] or a different strategy."
    )

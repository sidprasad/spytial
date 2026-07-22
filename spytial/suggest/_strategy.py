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

from typing import Any, Callable

from ..provider_system import CnDDataInstanceBuilder
from ._model import ClassInfo


class StrategyError(RuntimeError):
    """A Hypothesis strategy could not supply a usable witness."""


_MAX_EXAMPLES = 100


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
    buildable = _buildable_predicate(cls)

    # Recursive schemas need populated structural edges to ground an ask such as
    # "put every child below its parent". Prefer a root that exercises every
    # recursive field (both left and right, for example). Domain invariants may
    # make that impossible, so fall back to any graph containing another root-
    # type atom, then finally any buildable witness.
    if ci.self_ref_fields:
        fully_populated = _fully_populated_predicate(cls, ci, buildable)
        try:
            return find(source, fully_populated, settings=search_settings)
        except no_such_example:
            pass
        except Exception as exc:  # invalid strategy, bad generation, etc.
            raise _search_error(cls, exc) from exc

        nontrivial = _nontrivial_predicate(cls, buildable)
        try:
            return find(source, nontrivial, settings=search_settings)
        except no_such_example:
            pass
        except Exception as exc:  # invalid strategy, bad generation, etc.
            raise _search_error(cls, exc) from exc

    try:
        return find(source, buildable, settings=search_settings)
    except Exception as exc:  # noqa: BLE001 — present one stable public error
        raise _search_error(cls, exc) from exc


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


def _buildable_predicate(cls: type) -> Callable[[Any], bool]:
    def buildable(obj: Any) -> bool:
        if not isinstance(obj, cls):
            return False
        try:
            datum = CnDDataInstanceBuilder().build_instance(obj)
        except Exception:  # noqa: BLE001 — Hypothesis should keep searching
            return False
        return bool(datum.get("atoms"))

    return buildable


def _nontrivial_predicate(
    cls: type, buildable: Callable[[Any], bool]
) -> Callable[[Any], bool]:
    def nontrivial(obj: Any) -> bool:
        if not buildable(obj):
            return False
        try:
            datum = CnDDataInstanceBuilder().build_instance(obj)
        except Exception:  # pragma: no cover — buildable just established this
            return False
        return sum(a.get("type") == cls.__name__ for a in datum.get("atoms", [])) >= 2

    return nontrivial


def _fully_populated_predicate(
    cls: type, ci: ClassInfo, buildable: Callable[[Any], bool]
) -> Callable[[Any], bool]:
    fields = [f for f in ci.fields if f.is_self_ref and not f.is_private]

    def fully_populated(obj: Any) -> bool:
        if not buildable(obj):
            return False
        for field in fields:
            try:
                value = getattr(obj, field.name)
            except (AttributeError, TypeError):
                return False
            if field.container:
                if not _container_has(value, cls, set()):
                    return False
            elif not isinstance(value, cls):
                return False
        return True

    return fully_populated


def _container_has(value: Any, cls: type, seen: set) -> bool:
    """Does a possibly nested built-in container contain a ``cls`` instance?"""
    if isinstance(value, cls):
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
    return any(_container_has(item, cls, seen) for item in items)


def _search_error(cls: type, exc: Exception) -> StrategyError:
    detail = str(exc).strip()
    suffix = f" ({detail})" if detail else ""
    return StrategyError(
        f"strategy could not produce a buildable {cls.__name__} witness within "
        f"the search budget{suffix}. Pass examples=[...] or a different strategy."
    )

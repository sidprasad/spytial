"""Relationalizers for named singletons: enum members, functions, classes, modules.

These values reify by *reference*: the datum records an importable identity and
reify returns the very object that identity resolves to, so ``is``,
``isinstance``, and even address-bearing ``repr`` strings hold after a round
trip. Lambdas and closure-defined functions have no importable name; they get
no reference metadata and keep the structural-proxy fallback.
"""

import enum
import importlib
import inspect
from typing import Any, Dict, List, Optional, Tuple

from .base import RelationalizerBase, Atom, Relation


def _verified_reference(
    module: Optional[str], qualname: Optional[str], obj: Any
) -> Optional[Dict[str, str]]:
    """Reference metadata for *obj*, or None when the name doesn't lead back.

    A ``__qualname__`` records where something was *defined*, which is not the
    same as a name that still resolves to it. Rebinding breaks the link::

        def f(): ...
        g = f          # g.__qualname__ is still 'f'
        def f(): ...   # the name f now means something else

    Resolving ``g``'s recorded name at reify time returns the second ``f``:
    not a proxy, but a different callable that silently does something else.
    The same applies to a rebound class, where an enum member would come back
    as the same-named member of a different enum.

    So the name must round-trip to this very object before we claim reference
    semantics, checked with the resolver reify itself uses so the two cannot
    disagree. Anything that fails keeps the structural-proxy fallback.
    """
    if not qualname or not module or "<" in qualname:
        return None
    # Deferred import: provider_system imports this package at its own module
    # bottom, so a top-level import here would be circular.
    from ..provider_system import _resolve_named

    if _resolve_named(module, qualname) is not obj:
        return None
    return {"__ref_module__": module, "__ref_qualname__": qualname}


def _importable_identity(obj: Any) -> Optional[Dict[str, str]]:
    """Verified reference metadata for something named by its own qualname."""
    return _verified_reference(
        getattr(obj, "__module__", None), getattr(obj, "__qualname__", None), obj
    )


class EnumRelationalizer(RelationalizerBase):
    """Handles enum members (incl. IntEnum/StrEnum) as named singletons.

    A member is addressable as ``Class.MEMBER``, a dotted path the reference
    resolver walks directly, so it carries the same verified metadata as any
    other named singleton. Reify then returns the member itself rather than
    rebuilding a hollow instance, and a rebound enum class fails the round-trip
    check instead of silently yielding the same-named member of a different
    enum. Without the metadata (an older datum, or a class that no longer
    resolves), reify falls back to looking the label up on whatever class the
    atom's own ``__module__``/``__qualname__`` resolve to.
    """

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, enum.Enum)

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        cls = type(obj)
        atom = Atom(
            id=walker_func._get_id(obj),
            type=cls.__name__,
            label=obj.name,
            meta=_verified_reference(
                getattr(cls, "__module__", None),
                f"{cls.__qualname__}.{obj.name}"
                if getattr(cls, "__qualname__", None)
                else None,
                obj,
            ),
        )
        return [atom], []


class FunctionRelationalizer(RelationalizerBase):
    """Handles plain and builtin functions as importable references.

    Builtin *methods* (e.g. ``[].append``) have ``__module__ = None``, so the
    identity guard withholds reference metadata and they keep the proxy path —
    resolving their qualname would return the unbound descriptor, not the
    bound method.
    """

    def can_handle(self, obj: Any) -> bool:
        return inspect.isfunction(obj) or inspect.isbuiltin(obj)

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        atom = Atom(
            id=walker_func._get_id(obj),
            type="function",
            label=obj.__qualname__,
            meta=_importable_identity(obj),
        )
        return [atom], []


class TypeRelationalizer(RelationalizerBase):
    """Handles class objects as importable references."""

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, type)

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        atom = Atom(
            id=walker_func._get_id(obj),
            type="type",
            label=obj.__qualname__,
            meta=_importable_identity(obj),
        )
        return [atom], []


class ModuleRelationalizer(RelationalizerBase):
    """Handles modules as importable references."""

    def can_handle(self, obj: Any) -> bool:
        return inspect.ismodule(obj)

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        # Same round-trip requirement as functions and classes: a module whose
        # __name__ no longer imports back to it (renamed, or replaced in
        # sys.modules) must not claim reference semantics.
        meta = None
        name = getattr(obj, "__name__", None)
        if name:
            try:
                if importlib.import_module(name) is obj:
                    meta = {"__ref_import__": name}
            except Exception:
                meta = None
        atom = Atom(
            id=walker_func._get_id(obj),
            type="module",
            label=name or "module",
            meta=meta,
        )
        return [atom], []

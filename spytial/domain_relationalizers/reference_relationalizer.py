"""Relationalizers for named singletons: enum members, functions, classes, modules.

These values reify by *reference*: the datum records an importable identity and
reify returns the very object that identity resolves to, so ``is``,
``isinstance``, and even address-bearing ``repr`` strings hold after a round
trip. Lambdas and closure-defined functions have no importable name; they get
no reference metadata and keep the structural-proxy fallback.
"""

import enum
import inspect
from typing import Any, Dict, List, Optional, Tuple

from .base import RelationalizerBase, Atom, Relation


def _importable_identity(obj: Any) -> Optional[Dict[str, str]]:
    """Reference metadata for *obj*, or None when it has no importable name."""
    qualname = getattr(obj, "__qualname__", None)
    module = getattr(obj, "__module__", None)
    if not qualname or not module or "<" in qualname:
        return None
    return {"__ref_module__": module, "__ref_qualname__": qualname}


class EnumRelationalizer(RelationalizerBase):
    """Handles enum members (incl. IntEnum/StrEnum) as named singletons.

    The label is the member *name*: reify resolves the Enum class from the
    ``__module__``/``__qualname__`` that _walk records on the atom, then looks
    the member up with ``Cls[name]``, returning the real singleton.
    """

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, enum.Enum)

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        atom = Atom(
            id=walker_func._get_id(obj), type=type(obj).__name__, label=obj.name
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
        atom = Atom(
            id=walker_func._get_id(obj),
            type="module",
            label=obj.__name__,
            meta={"__ref_import__": obj.__name__},
        )
        return [atom], []

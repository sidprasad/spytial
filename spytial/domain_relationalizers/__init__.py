"""
Domain-specific relationalizers for common Python data types.

This package contains built-in relationalizers that handle standard Python
objects like primitives, collections, and generic objects.
"""

from .base import RelationalizerBase, Atom, Relation

# Import all relationalizers and register them
from .primitive_relationalizer import PrimitiveRelationalizer
from .dict_relationalizer import DictRelationalizer
from .list_relationalizer import ListRelationalizer
from .tuple_relationalizer import TupleRelationalizer
from .set_relationalizer import SetRelationalizer
from .range_relationalizer import RangeRelationalizer
from .dataclass_relationalizer import DataclassRelationalizer
from .generic_object_relationalizer import GenericObjectRelationalizer
from .fallback_relationalizer import FallbackRelationalizer
from .reference_relationalizer import (
    EnumRelationalizer,
    FunctionRelationalizer,
    TypeRelationalizer,
    ModuleRelationalizer,
)

# Store relationalizers and priorities for later registration
# Reference relationalizers sit above PrimitiveRelationalizer (10) so that
# IntEnum/StrEnum members route to enum-by-name instead of the int/str path.
_BUILTIN_RELATIONALIZERS = [
    (EnumRelationalizer, 11),
    (FunctionRelationalizer, 11),
    (TypeRelationalizer, 11),
    (ModuleRelationalizer, 11),
    (PrimitiveRelationalizer, 10),
    (DictRelationalizer, 9),
    (ListRelationalizer, 8),
    (TupleRelationalizer, 8),
    (SetRelationalizer, 8),
    (RangeRelationalizer, 8),
    (DataclassRelationalizer, 7),
    (GenericObjectRelationalizer, 5),
    (FallbackRelationalizer, 1),
]


def register_builtin_relationalizers(registry):
    """Register all built-in relationalizers with the given registry."""
    for relationalizer_cls, priority in _BUILTIN_RELATIONALIZERS:
        registry.register(relationalizer_cls, priority=priority)


__all__ = [
    "RelationalizerBase",
    "Atom",
    "Relation",
    "PrimitiveRelationalizer",
    "DictRelationalizer",
    "ListRelationalizer",
    "TupleRelationalizer",
    "SetRelationalizer",
    "RangeRelationalizer",
    "DataclassRelationalizer",
    "GenericObjectRelationalizer",
    "FallbackRelationalizer",
    "EnumRelationalizer",
    "FunctionRelationalizer",
    "TypeRelationalizer",
    "ModuleRelationalizer",
    "register_builtin_relationalizers",
]

"""
Domain-specific relationalizers for common Python data types.

This package contains built-in relationalizers that handle standard Python
objects like primitives, collections, and generic objects.
"""

from .base import RelationalizerBase, Atom, Relation

# Import all core relationalizers
from .primitive_relationalizer import PrimitiveRelationalizer
from .dict_relationalizer import DictRelationalizer
from .list_relationalizer import ListRelationalizer
from .set_relationalizer import SetRelationalizer
from .dataclass_relationalizer import DataclassRelationalizer
from .generic_object_relationalizer import GenericObjectRelationalizer
from .fallback_relationalizer import FallbackRelationalizer

# Store core relationalizers and priorities for later registration
_BUILTIN_RELATIONALIZERS = [
    (PrimitiveRelationalizer, 10),
    (DictRelationalizer, 9),
    (ListRelationalizer, 8),
    (SetRelationalizer, 8),
    (DataclassRelationalizer, 7),
    (GenericObjectRelationalizer, 5),
    (FallbackRelationalizer, 1),
]

# Domain-specific relationalizers (optional dependencies)
_DOMAIN_RELATIONALIZERS = []

# Pydantic support
try:
    from .pydantic_relationalizer import PydanticRelationalizer

    _DOMAIN_RELATIONALIZERS.append((PydanticRelationalizer, 15))
except ImportError:
    pass

# Attrs support
try:
    from .attrs_relationalizer import AttrsRelationalizer

    _DOMAIN_RELATIONALIZERS.append((AttrsRelationalizer, 14))
except ImportError:
    pass

# PyTorch support
try:
    from .pytorch_relationalizer import (
        PyTorchTensorRelationalizer,
        PyTorchModuleRelationalizer,
    )

    _DOMAIN_RELATIONALIZERS.extend(
        [(PyTorchTensorRelationalizer, 13), (PyTorchModuleRelationalizer, 12)]
    )
except ImportError:
    pass

# ANTLR support
try:
    from .antlr_relationalizer import ANTLRParseTreeRelationalizer

    _DOMAIN_RELATIONALIZERS.append((ANTLRParseTreeRelationalizer, 11))
except ImportError:
    pass

# NetworkX support
try:
    from .networkx_relationalizer import NetworkXRelationalizer

    _DOMAIN_RELATIONALIZERS.append((NetworkXRelationalizer, 16))
except ImportError:
    pass

# Pandas support
try:
    from .pandas_relationalizer import (
        PandasDataFrameRelationalizer,
        PandasSeriesRelationalizer,
        PandasIndexRelationalizer,
    )

    _DOMAIN_RELATIONALIZERS.extend(
        [
            (PandasDataFrameRelationalizer, 17),
            (PandasSeriesRelationalizer, 16),
            (PandasIndexRelationalizer, 15),
        ]
    )
except ImportError:
    pass


def register_builtin_relationalizers(registry):
    """Register all built-in relationalizers with the given registry."""
    # Register core relationalizers
    for relationalizer_cls, priority in _BUILTIN_RELATIONALIZERS:
        registry.register(relationalizer_cls, priority=priority)

    # Register domain-specific relationalizers
    for relationalizer_cls, priority in _DOMAIN_RELATIONALIZERS:
        registry.register(relationalizer_cls, priority=priority)


__all__ = [
    "RelationalizerBase",
    "Atom",
    "Relation",
    "PrimitiveRelationalizer",
    "DictRelationalizer",
    "ListRelationalizer",
    "SetRelationalizer",
    "DataclassRelationalizer",
    "GenericObjectRelationalizer",
    "FallbackRelationalizer",
    "register_builtin_relationalizers",
]

# Add domain-specific relationalizers to __all__ if available
try:
    from .pydantic_relationalizer import PydanticRelationalizer

    __all__.append("PydanticRelationalizer")
except ImportError:
    pass

try:
    from .attrs_relationalizer import AttrsRelationalizer

    __all__.append("AttrsRelationalizer")
except ImportError:
    pass

try:
    from .pytorch_relationalizer import (
        PyTorchTensorRelationalizer,
        PyTorchModuleRelationalizer,
    )

    __all__.extend(["PyTorchTensorRelationalizer", "PyTorchModuleRelationalizer"])
except ImportError:
    pass

try:
    from .antlr_relationalizer import ANTLRParseTreeRelationalizer

    __all__.append("ANTLRParseTreeRelationalizer")
except ImportError:
    pass

try:
    from .networkx_relationalizer import NetworkXRelationalizer

    __all__.append("NetworkXRelationalizer")
except ImportError:
    pass

try:
    from .pandas_relationalizer import (
        PandasDataFrameRelationalizer,
        PandasSeriesRelationalizer,
        PandasIndexRelationalizer,
    )

    __all__.extend(
        [
            "PandasDataFrameRelationalizer",
            "PandasSeriesRelationalizer",
            "PandasIndexRelationalizer",
        ]
    )
except ImportError:
    pass

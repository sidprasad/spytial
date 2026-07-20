"""Relationalizer for primitive Python types."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class PrimitiveRelationalizer(RelationalizerBase):
    """Handles primitive leaf types: int, float, complex, str, bytes,
    bytearray, bool, None, NotImplemented, and Ellipsis."""

    def can_handle(self, obj: Any) -> bool:
        return (
            isinstance(
                obj, (int, float, complex, str, bytes, bytearray, bool, type(None))
            )
            or obj is NotImplemented
            or obj is Ellipsis
        )

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        # bytes-family labels carry the full b'...' literal so reify can
        # recover the payload with ast.literal_eval; a bytearray borrows the
        # bytes-style label and the atom's type field keeps the two apart.
        if isinstance(obj, bytearray):
            label = repr(bytes(obj))
        elif isinstance(obj, bytes):
            label = repr(obj)
        else:
            label = str(obj)
        atom = Atom(id=walker_func._get_id(obj), type=type(obj).__name__, label=label)
        return [atom], []

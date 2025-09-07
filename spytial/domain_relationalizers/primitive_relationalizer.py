"""Relationalizer for primitive Python types."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class PrimitiveRelationalizer(RelationalizerBase):
    """Handles primitive types: int, float, str, bool, None."""

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, (int, float, str, bool, type(None)))

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        atom = Atom(
            id=walker_func._get_id(obj), type=type(obj).__name__, label=str(obj)
        )
        return [atom], []

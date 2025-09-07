"""Relationalizer for primitive Python types."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class PrimitiveRelationalizer(RelationalizerBase):
    """Handles primitive types: int, float, str, bool, None."""

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, (int, float, str, bool, type(None)))

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        # Wrap all strings in quotes for clarity
        if isinstance(obj, str):
            label = f'"{obj}"'
        else:
            label = str(obj)
        
        atom = Atom(
            id=walker_func._get_id(obj), type=type(obj).__name__, label=label
        )
        return [atom], []

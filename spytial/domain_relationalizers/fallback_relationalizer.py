"""Fallback relationalizer for objects that can't be handled by other relationalizers."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class FallbackRelationalizer(RelationalizerBase):
    """Fallback relationalizer for objects that can't be handled by other relationalizers."""

    def can_handle(self, obj: Any) -> bool:
        return True  # Always accepts

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        caller_namespace = getattr(walker_func, '_caller_namespace', None)
        label = self._make_label_with_fallback(obj, typ, caller_namespace, obj_id)
        atom = Atom(id=obj_id, type=typ, label=label)

        # Fallback doesn't process any relations - just returns the object as-is
        return [atom], []

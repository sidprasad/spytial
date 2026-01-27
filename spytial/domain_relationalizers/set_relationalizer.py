"""Relationalizer for set objects."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class SetRelationalizer(RelationalizerBase):
    """Handles set objects."""

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, set)

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        caller_namespace = getattr(walker_func, '_caller_namespace', None)
        label = self._make_label_with_fallback(obj, typ, caller_namespace, obj_id)
        atom = Atom(id=obj_id, type=typ, label=label)

        relations = []
        for element in obj:
            element_id = walker_func(element)
            relations.append(Relation("contains", [obj_id, element_id]))

        return [atom], relations

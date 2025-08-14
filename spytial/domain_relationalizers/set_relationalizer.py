"""Relationalizer for set objects."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class SetRelationalizer(RelationalizerBase):
    """Handles set objects."""

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, set)

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        obj_id = walker_func._get_id(obj)
        atom = Atom(id=obj_id, type="set", label=f"set[{len(obj)}]")

        relations = []
        for element in obj:
            element_id = walker_func(element)
            relations.append(
                Relation.binary("contains", obj_id, element_id)
            )

        return [atom], relations

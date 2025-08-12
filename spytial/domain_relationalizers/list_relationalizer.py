"""Relationalizer for list and tuple objects."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class ListRelationalizer(RelationalizerBase):
    """Handles list and tuple objects."""

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, (list, tuple))

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = Atom(id=obj_id, type=typ, label=f"{typ}[{len(obj)}]")

        relations = []
        for i, elt in enumerate(obj):
            eid = walker_func(elt)
            relations.append(Relation(name=str(i), source_id=obj_id, target_id=eid))

        return [atom], relations

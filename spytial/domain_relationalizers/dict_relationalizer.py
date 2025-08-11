"""Relationalizer for dictionary objects."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class DictRelationalizer(RelationalizerBase):
    """Handles dictionary objects."""

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, dict)

    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)
        atom = Atom(id=obj_id, type="dict", label=f"dict{{{len(obj)}}}")

        relations = []
        for k, v in obj.items():
            vid = walker_func(v)
            key_str = (
                str(k)
                if isinstance(k, (str, int, float, bool))
                else f"key_{len(relations)}"
            )
            relations.append(Relation(name=key_str, source_id=obj_id, target_id=vid))

        return atom, relations

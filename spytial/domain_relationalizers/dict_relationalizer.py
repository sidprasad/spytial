"""Relationalizer for dictionary objects."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class DictRelationalizer(RelationalizerBase):
    """Handles dictionary objects."""

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, dict)

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        caller_namespace = getattr(walker_func, '_caller_namespace', None)
        label = self._make_label_with_fallback(obj, typ, caller_namespace)

        atoms = [Atom(id=obj_id, type=typ, label=label)]
        relations = []
        for k, v in obj.items():
            # Create an atom for the key
            key_id = f"{obj_id}_key_{len(relations)}"
            key_str = (
                str(k)
                if isinstance(k, (str, int, float, bool))
                else f"key_{len(relations)}"
            )
            key_atom = Atom(id=key_id, type=type(k).__name__, label=key_str)
            atoms.append(key_atom)
            
            # Get the value ID
            vid = walker_func(v)
            
            # Create a ternary relation: keyval(dict, key, value)
            relations.append(Relation("kv", [obj_id, key_id, vid]))

        return atoms, relations

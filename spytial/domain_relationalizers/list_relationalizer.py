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

        atoms = [atom]
        relations = []
        for i, elt in enumerate(obj):
            # Create an atom for the index
            idx_id = f"{obj_id}_idx_{i}"
            idx_atom = Atom(id=idx_id, type="int", label=str(i))
            atoms.append(idx_atom)
            
            # Get the element ID
            eid = walker_func(elt)
            
            # Create a ternary relation: idx(list, index, element)
            relations.append(Relation("idx", [obj_id, idx_id, eid]))

        return atoms, relations

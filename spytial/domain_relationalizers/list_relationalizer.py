"""Relationalizer for listobjects."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class ListRelationalizer(RelationalizerBase):
    """Handles list objects."""

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, list)

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = Atom(id=obj_id, type=typ, label=f"{typ}[{len(obj)}]")

        atoms = [atom]
        relations = []
        for i, elt in enumerate(obj):
            # Create an atom for the index
            idx_id = walker_func._get_id(i)

            # Wait, only create the atom for the index if it's not already created?


            idx_atom = Atom(id=idx_id, type="int", label=str(i))
            atoms.append(idx_atom)
            
            # Get the element ID
            eid = walker_func(elt)
            
            # Create a ternary relation: idx(list, index, element)
            relations.append(Relation("idx", [obj_id, idx_id, eid]))

        return atoms, relations



## But these are ... very expensive ##

## Simple Idx ##

LIST_1D_IDX = "{ i : int, s : object | (some l : list | (l->i->s in idx)) }"

## TODO: 2D works ish.
LIST_2D_IDX = "{ i : int, j : int, s : object | (some l1, l2 : list | (l1->i->l2 in idx) and (l2->j->s in idx)) }"


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
        # Iterate a snapshot: walking an element runs arbitrary code (property
        # getters, custom relationalizers) that may append to this very list,
        # and a list that grows under its own loop never finishes (issue #140).
        for i, elt in enumerate(tuple(obj)):
            # Get the element ID; None means the walk refused the element
            # (spytial machinery) — no index atom, no tuple.
            eid = walker_func(elt)
            if eid is None:
                continue

            # Create an atom for the index
            idx_id = walker_func._get_id(i)
            idx_atom = Atom(id=idx_id, type="int", label=str(i))
            atoms.append(idx_atom)

            # Create a ternary relation: idx(list, index, element)
            relations.append(Relation("idx", [obj_id, idx_id, eid]))

        return atoms, relations


## But these are ... very expensive ##

## Simple Idx ##

LIST_1D_IDX = "{ i : int, s : object | (some l : list | (l->i->s in idx)) }"

## TODO: 2D works ish.
LIST_2D_IDX = "{ i : int, j : int, s : object | (some l1, l2 : list | (l1->i->l2 in idx) and (l2->j->s in idx)) }"

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


### Simple, stupid patterns. I don't like having these tho.

## TODO: Fix this.
LIST_1D_NEXT = "{x,y : idx[object][object] | @num:(x[idx[object]]) < @num:(y[idx[object]])}"
LIST_2D_SAME_ROW_NEXT = "{x,y : idx[object][idx_x][x], idx[object][idx_y][y] | add[@num:idx_x, 1] = @num:idx_y}"
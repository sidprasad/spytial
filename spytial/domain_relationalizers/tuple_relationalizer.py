
from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation

class TupleRelationalizer(RelationalizerBase):
    """Handles list and tuple objects."""

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, (tuple))

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        caller_namespace = getattr(walker_func, '_caller_namespace', None)
        label = self._make_label_with_fallback(obj, typ, caller_namespace, obj_id)
        atom = Atom(id=obj_id, type=typ, label=label)

        atoms = [atom]
        relations = []
        for i, elt in enumerate(obj):


            # Wait, only create the atom for the index if it's not already created?

            # Get the element ID
            eid = walker_func(elt)
            
            relations.append(Relation(f"t{i}", [obj_id, eid]))

        return atoms, relations

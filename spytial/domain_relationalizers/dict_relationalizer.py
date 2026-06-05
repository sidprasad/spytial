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
        caller_namespace = getattr(walker_func, "_caller_namespace", None)
        label = self._make_label_with_fallback(
            obj, typ, caller_namespace, obj_id, walker_func
        )

        atoms = [Atom(id=obj_id, type=typ, label=label)]
        relations = []
        for k, v in obj.items():
            # Walk every key through the normal pipeline — primitives *and*
            # complex keys (tuples, objects, …). _walk records the key's own
            # atom plus, for containers/objects, its nested structure and class
            # identity, which reify needs to rebuild the real key. A previous
            # shortcut emitted a synthetic, un-walked atom for non-primitive
            # keys, so they reified to empty shells (e.g. {('a','b'): 1} came
            # back as {(): 1}). Memoization also means a key object that appears
            # elsewhere now shares one atom instead of being duplicated.
            key_id = walker_func._walk(k)

            # Get the value ID
            vid = walker_func._walk(v)

            # Create a ternary relation: keyval(dict, key, value)
            relations.append(Relation("kv", [obj_id, key_id, vid]))

        return atoms, relations

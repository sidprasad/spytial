"""Relationalizer for generic objects with __dict__ or __slots__."""

import inspect
from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class GenericObjectRelationalizer(RelationalizerBase):
    """Handles generic objects with __dict__ or __slots__."""

    def can_handle(self, obj: Any) -> bool:
        return hasattr(obj, "__dict__") or hasattr(obj, "__slots__")

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = Atom(id=obj_id, type=typ, label=f"{typ}")

        relations = []

        # Handle __slots__
        if hasattr(obj, "__slots__"):
            for slot in obj.__slots__:
                if hasattr(obj, slot):
                    value = getattr(obj, slot)
                    vid = walker_func(value)
                    relations.append(
                        Relation.binary(slot, obj_id, vid)
                    )

        # Handle __dict__
        elif hasattr(obj, "__dict__"):
            for attr_name, attr_value in vars(obj).items():
                if not attr_name.startswith("_") and not inspect.ismethod(attr_value):
                    vid = walker_func(attr_value)
                    relations.append(
                        Relation.binary(attr_name, obj_id, vid)
                    )

        return [atom], relations

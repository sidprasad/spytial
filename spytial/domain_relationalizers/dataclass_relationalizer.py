"""Relationalizer for dataclass objects."""

import dataclasses
from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class DataclassRelationalizer(RelationalizerBase):
    """Handles dataclass objects."""

    def can_handle(self, obj: Any) -> bool:
        return dataclasses.is_dataclass(obj)

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = Atom(id=obj_id, type=typ, label=f"{typ}")

        relations = []
        for field in dataclasses.fields(obj):
            if not field.name.startswith("_"):
                value = getattr(obj, field.name)
                vid = walker_func(value)
                relations.append(
                    Relation(name=field.name, source_id=obj_id, target_id=vid)
                )

        return [atom], relations

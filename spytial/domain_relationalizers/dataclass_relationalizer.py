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

        # Try to get caller namespace from the walker (builder) if available
        caller_namespace = getattr(walker_func, "_caller_namespace", None)
        label = self._make_label_with_fallback(
            obj, typ, caller_namespace, obj_id, walker_func
        )

        atom = Atom(id=obj_id, type=typ, label=label)

        # Every declared field is relationalized, including underscore-prefixed
        # ones. A dataclass field is schema, not a privacy boundary: Python
        # decides fields by annotation alone, and `_x` participates in
        # __init__, __repr__, and __eq__ like any other. Skipping them dropped
        # structure from the diagram (a `_next` pointer drew no edge) and let
        # reify silently restore the class-level default in place of the
        # instance's real value. Hiding a field is a display decision, so it
        # belongs in a directive rather than here.
        relations = []
        for field in dataclasses.fields(obj):
            value = getattr(obj, field.name)
            vid = walker_func(value)
            relations.append(Relation(field.name, [obj_id, vid]))

        return [atom], relations

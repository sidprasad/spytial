"""Relationalizer for dataclass objects."""

import dataclasses
from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class DataclassRelationalizer(RelationalizerBase):
    """Handles dataclass objects."""

    def can_handle(self, obj: Any) -> bool:
        return dataclasses.is_dataclass(obj)

    def declared_relations(self, obj: Any) -> List[str]:
        # Every declared field, matching the loop in relationalize below —
        # including underscore-prefixed ones, for the same reason.
        return [field.name for field in dataclasses.fields(obj)]

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
            try:
                value = getattr(obj, field.name)
            except AttributeError:
                # A field(init=False) its owner never assigned — legal Python
                # (the usual __post_init__ idiom, skipped on some branch), and
                # reading it raises. Emitting no tuple is the honest answer;
                # declared_relations still carries the name into the instance,
                # so the field shows up as an empty relation rather than
                # crashing the whole build.
                continue
            vid = walker_func(value)
            if vid is None:
                # The walk refused the value (spytial machinery, issue #140).
                # declared_relations above still carries the field name, so
                # the field surfaces as an empty relation, not a misspelling.
                continue
            relations.append(Relation(field.name, [obj_id, vid]))

        return [atom], relations

"""Relationalizer for Attrs classes."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation

try:
    import attr
    import attrs

    ATTRS_AVAILABLE = True
except ImportError:
    ATTRS_AVAILABLE = False


class AttrsRelationalizer(RelationalizerBase):
    """Handles Attrs-decorated classes."""

    def can_handle(self, obj: Any) -> bool:
        if not ATTRS_AVAILABLE:
            return False
        return attr.has(obj) if hasattr(attr, "has") else attrs.has(obj)

    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)
        class_name = type(obj).__name__

        # Create the main atom for the attrs class
        atom = Atom(id=obj_id, type="AttrsClass", label=f"{class_name}")

        relations = []

        # Get attrs fields
        try:
            # Try attrs/attr.fields()
            if hasattr(attr, "fields"):
                fields = attr.fields(type(obj))
            elif hasattr(attrs, "fields"):
                fields = attrs.fields(type(obj))
            else:
                fields = []

            for field in fields:
                field_name = field.name
                if hasattr(obj, field_name):
                    value = getattr(obj, field_name)
                    vid = walker_func(value)
                    relations.append(
                        Relation(name=field_name, source_id=obj_id, target_id=vid)
                    )
        except Exception:
            # Fallback: use object's __dict__
            for field_name, value in obj.__dict__.items():
                if not field_name.startswith("_"):
                    vid = walker_func(value)
                    relations.append(
                        Relation(name=field_name, source_id=obj_id, target_id=vid)
                    )

        return atom, relations

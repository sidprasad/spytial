"""Relationalizer for Pydantic models."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation

try:
    from pydantic import BaseModel

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = None


class PydanticRelationalizer(RelationalizerBase):
    """Handles Pydantic model objects with field metadata."""

    def can_handle(self, obj: Any) -> bool:
        if not PYDANTIC_AVAILABLE:
            return False
        return isinstance(obj, BaseModel)

    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)
        model_name = type(obj).__name__

        # Create the main atom for the model
        atom = Atom(id=obj_id, type="PydanticModel", label=f"{model_name}")

        relations = []

        # Get model fields (handling both v1 and v2 syntax)
        if hasattr(obj, "__fields__"):  # Pydantic v1
            model_fields = obj.__fields__
            for field_name, field_info in model_fields.items():
                if hasattr(obj, field_name):
                    value = getattr(obj, field_name)
                    vid = walker_func(value)
                    relations.append(
                        Relation(name=field_name, source_id=obj_id, target_id=vid)
                    )
        elif hasattr(obj, "model_fields"):  # Pydantic v2
            model_fields = obj.model_fields
            for field_name, field_info in model_fields.items():
                if hasattr(obj, field_name):
                    value = getattr(obj, field_name)
                    vid = walker_func(value)
                    relations.append(
                        Relation(name=field_name, source_id=obj_id, target_id=vid)
                    )
        else:
            # Fallback: iterate through model dump
            try:
                model_data = obj.dict() if hasattr(obj, "dict") else obj.model_dump()
                for field_name, value in model_data.items():
                    vid = walker_func(value)
                    relations.append(
                        Relation(name=field_name, source_id=obj_id, target_id=vid)
                    )
            except Exception:
                # Last resort: use __dict__
                for field_name, value in obj.__dict__.items():
                    if not field_name.startswith("_"):
                        vid = walker_func(value)
                        relations.append(
                            Relation(name=field_name, source_id=obj_id, target_id=vid)
                        )

        return atom, relations

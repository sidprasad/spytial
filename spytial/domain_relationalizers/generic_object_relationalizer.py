"""
Relationalizer for generic objects with __dict__ or __slots__.

Design Decisions:
- Comprehensive inspection: Use inspect.getmembers to enumerate all attributes, ensuring we capture properties, descriptors, and inherited fields that serialization might include.
- Filtering for relevance: Skip private attributes (starting with "_"), methods, functions, and modules to focus on meaningful data for visualization.
- Serialization alignment: Include attributes even if not obviously serializable, as the relationalizer creates relations and the provider system handles serialization downstream.
- Property/descriptor handling: Evaluate properties and descriptors on the instance to get actual values, preventing issues with dynamic attributes.
- Performance: Limit to small/medium objects (<1 second) by using try-except for safe access and avoiding deep recursion.
- Overlap avoidance: Expand can_handle to include class-based objects but exclude basic types handled by other relationalizers (e.g., lists, dicts).
- Consistency: Maintain binary relations for simplicity, as established for generic objects.
"""

import inspect
from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation


class GenericObjectRelationalizer(RelationalizerBase):
    """Handles generic objects with __dict__ or __slots__."""

    def can_handle(self, obj: Any) -> bool:
        # Handle objects with __dict__, __slots__, or any class-based object (excluding built-ins handled elsewhere)
        return (
            hasattr(obj, "__dict__") 
            or hasattr(obj, "__slots__") 
            or (hasattr(obj, "__class__") and not isinstance(obj, (list, tuple, dict, str, int, float, bool, type)))
        )

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        caller_namespace = getattr(walker_func, '_caller_namespace', None)
        label = self._make_label_with_fallback(obj, typ, caller_namespace, obj_id)
        atom = Atom(id=obj_id, type=typ, label=label)

        relations = []

        # Use inspect to get all members, filtering for relevant attributes
        for name, value in inspect.getmembers(obj):
            # Skip private attributes, methods, functions, modules, and built-ins
            if (
                name.startswith("_") 
                or inspect.ismethod(value) 
                or inspect.isfunction(value) 
                or inspect.ismodule(value)
                or inspect.isbuiltin(value)  # Catch built-in methods
            ):
                continue
            
            # Handle properties and descriptors by evaluating on the instance
            if isinstance(value, property) or hasattr(value, '__get__'):
                try:
                    actual_value = getattr(obj, name)
                    # Skip if it's still a descriptor or primitive
                    if actual_value is value:
                        continue
                    vid = walker_func(actual_value)
                    relations.append(Relation(name, [obj_id, vid]))
                except (AttributeError, TypeError, ValueError):
                    continue
            else:
                vid = walker_func(value)
                relations.append(Relation(name, [obj_id, vid]))

        return [atom], relations
"""
CnD Data Instance Relationalizer Architecture

This module provides a pluggable system for converting Python objects
into CnD-compatible atom/relation representations using relationalizers.
"""

import inspect
from typing import Any, Dict, List, Tuple, Type, Optional

# Import base classes from domain-relationalizers
from .domain_relationalizers.base import RelationalizerBase, Atom, Relation


def relationalizer(cls: Type = None, *, priority: int = 0):
    """
    Decorator to register a class as a relationalizer.

    Args:
        priority: Higher priority relationalizers are tried first.
                 Priorities 0-99 are reserved for built-in relationalizers.
    """

    def decorator(relationalizer_cls):
        if not issubclass(relationalizer_cls, RelationalizerBase):
            raise TypeError("Relationalizer must inherit from RelationalizerBase")

        # Register the relationalizer
        RelationalizerRegistry.register(relationalizer_cls, priority)
        return relationalizer_cls

    if cls is None:
        return decorator
    else:
        return decorator(cls)


class RelationalizerRegistry:
    """Registry for relationalizers."""

    _relationalizers: List[Tuple[int, Type[RelationalizerBase]]] = []
    _instances: List[RelationalizerBase] = []

    @classmethod
    def register(cls, relationalizer_cls: Type[RelationalizerBase], priority: int = 0):
        """Register a relationalizer class with given priority."""
        cls._relationalizers.append((priority, relationalizer_cls))
        cls._relationalizers.sort(
            key=lambda x: x[0], reverse=True
        )  # Higher priority first
        cls._instances = [
            relationalizer_cls() for _, relationalizer_cls in cls._relationalizers
        ]

    @classmethod
    def find_relationalizer(cls, obj: Any) -> Optional[RelationalizerBase]:
        """Find the first relationalizer that can handle the given object."""
        # First check for object-specific relationalizers
        # Check registered class-level relationalizers
        for relationalizer in cls._instances:
            if relationalizer.can_handle(obj):
                return relationalizer
        return None

    @classmethod
    def list_relationalizers(cls) -> List[Tuple[int, str]]:
        """List all registered relationalizers with their priorities.
        
        Returns:
            List of (priority, relationalizer_class_name) tuples, sorted by priority (highest first)
        """
        return [(priority, relationalizer_cls.__name__) for priority, relationalizer_cls in cls._relationalizers]

    @classmethod
    def clear(cls):
        """Clear all registered relationalizers (for testing)."""
        cls._relationalizers.clear()
        cls._instances.clear()


class CnDDataInstanceBuilder:
    """Main builder that composes providers to build data instances."""

    def __init__(self):
        self._seen = {}
        self._atoms = []
        self._rels = {}
        self._id_counter = 0
        self._collected_decorators = {"constraints": [], "directives": []}

    def build_instance(self, obj: Any) -> Dict:
        """Build a complete data instance from an object."""
        self._seen.clear()
        self._atoms.clear()
        self._rels.clear()
        self._id_counter = 0
        self._collected_decorators = {"constraints": [], "directives": []}

        try:
            self._walk(obj)
        except Exception as e:
            print(f"Error during data instance building: {e}")
            print("Object:", obj)

        # Convert relations to include types (matching IRelation interface)
        relations = []
        for rel_name, tuples in self._rels.items():
            # For each tuple, get the types of the atoms involved
            typed_tuples = []
            for source_id, target_id in tuples:
                source_type = self._get_atom_type(source_id)
                target_type = self._get_atom_type(target_id)
                typed_tuples.append(
                    {
                        "atoms": [source_id, target_id],
                        "types": [source_type, target_type],
                    }
                )

            relations.append(
                {
                    "id": rel_name,
                    "name": rel_name,
                    "types": ["object", "object"],  # Default to Python's top type
                    "tuples": typed_tuples,
                }
            )

        # Use the updated `build_types` function
        typs = self.build_types(self._atoms)

        return {"atoms": self._atoms, "relations": relations, "types": typs}

    def get_collected_decorators(self) -> Dict:
        """Get all decorators collected during the build process."""
        return self._collected_decorators

    def _get_id(self, obj: Any) -> str:
        """Get or create an ID for an object."""
        oid = id(obj)

        if oid not in self._seen:
            # Check if object has a spytial ID for self-reference
            try:
                from .annotations import OBJECT_ID_ATTR, _OBJECT_ID_REGISTRY

                # First try to get ID from object directly
                if hasattr(obj, OBJECT_ID_ATTR):
                    spytial_id = getattr(obj, OBJECT_ID_ATTR)
                    self._seen[oid] = spytial_id
                    return spytial_id
                # Then check global registry
                elif oid in _OBJECT_ID_REGISTRY:
                    spytial_id = _OBJECT_ID_REGISTRY[oid]
                    self._seen[oid] = spytial_id
                    return spytial_id
            except ImportError:
                pass

            # Default behavior: generate new ID
            self._seen[oid] = f"n{self._id_counter}"
            self._id_counter += 1
        return self._seen[oid]

    def _walk(self, obj: Any, depth: int = 0, max_depth: int = 100) -> str:
        """Walk an object using the appropriate provider."""
        if depth > max_depth:
            raise RecursionError("Maximum recursion depth exceeded")

        oid = id(obj)
        if oid in self._seen:
            return self._seen[oid]

        # Collect decorators from this object
        try:
            from .annotations import collect_decorators

            obj_decorators = collect_decorators(obj)
            # Merge decorators into our collected set
            self._collected_decorators["constraints"].extend(
                obj_decorators["constraints"]
            )
            self._collected_decorators["directives"].extend(
                obj_decorators["directives"]
            )
        except Exception:
            # If decorator collection fails, continue without them
            # This prevents the entire visualization from failing due to annotation issues
            pass

        # Find appropriate relationalizer
        relationalizer = RelationalizerRegistry.find_relationalizer(obj)
        if relationalizer is None:
            raise ValueError(f"No relationalizer found for object of type {type(obj)}")

        # Get atom and relations from relationalizer
        atom_obj, relations_list = relationalizer.relationalize(obj, self)
        
        # Convert to old format for compatibility with existing code
        atom = atom_obj.to_dict()
        relations = [rel.to_tuple() for rel in relations_list]

        # Add full type hierarchy to the atom
        type_hierarchy = [cls.__name__ for cls in inspect.getmro(type(obj))]
        # Only override type if the relationalizer didn't provide a custom one
        if atom.get("type") == type(obj).__name__ or not atom.get("type"):
            atom["type"] = type_hierarchy[0]  # Most specific type (first in the hierarchy)
        atom["type_hierarchy"] = (
            type_hierarchy  # Store the full type hierarchy if needed
        )

        # Add atom to our collection
        self._atoms.append(atom)

        # Process relations
        for rel_name, source_id, target_id in relations:
            self._rels.setdefault(rel_name, []).append([source_id, target_id])

        return atom["id"]

    def __call__(self, obj: Any) -> str:
        """Allow the builder to be called as a function for recursive walking."""
        return self._walk(obj)

    def _get_atom_type(self, atom_id: str) -> str:
        """Get the type of an atom by its ID."""
        for atom in self._atoms:
            if atom["id"] == atom_id:
                return atom["type"]
        return "object"  # Default fallback

    def build_types(self, atoms: List[Dict]) -> List[Dict]:
        """
        Build the `types` field for the data instance.

        Args:
            atoms: List of atoms, each containing a "type" field with the most specific type.

        Returns:
            List of type definitions, each matching the desired format.
        """
        type_map = {}

        BUILTINTYPES = {"int", "float", "str", "bool", "NoneType", "object"}

        # Iterate over all atoms to populate the type map
        for atom in atoms:
            most_specific_type = atom["type"]  # The most specific type as a string
            if most_specific_type not in type_map:
                type_hierarchy = atom.get("type_hierarchy", [most_specific_type])

                # Initialize the type entry
                type_map[most_specific_type] = {
                    "_": "type",
                    "id": most_specific_type,
                    "types": type_hierarchy,  # Full type hierarchy
                    "atoms": [],  # List of atoms of this type
                    "meta": {"builtin": most_specific_type in BUILTINTYPES},
                }
            # Add the full atom details to the "atoms" list
            type_map[most_specific_type]["atoms"].append(
                {"_": "atom", "id": atom["id"], "type": atom["type"]}
            )

        # Convert the type_map dictionary to a list of its values
        return list(type_map.values())


# Import built-in relationalizers to ensure they get registered
# This import needs to happen after the registry is defined
from . import domain_relationalizers  # noqa: E402

# Register the built-in relationalizers
domain_relationalizers.register_builtin_relationalizers(RelationalizerRegistry)

"""
Spytial-Core Data Instance Relationalizer Architecture

This module provides a pluggable system for converting Python objects
into CnD-compatible atom/relation representations using relationalizers.
"""

import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

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
        return [
            (priority, relationalizer_cls.__name__)
            for priority, relationalizer_cls in cls._relationalizers
        ]

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
        self._current_depth = 0  # Track current recursion depth
        # Extensibility mechanism: custom reifiers for specific types
        self._custom_reifiers = {}
        self._caller_namespace = (
            None  # Store caller's namespace for variable name lookup
        )
        self._as_type = None  # Store type for root object

    def build_instance(self, obj: Any, as_type: Optional[Any] = None) -> Dict:
        """Build a complete data instance from an object.

        Args:
            obj: The Python object to build an instance from.
            as_type: Optional annotated type to treat the object as. Annotations
                     from this type will be applied in addition to introspected ones.
        """
        self._seen.clear()
        self._atoms.clear()
        self._rels.clear()
        self._id_counter = 0
        self._collected_decorators = {"constraints": [], "directives": []}
        self._current_depth = 0  # Reset depth
        self._as_type = as_type  # Store for use during walk

        # Extract annotations from as_type if provided
        if as_type is not None:
            try:
                from .annotations import extract_spytial_annotations

                type_annotations = extract_spytial_annotations(as_type)
                if type_annotations:
                    self._collected_decorators["constraints"].extend(
                        type_annotations["constraints"]
                    )
                    self._collected_decorators["directives"].extend(
                        type_annotations["directives"]
                    )
            except Exception:
                pass

        # Capture the caller's namespace for variable name lookup
        # Call stack: user_code -> diagram/evaluate -> build_instance
        # We need to go back to user_code (2 frames back from build_instance)
        try:
            frame = inspect.currentframe()
            # Walk back through the frames to find the user's code
            # Frame 0: build_instance, Frame 1: diagram/evaluate, Frame 2: user code
            user_frame = frame
            for _ in range(2):  # Go back 2 frames
                if user_frame and user_frame.f_back:
                    user_frame = user_frame.f_back
                else:
                    break

            if user_frame:
                # Merge locals and globals from the user's frame
                self._caller_namespace = {**user_frame.f_globals, **user_frame.f_locals}
            else:
                self._caller_namespace = None
        except Exception:
            self._caller_namespace = None

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
            for atom_tuple in tuples:
                # Handle all relations the same way (n-ary approach)
                atom_ids = atom_tuple
                atom_types = [self._get_atom_type(atom_id) for atom_id in atom_ids]
                typed_tuples.append(
                    {
                        "atoms": atom_ids,
                        "types": atom_types,
                    }
                )

            # Set the types to the types of the first relation in the tuple
            # Assume arity is constant across all tuples in a relation
            if typed_tuples:
                relation_types = ["object"] * len(typed_tuples[0]["types"])
            else:
                relation_types = ["object", "object"]  # Default binary

            relations.append(
                {
                    "id": rel_name,
                    "name": rel_name,
                    "types": relation_types,
                    "tuples": typed_tuples,
                }
            )

        # Deduplicate atoms by ID FIRST - if multiple atoms have the same ID, keep only the first
        # This is important for primitives where the same value may be referenced multiple times
        atoms_by_id = {}
        for atom in self._atoms:
            if atom["id"] not in atoms_by_id:
                atoms_by_id[atom["id"]] = atom

        deduplicated_atoms = list(atoms_by_id.values())

        # Build types from deduplicated atoms to avoid duplicate entries in type.atoms
        typs = self.build_types(deduplicated_atoms)

        return {"atoms": deduplicated_atoms, "relations": relations, "types": typs}

    def get_collected_decorators(self) -> Dict:
        """Get all decorators collected during the build process."""
        return self._collected_decorators

    def _get_id(self, obj: Any) -> str:
        """Get or create an ID for an object.

        For primitives, uses value-based lookup to avoid race conditions with memory addresses.
        For objects, uses memory-based ID with spytial registry fallback.
        """
        # For primitive types, always use value-based ID (no memory address confusion)
        if isinstance(obj, (int, float, bool)) or obj is None:
            return str(obj)
        elif isinstance(obj, str):
            # For strings, use quoted representation to distinguish from other IDs
            return f'"{obj}"'

        # For non-primitive objects, use memory-based ID with caching
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

            # Fall back to simple ID generation for objects
            # (This will be handled in the remainder of the method below)
            self._seen[oid] = f"n{self._id_counter}"
            self._id_counter += 1
        return self._seen[oid]

    def _walk(self, obj: Any, max_depth: int = 100) -> str:
        """Walk an object using the appropriate provider."""
        self._current_depth += 1
        if self._current_depth > max_depth:
            raise RecursionError("Maximum recursion depth exceeded")

        oid = id(obj)
        if oid in self._seen:
            self._current_depth -= 1
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
        except Exception as e:
            # If decorator collection fails, continue without them
            # This prevents the entire visualization from failing due to annotation issues
            pass

        # Find appropriate relationalizer
        relationalizer = RelationalizerRegistry.find_relationalizer(obj)
        if relationalizer is None:
            raise ValueError(f"No relationalizer found for object of type {type(obj)}")

        # Get atoms and relations from relationalizer
        atoms_list, relations_list = relationalizer.relationalize(obj, self)

        # Convert to old format for compatibility with existing code
        atoms = [atom_obj.to_dict() for atom_obj in atoms_list]

        # Process relations - use to_tuple() method for consistent format
        relations = []
        for rel in relations_list:
            # Use the to_tuple method: (name, atom1, atom2, ...)
            relations.append(rel.to_tuple())

        # Add full type hierarchy to each atom
        type_hierarchy = [cls.__name__ for cls in inspect.getmro(type(obj))]

        ## TODO: There's a bug here.
        primary_atom_id = None
        for i, atom in enumerate(atoms):
            # Only override type and hierarchy for the PRIMARY atom (the one representing this object)
            # Other atoms (like list elements) should keep their own types from the relationalizer
            if i == 0:  # Primary atom - represents the root object being walked
                if atom.get("type") == type(obj).__name__ or not atom.get("type"):
                    atom["type"] = type_hierarchy[0]  # Most specific type
                    atom["type_hierarchy"] = type_hierarchy
                else:
                    # Even if relationalizer provided a different type, add the hierarchy
                    atom["type_hierarchy"] = [atom["type"]] + type_hierarchy
                primary_atom_id = atom["id"]
            else:
                # Secondary atoms (e.g., list elements) - keep their relationalizer-provided type
                # Don't override with the container's type hierarchy
                if not atom.get("type_hierarchy"):
                    atom["type_hierarchy"] = [atom.get("type", "object")]

            # Add atom to our collection
            self._atoms.append(atom)

        # Process relations - handle tuples of arbitrary length
        for rel_data in relations:
            # Relations now come as (name, atom1, atom2, ...) tuples
            rel_name = rel_data[0]
            atom_ids = list(rel_data[1:])  # All atoms after the name
            self._rels.setdefault(rel_name, []).append(atom_ids)

        # Decrement depth after processing
        self._current_depth -= 1

        # Return the ID of the primary atom
        return primary_atom_id

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

    def reify(self, data_instance: Dict) -> Any:
        """
        Reconstruct Python objects from a Spytial-Core data instance.

        This method reverses the build_instance operation, converting atoms and relations
        back into Python objects.

        Args:
            data_instance: Dictionary containing 'atoms', 'relations', and 'types'
                          as returned by build_instance()

        Returns:
            The reconstructed Python object corresponding to the root atom

        Raises:
            ValueError: If the data instance is malformed or cannot be reconstructed
        """
        if not isinstance(data_instance, dict):
            raise ValueError("data_instance must be a dictionary")

        required_keys = {"atoms", "relations"}
        if not all(key in data_instance for key in required_keys):
            raise ValueError(f"data_instance must contain keys: {required_keys}")

        atoms = data_instance["atoms"]
        relations = data_instance["relations"]

        if not atoms:
            raise ValueError("data_instance must contain at least one atom")

        # Build maps for efficient lookup
        atom_map = {atom["id"]: atom for atom in atoms}

        # Build relation map: atom_id -> {relation_name: [target_atom_ids]}
        relation_map = {}
        for relation in relations:
            rel_name = relation["name"]
            for tuple_info in relation["tuples"]:
                source_id = tuple_info["atoms"][0]
                target_ids = tuple_info["atoms"][1:]

                if source_id not in relation_map:
                    relation_map[source_id] = {}
                if rel_name not in relation_map[source_id]:
                    relation_map[source_id][rel_name] = []
                relation_map[source_id][rel_name].extend(target_ids)

        # Track reconstructed objects to handle circular references
        reconstructed = {}

        def reify_atom(atom_id: str) -> Any:
            """Recursively reconstruct an object from its atom ID."""
            if atom_id in reconstructed:
                return reconstructed[atom_id]

            if atom_id not in atom_map:
                raise ValueError(f"Atom {atom_id} not found in atom_map")

            atom = atom_map[atom_id]
            atom_type = atom["type"]
            atom_label = atom["label"]

            # Handle primitive types
            if atom_type in {"str", "int", "float", "bool", "NoneType"}:
                obj = self._reify_primitive(atom_type, atom_label)
                reconstructed[atom_id] = obj
                return obj

            # Handle collections and complex types
            relations_for_atom = relation_map.get(atom_id, {})

            # Check for custom reifier first
            if atom_type in self._custom_reifiers:
                obj = self._custom_reifiers[atom_type](
                    atom, relations_for_atom, reify_atom
                )
            elif atom_type == "dict":
                obj = self._reify_dict(atom_id, relations_for_atom, reify_atom)
            elif atom_type == "list":
                obj = self._reify_list(atom_id, relations_for_atom, reify_atom)
            elif atom_type == "tuple":
                obj = self._reify_tuple(atom_id, relations_for_atom, reify_atom)
            elif atom_type == "set":
                obj = self._reify_set(atom_id, relations_for_atom, reify_atom)
            else:
                # Handle generic objects or custom types
                obj = self._reify_generic_object(atom, relations_for_atom, reify_atom)

            reconstructed[atom_id] = obj
            return obj

        # Find the root atom - it's the one that appears as source in relations
        # but never appears as a target, OR if no relations exist, use the last atom
        # (which is typically the root object processed by _walk)

        if not relations:
            # No relations - use the only atom or the last one
            root_atom_id = atoms[-1]["id"]
        else:
            # Find atoms that are sources but not targets
            source_atoms = set()
            target_atoms = set()

            for relation in relations:
                for tuple_info in relation["tuples"]:
                    atom_ids = tuple_info["atoms"]
                    source_atoms.add(atom_ids[0])
                    target_atoms.update(atom_ids[1:])

            # Root candidates are sources that are not targets
            root_candidates = source_atoms - target_atoms

            if root_candidates:
                # Use the first root candidate
                root_atom_id = next(iter(root_candidates))
            else:
                # Fallback: use the last atom (usually the root in our walk order)
                root_atom_id = atoms[-1]["id"]

        return reify_atom(root_atom_id)

    def _reify_primitive(self, atom_type: str, atom_label: str) -> Any:
        """Reconstruct a primitive value from its type and label."""
        if atom_type == "str":
            return atom_label
        elif atom_type == "int":
            return int(atom_label)
        elif atom_type == "float":
            return float(atom_label)
        elif atom_type == "bool":
            return atom_label.lower() == "true"
        elif atom_type == "NoneType":
            return None
        else:
            raise ValueError(f"Unknown primitive type: {atom_type}")

    def _reify_dict(self, atom_id: str, relations: Dict, reify_atom) -> dict:
        """Reconstruct a dictionary from its relations."""
        result = {}
        for rel_name, target_ids in relations.items():
            # Dictionary relations use the key name as the relation name
            for target_id in target_ids:
                key = rel_name
                value = reify_atom(target_id)
                result[key] = value
        return result

    def _reify_list(self, atom_id: str, relations: Dict, reify_atom) -> list:
        """Reconstruct a list from its relations."""
        result = []
        # List relations use numeric indices as relation names
        indexed_items = []
        for rel_name, target_ids in relations.items():
            try:
                index = int(rel_name)
                for target_id in target_ids:
                    value = reify_atom(target_id)
                    indexed_items.append((index, value))
            except ValueError:
                # Skip non-numeric relation names
                continue

        # Sort by index and build the list
        indexed_items.sort(key=lambda x: x[0])
        result = [item[1] for item in indexed_items]
        return result

    def _reify_tuple(self, atom_id: str, relations: Dict, reify_atom) -> tuple:
        """Reconstruct a tuple from its relations."""
        # Tuples are reconstructed like lists, then converted
        list_result = self._reify_list(atom_id, relations, reify_atom)
        return tuple(list_result)

    def _reify_set(self, atom_id: str, relations: Dict, reify_atom) -> set:
        """Reconstruct a set from its relations."""
        result = set()
        # Sets use "contains" relation name for elements
        if "contains" in relations:
            for target_id in relations["contains"]:
                value = reify_atom(target_id)
                result.add(value)
        return result

    def _reify_generic_object(self, atom: Dict, relations: Dict, reify_atom) -> Any:
        """
        Reconstruct a generic object from its atom and relations.

        This handles objects with __dict__ or custom classes.
        For complex reconstruction scenarios, this method can be extended
        or overridden to provide custom reification logic.
        """
        atom_type = atom["type"]

        # Try to get the class from built-in types first
        try:
            # For simple types, try to create an empty instance
            if atom_type in {"dict", "list", "tuple", "set"}:
                # These should have been handled by specific methods above
                raise ValueError(
                    f"Type {atom_type} should be handled by specific method"
                )

            # For other types, create a simple namespace object
            # This is a fallback that creates an object with attributes set from relations
            class ReconstructedObject:
                def __init__(self):
                    pass

                def __repr__(self):
                    attrs = [f"{k}={v!r}" for k, v in self.__dict__.items()]
                    return f"{atom_type}({', '.join(attrs)})"

            obj = ReconstructedObject()
            obj.__class__.__name__ = atom_type

            # Set attributes from relations
            for rel_name, target_ids in relations.items():
                if len(target_ids) == 1:
                    # Single value relation
                    value = reify_atom(target_ids[0])
                    setattr(obj, rel_name, value)
                else:
                    # Multiple value relation - create a list
                    values = [reify_atom(tid) for tid in target_ids]
                    setattr(obj, rel_name, values)

            return obj

        except Exception as e:
            raise ValueError(f"Cannot reconstruct object of type {atom_type}: {e}")

    def can_reify(self, data_instance: Dict) -> bool:
        """
        Check if a data instance can be reified.

        Args:
            data_instance: Dictionary to check

        Returns:
            True if the data instance appears to be valid for reification
        """
        try:
            if not isinstance(data_instance, dict):
                return False

            required_keys = {"atoms", "relations"}
            if not all(key in data_instance for key in required_keys):
                return False

            atoms = data_instance["atoms"]
            if not atoms or not isinstance(atoms, list):
                return False

            # Check if all atoms have required fields
            for atom in atoms:
                if not isinstance(atom, dict):
                    return False
                if not all(key in atom for key in ["id", "type", "label"]):
                    return False

            return True

        except Exception:
            return False

    def register_reifier(self, type_name: str, reifier_func: Callable[..., Any]) -> None:
        """
        Register a custom reifier function for a specific type.

        This provides an extensibility mechanism for complex reconstruction scenarios.

        Args:
            type_name: The atom type name to handle (e.g., "MyCustomClass")
            reifier_func: Function with signature (atom, relations, reify_atom) -> object
                         where:
                         - atom: Dict containing atom information (id, type, label, etc.)
                         - relations: Dict mapping relation names to lists of target atom IDs
                         - reify_atom: Function to recursively reify other atoms by ID

        Example:
            def custom_reifier(atom, relations, reify_atom):
                # Custom reconstruction logic
                obj = MyCustomClass()
                for rel_name, target_ids in relations.items():
                    setattr(obj, rel_name, [reify_atom(tid) for tid in target_ids])
                return obj

            builder.register_reifier("MyCustomClass", custom_reifier)
        """
        self._custom_reifiers[type_name] = reifier_func

    def unregister_reifier(self, type_name: str):
        """
        Remove a custom reifier for a specific type.

        Args:
            type_name: The atom type name to remove the reifier for
        """
        self._custom_reifiers.pop(type_name, None)

    def list_reifiers(self) -> List[str]:
        """
        List all registered custom reifier type names.

        Returns:
            List of type names that have custom reifiers registered
        """
        return list(self._custom_reifiers.keys())


# Import built-in relationalizers to ensure they get registered
# This import needs to happen after the registry is defined
from . import domain_relationalizers  # noqa: E402

# Register the built-in relationalizers
domain_relationalizers.register_builtin_relationalizers(RelationalizerRegistry)

"""
Spytial-Core Data Instance Relationalizer Architecture

This module provides a pluggable system for converting Python objects
into CnD-compatible atom/relation representations using relationalizers.
"""

import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

# Import base classes from domain-relationalizers
from .domain_relationalizers.base import RelationalizerBase, Atom, Relation


def _invoke_custom_reifier(fn, atom, relations, reify_atom, register):
    """Call a user-registered reifier, passing ``register`` only if it accepts it.

    Keeps backwards compatibility with the original 3-arg signature
    ``(atom, relations, reify_atom)`` while enabling cycle-safe reifiers that
    register a placeholder with ``(atom, relations, reify_atom, register)``.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(atom, relations, reify_atom)

    params = sig.parameters
    if "register" in params:
        return fn(atom, relations, reify_atom, register=register)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return fn(atom, relations, reify_atom, register=register)
    positional = [
        p
        for p in params.values()
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    if len(positional) >= 4:
        return fn(atom, relations, reify_atom, register)
    return fn(atom, relations, reify_atom)


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

    def __init__(
        self,
        preserve_object_ids: bool = False,
        identity_resolver: Optional[Callable[[Any], Optional[str]]] = None,
    ):
        self._seen = {}
        self._atoms = []
        self._rels = {}
        self._id_counter = 0
        self._preserve_object_ids = preserve_object_ids
        self._identity_resolver = identity_resolver
        self._identity_prefix = "identity:"
        self._build_identity_objects = {}
        self._persistent_object_ids = {}
        self._persistent_id_counter = 0
        self._collected_decorators = {"constraints": [], "directives": []}
        self._current_depth = 0  # Track current recursion depth
        # Extensibility mechanism: custom reifiers for specific types
        self._custom_reifiers = {}
        self._type_label_counters = {}  # Per-type counters for fallback labels
        self._caller_namespace = (
            None  # Store caller's namespace for variable name lookup
        )
        self._as_type = None  # Store type for root object
        self._last_root_id: Optional[str] = None  # Root atom from most recent build

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
        self._build_identity_objects = {}
        self._collected_decorators = {"constraints": [], "directives": []}
        self._current_depth = 0  # Reset depth
        self._type_label_counters = {}  # Reset per-type counters
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
            root_atom_id = self._walk(obj)
        except Exception as e:
            print(f"Error during data instance building: {e}")
            print("Object:", obj)
            raise

        # Cache the root so a later reify() call can reconstruct the same
        # object even when the graph is cyclic (topology alone can't pick the
        # root when every source also appears as a target).
        self._last_root_id = root_atom_id

        # Convert relations to include types (matching IRelation interface)
        relations = []
        for rel_name, tuples in self._rels.items():
            # Deduplicate tuples — the walker may reach the same
            # (source, target) pair via multiple traversal paths
            # (e.g. forward pointers and back-pointers through a
            # shared sentinel whose parent was mutated).
            seen_tuple_keys: set = set()
            typed_tuples = []
            for atom_tuple in tuples:
                tuple_key = tuple(atom_tuple)
                if tuple_key in seen_tuple_keys:
                    continue
                seen_tuple_keys.add(tuple_key)
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

        # Strip internal type_hierarchy field before sending to core
        for atom in deduplicated_atoms:
            atom.pop("type_hierarchy", None)

        return {
            "atoms": deduplicated_atoms,
            "relations": relations,
            "types": typs,
            "rootId": root_atom_id,
        }

    def get_collected_decorators(self) -> Dict:
        """Get all decorators collected during the build process, deduplicated.

        During _walk(), the same class-level decorators are collected once per
        object instance of that class.  This deduplicates them so the final
        YAML spec contains each unique rule only once.
        """
        from .annotations import _deduplicate_entries

        return {
            "constraints": _deduplicate_entries(
                self._collected_decorators["constraints"]
            ),
            "directives": _deduplicate_entries(
                self._collected_decorators["directives"]
            ),
        }

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

            if self._identity_resolver is not None:
                identity_key = self._identity_resolver(obj)
                if identity_key is not None:
                    if not isinstance(identity_key, str):
                        raise TypeError(
                            "diagramSequence identity hook must return a string or None"
                        )

                    existing_oid = self._build_identity_objects.get(identity_key)
                    if existing_oid is not None and existing_oid != oid:
                        # A second distinct Python object claims the same conceptual
                        # identity (e.g. a live node and a snapshot copy of the same
                        # tree node, reached via back-pointers).  The identity resolver
                        # is the authoritative source of conceptual identity, so we
                        # alias this object to the already-registered canonical atom —
                        # both Python objects collapse to the same atom in this frame.
                        canonical_id = f"{self._identity_prefix}{identity_key}"
                        self._seen[oid] = canonical_id
                        return canonical_id

                    self._build_identity_objects[identity_key] = oid
                    self._seen[oid] = f"{self._identity_prefix}{identity_key}"
                    return self._seen[oid]

            if self._preserve_object_ids:
                if oid not in self._persistent_object_ids:
                    self._persistent_object_ids[oid] = (
                        f"n{self._persistent_id_counter}"
                    )
                    self._persistent_id_counter += 1
                self._seen[oid] = self._persistent_object_ids[oid]
                return self._seen[oid]

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
                    "id": most_specific_type,
                    "types": type_hierarchy,  # Full type hierarchy
                    "atoms": [],  # List of atoms of this type
                    "isBuiltin": most_specific_type in BUILTINTYPES,
                }
            # Add the full atom details to the "atoms" list
            type_map[most_specific_type]["atoms"].append(
                {"id": atom["id"], "type": atom["type"], "label": atom["label"]}
            )

        # Convert the type_map dictionary to a list of its values
        return list(type_map.values())

    def reify(self, data_instance: Dict, root_id: Optional[str] = None) -> Any:
        """
        Reconstruct Python objects from a Spytial-Core data instance.

        This method reverses the build_instance operation, converting atoms and relations
        back into Python objects.

        Args:
            data_instance: Dictionary containing 'atoms', 'relations', and optionally
                'rootId' as returned by build_instance().
            root_id: Optional atom id to use as the reconstruction root. Overrides any
                'rootId' present in data_instance. When neither is provided the root is
                inferred from the relation topology.

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

        # Two views of the relations keyed by source atom:
        #   relation_map   — flat concatenation of every target across tuples.
        #                    Kept for backwards compatibility with user-supplied
        #                    custom reifiers registered via register_reifier().
        #   relation_tuples — preserves the target tuple structure, which is
        #                    required to reconstruct n-ary relations (notably
        #                    the ternary ``kv`` used for dicts).
        relation_map: Dict[str, Dict[str, List[str]]] = {}
        relation_tuples: Dict[str, Dict[str, List[List[str]]]] = {}
        for relation in relations:
            rel_name = relation["name"]
            for tuple_info in relation["tuples"]:
                source_id = tuple_info["atoms"][0]
                target_ids = tuple_info["atoms"][1:]

                if source_id not in relation_map:
                    relation_map[source_id] = {}
                    relation_tuples[source_id] = {}
                if rel_name not in relation_map[source_id]:
                    relation_map[source_id][rel_name] = []
                    relation_tuples[source_id][rel_name] = []
                relation_map[source_id][rel_name].extend(target_ids)
                relation_tuples[source_id][rel_name].append(list(target_ids))

        # Memoize reconstructed objects. For mutable containers we register an
        # empty placeholder *before* recursing into their children so that any
        # self- or back-reference resolves to the same object — this is what
        # makes cyclic structures (self-loops, A↔B, A→B→C→A) reifiable.
        reconstructed: Dict[str, Any] = {}

        def reify_atom(atom_id: str) -> Any:
            if atom_id in reconstructed:
                return reconstructed[atom_id]

            if atom_id not in atom_map:
                raise ValueError(f"Atom {atom_id} not found in atom_map")

            atom = atom_map[atom_id]
            atom_type = atom["type"]
            atom_label = atom["label"]

            if atom_type in {"str", "int", "float", "bool", "NoneType"}:
                obj = self._reify_primitive(atom_type, atom_label)
                reconstructed[atom_id] = obj
                return obj

            relations_for_atom = relation_map.get(atom_id, {})

            def register(placeholder: Any) -> Any:
                reconstructed[atom_id] = placeholder
                return placeholder

            if atom_type in self._custom_reifiers:
                obj = _invoke_custom_reifier(
                    self._custom_reifiers[atom_type],
                    atom,
                    relations_for_atom,
                    reify_atom,
                    register,
                )
            elif atom_type == "dict":
                obj = self._reify_dict(
                    atom_id,
                    relation_tuples.get(atom_id, {}),
                    reify_atom,
                    register,
                )
            elif atom_type == "list":
                obj = self._reify_list(
                    atom_id,
                    relation_tuples.get(atom_id, {}),
                    reify_atom,
                    register,
                )
            elif atom_type == "tuple":
                obj = self._reify_tuple(
                    atom_id, relations_for_atom, reify_atom
                )
            elif atom_type == "set":
                obj = self._reify_set(
                    atom_id, relations_for_atom, reify_atom, register
                )
            else:
                obj = self._reify_generic_object(
                    atom, relations_for_atom, reify_atom, register
                )

            # Register the final value. For reifiers that already registered a
            # mutable placeholder this is effectively a no-op (same object);
            # for tuples and primitive-style reifiers it installs the result.
            reconstructed[atom_id] = obj
            return obj

        root_atom_id = self._resolve_root_id(data_instance, atoms, relations, root_id)
        return reify_atom(root_atom_id)

    def _resolve_root_id(
        self,
        data_instance: Dict,
        atoms: List[Dict],
        relations: List[Dict],
        explicit_root_id: Optional[str],
    ) -> str:
        """Pick the atom id to start reification from.

        Precedence:
          1. Explicit ``root_id`` argument to reify().
          2. ``rootId`` field in the data instance (written by build_instance).
          3. Topology — prefer sources that are never targets; then sources that
             are only ever their own target (self-loops); else fall back to the
             last atom.
        """
        known_ids = {atom["id"] for atom in atoms}

        if explicit_root_id is not None and explicit_root_id in known_ids:
            return explicit_root_id

        stored_root = data_instance.get("rootId")
        if isinstance(stored_root, str) and stored_root in known_ids:
            return stored_root

        if not relations:
            return atoms[-1]["id"]

        source_atoms: set = set()
        # Targets from another atom (i.e. non-self-loop targets). Self-loops
        # should not disqualify an atom from being a root.
        non_self_targets: set = set()
        all_targets: set = set()

        for relation in relations:
            for tuple_info in relation["tuples"]:
                atom_ids = tuple_info["atoms"]
                src = atom_ids[0]
                source_atoms.add(src)
                for tgt in atom_ids[1:]:
                    all_targets.add(tgt)
                    if tgt != src:
                        non_self_targets.add(tgt)

        root_candidates = source_atoms - all_targets
        if root_candidates:
            return next(iter(root_candidates))

        root_candidates = source_atoms - non_self_targets
        if root_candidates:
            return next(iter(root_candidates))

        return atoms[-1]["id"]

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

    def _reify_dict(
        self, atom_id: str, relation_tuples: Dict, reify_atom, register
    ) -> dict:
        """Reconstruct a dictionary from its relations.

        Expects ``relation_tuples`` (source-grouped, tuple-preserving) because
        DictRelationalizer emits a ternary ``kv(dict, key, value)`` relation.
        Registers the empty dict before recursing so self- or back-references
        to this dict see the same object.
        """
        result: dict = {}
        register(result)

        kv_tuples = relation_tuples.get("kv", [])
        for targets in kv_tuples:
            if len(targets) < 2:
                continue
            key = reify_atom(targets[0])
            value = reify_atom(targets[1])
            try:
                result[key] = value
            except TypeError:
                # Unhashable key (e.g. a mutable object that the build side
                # allowed through a synthetic key atom). Fall back to string.
                result[str(key)] = value

        # Back-compat path: earlier versions emitted per-key binary relations
        # where the relation name itself was the dict key. Handle any leftover
        # relations of that shape so older data instances still reify.
        for rel_name, tuples in relation_tuples.items():
            if rel_name == "kv":
                continue
            for targets in tuples:
                if not targets:
                    continue
                result[rel_name] = reify_atom(targets[0])
        return result

    def _reify_list(
        self, atom_id: str, relation_tuples: Dict, reify_atom, register
    ) -> list:
        """Reconstruct a list from its relations.

        Expects ``relation_tuples`` (tuple-preserving) because ListRelationalizer
        emits a ternary ``idx(list, index_atom, value_atom)``. Registers the
        empty list before recursing so self-references resolve to the same
        object, then populates in place.
        """
        result: list = []
        register(result)

        indexed_items = []
        for targets in relation_tuples.get("idx", []):
            if len(targets) < 2:
                continue
            index_value = reify_atom(targets[0])
            try:
                index = int(index_value)
            except (TypeError, ValueError):
                continue
            indexed_items.append((index, reify_atom(targets[1])))

        indexed_items.sort(key=lambda x: x[0])
        # Populate in place so the already-registered list instance is the one
        # filled — preserves identity for back-references that resolved mid-flight.
        result.extend(item[1] for item in indexed_items)
        return result

    def _reify_tuple(self, atom_id: str, relations: Dict, reify_atom) -> tuple:
        """Reconstruct a tuple from its relations.

        TupleRelationalizer emits one binary relation per index named
        ``t0``, ``t1``, … Tuples are immutable so we cannot register a
        placeholder; a genuinely self-referential tuple is not representable
        in Python. Non-self shared references still resolve via memoization.
        """
        indexed_items = []
        for rel_name, target_ids in relations.items():
            if not rel_name.startswith("t"):
                continue
            try:
                index = int(rel_name[1:])
            except ValueError:
                continue
            for target_id in target_ids:
                indexed_items.append((index, reify_atom(target_id)))
        indexed_items.sort(key=lambda x: x[0])
        return tuple(item[1] for item in indexed_items)

    def _reify_set(
        self, atom_id: str, relations: Dict, reify_atom, register
    ) -> set:
        """Reconstruct a set from its relations."""
        result: set = set()
        register(result)
        if "contains" in relations:
            for target_id in relations["contains"]:
                result.add(reify_atom(target_id))
        return result

    def _reify_generic_object(
        self, atom: Dict, relations: Dict, reify_atom, register
    ) -> Any:
        """Reconstruct a generic object from its atom and relations.

        Allocates the attribute-bag instance and registers it *before*
        recursing into relations so self-loops and back-pointers resolve to
        the same instance.
        """
        atom_type = atom["type"]

        if atom_type in {"dict", "list", "tuple", "set"}:
            raise ValueError(f"Type {atom_type} should be handled by specific method")

        class ReconstructedObject:
            def __init__(self):
                pass

            def __repr__(self):
                attrs = [f"{k}={v!r}" for k, v in self.__dict__.items()]
                return f"{atom_type}({', '.join(attrs)})"

        obj = ReconstructedObject()
        obj.__class__.__name__ = atom_type
        register(obj)

        for rel_name, target_ids in relations.items():
            if len(target_ids) == 1:
                setattr(obj, rel_name, reify_atom(target_ids[0]))
            else:
                setattr(obj, rel_name, [reify_atom(tid) for tid in target_ids])

        return obj

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

    def register_reifier(
        self, type_name: str, reifier_func: Callable[..., Any]
    ) -> None:
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

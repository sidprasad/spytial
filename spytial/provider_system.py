"""
CnD Data Instance Relationalizer Architecture

This module provides a pluggable system for converting Python objects
into CnD-compatible atom/relation representations using relationalizers.
"""

import abc
import dataclasses
import inspect
from typing import Any, Dict, List, Tuple, Type, Optional, Protocol
import collections.abc


@dataclasses.dataclass
class Atom:
    """
    Represents an atom in the spatial visualization.
    
    An atom is a fundamental unit of data that can be positioned and styled
    in the spatial diagram.
    """
    id: str
    type: str
    label: str
    
    def to_dict(self) -> Dict[str, str]:
        """Convert atom to dictionary format expected by CnD."""
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label
        }


@dataclasses.dataclass
class Relation:
    """
    Represents a relation between atoms in the spatial visualization.
    
    A relation connects two atoms through a named relationship.
    """
    name: str
    source_id: str
    target_id: str
    
    def to_tuple(self) -> Tuple[str, str, str]:
        """Convert relation to tuple format expected by CnD."""
        return (self.name, self.source_id, self.target_id)


class RelationalizerBase(abc.ABC):
    """
    Abstract base class for relationalizers.
    
    Relationalizers convert Python objects into atoms and relations for spatial
    visualization. They define how objects are represented as atoms and how
    relationships between objects are expressed as spatial relations.
    """
    
    @abc.abstractmethod
    def can_handle(self, obj: Any) -> bool:
        """
        Return True if this relationalizer can handle the given object.
        
        Args:
            obj: The Python object to test
            
        Returns:
            True if this relationalizer can process the object, False otherwise
        """
        pass
    
    @abc.abstractmethod
    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        """
        Convert object to atoms and relations using structured types.
        
        Args:
            obj: The object to convert
            walker_func: Function to recursively walk nested objects
            
        Returns:
            Tuple of (atom, relations_list)
            atom: Atom instance representing the object
            relations_list: List of Relation instances connecting this object to others
        """
        pass
    
    def provide_atoms_and_relations(self, obj: Any, walker_func) -> Tuple[Dict, List[Tuple[str, str, str]]]:
        """
        Convert object to atoms and relations (legacy format for backward compatibility).
        
        This method provides backward compatibility with the old provider system.
        New relationalizers should implement relationalize() instead.
        
        Args:
            obj: The object to convert
            walker_func: Function to recursively walk nested objects
            
        Returns:
            Tuple of (atom_dict, relations_list)
            atom_dict: {"id": str, "type": str, "label": str}
            relations_list: [(relation_name, source_id, target_id), ...]
        """
        atom, relations = self.relationalize(obj, walker_func)
        return atom.to_dict(), [rel.to_tuple() for rel in relations]


# Keep DataInstanceProvider as a deprecated alias for backward compatibility
class DataInstanceProvider(RelationalizerBase):
    """
    Deprecated: Use RelationalizerBase instead.
    
    Abstract base class for data instance providers.
    This class provides backward compatibility for the old provider system.
    """
    
    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        """
        Default implementation that calls the old provide_atoms_and_relations method.
        """
        atom_dict, relations_tuples = self.provide_atoms_and_relations(obj, walker_func)
        atom = Atom(
            id=atom_dict["id"],
            type=atom_dict["type"],
            label=atom_dict["label"]
        )
        relations = [Relation(name=name, source_id=src, target_id=tgt) 
                    for name, src, tgt in relations_tuples]
        return atom, relations


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


# Keep data_provider as a deprecated alias for backward compatibility
def data_provider(cls: Type = None, *, priority: int = 0):
    """
    Deprecated: Use @relationalizer decorator instead.
    
    Decorator to register a class as a data provider.
    
    Args:
        priority: Higher priority providers are tried first
    """
    return relationalizer(cls, priority=priority)


# Object-level relationalizer storage
OBJECT_RELATIONALIZER_ATTR = "__spytial_object_relationalizer__"
_OBJECT_RELATIONALIZER_REGISTRY: Dict[int, RelationalizerBase] = {}

# Keep old provider names for backward compatibility
OBJECT_PROVIDER_ATTR = OBJECT_RELATIONALIZER_ATTR
_OBJECT_PROVIDER_REGISTRY = _OBJECT_RELATIONALIZER_REGISTRY


class RelationalizerRegistry:
    """Registry for relationalizers."""
    
    _relationalizers: List[Tuple[int, Type[RelationalizerBase]]] = []
    _instances: List[RelationalizerBase] = []
    
    @classmethod
    def register(cls, relationalizer_cls: Type[RelationalizerBase], priority: int = 0):
        """Register a relationalizer class with given priority."""
        cls._relationalizers.append((priority, relationalizer_cls))
        cls._relationalizers.sort(key=lambda x: x[0], reverse=True)  # Higher priority first
        cls._instances = [relationalizer_cls() for _, relationalizer_cls in cls._relationalizers]
    
    @classmethod
    def find_relationalizer(cls, obj: Any) -> Optional[RelationalizerBase]:
        """Find the first relationalizer that can handle the given object."""
        # First check for object-specific relationalizers
        object_relationalizer = cls._get_object_relationalizer(obj)
        if object_relationalizer is not None:
            return object_relationalizer
        
        # Then check registered class-level relationalizers
        for relationalizer in cls._instances:
            if relationalizer.can_handle(obj):
                return relationalizer
        return None
    
    @classmethod
    def _get_object_relationalizer(cls, obj: Any) -> Optional[RelationalizerBase]:
        """Get object-specific relationalizer if one exists."""
        # First check if stored on object directly
        if hasattr(obj, OBJECT_RELATIONALIZER_ATTR):
            return getattr(obj, OBJECT_RELATIONALIZER_ATTR)
        
        # Then check global registry for objects that can't store attributes
        obj_id = id(obj)
        if obj_id in _OBJECT_RELATIONALIZER_REGISTRY:
            return _OBJECT_RELATIONALIZER_REGISTRY[obj_id]
        
        return None
    
    @classmethod
    def clear(cls):
        """Clear all registered relationalizers (for testing)."""
        cls._relationalizers.clear()
        cls._instances.clear()
        _OBJECT_RELATIONALIZER_REGISTRY.clear()


# Keep DataInstanceRegistry as a deprecated alias for backward compatibility
class DataInstanceRegistry:
    """Deprecated: Use RelationalizerRegistry instead."""
    
    _providers: List[Tuple[int, Type[RelationalizerBase]]] = []
    _instances: List[RelationalizerBase] = []
    
    @classmethod
    def register(cls, provider_cls: Type[RelationalizerBase], priority: int = 0):
        """Register a provider class with given priority."""
        return RelationalizerRegistry.register(provider_cls, priority)
    
    @classmethod
    def find_provider(cls, obj: Any) -> Optional[RelationalizerBase]:
        """Find the first provider that can handle the given object."""
        return RelationalizerRegistry.find_relationalizer(obj)
    
    @classmethod
    def _get_object_provider(cls, obj: Any) -> Optional[RelationalizerBase]:
        """Get object-specific provider if one exists."""
        return RelationalizerRegistry._get_object_relationalizer(obj)
    
    @classmethod
    def clear(cls):
        """Clear all registered providers (for testing)."""
        return RelationalizerRegistry.clear()


# Built-in relationalizers

@relationalizer(priority=10)
class PrimitiveRelationalizer(RelationalizerBase):
    """Handles primitive types: int, float, str, bool, None."""
    
    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, (int, float, str, bool, type(None)))
    
    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        atom = Atom(
            id=walker_func._get_id(obj),
            type=type(obj).__name__,
            label=str(obj)
        )
        return atom, []


@relationalizer(priority=9)
class DictRelationalizer(RelationalizerBase):
    """Handles dictionary objects."""
    
    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, dict)
    
    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)
        atom = Atom(
            id=obj_id,
            type="dict",
            label=f"dict{{{len(obj)}}}"
        )
        
        relations = []
        for k, v in obj.items():
            vid = walker_func(v)
            key_str = str(k) if isinstance(k, (str, int, float, bool)) else f"key_{len(relations)}"
            relations.append(Relation(name=key_str, source_id=obj_id, target_id=vid))
        
        return atom, relations


@relationalizer(priority=8)
class ListRelationalizer(RelationalizerBase):
    """Handles list and tuple objects."""
    
    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, (list, tuple))
    
    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = Atom(
            id=obj_id,
            type=typ,
            label=f"{typ}[{len(obj)}]"
        )
        
        relations = []
        for i, elt in enumerate(obj):
            eid = walker_func(elt)
            relations.append(Relation(name=str(i), source_id=obj_id, target_id=eid))
        
        return atom, relations


@relationalizer(priority=8)
class SetRelationalizer(RelationalizerBase):
    """Handles set objects."""
    
    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, set)
    
    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)
        atom = Atom(
            id=obj_id,
            type="set",
            label=f"set[{len(obj)}]"
        )
        
        relations = []
        for element in obj:
            element_id = walker_func(element)
            relations.append(Relation(name="contains", source_id=obj_id, target_id=element_id))
        
        return atom, relations


@relationalizer(priority=7)
class DataclassRelationalizer(RelationalizerBase):
    """Handles dataclass objects."""
    
    def can_handle(self, obj: Any) -> bool:
        return dataclasses.is_dataclass(obj)
    
    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = Atom(
            id=obj_id,
            type=typ,
            label=f"{typ}"
        )
        
        relations = []
        for field in dataclasses.fields(obj):
            if not field.name.startswith('_'):
                value = getattr(obj, field.name)
                vid = walker_func(value)
                relations.append(Relation(name=field.name, source_id=obj_id, target_id=vid))
        
        return atom, relations


@relationalizer(priority=5)
class GenericObjectRelationalizer(RelationalizerBase):
    """Handles generic objects with __dict__ or __slots__."""
    
    def can_handle(self, obj: Any) -> bool:
        return hasattr(obj, "__dict__") or hasattr(obj, "__slots__")
    
    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = Atom(
            id=obj_id,
            type=typ,
            label=f"{typ}"
        )
        
        relations = []
        
        # Handle __slots__
        if hasattr(obj, "__slots__"):
            for slot in obj.__slots__:
                if hasattr(obj, slot):
                    value = getattr(obj, slot)
                    vid = walker_func(value)
                    relations.append(Relation(name=slot, source_id=obj_id, target_id=vid))
        
        # Handle __dict__
        elif hasattr(obj, "__dict__"):
            for attr_name, attr_value in vars(obj).items():
                if not attr_name.startswith('_') and not inspect.ismethod(attr_value):
                    vid = walker_func(attr_value)
                    relations.append(Relation(name=attr_name, source_id=obj_id, target_id=vid))
        
        return atom, relations


@relationalizer(priority=1)
class FallbackRelationalizer(RelationalizerBase):
    """Fallback relationalizer for objects that can't be handled by other relationalizers."""
    
    def can_handle(self, obj: Any) -> bool:
        return True  # Always accepts
    
    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = Atom(
            id=obj_id,
            type=typ,
            label=f"{typ}"
        )

        ## TODO: What about other things referenced here?

        return atom, []


# Keep old provider classes as aliases for backward compatibility
PrimitiveProvider = PrimitiveRelationalizer
DictProvider = DictRelationalizer
ListProvider = ListRelationalizer
SetProvider = SetRelationalizer
DataclassProvider = DataclassRelationalizer
GenericObjectProvider = GenericObjectRelationalizer
FallbackProvider = FallbackRelationalizer


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
                typed_tuples.append({
                    "atoms": [source_id, target_id],
                    "types": [source_type, target_type]
                })

            relations.append({
                "id": rel_name,
                "name": rel_name,
                "types": ["object", "object"],  # Default to Python's top type
                "tuples": typed_tuples
            })

        # Use the updated `build_types` function
        typs = self.build_types(self._atoms)

        return {
            "atoms": self._atoms,
            "relations": relations,
            "types": typs
        }
    
    def get_collected_decorators(self) -> Dict:
        """Get all decorators collected during the build process."""
        return self._collected_decorators
    
    
    
    def _get_id(self, obj: Any) -> str:
        """Get or create an ID for an object."""
        oid = id(obj)

        ## I wonder if primitives should have matching IDs and Labels?       

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
            self._collected_decorators["constraints"].extend(obj_decorators["constraints"])
            self._collected_decorators["directives"].extend(obj_decorators["directives"])
        except Exception as e:
            # If decorator collection fails, continue without them
            # This prevents the entire visualization from failing due to annotation issues
            pass
        
        # Find appropriate relationalizer
        relationalizer = RelationalizerRegistry.find_relationalizer(obj)
        if relationalizer is None:
            raise ValueError(f"No relationalizer found for object of type {type(obj)}")
        
        # Get atom and relations from relationalizer
        atom, relations = relationalizer.provide_atoms_and_relations(obj, self)
        
        
        # Add full type hierarchy to the atom
        type_hierarchy = [cls.__name__ for cls in inspect.getmro(type(obj))]
        atom["type"] = type_hierarchy[0] # Most specific type (first in the hierarchy)
        atom["type_hierarchy"] = type_hierarchy  # Store the full type hierarchy if needed
    
        
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
                    "meta": {
                        "builtin": most_specific_type in BUILTINTYPES
                    }
                }
            # Add the full atom details to the "atoms" list
            type_map[most_specific_type]["atoms"].append({
                "_": "atom",
                "id": atom["id"],
                "type": atom["type"]
            })

        # Convert the type_map dictionary to a list of its values
        return list(type_map.values())


# Backwards compatibility alias
CnDSerializer = CnDDataInstanceBuilder


def set_object_relationalizer(obj: Any, relationalizer: RelationalizerBase) -> Any:
    """
    Set a custom relationalizer for a specific object instance.
    
    Args:
        obj: The object to set the relationalizer for
        relationalizer: The relationalizer instance to use for this object
        
    Returns:
        The object (for chaining)
    """
    try:
        # Try to store directly on the object
        setattr(obj, OBJECT_RELATIONALIZER_ATTR, relationalizer)
    except (AttributeError, TypeError):
        # For immutable objects, store in global registry
        _OBJECT_RELATIONALIZER_REGISTRY[id(obj)] = relationalizer
    
    return obj


def object_relationalizer(relationalizer: RelationalizerBase):
    """
    Decorator to set a custom relationalizer for an object.
    
    Usage:
        my_obj = object_relationalizer(CustomRelationalizer())(my_obj)
    
    Args:
        relationalizer: The relationalizer instance to use
        
    Returns:
        Decorator function
    """
    def decorator(obj: Any) -> Any:
        return set_object_relationalizer(obj, relationalizer)
    
    return decorator


def get_object_relationalizer(obj: Any) -> Optional[RelationalizerBase]:
    """
    Get the custom relationalizer set for an object, if any.
    
    Args:
        obj: The object to check
        
    Returns:
        The custom relationalizer or None if no custom relationalizer is set
    """
    return RelationalizerRegistry._get_object_relationalizer(obj)


# Keep old provider functions as aliases for backward compatibility
def set_object_provider(obj: Any, provider: RelationalizerBase) -> Any:
    """Deprecated: Use set_object_relationalizer instead."""
    return set_object_relationalizer(obj, provider)


def object_provider(provider: RelationalizerBase):
    """Deprecated: Use object_relationalizer instead."""
    return object_relationalizer(provider)


def get_object_provider(obj: Any) -> Optional[RelationalizerBase]:
    """Deprecated: Use get_object_relationalizer instead."""
    return get_object_relationalizer(obj)

"""
CnD Data Instance Provider Architecture

This module provides a pluggable system for converting Python objects
into CnD-compatible atom/relation representations.
"""

import abc
import dataclasses
import inspect
from typing import Any, Dict, List, Tuple, Type, Optional, Protocol
import collections.abc


class DataInstanceProvider(abc.ABC):
    """Abstract base class for data instance providers."""
    
    @abc.abstractmethod
    def can_handle(self, obj: Any) -> bool:
        """Return True if this provider can handle the given object."""
        pass
    
    @abc.abstractmethod
    def provide_atoms_and_relations(self, obj: Any, walker_func) -> Tuple[Dict, List[Tuple[str, str, str]]]:
        """
        Convert object to atoms and relations.
        
        Args:
            obj: The object to convert
            walker_func: Function to recursively walk nested objects
            
        Returns:
            Tuple of (atom_dict, relations_list)
            atom_dict: {"id": str, "type": str, "label": str}
            relations_list: [(relation_name, source_id, target_id), ...]
        """
        pass


def data_provider(cls: Type = None, *, priority: int = 0):
    """
    Decorator to register a class as a data provider.
    
    Args:
        priority: Higher priority providers are tried first
    """
    def decorator(provider_cls):
        if not issubclass(provider_cls, DataInstanceProvider):
            raise TypeError("Data provider must inherit from DataInstanceProvider")
        
        # Register the provider
        DataInstanceRegistry.register(provider_cls, priority)
        return provider_cls
    
    if cls is None:
        return decorator
    else:
        return decorator(cls)


# Object-level provider storage
OBJECT_PROVIDER_ATTR = "__spytial_object_provider__"
_OBJECT_PROVIDER_REGISTRY: Dict[int, DataInstanceProvider] = {}


class DataInstanceRegistry:
    """Registry for data instance providers."""
    
    _providers: List[Tuple[int, Type[DataInstanceProvider]]] = []
    _instances: List[DataInstanceProvider] = []
    
    @classmethod
    def register(cls, provider_cls: Type[DataInstanceProvider], priority: int = 0):
        """Register a provider class with given priority."""
        cls._providers.append((priority, provider_cls))
        cls._providers.sort(key=lambda x: x[0], reverse=True)  # Higher priority first
        cls._instances = [provider_cls() for _, provider_cls in cls._providers]
    
    @classmethod
    def find_provider(cls, obj: Any) -> Optional[DataInstanceProvider]:
        """Find the first provider that can handle the given object."""
        # First check for object-specific providers
        object_provider = cls._get_object_provider(obj)
        if object_provider is not None:
            return object_provider
        
        # Then check registered class-level providers
        for provider in cls._instances:
            if provider.can_handle(obj):
                return provider
        return None
    
    @classmethod
    def _get_object_provider(cls, obj: Any) -> Optional[DataInstanceProvider]:
        """Get object-specific provider if one exists."""
        # First check if stored on object directly
        if hasattr(obj, OBJECT_PROVIDER_ATTR):
            return getattr(obj, OBJECT_PROVIDER_ATTR)
        
        # Then check global registry for objects that can't store attributes
        obj_id = id(obj)
        if obj_id in _OBJECT_PROVIDER_REGISTRY:
            return _OBJECT_PROVIDER_REGISTRY[obj_id]
        
        return None
    
    @classmethod
    def clear(cls):
        """Clear all registered providers (for testing)."""
        cls._providers.clear()
        cls._instances.clear()
        _OBJECT_PROVIDER_REGISTRY.clear()


# Built-in providers

@data_provider(priority=10)
class PrimitiveProvider(DataInstanceProvider):
    """Handles primitive types: int, float, str, bool, None."""
    
    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, (int, float, str, bool, type(None)))
    
    def provide_atoms_and_relations(self, obj: Any, walker_func) -> Tuple[Dict, List[Tuple[str, str, str]]]:
        atom = {
            "id": walker_func._get_id(obj),
            "type": type(obj).__name__,
            "label": str(obj)
        }
        return atom, []


@data_provider(priority=9)
class DictProvider(DataInstanceProvider):
    """Handles dictionary objects."""
    
    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, dict)
    
    def provide_atoms_and_relations(self, obj: Any, walker_func) -> Tuple[Dict, List[Tuple[str, str, str]]]:
        obj_id = walker_func._get_id(obj)
        atom = {
            "id": obj_id,
            "type": "dict",
            "label": f"dict{{{len(obj)}}}"
        }
        
        relations = []
        for k, v in obj.items():
            vid = walker_func(v)
            key_str = str(k) if isinstance(k, (str, int, float, bool)) else f"key_{len(relations)}"
            relations.append((key_str, obj_id, vid))
        
        return atom, relations


@data_provider(priority=8)
class ListProvider(DataInstanceProvider):
    """Handles list and tuple objects."""
    
    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, (list, tuple))
    
    def provide_atoms_and_relations(self, obj: Any, walker_func) -> Tuple[Dict, List[Tuple[str, str, str]]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = {
            "id": obj_id,
            "type": typ,
            "label": f"{typ}[{len(obj)}]"
        }
        
        relations = []
        for i, elt in enumerate(obj):
            eid = walker_func(elt)
            relations.append((str(i), obj_id, eid))
        
        return atom, relations


@data_provider(priority=8)
class SetProvider(DataInstanceProvider):
    """Handles set objects."""
    
    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, set)
    
    def provide_atoms_and_relations(self, obj: Any, walker_func) -> Tuple[Dict, List[Tuple[str, str, str]]]:
        obj_id = walker_func._get_id(obj)
        atom = {
            "id": obj_id,
            "type": "set",
            "label": f"set[{len(obj)}]"
        }
        
        relations = []
        for element in obj:
            element_id = walker_func(element)
            relations.append(("contains", obj_id, element_id))
        
        return atom, relations


@data_provider(priority=7)
class DataclassProvider(DataInstanceProvider):
    """Handles dataclass objects."""
    
    def can_handle(self, obj: Any) -> bool:
        return dataclasses.is_dataclass(obj)
    
    def provide_atoms_and_relations(self, obj: Any, walker_func) -> Tuple[Dict, List[Tuple[str, str, str]]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = {
            "id": obj_id,
            "type": typ,
            "label": f"{typ}"
        }
        
        relations = []
        for field in dataclasses.fields(obj):
            if not field.name.startswith('_'):
                value = getattr(obj, field.name)
                vid = walker_func(value)
                relations.append((field.name, obj_id, vid))
        
        return atom, relations


@data_provider(priority=5)
class GenericObjectProvider(DataInstanceProvider):
    """Handles generic objects with __dict__ or __slots__."""
    
    def can_handle(self, obj: Any) -> bool:
        return hasattr(obj, "__dict__") or hasattr(obj, "__slots__")
    
    def provide_atoms_and_relations(self, obj: Any, walker_func) -> Tuple[Dict, List[Tuple[str, str, str]]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = {
            "id": obj_id,
            "type": typ,
            "label": f"{typ}"
        }
        
        relations = []
        
        # Handle __slots__
        if hasattr(obj, "__slots__"):
            for slot in obj.__slots__:
                if hasattr(obj, slot):
                    value = getattr(obj, slot)
                    vid = walker_func(value)
                    relations.append((slot, obj_id, vid))
        
        # Handle __dict__
        elif hasattr(obj, "__dict__"):
            for attr_name, attr_value in vars(obj).items():
                if not attr_name.startswith('_') and not inspect.ismethod(attr_value):
                    vid = walker_func(attr_value)
                    relations.append((attr_name, obj_id, vid))
        
        return atom, relations


@data_provider(priority=1)
class FallbackProvider(DataInstanceProvider):
    """Fallback provider for objects that can't be handled by other providers."""
    
    def can_handle(self, obj: Any) -> bool:
        return True  # Always accepts
    
    def provide_atoms_and_relations(self, obj: Any, walker_func) -> Tuple[Dict, List[Tuple[str, str, str]]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        atom = {
            "id": obj_id,
            "type": typ,
            "label": f"{typ}"
        }

        ## TODO: What about other things referenced here?

        return atom, []


class CnDDataInstanceBuilder:
    """Main builder that composes providers to build data instances."""
    
    def __init__(self):
        self._seen = {}
        self._atoms = []
        self._rels = {}
        self._id_counter = 0
    
    def build_instance(self, obj: Any) -> Dict:
        """Build a complete data instance from an object."""
        self._seen.clear()
        self._atoms.clear()
        self._rels.clear()
        self._id_counter = 0

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
    
    
    
    def _get_id(self, obj: Any) -> str:
        """Get or create an ID for an object."""
        oid = id(obj)
       

        if oid not in self._seen:
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
        
        # Find appropriate provider
        provider = DataInstanceRegistry.find_provider(obj)
        if provider is None:
            raise ValueError(f"No provider found for object of type {type(obj)}")
        
        # Get atom and relations from provider
        atom, relations = provider.provide_atoms_and_relations(obj, self)
        
        
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


def set_object_provider(obj: Any, provider: DataInstanceProvider) -> Any:
    """
    Set a custom provider for a specific object instance.
    
    Args:
        obj: The object to set the provider for
        provider: The provider instance to use for this object
        
    Returns:
        The object (for chaining)
    """
    try:
        # Try to store directly on the object
        setattr(obj, OBJECT_PROVIDER_ATTR, provider)
    except (AttributeError, TypeError):
        # For immutable objects, store in global registry
        _OBJECT_PROVIDER_REGISTRY[id(obj)] = provider
    
    return obj


def object_provider(provider: DataInstanceProvider):
    """
    Decorator to set a custom provider for an object.
    
    Usage:
        my_obj = object_provider(CustomProvider())(my_obj)
    
    Args:
        provider: The provider instance to use
        
    Returns:
        Decorator function
    """
    def decorator(obj: Any) -> Any:
        return set_object_provider(obj, provider)
    
    return decorator


def get_object_provider(obj: Any) -> Optional[DataInstanceProvider]:
    """
    Get the custom provider set for an object, if any.
    
    Args:
        obj: The object to check
        
    Returns:
        The custom provider or None if no custom provider is set
    """
    return DataInstanceRegistry._get_object_provider(obj)

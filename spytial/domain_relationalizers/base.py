"""
Base classes for the relationalizer system.

This module contains the core abstract classes and data structures
that form the foundation of the relationalizer architecture.
"""

import abc
import dataclasses
import inspect
from typing import Any, Dict, List, Tuple, Optional


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
        return {"id": self.id, "type": self.type, "label": self.label}


@dataclasses.dataclass
class Relation:
    """
    Represents a relation between atoms in the spatial visualization.

    A relation can connect two or more atoms through a named relationship.
    Binary relations are just n-ary relations where n=2.
    """

    name: str
    atoms: List[str]

    def __post_init__(self):
        """Validate that relation connects at least 2 atoms."""
        if len(self.atoms) < 2:
            raise ValueError("Relations must connect at least 2 atoms")

    def to_tuple(self) -> Tuple[str, ...]:
        """Convert relation to tuple format.

        Returns:
            Tuple where first element is the relation name,
            followed by all atom IDs: (name, atom1, atom2, ...)
        """
        return (self.name, *self.atoms)


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
    def relationalize(
        self, obj: Any, walker_func: Any
    ) -> Tuple[List[Atom], List[Relation]]:
        """
        Convert object to atoms and relations using structured types.

        Args:
            obj: The object to convert
            walker_func: Function to recursively walk nested objects

        Returns:
            Tuple of (atoms_list, relations_list)
            atoms_list: List of Atom instances representing the object
            relations_list: List of Relation instances connecting this object to others
        """
        pass

    def _try_get_variable_name(self, obj: Any, caller_namespace: Optional[Dict] = None) -> Optional[str]:
        """
        Attempt to find the variable name for an object.
        
        Args:
            obj: The object to find a name for
            caller_namespace: Optional namespace dict from the original caller (diagram/evaluate)
        
        Returns:
            Variable name if found, None otherwise
        
        This is a shared helper method that subclasses can use for improved labeling.
        """
        # Names used internally by spytial that should not be returned as variable names
        internal_names = {'obj', 'value', 'self', 'walker_func', 'builder', 'instance',
                          'item', 'element', 'child', 'node', 'result', 'data', 'target', 'elt'}
        
        try:
            # First try the provided caller namespace (most reliable)
            if caller_namespace:
                for name, value in caller_namespace.items():
                    if (value is obj and not name.startswith('_') 
                        and name.isidentifier() and name not in internal_names):
                        return name
            
            # Fallback: walk up the call stack to find user's frame
            # This is less reliable but better than nothing
            frame = inspect.currentframe()
            # Skip up several frames to get past the serialization internals
            # Typical stack: this method -> relationalize -> _walk -> build_instance -> diagram
            for _ in range(10):  # Look deeper in the stack
                if frame is None:
                    break
                frame = frame.f_back
                
                # Skip frames that are clearly internal (have 'obj', 'value', 'walker_func', etc)
                if frame and frame.f_locals:
                    # Check if this frame looks like user code (has varied variable names)
                    local_vars = list(frame.f_locals.keys())
                    # Skip frames dominated by generic names
                    if len(local_vars) > len(internal_names.intersection(local_vars)):
                        # This might be user code, check for the object
                        for name, value in frame.f_locals.items():
                            if (value is obj and not name.startswith('_') 
                                and name.isidentifier() and name not in internal_names):
                                return name
            
            return None
        except Exception:
            # Frame inspection can fail in various scenarios - silently fall back
            return None

    def _make_label_with_fallback(self, obj: Any, typ: str, caller_namespace: Optional[Dict] = None, atom_id: Optional[str] = None) -> str:
        """
        Create a label with variable name if available, otherwise use atom ID.
        
        Priority: variable name > atom_id
        
        Args:
            obj: The object to label
            typ: The type name to use in the label
            caller_namespace: Optional namespace dict from the original caller
            atom_id: Optional atom ID to use as fallback label
            
        Returns:
            A label string like "varname" or the atom ID
        """
        # Try to get variable name
        var_name = self._try_get_variable_name(obj, caller_namespace)
        if var_name:
            return var_name
        
        # Fallback: use the atom ID if provided, otherwise type name
        return atom_id if atom_id else typ

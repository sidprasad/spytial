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
    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
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

    def _try_get_variable_name(self, obj: Any) -> Optional[str]:
        """
        Attempt to find the variable name from the calling frame.
        Returns None if unable to determine.
        
        This is a shared helper method that subclasses can use for improved labeling.
        """
        try:
            # Walk up the call stack to find the frame where the object was created
            frame = inspect.currentframe()
            # Skip up through: this method -> relationalize -> walker_func -> diagram/user code
            for _ in range(5):
                if frame is None:
                    break
                frame = frame.f_back
            
            if frame is None:
                return None
            
            # Check local and global variables in the caller's frame
            for name, value in list(frame.f_locals.items()) + list(frame.f_globals.items()):
                if value is obj and not name.startswith('_') and name.isidentifier():
                    return name
            
            return None
        except Exception:
            # Frame inspection can fail in various scenarios - silently fall back
            return None

    def _make_label_with_fallback(self, obj: Any, typ: str) -> str:
        """
        Create a label with variable name if available, otherwise use object ID.
        
        Priority: variable name > type_shortid
        
        Args:
            obj: The object to label
            typ: The type name to use in the label
            
        Returns:
            A label string like "Type:varname" or "Type_a3f2"
        """
        # Try to get variable name from frame inspection
        var_name = self._try_get_variable_name(obj)
        if var_name:
            return f"{typ}:{var_name}"
        
        # Fallback: use last 4 hex digits of object ID
        short_id = hex(id(obj))[-4:]
        return f"{typ}_{short_id}"

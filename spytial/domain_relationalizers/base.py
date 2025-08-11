"""
Base classes for the relationalizer system.

This module contains the core abstract classes and data structures
that form the foundation of the relationalizer architecture.
"""

import abc
import dataclasses
from typing import Any, Dict, List, Tuple


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

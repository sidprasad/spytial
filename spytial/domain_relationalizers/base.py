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

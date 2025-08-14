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

    @classmethod
    def from_atoms(cls, name: str, atoms: List[str]) -> "Relation":
        """Create an n-ary relation from a list of atom IDs.

        Args:
            name: The relation name
            atoms: List of atom IDs to connect (must have at least 2)

        Returns:
            Relation instance connecting the specified atoms
        """
        return cls(name=name, atoms=atoms)

    @classmethod
    def binary(cls, name: str, source_id: str, target_id: str) -> "Relation":
        """Create a binary relation (convenience method for clarity).

        Args:
            name: The relation name
            source_id: Source atom ID
            target_id: Target atom ID

        Returns:
            Binary relation instance
        """
        return cls(name=name, atoms=[source_id, target_id])

    def is_binary(self) -> bool:
        """Check if this is a binary relation (exactly 2 atoms)."""
        return len(self.atoms) == 2

    def arity(self) -> int:
        """Return the arity (number of atoms) of this relation."""
        return len(self.atoms)


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

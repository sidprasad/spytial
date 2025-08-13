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
    For backward compatibility, binary relations can be created using source_id and target_id.
    For n-ary relations, use the atoms parameter or from_atoms class method.
    """

    name: str
    source_id: str = None
    target_id: str = None
    atoms: List[str] = None

    def __post_init__(self):
        """Ensure atoms list is populated based on source_id/target_id or atoms parameter."""
        if self.atoms is None:
            if self.source_id is not None and self.target_id is not None:
                # Binary relation specified via source_id/target_id
                self.atoms = [self.source_id, self.target_id]
            else:
                raise ValueError(
                    "Either (source_id, target_id) or atoms must be provided"
                )
        else:
            # N-ary relation specified via atoms
            if len(self.atoms) < 2:
                raise ValueError("Relations must connect at least 2 atoms")
            # For backward compatibility, set source_id/target_id for binary relations
            if (
                len(self.atoms) == 2
                and self.source_id is None
                and self.target_id is None
            ):
                self.source_id = self.atoms[0]
                self.target_id = self.atoms[1]

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
        return cls(name=name, source_id=source_id, target_id=target_id)

    def to_tuple(self) -> Tuple[str, str, str]:
        """Convert relation to tuple format expected by CnD (for binary relations only).

        For backward compatibility with existing code that expects binary tuples.
        Raises ValueError for n-ary relations with more than 2 atoms.
        """
        if len(self.atoms) != 2:
            raise ValueError(
                f"to_tuple() only supports binary relations, but this relation has {len(self.atoms)} atoms"
            )
        return (self.name, self.atoms[0], self.atoms[1])

    def to_atoms_tuple(self) -> Tuple[str, List[str]]:
        """Convert relation to (name, atoms_list) format for n-ary relations."""
        return (self.name, self.atoms)

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

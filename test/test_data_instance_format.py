"""
Tests that build_instance() output matches the spytial-core v2.2.3 IJsonDataInstance format.

See spytial-core/docs/JSON_DATA_INSTANCE.md for the canonical spec.
"""

import pytest
from dataclasses import dataclass
from spytial import CnDDataInstanceBuilder


@dataclass
class Node:
    val: int
    label: str


@dataclass
class Tree:
    root: Node
    left: Node
    right: Node


def _build(obj, **kwargs):
    builder = CnDDataInstanceBuilder()
    return builder.build_instance(obj, **kwargs)


# -- atoms -------------------------------------------------------------------

class TestAtomFormat:
    def test_atoms_have_required_fields(self):
        result = _build(Node(val=1, label="x"))
        for atom in result["atoms"]:
            assert "id" in atom
            assert "type" in atom
            assert "label" in atom

    def test_atoms_have_no_internal_fields(self):
        result = _build(Node(val=1, label="x"))
        for atom in result["atoms"]:
            assert "type_hierarchy" not in atom, "type_hierarchy is internal and must be stripped"
            assert "_" not in atom, "legacy _ marker must not be present"


# -- types --------------------------------------------------------------------

class TestTypeFormat:
    def test_types_have_required_fields(self):
        result = _build(Node(val=1, label="x"))
        for typ in result["types"]:
            assert "id" in typ
            assert "types" in typ and isinstance(typ["types"], list)
            assert "atoms" in typ and isinstance(typ["atoms"], list)
            assert "isBuiltin" in typ and isinstance(typ["isBuiltin"], bool)

    def test_types_have_no_legacy_fields(self):
        result = _build(Node(val=1, label="x"))
        for typ in result["types"]:
            assert "_" not in typ, "legacy _ marker must not be present on types"
            assert "meta" not in typ, "legacy meta wrapper must not be present"

    def test_type_atoms_have_label(self):
        result = _build(Node(val=1, label="x"))
        for typ in result["types"]:
            for atom in typ["atoms"]:
                assert "label" in atom, "type atoms must include label"
                assert "_" not in atom, "legacy _ marker must not be present on type atoms"

    def test_builtin_types_flagged_correctly(self):
        result = _build(Node(val=1, label="x"))
        type_map = {t["id"]: t for t in result["types"]}
        assert type_map["int"]["isBuiltin"] is True
        assert type_map["str"]["isBuiltin"] is True
        assert type_map["Node"]["isBuiltin"] is False

    def test_type_hierarchy_present(self):
        result = _build(Node(val=1, label="x"))
        type_map = {t["id"]: t for t in result["types"]}
        # Every type hierarchy should start with the type itself
        for typ in result["types"]:
            assert typ["types"][0] == typ["id"]


# -- relations ----------------------------------------------------------------

class TestRelationFormat:
    def test_relations_use_tuples_format(self):
        result = _build(Tree(root=Node(1, "a"), left=Node(2, "b"), right=Node(3, "c")))
        for rel in result["relations"]:
            assert "id" in rel
            assert "name" in rel
            assert "types" in rel and isinstance(rel["types"], list)
            assert "tuples" in rel and isinstance(rel["tuples"], list)
            # Must NOT have old binary format fields
            assert "source" not in rel
            assert "target" not in rel

    def test_relation_tuples_have_atoms_and_types(self):
        result = _build(Tree(root=Node(1, "a"), left=Node(2, "b"), right=Node(3, "c")))
        atom_ids = {a["id"] for a in result["atoms"]}
        for rel in result["relations"]:
            for tup in rel["tuples"]:
                assert "atoms" in tup and isinstance(tup["atoms"], list)
                assert "types" in tup and isinstance(tup["types"], list)
                assert len(tup["atoms"]) == len(tup["types"])
                # All atom refs must exist
                for atom_id in tup["atoms"]:
                    assert atom_id in atom_ids, f"tuple references unknown atom {atom_id}"


# -- full round-trip ----------------------------------------------------------

class TestFullInstance:
    def test_instance_has_required_top_level_keys(self):
        result = _build(Node(val=1, label="x"))
        assert "atoms" in result
        assert "relations" in result
        assert "types" in result

    def test_type_atoms_are_subset_of_top_level_atoms(self):
        """Every atom referenced in a type entry must exist in the top-level atoms list."""
        result = _build(Tree(root=Node(1, "a"), left=Node(2, "b"), right=Node(3, "c")))
        top_level_ids = {a["id"] for a in result["atoms"]}
        for typ in result["types"]:
            for atom in typ["atoms"]:
                assert atom["id"] in top_level_ids

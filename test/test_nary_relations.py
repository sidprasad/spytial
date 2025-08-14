#!/usr/bin/env python3
"""
Test file for n-ary relations support.

This file tests:
- N-ary Relation class functionality
- Backward compatibility with binary relations
- Integration with relationalizers and provider system
- Visualization of n-ary relations
"""

import pytest
from typing import Any, List, Tuple
from spytial import (
    RelationalizerBase,
    relationalizer,
    Atom,
    Relation,
    CnDDataInstanceBuilder,
    diagram,
)
from spytial.provider_system import RelationalizerRegistry


def test_relation_class_backward_compatibility():
    """Test that the Relation class works with binary relations as n-ary with n=2."""

    # Test binary relation creation using binary() convenience method
    rel = Relation.binary("follows", "user1", "user2")
    assert rel.name == "follows"
    assert rel.atoms == ["user1", "user2"]
    assert rel.is_binary()
    assert rel.arity() == 2


def test_relation_class_nary_functionality():
    """Test n-ary relation functionality."""

    # Test ternary relation
    rel = Relation.from_atoms("meeting", ["person1", "person2", "location"])
    assert rel.name == "meeting"
    assert rel.atoms == ["person1", "person2", "location"]
    assert not rel.is_binary()
    assert rel.arity() == 3


def test_relation_class_binary_via_atoms():
    """Test creating binary relations via atoms parameter."""

    rel = Relation.from_atoms("connected", ["node1", "node2"])
    assert rel.name == "connected"
    assert rel.atoms == ["node1", "node2"]
    assert rel.is_binary()
    assert rel.arity() == 2


def test_relation_class_validation():
    """Test relation validation."""

    # Test that relations must have at least 2 atoms
    with pytest.raises(ValueError, match="Relations must connect at least 2 atoms"):
        Relation.from_atoms("invalid", ["single_atom"])

    with pytest.raises(ValueError, match="Relations must connect at least 2 atoms"):
        Relation.from_atoms("invalid", [])

    # Test that atoms must be provided
    with pytest.raises(TypeError):
        Relation(name="invalid")


def test_relation_convenience_methods():
    """Test convenience methods for relation creation."""

    # Test binary() class method
    rel = Relation.binary("likes", "user1", "user2")
    assert rel.name == "likes"
    assert rel.atoms == ["user1", "user2"]
    assert rel.is_binary()


def test_nary_relationalizer():
    """Test a custom relationalizer that creates n-ary relations."""

    # Save current state
    original_relationalizers = RelationalizerRegistry._relationalizers.copy()
    original_instances = RelationalizerRegistry._instances.copy()

    try:

        @relationalizer(priority=100)
        class MeetingRelationalizer(RelationalizerBase):
            """Custom relationalizer that creates ternary relations for meetings."""

            def can_handle(self, obj: Any) -> bool:
                return (
                    isinstance(obj, dict)
                    and "meeting" in obj
                    and "participants" in obj
                    and "location" in obj
                )

            def relationalize(
                self, obj: Any, walker_func
            ) -> Tuple[List[Atom], List[Relation]]:
                obj_id = walker_func._get_id(obj)
                atom = Atom(
                    id=obj_id, type="meeting", label=f"Meeting: {obj['meeting']}"
                )

                # Create n-ary relation connecting meeting with all participants and location
                participant_ids = [walker_func(p) for p in obj["participants"]]
                location_id = walker_func(obj["location"])

                # Create ternary relation: meeting -> participant1 -> participant2 -> location
                all_ids = [obj_id] + participant_ids + [location_id]
                nary_relation = Relation.from_atoms("involves", all_ids)

                return [atom], [nary_relation]

        # Test the relationalizer
        meeting_data = {
            "meeting": "Project Planning",
            "participants": ["Alice", "Bob"],
            "location": "Conference Room A",
        }

        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(meeting_data)

        # Check that we have the expected structure
        assert len(data_instance["atoms"]) >= 4  # meeting + 2 participants + location
        assert len(data_instance["relations"]) >= 1

        # Find the n-ary relation
        involves_relation = None
        for rel in data_instance["relations"]:
            if rel["name"] == "involves":
                involves_relation = rel
                break

        assert involves_relation is not None
        assert len(involves_relation["tuples"]) == 1

        # The tuple should have 4 atoms (meeting + 2 participants + location)
        tuple_data = involves_relation["tuples"][0]
        assert len(tuple_data["atoms"]) == 4
        assert len(tuple_data["types"]) == 4

    finally:
        # Restore original state
        RelationalizerRegistry._relationalizers = original_relationalizers
        RelationalizerRegistry._instances = original_instances


def test_mixed_binary_and_nary_relations():
    """Test that binary and n-ary relations can coexist."""

    # Save current state
    original_relationalizers = RelationalizerRegistry._relationalizers.copy()
    original_instances = RelationalizerRegistry._instances.copy()

    try:

        @relationalizer(priority=100)
        class MixedRelationRelationalizer(RelationalizerBase):
            """Relationalizer that creates both binary and n-ary relations."""

            def can_handle(self, obj: Any) -> bool:
                return isinstance(obj, dict) and "mixed_test" in obj

            def relationalize(
                self, obj: Any, walker_func
            ) -> Tuple[List[Atom], List[Relation]]:
                obj_id = walker_func._get_id(obj)
                atom = Atom(id=obj_id, type="mixed", label="Mixed Relations")

                # Create some child atoms
                child1_id = walker_func("child1")
                child2_id = walker_func("child2")
                child3_id = walker_func("child3")

                relations = [
                    # Binary relation
                    Relation.binary("binary_rel", obj_id, child1_id),
                    # Ternary relation
                    Relation.from_atoms("ternary_rel", [obj_id, child2_id, child3_id]),
                    # Quaternary relation
                    Relation.from_atoms(
                        "quaternary_rel", [obj_id, child1_id, child2_id, child3_id]
                    ),
                ]

                return [atom], relations

        test_data = {"mixed_test": True}
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(test_data)

        # Should have multiple relations with different arities
        relation_names = [rel["name"] for rel in data_instance["relations"]]
        assert "binary_rel" in relation_names
        assert "ternary_rel" in relation_names
        assert "quaternary_rel" in relation_names

        # Check specific relation arities
        for rel in data_instance["relations"]:
            if rel["name"] == "binary_rel":
                assert len(rel["tuples"][0]["atoms"]) == 2
            elif rel["name"] == "ternary_rel":
                assert len(rel["tuples"][0]["atoms"]) == 3
            elif rel["name"] == "quaternary_rel":
                assert len(rel["tuples"][0]["atoms"]) == 4

    finally:
        # Restore original state
        RelationalizerRegistry._relationalizers = original_relationalizers
        RelationalizerRegistry._instances = original_instances


def test_nary_relations_visualization():
    """Test that n-ary relations can be visualized."""

    # Save current state
    original_relationalizers = RelationalizerRegistry._relationalizers.copy()
    original_instances = RelationalizerRegistry._instances.copy()

    try:

        @relationalizer(priority=100)
        class SimpleNAryRelationalizer(RelationalizerBase):
            """Simple relationalizer for testing n-ary visualization."""

            def can_handle(self, obj: Any) -> bool:
                return (
                    isinstance(obj, tuple) and len(obj) >= 3 and obj[0] == "nary_test"
                )

            def relationalize(
                self, obj: Any, walker_func
            ) -> Tuple[List[Atom], List[Relation]]:
                obj_id = walker_func._get_id(obj)
                atom = Atom(
                    id=obj_id,
                    type="nary_test",
                    label=f"N-ary Test ({len(obj)} elements)",
                )

                # Create child atoms for each element (skip the first 'nary_test' marker)
                child_ids = [walker_func(element) for element in obj[1:]]

                # Create n-ary relation connecting all elements
                all_ids = [obj_id] + child_ids
                nary_relation = Relation.from_atoms("connects_all", all_ids)

                return [atom], [nary_relation]

        # Test with different arities
        test_cases = [
            ("nary_test", "A", "B", "C"),  # Quaternary (4 atoms)
            ("nary_test", "X", "Y", "Z", "W", "V"),  # 6-ary (6 atoms)
        ]

        for test_data in test_cases:
            # Should be able to create visualization without errors
            result = diagram(test_data, method="file", auto_open=False)
            assert result.endswith(".html")

            # Check the underlying data structure
            builder = CnDDataInstanceBuilder()
            data_instance = builder.build_instance(test_data)

            # Should have one relation with the expected arity
            connects_all_rel = None
            for rel in data_instance["relations"]:
                if rel["name"] == "connects_all":
                    connects_all_rel = rel
                    break

            assert connects_all_rel is not None
            expected_arity = len(test_data)  # Including the root atom
            assert len(connects_all_rel["tuples"][0]["atoms"]) == expected_arity

    finally:
        # Restore original state
        RelationalizerRegistry._relationalizers = original_relationalizers
        RelationalizerRegistry._instances = original_instances


def test_builtin_relationalizers_still_work():
    """Ensure built-in relationalizers still work after n-ary relation changes."""

    # Test various data structures
    test_cases = [
        42,  # Primitive
        "hello world",  # String
        [1, 2, 3, 4],  # List
        {"a": 1, "b": 2},  # Dict
        {1, 2, 3},  # Set
        {"nested": {"deep": [1, 2, 3]}},  # Nested structure
    ]

    for test_data in test_cases:
        # Should be able to visualize without errors
        result = diagram(test_data, method="file", auto_open=False)
        assert result.endswith(".html")

        # Should be able to build data instance
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(test_data)
        assert "atoms" in data_instance
        assert "relations" in data_instance
        assert "types" in data_instance


if __name__ == "__main__":
    print("Testing N-ary Relations Support")

    # Run tests manually since pytest might not be available everywhere
    test_functions = [
        test_relation_class_backward_compatibility,
        test_relation_class_nary_functionality,
        test_relation_class_binary_via_atoms,
        test_relation_class_validation,
        test_relation_convenience_methods,
        test_nary_relationalizer,
        test_mixed_binary_and_nary_relations,
        test_nary_relations_visualization,
        test_builtin_relationalizers_still_work,
    ]

    passed = 0
    failed = 0

    for test_func in test_functions:
        try:
            test_func()
            print(f"✓ {test_func.__name__}")
            passed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__}: {e}")
            failed += 1

    print(f"\n🎉 N-ary relations tests completed!")
    print(f"Passed: {passed}, Failed: {failed}")

    if failed == 0:
        print("All tests passed! N-ary relations are working correctly.")
    else:
        print("Some tests failed. Please check the implementation.")

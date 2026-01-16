"""
Test that class-level decorators are deduplicated in generated CnD specs
to avoid redundant YAML rules.
"""

import spytial
from spytial.provider_system import CnDDataInstanceBuilder
from spytial.annotations import serialize_to_yaml_string


def test_class_decorators_not_duplicated():
    """Test that class decorators are collected only once, not per instance."""

    @spytial.orientation(selector="children", directions=["below"])
    @spytial.atomColor(selector="self", value="blue")
    class Node:
        def __init__(self, value, children=None):
            self.value = value
            self.children = children or []

    # Create multiple instances of the same class
    root = Node(
        "root",
        [
            Node("child1", [Node("grandchild1"), Node("grandchild2")]),
            Node("child2", [Node("grandchild3")]),
            Node("child3"),
        ],
    )

    # Build data instance
    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(root)
    decorators = builder.get_collected_decorators()

    # Should have exactly 1 of each decorator, not 7 (one per instance)
    assert (
        len(decorators["constraints"]) == 1
    ), f"Expected 1 constraint, got {len(decorators['constraints'])}"
    assert (
        len(decorators["directives"]) == 1
    ), f"Expected 1 directive, got {len(decorators['directives'])}"

    # Verify the decorator content is correct
    assert decorators["constraints"][0] == {
        "orientation": {"selector": "children", "directions": ["below"]}
    }
    assert decorators["directives"][0] == {
        "atomColor": {"selector": "self", "value": "blue"}
    }


def test_different_classes_contribute_unique_decorators():
    """Test that different classes each contribute their decorators once."""

    @spytial.orientation(selector="children", directions=["below"])
    @spytial.atomColor(selector="self", value="blue")
    class Node:
        def __init__(self, value, children=None):
            self.value = value
            self.children = children or []

    @spytial.orientation(selector="items", directions=["horizontal"])
    @spytial.atomColor(selector="self", value="red")
    class Leaf:
        def __init__(self, value, items=None):
            self.value = value
            self.items = items or []

    # Create structure with both classes
    root = Node(
        "root", [Node("child1"), Leaf("leaf1", [Leaf("leaf2")]), Node("child2")]
    )

    # Build data instance
    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(root)
    decorators = builder.get_collected_decorators()

    # Should have 2 constraints (one per class) and 2 directives (one per class)
    assert (
        len(decorators["constraints"]) == 2
    ), f"Expected 2 constraints, got {len(decorators['constraints'])}"
    assert (
        len(decorators["directives"]) == 2
    ), f"Expected 2 directives, got {len(decorators['directives'])}"


def test_object_annotations_preserved_not_deduplicated():
    """Test that object-level annotations are preserved (not deduplicated)."""

    @spytial.orientation(selector="children", directions=["below"])
    class Node:
        def __init__(self, value, children=None):
            self.value = value
            self.children = children or []

    # Create nodes
    root = Node("root", [Node("child1"), Node("child2")])

    # Add object-level annotations to specific nodes
    spytial.annotate_atomColor(root, selector="self", value="red")
    spytial.annotate_atomColor(root.children[0], selector="self", value="blue")

    # Build data instance
    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(root)
    decorators = builder.get_collected_decorators()

    # Should have 1 class-level constraint and 2 object-level directives
    assert (
        len(decorators["constraints"]) == 1
    ), f"Expected 1 constraint, got {len(decorators['constraints'])}"
    assert (
        len(decorators["directives"]) == 2
    ), f"Expected 2 directives, got {len(decorators['directives'])}"

    # Verify object-level annotations have unique selectors
    directive_selectors = [d["atomColor"]["selector"] for d in decorators["directives"]]
    assert len(directive_selectors) == 2
    assert len(set(directive_selectors)) == 2, "Object-level selectors should be unique"


def test_yaml_size_reduction():
    """Test that YAML output is significantly reduced with deduplication."""

    @spytial.orientation(selector="children", directions=["below"])
    @spytial.atomColor(selector="self", value="blue")
    @spytial.group(field="children", groupOn=0, addToGroup=1)
    class Node:
        def __init__(self, value, children=None):
            self.value = value
            self.children = children or []

    # Create a structure with many instances
    root = Node(
        "root",
        [
            Node("child1", [Node("g1"), Node("g2"), Node("g3")]),
            Node("child2", [Node("g4"), Node("g5")]),
            Node("child3", [Node("g6"), Node("g7"), Node("g8")]),
        ],
    )

    # Build data instance
    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(root)
    decorators = builder.get_collected_decorators()
    yaml_spec = serialize_to_yaml_string(decorators)

    # Should have exactly 1 of each decorator type (not 12 - one per instance)
    assert len(decorators["constraints"]) == 2  # orientation + group
    assert len(decorators["directives"]) == 1  # atomColor

    # YAML should be relatively small (< 250 chars)
    # Without deduplication, it would be ~1200+ chars
    assert (
        len(yaml_spec) < 250
    ), f"YAML spec too large ({len(yaml_spec)} chars), deduplication may not be working"


def test_inheritance_with_deduplication():
    """Test that inherited decorators are properly deduplicated."""

    @spytial.orientation(selector="children", directions=["below"])
    class Parent:
        def __init__(self, value, children=None):
            self.value = value
            self.children = children or []

    @spytial.atomColor(selector="self", value="blue")
    class Child(Parent):
        pass

    # Create instances of both classes
    root = Child("root", [Child("child1"), Parent("parent1", [Parent("parent2")])])

    # Build data instance
    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(root)
    decorators = builder.get_collected_decorators()

    # Should have 1 constraint (inherited orientation) and 1 directive (child's atomColor)
    # Both Parent and Child classes contribute, but each only once
    assert len(decorators["constraints"]) == 1
    assert len(decorators["directives"]) == 1

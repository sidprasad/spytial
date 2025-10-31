"""
Tests for CnD spec deduplication functionality.

This module tests that redundant constraints and directives are removed
from the generated CnD specifications, addressing the issue of bloated
YAML specs when multiple instances of the same class are visualized.
"""

import re
import pytest
import spytial
from spytial.provider_system import CnDDataInstanceBuilder
from spytial.annotations import orientation, atomColor, group


def test_class_decorator_deduplication():
    """Test that class-level decorators are deduplicated across multiple instances."""

    @orientation(selector="children", directions=["below"])
    @atomColor(selector="self", value="red")
    class Node:
        def __init__(self, value, children=None):
            self.value = value
            self.children = children or []

    # Create a tree with multiple Node instances
    root = Node(
        "root",
        [
            Node("child1", [Node("grandchild1"), Node("grandchild2")]),
            Node("child2"),
            Node("child3", [Node("grandchild3")]),
        ],
    )

    # Build the data instance
    builder = CnDDataInstanceBuilder()
    builder.build_instance(root)
    collected_decorators = builder.get_collected_decorators()

    # Should only have 1 of each decorator, not 7 (one per Node instance)
    assert (
        len(collected_decorators["constraints"]) == 1
    ), f"Expected 1 unique constraint, got {len(collected_decorators['constraints'])}"
    assert (
        len(collected_decorators["directives"]) == 1
    ), f"Expected 1 unique directive, got {len(collected_decorators['directives'])}"

    # Verify the decorator content is correct
    assert (
        collected_decorators["constraints"][0]["orientation"]["selector"] == "children"
    )
    assert collected_decorators["constraints"][0]["orientation"]["directions"] == [
        "below"
    ]
    assert collected_decorators["directives"][0]["atomColor"]["selector"] == "self"
    assert collected_decorators["directives"][0]["atomColor"]["value"] == "red"


def test_mixed_decorators_deduplication():
    """Test deduplication with a mix of class-level and object-level decorators."""

    @orientation(selector="items", directions=["horizontal"])
    class Container:
        def __init__(self, items):
            self.items = items

    # Create multiple containers
    container1 = Container([1, 2, 3])
    container2 = Container([4, 5, 6])

    # Add object-level annotation to both (same annotation)
    # Note: 'self' gets converted to unique object IDs, so these will be different
    spytial.annotate_atomColor(container1, selector="self", value="blue")
    spytial.annotate_atomColor(container2, selector="self", value="blue")

    # Build from a list containing both
    data = [container1, container2]
    builder = CnDDataInstanceBuilder()
    builder.build_instance(data)
    collected_decorators = builder.get_collected_decorators()

    # Should have 1 orientation constraint
    # Object-level 'self' selectors get converted to unique IDs, so we get 2 directives
    assert len(collected_decorators["constraints"]) == 1
    assert len(collected_decorators["directives"]) == 2

    # Verify both have the same color (blue) but different selectors
    colors = [d["atomColor"]["value"] for d in collected_decorators["directives"]]
    assert all(c == "blue" for c in colors)


def test_different_decorators_not_deduplicated():
    """Test that different decorators are NOT deduplicated."""

    @orientation(selector="items", directions=["horizontal"])
    class Container:
        def __init__(self, items):
            self.items = items

    # Create containers with different object-level decorators
    container1 = Container([1, 2, 3])
    container2 = Container([4, 5, 6])

    # Add different object-level annotations
    spytial.annotate_atomColor(container1, selector="self", value="blue")
    spytial.annotate_atomColor(
        container2, selector="self", value="red"
    )  # Different color

    # Build from a list containing both
    data = [container1, container2]
    builder = CnDDataInstanceBuilder()
    builder.build_instance(data)
    collected_decorators = builder.get_collected_decorators()

    # Should have 1 orientation constraint and 2 different atomColor directives
    assert len(collected_decorators["constraints"]) == 1
    assert len(collected_decorators["directives"]) == 2

    # Verify both colors are present
    colors = [d["atomColor"]["value"] for d in collected_decorators["directives"]]
    assert "blue" in colors
    assert "red" in colors


def test_empty_decorators():
    """Test that deduplication works with no decorators."""

    class SimpleClass:
        def __init__(self, value):
            self.value = value

    obj = SimpleClass(42)

    builder = CnDDataInstanceBuilder()
    builder.build_instance(obj)
    collected_decorators = builder.get_collected_decorators()

    # Should be empty
    assert len(collected_decorators["constraints"]) == 0
    assert len(collected_decorators["directives"]) == 0


def test_deduplication_preserves_order():
    """Test that deduplication preserves the order of first occurrence."""

    @orientation(selector="items", directions=["horizontal"])
    @group(field="items", groupOn=0, addToGroup=1)
    @atomColor(selector="self", value="green")
    class Container:
        def __init__(self, items):
            self.items = items

    # Create multiple containers
    containers = [Container([i]) for i in range(5)]

    builder = CnDDataInstanceBuilder()
    builder.build_instance(containers)
    collected_decorators = builder.get_collected_decorators()

    # Should have 2 constraints and 1 directive (deduplicated)
    assert len(collected_decorators["constraints"]) == 2
    assert len(collected_decorators["directives"]) == 1

    # Verify the expected constraint types are present (order may vary)
    constraint_types = [list(c.keys())[0] for c in collected_decorators["constraints"]]
    assert "orientation" in constraint_types
    assert "group" in constraint_types

    # Verify directive
    assert "atomColor" in collected_decorators["directives"][0]


def test_yaml_output_no_duplicates():
    """Test that the final YAML output doesn't contain duplicate rules."""

    @orientation(selector="children", directions=["below"])
    class Node:
        def __init__(self, value, children=None):
            self.value = value
            self.children = children or []

    # Create a tree with multiple nodes
    root = Node("root", [Node("c1"), Node("c2"), Node("c3")])

    # Generate visualization
    result = spytial.diagram(root, method="file", auto_open=False)

    # Read the generated HTML and extract YAML
    with open(result, "r") as f:
        content = f.read()
        match = re.search(r"const cndSpec = `(.*?)`;", content, re.DOTALL)
        assert match, "Could not find cndSpec in HTML"
        yaml_content = match.group(1)

    # Count occurrences of the orientation constraint
    # Should only appear once, not 4 times (once per node)
    orientation_count = yaml_content.count("orientation:")
    assert (
        orientation_count == 1
    ), f"Expected 1 orientation constraint, found {orientation_count}"

    # Verify the constraint is present and correct
    assert "selector: children" in yaml_content
    assert "- below" in yaml_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

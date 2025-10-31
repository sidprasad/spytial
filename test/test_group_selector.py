#!/usr/bin/env python3
"""
Test file to validate group by selector annotation functionality for Issue #17.
"""

from spytial.annotations import (
    group,
    annotate_group,
    annotate,
    collect_decorators,
    serialize_to_yaml_string,
)


def test_selector_based_group_constraint():
    """Test the new selector-based group constraint."""
    # Test with new selector-based parameters
    my_set = {1, 2, 3, 4, 5}
    annotate_group(
        my_set,
        selector="{b : Basket, a : Fruit | (a in b.fruit) and a.status = Rotten }",
        name="rottenFruit",
    )

    decorators = collect_decorators(my_set)
    assert len(decorators["constraints"]) == 1
    constraint = decorators["constraints"][0]["group"]
    assert (
        constraint["selector"]
        == "{b : Basket, a : Fruit | (a in b.fruit) and a.status = Rotten }"
    )
    assert constraint["name"] == "rottenFruit"


def test_field_based_group_still_works():
    """Test that the original field-based group constraint still works."""
    my_list = [1, 2, 3, 4, 5]
    annotate_group(my_list, field="elements", groupOn=0, addToGroup=1)

    decorators = collect_decorators(my_list)
    assert len(decorators["constraints"]) == 1
    constraint = decorators["constraints"][0]["group"]
    assert constraint["field"] == "elements"
    assert constraint["groupOn"] == 0
    assert constraint["addToGroup"] == 1


def test_group_decorator_with_selector():
    """Test the group decorator with selector parameters."""
    my_dict = {"a": 1, "b": 2}
    my_dict = group(selector='{x : Item | x.type = "special"}', name="specialItems")(
        my_dict
    )

    decorators = collect_decorators(my_dict)
    assert len(decorators["constraints"]) == 1
    constraint = decorators["constraints"][0]["group"]
    assert constraint["selector"] == '{x : Item | x.type = "special"}'
    assert constraint["name"] == "specialItems"


def test_class_level_selector_group():
    """Test class-level selector-based group decorator."""

    @group(selector="{x : Item | x.value > 10}", name="highValueItems")
    class DataContainer:
        def __init__(self, data):
            self.data = data

    container = DataContainer({"a": 15, "b": 5})
    decorators = collect_decorators(container)

    assert len(decorators["constraints"]) == 1
    constraint = decorators["constraints"][0]["group"]
    assert constraint["selector"] == "{x : Item | x.value > 10}"
    assert constraint["name"] == "highValueItems"


def test_yaml_serialization_matches_issue_requirements():
    """Test that YAML output matches the exact format requested in Issue #17."""
    my_obj = [1, 2, 3]
    annotate_group(
        my_obj,
        selector="{b : Basket, a : Fruit | (a in b.fruit) and a.status = Rotten }",
        name="rottenFruit",
    )

    decorators = collect_decorators(my_obj)
    yaml_output = serialize_to_yaml_string(decorators)

    # Check that the YAML contains expected elements matching the issue
    assert "constraints:" in yaml_output
    assert "group:" in yaml_output
    assert "selector:" in yaml_output
    assert "name: rottenFruit" in yaml_output
    assert "Basket" in yaml_output and "Fruit" in yaml_output


def test_both_group_types_coexist():
    """Test that both field-based and selector-based group constraints can coexist."""
    my_list = [1, 2, 3]

    # Add both types of group constraints
    annotate_group(my_list, field="items", groupOn=0, addToGroup=1)
    annotate_group(my_list, selector="{x : Item | x.value < 3}", name="smallItems")

    decorators = collect_decorators(my_list)
    assert len(decorators["constraints"]) == 2

    # Check that both constraints exist
    field_constraint = None
    selector_constraint = None

    for constraint_entry in decorators["constraints"]:
        group_data = constraint_entry["group"]
        if "field" in group_data:
            field_constraint = group_data
        elif "selector" in group_data:
            selector_constraint = group_data

    assert field_constraint is not None
    assert field_constraint["field"] == "items"

    assert selector_constraint is not None
    assert selector_constraint["selector"] == "{x : Item | x.value < 3}"
    assert selector_constraint["name"] == "smallItems"


if __name__ == "__main__":
    print("Testing Issue #17: Group by selector annotation")

    test_field_based_group_still_works()
    print("✓ Field-based group constraint still works")

    test_selector_based_group_constraint()
    print("✓ Selector-based group constraint works")

    test_group_decorator_with_selector()
    print("✓ Group decorator with selector works")

    test_class_level_selector_group()
    print("✓ Class-level selector group works")

    test_yaml_serialization_matches_issue_requirements()
    print("✓ YAML serialization matches issue requirements")

    test_both_group_types_coexist()
    print("✓ Both group types can coexist")

    print("\n🎉 All Issue #17 tests passed!")

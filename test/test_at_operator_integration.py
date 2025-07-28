"""
Test integration of @: operator with annotation system.

This tests that annotations using the new @: operator syntax work correctly
with the sPyTial annotation system.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spytial.annotations import (
    atomColor, orientation, collect_decorators, serialize_to_yaml_string
)


def test_at_operator_in_atomColor():
    """Test @: operator in atomColor selector."""
    print("=== Testing @: Operator in atomColor ===")
    
    # Test class-level decorator with @: operator
    @atomColor(selector='{ x : RBTreeNode | @:(x.color) = red }', value='red')
    class RBTreeNode:
        def __init__(self, value, color):
            self.value = value
            self.color = color
    
    # Create instance and collect decorators
    node = RBTreeNode(10, "red")
    decorators = collect_decorators(node)
    
    # Verify the selector was preprocessed
    expected_selector = '{ x : RBTreeNode | getLabelForValue(x.color) = red }'
    actual_selector = decorators['directives'][0]['atomColor']['selector']
    
    print(f"Expected selector: {expected_selector}")
    print(f"Actual selector:   {actual_selector}")
    
    assert actual_selector == expected_selector
    assert decorators['directives'][0]['atomColor']['value'] == 'red'
    print("✓ @: operator in atomColor works")
    print()


def test_at_operator_in_orientation():
    """Test @: operator in orientation selector."""
    print("=== Testing @: Operator in orientation ===")
    
    # Test multiple @: operators
    @orientation(selector='{ x, y : Node | @:(x.type) = @:(y.type) }', directions=['left'])
    class Node:
        def __init__(self, node_type):
            self.type = node_type
    
    node = Node("leaf")
    decorators = collect_decorators(node)
    
    expected_selector = '{ x, y : Node | getLabelForValue(x.type) = getLabelForValue(y.type) }'
    actual_selector = decorators['constraints'][0]['orientation']['selector']
    
    print(f"Expected selector: {expected_selector}")
    print(f"Actual selector:   {actual_selector}")
    
    assert actual_selector == expected_selector
    print("✓ @: operator in orientation works")
    print()


def test_equals_operator_rejection_in_annotation():
    """Test that == operator is rejected in annotations."""
    print("=== Testing == Operator Rejection in Annotations ===")
    
    try:
        @atomColor(selector='{ x : Node | x.value == 5 }', value='blue')
        class BadNode:
            pass
        assert False, "Should have raised ValueError for == operator"
    except ValueError as e:
        print(f"✓ Correctly rejected == operator: {str(e)}")
    
    try:
        @orientation(selector='{ x, y : Node | x.id == y.id }', directions=['left'])
        class AnotherBadNode:
            pass
        assert False, "Should have raised ValueError for == operator"
    except ValueError as e:
        print(f"✓ Correctly rejected == operator: {str(e)}")
    
    print("✓ == operator rejection in annotations works")
    print()


def test_mixed_selectors():
    """Test selectors mixing @: operator with regular expressions."""
    print("=== Testing Mixed Selectors ===")
    
    @atomColor(selector='{ x : Tree | @:(x.color) = green and x.height > 10 }', value='green')
    class Tree:
        def __init__(self, color, height):
            self.color = color
            self.height = height
    
    tree = Tree("green", 15)
    decorators = collect_decorators(tree)
    
    expected_selector = '{ x : Tree | getLabelForValue(x.color) = green and x.height > 10 }'
    actual_selector = decorators['directives'][0]['atomColor']['selector']
    
    print(f"Expected selector: {expected_selector}")
    print(f"Actual selector:   {actual_selector}")
    
    assert actual_selector == expected_selector
    print("✓ Mixed selectors work")
    print()


def test_yaml_serialization_with_at_operator():
    """Test that YAML serialization works with @: operator."""
    print("=== Testing YAML Serialization with @: Operator ===")
    
    @atomColor(selector='{ x : RBTreeNode | @:(x.color) = black }', value='black')
    @orientation(selector='{ x, y : RBTreeNode | @:(x.level) = @:(y.level) }', directions=['horizontal'])
    class RBTreeNode:
        def __init__(self, value, color, level):
            self.value = value
            self.color = color
            self.level = level
    
    node = RBTreeNode(5, "black", 2)
    decorators = collect_decorators(node)
    yaml_output = serialize_to_yaml_string(decorators)
    
    print("YAML Output:")
    print(yaml_output)
    
    # Verify the processed selectors are in the YAML
    assert 'getLabelForValue(x.color)' in yaml_output
    assert 'getLabelForValue(x.level)' in yaml_output
    assert '==' not in yaml_output  # Should not contain == operator
    
    print("✓ YAML serialization with @: operator works")
    print()


def test_object_level_annotations_with_at_operator():
    """Test object-level annotations with @: operator."""
    print("=== Testing Object-Level Annotations with @: Operator ===")
    
    from spytial.annotations import annotate_atomColor, annotate_orientation
    
    class SimpleNode:
        def __init__(self, value, status):
            self.value = value
            self.status = status
    
    node = SimpleNode(42, "active")
    
    # Add object-level annotations with @: operator
    annotate_atomColor(node, selector='{ x : SimpleNode | @:(x.status) = active }', value='green')
    annotate_orientation(node, selector='{ x, y : SimpleNode | @:(x.value) = @:(y.value) }', directions=['vertical'])
    
    decorators = collect_decorators(node)
    
    # Check that both annotations were processed correctly
    assert len(decorators['directives']) == 1
    assert len(decorators['constraints']) == 1
    
    atomcolor_selector = decorators['directives'][0]['atomColor']['selector']
    orientation_selector = decorators['constraints'][0]['orientation']['selector']
    
    expected_atomcolor = '{ x : SimpleNode | getLabelForValue(x.status) = active }'
    expected_orientation = '{ x, y : SimpleNode | getLabelForValue(x.value) = getLabelForValue(y.value) }'
    
    print(f"AtomColor selector: {atomcolor_selector}")
    print(f"Expected:           {expected_atomcolor}")
    assert atomcolor_selector == expected_atomcolor
    
    print(f"Orientation selector: {orientation_selector}")
    print(f"Expected:             {expected_orientation}")
    assert orientation_selector == expected_orientation
    
    print("✓ Object-level annotations with @: operator work")
    print()


def run_all_tests():
    """Run all integration tests."""
    print("Testing @: Operator Integration with Annotation System")
    print("=" * 60)
    
    test_at_operator_in_atomColor()
    test_at_operator_in_orientation()
    test_equals_operator_rejection_in_annotation()
    test_mixed_selectors()
    test_yaml_serialization_with_at_operator()
    test_object_level_annotations_with_at_operator()
    
    print("🎉 All @: operator integration tests passed!")


if __name__ == "__main__":
    run_all_tests()
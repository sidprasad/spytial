#!/usr/bin/env python3
"""
Simple test file to validate object-level CND annotations.
"""

from spytial.annotations import (
    orientation, cyclic, 
    annotate, annotate_orientation, annotate_group, annotate_atomColor,
    collect_decorators, serialize_to_yaml_string
)

def test_object_annotations_basic():
    """Test basic object-level annotations."""
    print("=== Testing Basic Object Annotations ===")
    
    # Test with a list
    my_list = [1, 2, 3]
    annotate_orientation(my_list, selector='items', directions=['horizontal'])
    
    decorators = collect_decorators(my_list)
    assert len(decorators['constraints']) == 1
    assert decorators['constraints'][0]['orientation']['selector'] == 'items'
    print("✓ Basic object annotation works")

def test_object_annotations_builtin_types():
    """Test object annotations with built-in types that can't store attributes."""
    print("=== Testing Built-in Types (set, tuple, etc.) ===")
    
    # Test with set (immutable, no attribute assignment)
    my_set = {1, 2, 3, 4, 5}
    annotate_group(my_set, field='elements', groupOn=0, addToGroup=1)
    
    decorators = collect_decorators(my_set)
    assert len(decorators['constraints']) == 1
    assert decorators['constraints'][0]['group']['field'] == 'elements'
    
    # Test that other sets are unaffected
    other_set = {6, 7, 8}
    other_decorators = collect_decorators(other_set)
    assert len(other_decorators['constraints']) == 0
    print("✓ Built-in types annotation works")

def test_class_and_object_annotations_combined():
    """Test that class-level and object-level annotations work together."""
    print("=== Testing Class + Object Annotations ===")
    
    @orientation(selector='left', directions=['left'])
    @cyclic(selector='root', direction='clockwise')
    class Tree:
        def __init__(self, val):
            self.val = val

    # Create two instances
    tree1 = Tree(1)
    tree2 = Tree(2)

    # Add object-specific annotations to tree2
    annotate_group(tree2, field='children', groupOn=0, addToGroup=1)
    annotate_atomColor(tree2, selector='self', value='red')

    # tree1 should only have class annotations
    tree1_decorators = collect_decorators(tree1)
    assert len(tree1_decorators['constraints']) == 2  # orientation + cyclic
    assert len(tree1_decorators['directives']) == 0

    # tree2 should have class + object annotations
    tree2_decorators = collect_decorators(tree2)
    assert len(tree2_decorators['constraints']) == 3  # orientation + cyclic + group
    assert len(tree2_decorators['directives']) == 1   # atomColor
    
    print("✓ Class + object annotations combine correctly")

def test_general_annotate_function():
    """Test the general annotate function."""
    print("=== Testing General annotate() Function ===")
    
    my_dict = {'a': 1, 'b': 2}
    
    # Use general annotate function
    annotate(my_dict, 'atomColor', selector='keys', value='blue')
    annotate(my_dict, 'orientation', selector='layout', directions=['vertical'])
    
    decorators = collect_decorators(my_dict)
    assert len(decorators['constraints']) == 1
    assert len(decorators['directives']) == 1
    assert decorators['directives'][0]['atomColor']['value'] == 'blue'
    print("✓ General annotate() function works")

def test_yaml_serialization():
    """Test that annotations serialize properly to YAML."""
    print("=== Testing YAML Serialization ===")
    
    my_list = [1, 2, 3]
    annotate_orientation(my_list, selector='items', directions=['horizontal'])
    annotate_atomColor(my_list, selector='nums', value='green')
    
    decorators = collect_decorators(my_list)
    yaml_output = serialize_to_yaml_string(decorators)
    
    # Basic checks
    assert 'constraints:' in yaml_output
    assert 'directives:' in yaml_output
    assert 'orientation:' in yaml_output
    assert 'atomColor:' in yaml_output
    assert 'horizontal' in yaml_output
    assert 'green' in yaml_output
    print("✓ YAML serialization works")

if __name__ == "__main__":
    print("Testing Object-Level CND Annotations\n")
    
    test_object_annotations_basic()
    test_object_annotations_builtin_types()
    test_class_and_object_annotations_combined() 
    test_general_annotate_function()
    test_yaml_serialization()
    
    print("\n🎉 All tests passed! Object-level CND annotations are working correctly.")
    print("\nExample usage:")
    print("  from spytial import annotate_group, diagram")
    print("  my_set = {1, 2, 3, 4, 5}")
    print("  annotate_group(my_set, field='elements', groupOn=0, addToGroup=1)")
    print("  diagram(my_set)  # Will show the set as a group")
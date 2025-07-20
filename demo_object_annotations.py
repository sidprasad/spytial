#!/usr/bin/env python3
"""
Demo of object-level CND annotations showing the issue example:
Annotating specific objects (like sets) without modifying their classes.
"""

from spytial import (
    diagram, 
    orientation, cyclic,  # Class decorators
    annotate_group, annotate_atomColor, annotate_orientation  # Object functions
)

def demo_set_grouping():
    """Demo from the issue: Show sets as groups without overriding Set class."""
    print("=== Demo: Set Grouping (Issue Example) ===")
    
    # Create different sets - each can be annotated differently
    fruits = {"apple", "banana", "cherry", "date"}
    numbers = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
    colors = {"red", "green", "blue"}
    
    # Annotate each set differently without modifying the Set class
    annotate_group(fruits, field='items', groupOn=0, addToGroup=1)
    annotate_atomColor(fruits, selector='items', value='orange')
    
    annotate_group(numbers, field='digits', groupOn=0, addToGroup=1)
    annotate_atomColor(numbers, selector='digits', value='blue')
    
    # Leave colors set without special annotations
    
    # Create a container to show them all
    data = {
        "fruits": fruits,
        "numbers": numbers, 
        "colors": colors,
        "note": "fruits and numbers are grouped, colors is not"
    }
    
    print("Fruits set annotations:", annotate_group.__doc__)
    print("This demonstrates the core issue request: annotating objects without modifying classes")
    print("Generating visualization...")
    
    # This will show:
    # - fruits set as a group with orange coloring
    # - numbers set as a group with blue coloring  
    # - colors set with default rendering
    return data

def demo_class_and_object_annotations():
    """Demo showing class-level and object-level annotations working together."""
    print("\n=== Demo: Class + Object Annotations ===")
    
    @orientation(selector='left', directions=['left'])
    @cyclic(selector='children', direction='clockwise')
    class TreeNode:
        def __init__(self, value, left=None, right=None):
            self.value = value
            self.left = left
            self.right = right
    
    # Create a tree structure
    root = TreeNode("root")
    root.left = TreeNode("left-child")
    root.right = TreeNode("right-child")
    root.left.left = TreeNode("left-left")
    root.left.right = TreeNode("left-right")
    
    # Add object-specific annotations to specific nodes
    # The root gets special coloring
    annotate_atomColor(root, selector='self', value='red')
    
    # The left subtree gets grouped differently
    annotate_group(root.left, field='subtree', groupOn=0, addToGroup=1)
    annotate_orientation(root.left, selector='self', directions=['below'])
    
    print("Class annotations apply to ALL TreeNode instances")
    print("Object annotations apply only to specific instances")
    print("Both combine when collecting annotations")
    
    return root

def demo_built_in_types():
    """Demo annotations on various built-in types that can't normally store attributes."""
    print("\n=== Demo: Built-in Types Annotations ===")
    
    # Tuple (immutable)
    coordinates = (10, 20, 30)
    annotate_orientation(coordinates, selector='axes', directions=['horizontal'])
    
    # Frozenset (immutable)
    immutable_set = frozenset([1, 2, 3, 4])
    annotate_group(immutable_set, field='elements', groupOn=0, addToGroup=1)
    
    # String (immutable) 
    text = "Hello World"
    annotate_atomColor(text, selector='characters', value='purple')
    
    # Combine in data structure
    data = {
        "coordinates": coordinates,
        "immutable_set": immutable_set,
        "text": text,
        "info": "All these immutable types have object-specific annotations"
    }
    
    print("Successfully annotated immutable built-in types:")
    print(f"- tuple: {coordinates}")
    print(f"- frozenset: {immutable_set}")
    print(f"- string: '{text}'")
    
    return data

if __name__ == "__main__":
    print("Object-Level CND Annotations Demo")
    print("="*50)
    
    # Run all demos
    set_data = demo_set_grouping()
    tree_data = demo_class_and_object_annotations()
    builtin_data = demo_built_in_types()
    
    print("\n" + "="*50)
    print("Visualization Examples:")
    print("="*50)
    
    print("\n1. Set Grouping Demo:")
    print("   This shows different sets with object-specific group annotations")
    # Uncomment to generate actual visualization:
    # diagram(set_data, method="file")
    print("   (Call diagram(set_data) to visualize)")
    
    print("\n2. Tree with Mixed Annotations:")
    print("   Shows class decorators + object annotations working together")
    # Uncomment to generate actual visualization:
    # diagram(tree_data, method="file")
    print("   (Call diagram(tree_data) to visualize)")
    
    print("\n3. Built-in Types Demo:")
    print("   Shows annotations work on immutable types like tuple, frozenset, str")
    # Uncomment to generate actual visualization:
    # diagram(builtin_data, method="file")
    print("   (Call diagram(builtin_data) to visualize)")
    
    print("\n🎯 Key Achievement:")
    print("   CND annotations now work on OBJECTS, not just classes!")
    print("   - Annotate specific instances without modifying their class")
    print("   - Works with built-in/immutable types (set, tuple, frozenset, str)")
    print("   - Class and object annotations combine as expected")
    print("   - Backward compatible with existing class-level decorators")
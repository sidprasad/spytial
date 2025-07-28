"""
Demo of the new @: operator for sPyTial selector syntax.

This demonstrates the solution to issue #10, showing how the new @: operator
replaces the problematic == operator for label comparisons.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spytial.annotations import (
    atomColor, orientation, attribute, collect_decorators, serialize_to_yaml_string
)


def demo_new_at_operator():
    """Demonstrate the new @: operator syntax."""
    print("sPyTial @: Operator Demo")
    print("=" * 40)
    print()
    
    print("The new @: operator allows comparing LABELS instead of IDs:")
    print("- @:(x.color) = black   # Check if label has value 'black'")
    print("- (x.color) = black     # Check if node ID 'black' equals x.color")
    print("- @:(x.v) = @:(y.v)     # Compare labels instead of IDs")
    print()
    
    # Define RBTreeNode with new @: operator syntax
    @orientation(selector='{ x, y : RBTreeNode | x.left = y}', directions=['below', 'left'])
    @orientation(selector='{ x, y : RBTreeNode | x.right = y}', directions=['below', 'right'])
    @atomColor(selector='{ x : RBTreeNode | @:(x.color) = red }', value='red')
    @atomColor(selector='{ x : RBTreeNode | @:(x.color) = black }', value='black')
    @attribute(field='value')
    class RBTreeNode:
        def __init__(self, value, color, left=None, right=None):
            self.value = value
            self.color = color
            self.left = left
            self.right = right

        def __repr__(self):
            return f"RBTreeNode({self.value}, {self.color})"
            
        def traditional_print(self, level=0):
            """Traditional colored tree printing"""
            if self.right:
                self.right.traditional_print(level + 1)
            color_marker = "(R)" if self.color == "red" else "(B)"
            print('    ' * level + f"{self.value}{color_marker}")
            if self.left:
                self.left.traditional_print(level + 1)
    
    # Create a sample red-black tree
    rb_root = RBTreeNode(
        10, "black",
        left=RBTreeNode(
            5, "red",
            left=RBTreeNode(3, "black"),
            right=RBTreeNode(7, "black")
        ),
        right=RBTreeNode(
            15, "red", 
            left=RBTreeNode(12, "black"),
            right=RBTreeNode(18, "black")
        )
    )
    
    print("Created RB-Tree structure:")
    rb_root.traditional_print()
    print()
    
    # Collect and display the annotations
    decorators = collect_decorators(rb_root)
    
    print("Processed annotations (with @: operator transformed):")
    yaml_output = serialize_to_yaml_string(decorators)
    print(yaml_output)
    
    # Show the transformation
    print("Transformation examples:")
    print("  Original: { x : RBTreeNode | @:(x.color) = red }")
    print("  Processed: { x : RBTreeNode | getLabelForValue(x.color) = red }")
    print()
    print("  Original: { x : RBTreeNode | @:(x.color) = black }")
    print("  Processed: { x : RBTreeNode | getLabelForValue(x.color) = black }")
    print()
    
    return rb_root, decorators


def demo_comparison_operators():
    """Demonstrate the different comparison operators."""
    print("Comparison Operator Examples")
    print("=" * 40)
    print()
    
    examples = [
        ("@:(x.color) = black", "getLabelForValue(x.color) = black", 
         "Compare label value - checks if x.color has label 'black'"),
        ("(x.color) = black", "(x.color) = black", 
         "Compare ID - checks if node ID 'black' equals x.color"),
        ("@:(x.v) = @:(y.v)", "getLabelForValue(x.v) = getLabelForValue(y.v)", 
         "Compare two labels - checks if both have same label value"),
    ]
    
    for original, processed, description in examples:
        print(f"Original:    {{ x : Node | {original} }}")
        print(f"Processed:   {{ x : Node | {processed} }}")
        print(f"Meaning:     {description}")
        print()


def demo_error_handling():
    """Demonstrate error handling for prohibited == operator."""
    print("Error Handling Demo")
    print("=" * 40)
    print()
    
    print("The == operator is now prohibited and will raise an error:")
    
    try:
        @atomColor(selector='{ x : Node | x.value == 5 }', value='blue')
        class BadNode:
            pass
    except ValueError as e:
        print(f"✓ Error caught: {str(e)}")
    
    print()
    print("Use the new syntax instead:")
    print("  For label comparison: @:(x.value) = 5")
    print("  For ID comparison:    (x.value) = 5")
    print()


def main():
    """Run all demos."""
    demo_new_at_operator()
    demo_comparison_operators()
    demo_error_handling()
    
    print("🎉 Demo completed successfully!")
    print()
    print("The @: operator is now ready to use in your sPyTial annotations!")
    

if __name__ == "__main__":
    main()
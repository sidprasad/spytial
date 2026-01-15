"""
Example: Type Alias Annotations + Auto Method Detection

This example demonstrates both new features:
1. Clean type alias annotations using typing.Annotated
2. Automatic method selection based on environment
"""

from typing import Annotated
import spytial

# ============================================================================
# Feature 1: Type Alias Annotations with typing.Annotated
# ============================================================================

# Define annotated type aliases with spatial constraints
IntList = Annotated[list[int],
    spytial.Orientation(selector='items', directions=['horizontal']),
    spytial.AtomColor(selector='self', value='steelblue')
]

VerticalList = Annotated[list[str],
    spytial.Orientation(selector='items', directions=['vertical']),
    spytial.AtomColor(selector='items', value='coral'),
    spytial.Size(selector='items', height=40, width=60)
]

TreeDict = Annotated[dict,
    spytial.Orientation(selector='values', directions=['below']),
    spytial.EdgeColor(field='*', value='green')
]

# ============================================================================
# Feature 2: Auto Method Detection
# ============================================================================

# Create test data
horizontal_data: IntList = [1, 2, 3, 4, 5]
vertical_data: VerticalList = ['apple', 'banana', 'cherry']
tree_data: TreeDict = {
    'root': {
        'left': {'value': 1},
        'right': {'value': 2}
    }
}

# ============================================================================
# Usage Examples
# ============================================================================

print("=" * 70)
print("sPyTial Example: Type Aliases + Auto Method Detection")
print("=" * 70)
print()

# Example 1: No method argument - automatically detects environment
print("1. Using diagram() with NO method argument:")
print("   - In Jupyter notebook: will display inline")
print("   - In Python script: will open in browser")
print()

# This will open in browser since we're running as a script
result = spytial.diagram(horizontal_data, auto_open=False)
print(f"   Result: {result}")
print()

# Example 2: Explicit method still works
print("2. Explicitly specifying method='file':")
file_path = spytial.diagram(vertical_data, method='file', auto_open=False)
print(f"   Saved to: {file_path}")
print()

# Example 3: Multiple type aliases in one visualization
print("3. Combining multiple annotated types:")
combined = {
    'horizontal': horizontal_data,
    'vertical': vertical_data,
    'tree': tree_data
}
result = spytial.diagram(combined, auto_open=False)
print(f"   Result: {result}")
print()

print("=" * 70)
print("Key Benefits")
print("=" * 70)
print("""
✅ Type Aliases:
   - Clean, declarative syntax using typing.Annotated
   - Works with type checkers (mypy, pyright)
   - Composable - stack multiple annotations
   - Immutable - no mutable global state

✅ Auto Method Detection:
   - Smart defaults based on environment
   - In notebooks: renders inline automatically
   - In scripts: opens browser automatically
   - Can still override with explicit method= argument

Example Usage:
   
   # Define annotated types
   IntList = Annotated[list[int],
       spytial.Orientation(selector='items', directions=['horizontal']),
       spytial.AtomColor(selector='self', value='blue')
   ]
   
   # Use in code
   data: IntList = [1, 2, 3, 4, 5]
   
   # Visualize - automatically picks right method!
   spytial.diagram(data)  # No method= needed!
""")

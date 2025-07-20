# Object-Level CND Annotations

This document demonstrates the new object-level annotation capabilities that solve Issue #6.

## Problem Solved

Previously, CND annotations could only be applied to **classes** using decorators like `@orientation` and `@cyclic`. The issue requested the ability to annotate specific **objects** (instances) without modifying their classes.

**Example from Issue**: "I might want to show sets as a group -- but not override the Set data structure."

## Solution

Object-level annotations are now supported alongside class-level annotations. Both types combine when collecting annotations ("all apply").

## Usage Examples

### Basic Object Annotations

```python
from spytial import annotate_group, annotate_orientation, annotate_atomColor, diagram

# Annotate a specific set without modifying the Set class
my_set = {1, 2, 3, 4, 5}
annotate_group(my_set, field='elements', groupOn=0, addToGroup=1)
diagram(my_set)  # Shows the set as a group

# Works with any object type
my_list = [1, 2, 3]
annotate_orientation(my_list, selector='items', directions=['horizontal'])

my_dict = {'a': 1, 'b': 2}
annotate_atomColor(my_dict, selector='keys', value='blue')
```

### General Annotation Function

```python
from spytial import annotate

# Use the general annotate function for any annotation type
annotate(my_object, 'orientation', selector='test', directions=['left'])
annotate(my_object, 'atomColor', selector='items', value='red')
```

### Combining Class and Object Annotations

```python
from spytial import orientation, cyclic, annotate_group, annotate_atomColor

@orientation(selector='left', directions=['left'])
@cyclic(selector='children', direction='clockwise')
class TreeNode:
    def __init__(self, value):
        self.value = value

# Create instances
tree1 = TreeNode("A")
tree2 = TreeNode("B")

# Add object-specific annotations to tree2 only
annotate_group(tree2, field='subtree', groupOn=0, addToGroup=1)
annotate_atomColor(tree2, selector='self', value='red')

# tree1: only class annotations (orientation + cyclic)
# tree2: class annotations + object annotations (orientation + cyclic + group + atomColor)
```

### Built-in/Immutable Types

The system works with built-in types that normally can't store attributes:

```python
# Immutable types work perfectly
coordinates = (10, 20, 30)
annotate_orientation(coordinates, selector='axes', directions=['horizontal'])

frozen_set = frozenset([1, 2, 3])
annotate_group(frozen_set, field='elements', groupOn=0, addToGroup=1)

text = "Hello World"
annotate_atomColor(text, selector='characters', value='purple')
```

## Available Object Annotation Functions

All class-level decorators have corresponding object annotation functions:

### Constraints
- `annotate_orientation(obj, selector='...', directions=[...])`
- `annotate_cyclic(obj, selector='...', direction='...')`
- `annotate_group(obj, field='...', groupOn=..., addToGroup=...)`

### Directives  
- `annotate_atomColor(obj, selector='...', value='...')`
- `annotate_size(obj, selector='...', height=..., width=...)`
- `annotate_icon(obj, selector='...', path='...', showLabels=...)`
- `annotate_edgeColor(obj, field='...', color='...')`
- `annotate_projection(obj, sig='...')`
- `annotate_attribute(obj, field='...')`
- `annotate_hideField(obj, field='...')`
- `annotate_hideAtom(obj, selector='...')`
- `annotate_inferredEdge(obj, name='...', selector='...')`

## Technical Implementation

### Dual Storage System
- **Regular objects**: Annotations stored directly on object via `__spytial_object_annotations__` attribute
- **Immutable types**: Annotations stored in global registry keyed by object ID

### Annotation Collection
The `collect_decorators(obj)` function now:
1. Collects class-level annotations from the object's class hierarchy
2. Collects object-level annotations from the object instance  
3. Combines both types into a single registry

### Backward Compatibility
- All existing class-level decorators work unchanged
- Existing code requires no modifications
- New object annotation functions are additive

## Integration with Visualizer

Object annotations integrate seamlessly with the existing visualization system:

```python
from spytial import diagram, annotate_group

# The issue example in action
fruits = {"apple", "banana", "cherry"}
annotate_group(fruits, field='items', groupOn=0, addToGroup=1)

data = {"fruit_collection": fruits}
diagram(data)  # The fruits set will be rendered as a group
```

The annotations are automatically:
1. Collected by `collect_decorators()`
2. Serialized to YAML by `serialize_to_yaml_string()`
3. Passed to the visualizer
4. Applied during rendering

## Key Benefits

1. **Solves the Issue**: Can annotate specific objects without modifying their classes
2. **Flexible**: Works with any object type, including built-ins and immutables
3. **Composable**: Class and object annotations combine naturally
4. **Compatible**: Fully backward compatible with existing code
5. **Integrated**: Works seamlessly with existing visualization pipeline

This implementation fully addresses Issue #6 by enabling CND annotations on objects while maintaining all existing functionality.
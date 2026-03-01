# Operations

Operations define how sPyTial interprets and renders your data. They fall into two categories:

- **Constraints** describe layout.
- **Directives** describe drawing and presentation.

Most users attach operations to classes with decorators. You can also attach them to specific objects or supply them via `typing.Annotated` or `spytial.AnnotatedType`.

## Constraints

Constraints shape the geometry of the final diagram:

- `orientation`: directional relationships between selected boxes
- `align`: force selected boxes to share an axis
- `cyclic`: arrange selected boxes in a cycle
- `group`: place selected boxes inside a labeled bounding region

## Directives

Directives change what the diagram looks like without changing the structure:

- `atomColor` and `edgeColor`
- `attribute`
- `tag`
- `inferredEdge`
- `icon`
- `hideField` and `hideAtom`
- `size`

The API Reference lists the full argument surface for each operation.

## Class decorators

Attach operations to a class using decorators. This is the most common and reusable approach.

```python
import spytial

@spytial.orientation(selector="children", directions=["below"])
@spytial.group(selector="children", name="subtree")
class Node:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []
```

## Object-level annotations

Attach operations to a single instance without modifying the class:

```python
import spytial

node = Node("root")
spytial.annotate_group(node, selector="children", name="root children")
spytial.annotate_orientation(node, selector="children", directions=["below"])
```

## `typing.Annotated` and `AnnotatedType`

Use these when you want to annotate plain containers such as `dict` and `list` values.

```python
from typing import Dict, List
from spytial import AnnotatedType, InferredEdge, Orientation

Graph = AnnotatedType(
    Dict[int, List[int]],
    InferredEdge(name="edge", selector="values"),
    Orientation(selector="values", directions=["right"]),
)

spytial.diagram({0: [1, 2]}, as_type=Graph)
```

## Example directives

The `tag` directive displays computed values as node attributes without removing the underlying edges:

```python
import spytial

@spytial.tag(toTag="Person", name="age", value="age")
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
```

Edge appearance can be customized with color, style, weight, and visibility:

```python
import spytial

@spytial.edgeColor(field="parent", value="blue", style="solid", weight=2)
@spytial.edgeColor(field="sibling", value="gray", style="dashed")
class TreeNode:
    def __init__(self, value, parent=None):
        self.value = value
        self.parent = parent
```

## Convenience operations

`apply_if` lets you conditionally attach operations:

```python
import spytial

@spytial.apply_if(
    lambda cls: cls.__name__.endswith("Node"),
    spytial.atomColor(selector="self", value="lightblue"),
)
class TreeNode:
    def __init__(self, value):
        self.value = value
```

## Patterns used in `spytial-clrs`

The CLRS notebooks are a good source of idiomatic operation usage:

- linked lists use `attribute(...)` to turn fields into compact labels
- heaps and matrix-style examples use `align(...)` to create readable rows or sibling levels
- disjoint sets, hash tables, and SCC views use `group(...)` to expose higher-level regions

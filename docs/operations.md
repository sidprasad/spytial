# Operations

Operations define how sPyTial interprets and renders your data. They fall into two categories:

- **Constraints**: describe how things should be laid out.
- **Directives**: describe how things should be drawn.

Most users attach operations to classes with decorators. You can also attach them to specific objects or supply them via `typing.Annotated` or `spytial.AnnotatedType`.

## Constraints (layout)

Constraints affect the structure and layout of the diagram:

- **orientation**: set overall direction (`"LR"`, `"RL"`, `"TB"`, `"BT"`).
- **align**: align nodes to a row or column.
- **cyclic**: mark a structure as cyclic so the layout can account for it.
- **group**: cluster nodes together under a shared label.

## Directives (drawing)

Directives control rendering details. Common directives include:

- **size**: set width/height for atoms.
- **atomColor** / **edgeColor**: set color styling for atoms or edges.
- **icon**: supply an icon for a node.
- **projection** / **attribute**: customize displayed attributes.
- **hideField** / **hideAtom**: remove fields or atoms from the diagram.
- **inferredEdge**: declare edges implied by fields or collections.
- **flag**: add a Boolean marker used in rendering logic.

The API Reference lists every operation and its arguments.

## Primary attachment: class decorators

Attach operations to a class using decorators. This is the most common and reusable approach.

```python
import spytial

@spytial.orientation(direction="TB")
@spytial.group(name="Cluster A")
class Node:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []
```

## Other attachment methods

### Object annotations

Attach operations to a single instance without modifying the class:

```python
node = Node("root")
spytial.annotate_orientation(node, direction="LR")
spytial.annotate_group(node, name="Root Group")
```

### typing.Annotated / AnnotatedType

Treat a plain value as an annotated type (useful for dict/list data):

```python
from typing import Annotated, Dict, List
from spytial import InferredEdge, Orientation

Graph = Annotated[
    Dict[int, List[int]],
    InferredEdge(target_field="__values__"),
    Orientation(direction="LR"),
]

spytial.diagram({0: [1, 2]}, as_type=Graph)
```

## Convenience operations

Some operations help you express common logic without repeating boilerplate.

### `apply_if`

Use `apply_if` to conditionally apply operations. This is convenient when only some instances should carry a decorator or directive.

```python
import spytial

@spytial.apply_if(lambda cls: cls.__name__.endswith("Node"), spytial.icon(name="tree"))
class TreeNode:
    def __init__(self, value):
        self.value = value
```

!!! note
    `apply_if` is a shorthand for conditionally attaching operations. If the predicate returns `False`, no operation is applied.

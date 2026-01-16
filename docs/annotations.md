# Annotations & Constraints

sPyTial uses annotations to attach spatial constraints and rendering directives to your types or instances. You can use class decorators, object-level annotation functions, or `typing.Annotated`/`AnnotatedType` to apply them.

## Class decorators

Decorators attach metadata to a class definition:

```python
import spytial

@spytial.orientation(direction="TB")
@spytial.group(name="Cluster A")
class Node:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []
```

## Object annotations

Annotate a single instance without touching the class definition:

```python
node = Node("root")
spytial.annotate_orientation(node, direction="LR")
spytial.annotate_group(node, name="Root Group")
```

## Typing annotations

Use `typing.Annotated` or `spytial.AnnotatedType` when you want to treat plain data as a particular annotated type:

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

## Common directives

Below are frequently used annotations. Each has both a decorator and an object annotation function (e.g., `orientation(...)` and `annotate_orientation(...)`).

- **orientation**: control layout direction (`"LR"`, `"RL"`, `"TB"`, `"BT"`).
- **align**: align nodes to a row or column.
- **group**: group nodes into labeled clusters.
- **size**: set width/height for atoms.
- **atomColor** / **edgeColor**: set color styling for atoms or edges.
- **icon**: supply an icon for a node.
- **projection** / **attribute**: customize displayed attributes.
- **hideField** / **hideAtom**: remove fields or atoms from the diagram.
- **inferredEdge**: declare edges implied by fields or collections.
- **flag**: add a Boolean marker used in rendering logic.

## Inheritance controls

You can stop constraints and directives from being inherited by subclasses:

```python
@spytial.dont_inherit_constraints
class Base:
    ...
```

Use `dont_inherit_directives` or `dont_inherit_annotations` for finer control.

!!! note
    The complete list of annotations and their arguments is available in the API Reference.

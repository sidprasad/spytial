# Operations

Operations define how sPyTial interprets and renders your data. They fall into two categories:

- **Constraints**: describe how things should be laid out.
- **Directives**: describe how things should be drawn.

Most users attach operations to classes with decorators. You can also attach them to specific objects or supply them via `typing.Annotated` or `spytial.AnnotatedType`.

## Constraints (layout)

Constraints affect the structure and layout of the diagram. Think of them as statements about **where boxes should go** relative to each other.

- **orientation**: directional relationships between selected boxes (for example, `left` vs. `directlyLeft`). The stricter forms imply alignment on the perpendicular axis.
- **align**: force selected boxes to share a common axis (e.g., vertical alignment means they share the same top-left `x` coordinate).
- **cyclic**: arrange a sequence of boxes in a polygonal pattern, derived from an adjacency relation, to reflect cycles or ordered chains.
- **group**: introduce a bounding region that must contain selected boxes and exclude others (optionally with keyed subgroups).

These constraints influence the geometry the solver must satisfy, so they directly shape layout.

## Directives (drawing)

Directives control rendering details. They **do not change the underlying structure**, but they alter how nodes and edges are drawn.

- **atomColor** / **edgeColor**: apply color to boxes or edges.
- **attribute**: replace outgoing edges with labels.
- **inferredEdge**: add derived edges to expose implicit relationships.
- **icon**: attach a graphical icon (optionally alongside the label).
- **hideField**: suppress drawing a field edge.

Two operations are often used alongside directives:

- **hideAtom**: remove selected atoms from the realized layout entirely (prunes the diagram before solving).
- **size**: set explicit width/height for selected boxes.

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

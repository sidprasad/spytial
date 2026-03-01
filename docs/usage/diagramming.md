# Diagramming

`spytial.diagram()` turns Python objects into a spatial diagram. It works with built-in containers, dataclasses, custom classes, and graph-like structures.

## Basic usage

```python
import spytial

spytial.diagram({"a": 1, "b": [1, 2, 3]})
```

## Sequence diagrams

Use `spytial.diagramSequence()` when you want to step through multiple states with the temporal policies from `spytial-core`.

```python
import spytial

states = [
    {"count": 0, "items": ["a"]},
    {"count": 1, "items": ["a", "b"]},
    {"count": 2, "items": ["b"]},
]

spytial.diagramSequence(states, sequence_policy="stability")
```

Available sequence policies:

- `ignore_history`
- `stability`
- `change_emphasis`
- `random_positioning`

### When to use `identity`

If each step reuses the same live Python objects and mutates them over time, `diagramSequence()` can usually preserve IDs without extra help.

```python
class Node:
    def __init__(self, node_id, value):
        self.id = node_id
        self.value = value

node = Node("A", 1)
states = [node]
node.value = 2
states.append(node)

spytial.diagramSequence(states, sequence_policy="stability")
```

If each step rebuilds fresh objects, pass `identity=` so the same conceptual entity gets the same atom ID across steps.

```python
class Node:
    def __init__(self, node_id, value):
        self.id = node_id
        self.value = value

states = [
    Node("A", 1),
    Node("A", 2),
]

spytial.diagramSequence(
    states,
    sequence_policy="stability",
    identity=lambda obj: obj.id if hasattr(obj, "id") else None,
)
```

`identity` is only used by `diagramSequence()`. It is object-only, and it must return either:

- a string for objects that should keep the same identity across steps
- `None` for everything else

If two distinct objects in the same snapshot return the same identity string, `diagramSequence()` raises an error instead of guessing.

## Display options

```python
spytial.diagram(data, method="browser")  # open a new tab
spytial.diagram(data, method="file")     # save as spytial_visualization.html
spytial.diagram(data, method="inline")   # force notebook output
spytial.diagramSequence(states, method="file")  # save as spytial_sequence_visualization.html
```

## Sizing and title

```python
spytial.diagram(data, width=900, height=600, title="My Diagram")
```

## Passing annotations with `as_type`

Use `AnnotatedType` or `typing.Annotated` to attach spatial constraints to a type you want the object treated as.

```python
from typing import Dict, List
from spytial import AnnotatedType, InferredEdge, Orientation, Tag

Graph = AnnotatedType(
    Dict[int, List[int]],
    InferredEdge(name="edge", selector="values"),
    Orientation(selector="values", directions=["right"]),
    Tag(toTag="univ", name="count", value="values"),
)

graph = {0: [1, 2], 1: [3]}
spytial.diagram(graph, as_type=Graph)
```

## Common workflow

For non-trivial objects, the usual workflow is:

1. `spytial.evaluate(obj)` to confirm the serialized atoms and relations.
2. `spytial.diagram(obj)` to see the layout.
3. Add decorators or `AnnotatedType(...)` annotations if you want more control over layout or styling.

## Headless benchmarking

For large structures, you can render multiple times and save aggregated timing.

```python
import spytial

metrics = spytial.diagram(
    data,
    headless=True,
    perf_path="perf.json",
    perf_iterations=5,
)
```

!!! note
    Headless mode requires Selenium and a Chrome/Chromedriver installation. Use `pip install spytial_diagramming[headless]` and ensure the driver is on your PATH.

## Return values

- `method="browser"` and `method="file"` return the HTML file path.
- `headless=True` returns performance metrics when `perf_iterations` is set.

## Patterns from `spytial-clrs`

If you want realistic examples instead of toy snippets, use the notebooks in [`spytial-clrs`](https://github.com/sidprasad/spytial-clrs):

- `linked-lists.ipynb` shows list-like structures and cyclic constraints.
- `heaps.ipynb` and `trees.ipynb` show recursive structures with alignment and attributes.
- `graphs.ipynb` and `disjoint-sets.ipynb` show grouping-heavy layouts.

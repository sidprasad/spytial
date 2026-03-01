# Diagramming

`spytial.diagram()` turns Python objects into a spatial diagram. It works with built-in containers, dataclasses, custom classes, and graph-like structures.

## Basic usage

```python
import spytial

spytial.diagram({"a": 1, "b": [1, 2, 3]})
```

## Display options

```python
spytial.diagram(data, method="browser")  # open a new tab
spytial.diagram(data, method="file")     # save as spytial_visualization.html
spytial.diagram(data, method="inline")   # force notebook output
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

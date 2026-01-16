# Diagramming

`spytial.diagram()` turns Python objects into a spatial diagram. You can invoke it with any object: dicts, lists, dataclasses, custom classes, and graph-like structures.

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

### Sizing and title

```python
spytial.diagram(data, width=900, height=600, title="My Diagram")
```

### Passing annotations with `as_type`

Use `AnnotatedType` (or `typing.Annotated`) to attach spatial constraints to a type you want the object treated as.

```python
from typing import Dict, List
from spytial import AnnotatedType, InferredEdge, Orientation

Graph = AnnotatedType(
    Dict[int, List[int]],
    InferredEdge(target_field="__values__"),
    Orientation(direction="LR"),
)

graph = {0: [1, 2], 1: [3]}
spytial.diagram(graph, as_type=Graph)
```

### Performance benchmarking

For large structures, you can render multiple times and save aggregated timing.

```python
spytial.diagram(
    data,
    method="file",
    perf_path="perf.json",
    perf_iterations=5,
)
```

### Headless mode

Headless mode uses a Chrome driver to render without opening a browser.

```python
spytial.diagram(
    data,
    headless=True,
    perf_iterations=3,
    timeout=300,
)
```

!!! note
    Headless mode requires Selenium and a Chrome/Chromedriver installation. Use `pip install spytial_diagramming[headless]` and ensure the driver is on your PATH.

## Return values

- `method="browser"` and `method="file"` return the HTML file path.
- `method="headless"` returns performance metrics if you set `perf_iterations`.

# Getting Started

## Install

```bash
pip install spytial-diagramming
```

## First diagram

```python
import spytial

example = {
    "id": "root",
    "children": [
        {"id": "left"},
        {"id": "right"},
    ],
}

spytial.diagram(example)
```

## Display methods

`sPyTial` chooses a display method based on environment:

- **Notebook:** renders inline.
- **Anywhere else:** opens a browser tab.

You can override this explicitly:

```python
spytial.diagram(example, method="browser")   # open a new tab
spytial.diagram(example, method="file")      # write an HTML file
spytial.diagram(example, method="inline")    # force inline output
```

## When to use each tool

| Tool | Best for | Output |
| --- | --- | --- |
| `diagram()` | Visualizing object structure | HTML diagram (inline or browser) |
| `evaluate()` | Inspecting serialized data | HTML evaluator view |
| `dataclass_builder()` | Constructing dataclass instances | Interactive builder |

Next, dive into **Usage** to learn about the diagram and evaluator workflows.

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

By default, sPyTial renders inline in notebooks and opens a browser tab everywhere else.

## Inspect before you diagram

If you want to confirm how an object is being serialized, use the evaluator first:

```python
import spytial

spytial.evaluate(example)
```

This is useful when you are debugging a custom class, an annotation, or a relationalizer.

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

## Next steps

- Read [Diagramming](usage/diagramming.md) for the main rendering workflow.
- Read [Operations](operations.md) to control layout and drawing.
- Browse [CLRS Examples](examples/spytial-clrs.md) for richer data-structure examples.

# sPyTial

sPyTial helps you turn Python objects into meaningful **box-and-arrow diagrams** using spatial layout rules. It focuses on the structure of your data rather than UI chrome, making it ideal for debugging, teaching, and research.

## What you can do

- **Diagram** any Python object in a browser tab or notebook.
- **Evaluate** your data as a structured payload to validate serialization.
- **Annotate** types or instances with spatial constraints (orientation, grouping, colors, icons, etc.).
- **Build** dataclass instances with a visual, copy/pasteable builder.
- **Extend** the serializer with custom relationalizers for domain objects.

## Install

```bash
pip install spytial-diagramming
```

## Quick start

```python
import spytial

data = {
    "name": "root",
    "children": [
        {"value": 1},
        {"value": 2},
        {"value": 3},
    ],
}

# Open a diagram in a browser or inline notebook view.
spytial.diagram(data)
```

## Documentation layout

Use the sections in the navigation to explore:

- **Getting Started** for installation and first steps.
- **Usage** for diagramming, evaluation, and builder workflows.
- **Annotations & Constraints** for spatial controls.
- **Custom Relationalizers** to extend serialization for your own types.
- **API Reference** for auto-generated docs from the codebase.

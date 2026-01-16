# sPyTial: Lightweight Diagrams for Structured Python Data

```
pip install spytial-diagramming
```


Sometimes you just want to see your data.

You’re working with a tree, a graph, a recursive object -- maybe an AST, a neural network, or a symbolic term. You don’t need an interactive dashboard or a production-grade visualization system. You just need a diagram, something that lays it out clearly so you can understand what’s going on.

That’s what `sPyTial` is for. It’s designed for developers, educators, and researchers who work with structured data and need to make that structure visible — to themselves or to others — with minimal effort. 

## Why Spatial Representation Matters

There’s strong evidence — from cognitive science, human-computer interaction, and decades of programming tool design — that **spatial representations help people understand structure**. When elements are placed meaningfully in space — grouped, aligned, oriented — we can spot patterns, detect errors, and reason more effectively. This idea shows up in research from Barbara Tversky, Larkin & Simon, and in the design of tools like Alloy and Scratch. 

`sPyTial` gives you that kind of spatial layout **by default**. When you visualize a Python object, the diagram reflects how the parts are connected, not just how they're stored. You get:
- A **box-and-arrow diagram** that shows the shape of your data
- A layout that follows cognitive and structural conventions
- A tool that knows when something doesn't make sense

## Quick Start

```python
import spytial

# Visualize any Python object
data = {
    'name': 'root',
    'children': [
        {'value': 1},
        {'value': 2},
        {'value': 3}
    ]
}

# Opens in browser or inline if in a jupyter notebook.
spytial.diagram(data)

# Or save to file
spytial.diagram(data, method='file')
```

## Documentation

User-facing documentation is available at https://sidprasad.github.io/spytial/ and is generated with MkDocs from the codebase and Markdown guides.


## License
This project is licensed under the MIT License. See the LICENSE file for details.


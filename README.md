# sPyTial: Lightweight Diagrams for Structured Python Data

Sometimes you just want to see your data.

You’re working with a tree, a graph, a recursive object -- maybe an AST, a neural network, or a symbolic term. You don’t need an interactive dashboard or a production-grade visualization system. You just need a diagram, something that lays it out clearly so you can understand what’s going on.

That’s what `sPyTial` is for. It’s designed for developers, educators, and researchers who work with structured data and need to make that structure visible — to themselves or to others — with minimal effort. 

## Why Spatial Representation Matters

There’s strong evidence — from cognitive science, human-computer interaction, and decades of programming tool design — that **spatial representations help people understand structure**. When elements are placed meaningfully in space — grouped, aligned, oriented — we can spot patterns, detect errors, and reason more effectively. This idea shows up in research from Barbara Tversky, Larkin & Simon, and in the design of tools like Alloy and Scratch. 

`sPyTial` gives you that kind of spatial layout **by default**. When you visualize a Python object, the diagram reflects how the parts are connected, not just how they're stored. You get:
- A **box-and-arrow diagram** that shows the shape of your data
- A layout that follows cognitive and structural conventions
- A tool that knows when something doesn't make sense


## Diagramming by Refinement

The default diagrams are often enough. But when they’re not, you can refine them; not by writing rendering code, but by annotating your data with **layout constraints**. These annotations are deeply integrated into the language:

```python
from spytial import diagram, orientation

@orientation("left", selector="left")
@orientation("right", selector="right")
class Node:
    def __init__(self, val, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

tree = Node(1, Node(2), Node(3))
diagram(tree)
```

This adds meaning to the diagram: left children go to the left, right children to the right. You don’t have to describe the layout explicitly — the constraints are declared with the data. Other annotations include grouping, cyclic structure, and more. All are optional. You can start small, then add structure as needed.

## Surfacing Errors Through Layout

`sPyTial` works bycompiling to the [Cope and Drag](https:/www.siddharthaprasad.com/copeanddrag) formal methods diagramming language.
This means, that you get the benefits of formal reasoning for free. One of the most useful effects of this is what happens when the constraints can’t be satisfied. If your data structure is malformed (e.g., your tree has a loop) sPyTial won’t quietly draw something misleading. It will tell you: this layout is unsatisfiable, and *here's why*.

This acts like a type checker for spatial meaning. You don’t just see the structure. You see when the structure is wrong.


## Configurable Visualization Size

The visualization container size is automatically optimized based on object complexity and display context, with sensible defaults. You can also customize the display size according to your needs:

```python
from spytial import diagram

# Use automatic sizing (recommended)
diagram(my_object)

# Customize the size if needed
diagram(my_object, width=1200, height=900)

# For compact displays
diagram(my_object, width=400, height=300)
```

The automatic sizing considers:
- Object complexity (number of attributes, nested structures)
- Display method (Jupyter notebooks use more conservative sizing)
- Reasonable bounds (400-1600px width, 300-1200px height)

## Limitations
- Does not handle functions, modules, or file handles.
- Limited support for custom serialization methods like `__reduce__` or `__getstate__`.
- Performance may degrade for very large or deeply nested objects.

## TODO:
- Need to add tests for the annotations and provider systems E.g. how annotations become objects / yaml.
- Figure out the constraint conflict story here.
- Figure out guarding of things w/ their nodes. Like the self type should be got from the cnd annotation somehow? Can we have some templating / allow default top type in squery lang.
- Documentation and demos.
- Hiding flags.

## License
This project is licensed under the MIT License. See the LICENSE file for details.


### Issues

- Selectors are really hard to write with no evaluator, and we get sort of minimal feedback here :(
- I don't like the demos of use (which I asked CoPilot to generate)
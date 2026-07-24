# Spytial


Often, all that is needed is a clear picture of a program's values. An
interactive dashboard or a production-grade visualization system is not
required. A diagram that lays the values out clearly is enough to show what is
happening.

Spytial is built for this. It is a diagramming system that makes a diagram as
easy to get as a call to `print`.

Every value gets a diagram by default. Spytial's constraint vocabulary then
refines that diagram until it matches the expected result.

[Get started](getting-started.md){ .md-button .md-button--primary }
[Try it in the browser](playground/index.html){ .md-button }

<div class="sp-hero" markdown="1">

<div class="sp-code" markdown="1">

```python
from spytial import orientation, attribute, hideAtom, flag, diagram

@orientation(selector='{ x : TreeNode, y : TreeNode | x.left = y }', directions=['below', 'left'])
@orientation(selector='{ x : TreeNode, y : TreeNode | x.right = y }', directions=['below', 'right'])
@attribute(field='value')
@hideAtom(selector='NoneType')
@flag(name="hideDisconnected")
class TreeNode:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right

root = TreeNode(
    value=10,
    left=TreeNode(value=5, left=TreeNode(3), right=TreeNode(7)),
    right=TreeNode(value=15, left=TreeNode(12), right=TreeNode(18)),
)

diagram(root)
```

</div>

<div class="sp-viz">
  <iframe src="assets/hero-tree.html" title="A binary tree rendered by Spytial" loading="lazy"></iframe>
  <div class="sp-cap">↑ The live output of the code above. Drag to explore, and scroll to zoom.</div>
</div>

</div>

## Get started

1. **Install**: `pip install spytial-diagramming` (Python 3.8 to 3.12, with
   nothing else to set up).
2. **Decorate**: add layout rules to a class with decorators such as
   `@orientation` and `@attribute`.
3. **Draw**: call `spytial.diagram(obj)`. It opens in the browser, or renders
   inline in a notebook.

That is the whole loop. [Walk through the example above, line by line.](getting-started.md)

## Operations at a glance

Layout is controlled by two kinds of operation. Attach them as class decorators
(`@spytial.orientation(...)`), attach them to individual objects, or apply them
through `typing.Annotated`. Full details and arguments are in
[Operations](operations.md).

<div class="sp-ops" markdown="1">

<div markdown="1">

**Constraints**: shape the geometry

| Operation | What it does |
| --- | --- |
| `orientation` | Place a field's target in a direction (`below`, `left`, …) |
| `align` | Line selected nodes up on a shared axis |
| `cyclic` | Arrange selected nodes in a ring |
| `group` | Enclose selected nodes in a labelled region |

</div>

<div markdown="1">

**Directives**: change how things are drawn

| Operation | What it does |
| --- | --- |
| `attribute` | Show a field as a label inside the node |
| `atomStyle` · `edgeStyle` | Style nodes and edges (border, fill, line, labels) |
| `hideAtom` · `hideField` | Hide nodes and fields |
| `tag` | Add a computed label to matching nodes |
| `inferredEdge` | Draw a derived edge between nodes |
| `size` · `icon` | Resize nodes, or add an icon |

</div>

</div>

## More

- [Playground](playground/index.html): edit and run Spytial in the browser.
- [Getting Started](getting-started.md): install and a walkthrough.
- [Operations](operations.md): every constraint and directive.
- [`spytial-clrs`](https://github.com/sidprasad/spytial-clrs): more examples,
  the CLRS data structures rendered with Spytial.

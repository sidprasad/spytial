# Editor (Structured Input)

`spytial.edit()` is the interactive counterpart to [`spytial.diagram()`](diagramming.md). Where `diagram()` *shows* a value, `edit()` lets you *build or change* one visually and hand it back to Python — for **any** value, not just dataclasses.

## The live editor

```python
from dataclasses import dataclass
from typing import Optional
import spytial

@dataclass
class TreeNode:
    value: int = 0
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None

ed = spytial.edit(TreeNode())   # cell 1 — shows the editor inline
ed
```

Edit the structure visually, then read the result in a later cell:

```python
result = ed.value   # cell 2 — a fresh TreeNode reified from the current state
```

`.value` reflects the editor's current state **each time you read it** — there is no commit step, and the value you passed in is never mutated. (Reading `spytial.edit(x).value` on a single line just returns the initial state — there was no chance to edit; use two cells.)

`edit()` returns an [`Editor`][spytial.structured_input.Editor] widget and requires `anywidget` + a Jupyter kernel.

### Any value, not just dataclasses

`edit()` accepts whatever `diagram()` accepts:

```python
spytial.edit({"a": 1, "items": [1, 2, 3]})   # dict
spytial.edit([{"x": 1}, {"x": 2}])            # list
spytial.edit(my_graph_node)                    # an arbitrary object (cycles ok)
```

When the seed is a dataclass, declared field defaults are filled for any field an edit may have dropped. For other values, reconstruction uses the general path (builtins rebuild as themselves; arbitrary classes rebuild via their import path).

### React to every edit

```python
ed.on_change(lambda tree: print("valid BST?", is_valid_bst(tree)))
```

## Reify directly

If you already have a data instance (e.g. from `build_instance`, a saved file, or the editor) you can reconstruct the object without the widget:

```python
di  = spytial.CnDDataInstanceBuilder().build_instance(my_value)
obj = spytial.reify(di)            # inverse of build_instance
txt = spytial.replit(di)           # repr() of what reify() would return
```

`reify()` handles builtins, arbitrary classes, and cyclic structures.

## Kernel-free / pyodide path

`spytial.edit_html()` renders the same editor as standalone HTML (no kernel required) and uses the built-in **Export** button to copy constructor code. It also accepts any value.

```python
spytial.edit_html(TreeNode())                 # inline iframe / browser tab
spytial.edit_html({"a": 1}, method="browser")
spytial.edit_html([1, 2, 3], method="file")
```

## Naming note

This module was previously `dataclass_builder` and was dataclass-only: the widget was `DataClassBuilder` and the HTML helper was `dataclass_builder()`. It now lives in `spytial.structured_input` and accepts any value; the current names are `Editor` / `edit()` (live widget) and `edit_html()` (standalone HTML). The old `DataClassBuilder` / `dataclass_builder()` names were removed.

!!! tip
    For large structures, start from a minimal seed (`TreeNode()`, `{}`, `[]`) and build up visually before reading `.value`.

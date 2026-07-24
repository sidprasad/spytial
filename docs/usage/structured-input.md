# Structured Input

`spytial.edit()` is the interactive counterpart to [`spytial.diagram()`](diagramming.md). `diagram()` shows a value. `edit()` builds or changes a value visually and returns it to Python. `edit()` accepts any value, not only dataclasses.

## edit(): edit, click Done, get the value back

```python
from dataclasses import dataclass
from typing import Optional
import spytial

@dataclass
class TreeNode:
    value: int = 0
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None

result = spytial.edit(TreeNode())   # opens the editor; blocks until Done is clicked
```

`edit()` serves the editor as a page. The page appears inline in a local Jupyter cell, or in a browser tab from a script. `edit()` blocks until the user clicks **Done** (or **Cancel**). `edit()` then reconstructs a fresh Python object with [`reify`](#reify-directly) and returns it. `edit()` does not mutate the input value.

`edit()` uses no Jupyter comm and no widget framework. `edit()` uses only the standard library and a browser. `edit()` cannot hang the kernel. If the editor never connects, stops responding, or the user closes it, `edit()` unblocks and returns per `on_cancel`. In pyodide and hosted notebooks (Colab, JupyterHub, Binder), the browser cannot reach the local server. In this case, `edit()` prints a note, shows [`edit_html()`](#standalone-html-no-server) (Export button) instead, and returns `None`.

### Any value, not just dataclasses

`edit()` accepts whatever `diagram()` accepts:

```python
spytial.edit({"a": 1, "items": [1, 2, 3]})   # dict
spytial.edit([{"x": 1}, {"x": 2}])            # list
spytial.edit(my_graph_node)                    # an arbitrary object (cycles ok)
```

When the seed is a dataclass, declared field defaults fill any field that the round-trip dropped. Other values reconstruct through the general path: builtins rebuild as themselves, and arbitrary classes rebuild through their import path.

### Cancelling

Click **Cancel**, close the tab, or interrupt the kernel. `edit()` then returns per `on_cancel`:

```python
spytial.edit(x)                      # -> the original x, unchanged (default: on_cancel="seed")
spytial.edit(x, on_cancel="none")    # -> None
spytial.edit(x, on_cancel="raise")   # -> raises spytial.EditCancelled
```

The default `"seed"` keeps `edit()` total. A call always returns a usable value of the same kind. `None` is reserved for the case where the committed value really is `None`.

## Reify directly

If a data instance already exists (from `build_instance`, a saved file, or the editor), reconstruct the object without the UI:

```python
di  = spytial.CnDDataInstanceBuilder().build_instance(my_value)
obj = spytial.reify(di)            # inverse of build_instance
txt = spytial.replit(di)           # repr() of what reify() would return
```

`reify()` handles builtins, arbitrary classes, and cyclic structures.

## Standalone HTML (no server)

`spytial.edit_html()` renders the editor as standalone HTML. It uses the built-in **Export** button to copy constructor code. This function is useful where the local server is not reachable (for example, pyodide). `edit_html()` also accepts any value.

```python
spytial.edit_html(TreeNode())                 # inline iframe (notebook), else a browser tab
spytial.edit_html({"a": 1}, method="browser") # force a browser tab
spytial.edit_html([1, 2, 3], method="inline") # force an inline iframe
```

## Naming note

This module was previously named `dataclass_builder` and supported dataclasses only (a `DataClassBuilder` anywidget widget and a `dataclass_builder()` HTML helper). The module now lives in `spytial.structured_input`, accepts any value, and exposes two verbs: `edit()` (open editor, return the value on Done) and `edit_html()` (standalone HTML). The old `DataClassBuilder` and `dataclass_builder()` names and the anywidget widget were removed.

!!! tip
    Start from a minimal seed (`TreeNode()`, `{}`, `[]`). Build the value visually before clicking **Done**.

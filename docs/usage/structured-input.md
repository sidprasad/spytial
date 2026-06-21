# Structured Input

`spytial.edit()` is the interactive counterpart to [`spytial.diagram()`](diagramming.md). Where `diagram()` *shows* a value, `edit()` lets you *build or change* one visually and hand it back to Python — for **any** value, not just dataclasses.

## edit() — edit, click Done, get the value back

```python
from dataclasses import dataclass
from typing import Optional
import spytial

@dataclass
class TreeNode:
    value: int = 0
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None

result = spytial.edit(TreeNode())   # opens the editor, blocks until you click Done
```

`edit()` serves the editor as a page — inline in a local Jupyter cell, or a browser tab from a script — **blocks** until you click **Done** (or **Cancel**), then reconstructs a fresh Python object with [`reify`](#reify-directly) and returns it. The value you passed in is never mutated.

No Jupyter comm and no widget framework — only the standard library and a browser. It can't hang your kernel: if the editor never connects, stops responding, or you close it, `edit()` unblocks and returns per `on_cancel`. In **pyodide** and **hosted notebooks** (Colab, JupyterHub, Binder) the browser can't reach the local server, so `edit()` prints a note, shows [`edit_html()`](#standalone-html-no-server) (Export button) instead, and returns `None`.

### Any value, not just dataclasses

`edit()` accepts whatever `diagram()` accepts:

```python
spytial.edit({"a": 1, "items": [1, 2, 3]})   # dict
spytial.edit([{"x": 1}, {"x": 2}])            # list
spytial.edit(my_graph_node)                    # an arbitrary object (cycles ok)
```

When the seed is a dataclass, declared field defaults fill for any field the round-trip dropped. Other values reconstruct via the general path (builtins rebuild as themselves; arbitrary classes via their import path).

### Cancelling

Click **Cancel**, close the tab, or interrupt the kernel, and `edit()` returns per `on_cancel`:

```python
spytial.edit(x)                      # -> the original x, unchanged (default: on_cancel="seed")
spytial.edit(x, on_cancel="none")    # -> None
spytial.edit(x, on_cancel="raise")   # -> raises spytial.EditCancelled
```

Defaulting to `"seed"` keeps `edit()` total — you always get back a usable value of the same kind, and `None` is reserved for "the committed value really is `None`."

## Reify directly

If you already have a data instance (from `build_instance`, a saved file, or the editor) you can reconstruct the object without the UI:

```python
di  = spytial.CnDDataInstanceBuilder().build_instance(my_value)
obj = spytial.reify(di)            # inverse of build_instance
txt = spytial.replit(di)           # repr() of what reify() would return
```

`reify()` handles builtins, arbitrary classes, and cyclic structures.

## Standalone HTML (no server)

`spytial.edit_html()` renders the editor as standalone HTML and uses the built-in **Export** button to copy constructor code — handy where the local server isn't reachable (e.g. pyodide). It also accepts any value.

```python
spytial.edit_html(TreeNode())                 # inline iframe (notebook), else a browser tab
spytial.edit_html({"a": 1}, method="browser") # force a browser tab
spytial.edit_html([1, 2, 3], method="inline") # force an inline iframe
```

## Naming note

This module was previously `dataclass_builder` and was dataclass-only (a `DataClassBuilder` anywidget widget + a `dataclass_builder()` HTML helper). It now lives in `spytial.structured_input`, accepts any value, and exposes just two verbs: `edit()` (open editor, return the value on Done) and `edit_html()` (standalone HTML). The old `DataClassBuilder` / `dataclass_builder()` names and the anywidget widget were removed.

!!! tip
    Start from a minimal seed (`TreeNode()`, `{}`, `[]`) and build up visually before clicking **Done**.

# Editor (Structured Input)

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

`edit()` serves the editor as a page — inline in a Jupyter cell, or a browser tab from a script — **blocks** until you click **Done** (or **Cancel**), then reconstructs a fresh Python object with [`reify`](#reify-directly) and returns it. The value you passed in is never mutated.

No Jupyter comm and no `anywidget` — only the standard library and a browser. (v1 targets local scripts and a **local** Jupyter kernel; hosted notebooks like Colab are a follow-up.)

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
spytial.edit(x)                      # -> None on cancel (default)
spytial.edit(x, on_cancel="seed")    # -> the original x, unchanged
spytial.edit(x, on_cancel="raise")   # -> raises spytial.EditCancelled
```

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
spytial.edit_html(TreeNode())                 # inline iframe / browser tab
spytial.edit_html({"a": 1}, method="browser")
spytial.edit_html([1, 2, 3], method="file")
```

## Naming note

This module was previously `dataclass_builder` and was dataclass-only: the widget was `DataClassBuilder` and the HTML helper was `dataclass_builder()`. It now lives in `spytial.structured_input` and accepts any value; the current names are `edit()` (open editor, return the value on Done) and `edit_html()` (standalone HTML). The old `DataClassBuilder` / `dataclass_builder()` names were removed.

!!! tip
    Start from a minimal seed (`TreeNode()`, `{}`, `[]`) and build up visually before clicking **Done**.

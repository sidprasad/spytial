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

`edit()` serves the editor as a page. The page appears inline in a local Jupyter cell, or in a browser tab from a script. `edit()` blocks until the user clicks **Done** (or **Cancel**). `edit()` then reconstructs the represented value with [`reify`](#reify-directly) and returns it. Containers and ordinary instances are rebuilt; named references can resolve to existing objects.

`edit()` uses no Jupyter comm and no widget framework. `edit()` uses only the standard library and a browser. `edit()` cannot hang the kernel. If the editor never connects, stops responding, or the user closes it, `edit()` unblocks and returns per `on_cancel`. In pyodide and hosted notebooks (Colab, JupyterHub, Binder), the browser cannot reach the local server. In this case, `edit()` prints a note, shows [`edit_html()`](#standalone-html-no-server) (Export button) instead, and returns `None`.

### Any value, not just dataclasses

`edit()` accepts whatever `diagram()` accepts:

```python
spytial.edit({"a": 1, "items": [1, 2, 3]})   # dict
spytial.edit([{"x": 1}, {"x": 2}])            # list
spytial.edit(my_graph_node)                    # an arbitrary object (cycles ok)
```

When the seed is a dataclass, the editor registers reifiers that apply declared
field defaults before restoring recorded values. Other values use the general
reification path. Reconstruction support varies by type; accepting a value
for diagramming does not guarantee a lossless round trip. See
[Python Type Coverage](../reference/python-types.md).

### Cancelling

Click **Cancel**, close the tab, or interrupt the kernel. `edit()` then returns per `on_cancel`:

```python
spytial.edit(x)                      # -> the original x, unchanged (default: on_cancel="seed")
spytial.edit(x, on_cancel="none")    # -> None
spytial.edit(x, on_cancel="raise")   # -> raises spytial.EditCancelled
```

The default `"seed"` returns the original input on cancellation. This policy
does not prevent errors or information loss when reconstructing a committed
value. The `"none"` policy can return `None` for cancellation as well as for a
committed Python `None` value.

## Reify directly

If a data instance already exists (from `build_instance`, a saved file, or the editor), reconstruct the object without the UI:

```python
di  = spytial.CnDDataInstanceBuilder().build_instance(my_value)
obj = spytial.reify(di)            # reconstruct the represented value
txt = spytial.replit(di)           # repr() of what reify() would return
```

`reify()` rebuilds supported builtins and class instances, preserves many
shared references and cycles, and resolves named references. Unsupported
types can produce attribute proxies, incomplete objects, or exceptions.
See [Reification](../reference/reification.md) for the procedure, compatibility
mechanisms, and known failures.

Reconstruction does not use `IAtom.metadata`. Its current host-specific hints
and the remaining work on relation identity and portable reconstruction are
described in the [reification design note](../reification-design.md).

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

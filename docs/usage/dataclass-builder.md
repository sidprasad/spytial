# Dataclass Builder

`spytial.dataclass_builder()` opens an interactive builder for a dataclass instance. It lets you visually edit the structure and export the resulting constructor code.

## Example

```python
from dataclasses import dataclass
from typing import Optional
import spytial

@dataclass
class TreeNode:
    value: int = 0
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None

# Start with an empty instance
spytial.dataclass_builder(TreeNode())
```

## What it expects

The builder requires a dataclass instance, not a class object. Pass `TreeNode()` rather than `TreeNode`.

## Output methods

```python
spytial.dataclass_builder(TreeNode(), method="browser")
spytial.dataclass_builder(TreeNode(), method="file")
spytial.dataclass_builder(TreeNode(), method="inline")
```

## Typical workflow

1. Start with a minimal dataclass instance.
2. Open the builder.
3. Edit the structure in the UI.
4. Use **Export** to copy the generated constructor code back into your Python code.

!!! tip
    For large models, start with a minimal instance and build up visually before exporting the final constructor.

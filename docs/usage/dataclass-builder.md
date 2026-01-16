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

## Methods

```python
spytial.dataclass_builder(TreeNode(), method="browser")
spytial.dataclass_builder(TreeNode(), method="file")
spytial.dataclass_builder(TreeNode(), method="inline")
```

## Output

Use the **Export** button in the UI to copy the generated Python constructor code. Paste it back into your codebase to recreate the edited structure.

!!! tip
    For large models, start with a minimal instance and build up visually before exporting the final constructor.

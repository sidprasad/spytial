# Sequences of Diagrams

```
Sequence functionality is very much experimental.
```

`spytial.sequence()` records a series of snapshots of a data structure. It plays the snapshots back as an interactive step-by-step visualization. The function is designed for two use cases:

- **Algorithm tracing**. Call `.record()` inside an algorithm as each step completes.
- **Temporal snapshots**. Record a structure at multiple points in time.

## Basic usage

```python
import spytial

with spytial.sequence(sequence_policy="stability") as seq:
    seq.record({"count": 0, "items": ["a"]})
    seq.record({"count": 1, "items": ["a", "b"]})
    seq.record({"count": 2, "items": ["b"]})
seq.diagram()
```

`sequence()` returns a `SequenceRecorder`. Each `.record(obj)` call captures the current state of `obj` as the next frame. `.diagram()` renders all frames into an interactive viewer with Previous / Next navigation.

## Labelling steps

`record()` accepts two optional keyword arguments that give frames semantic meaning in the viewer:

- `label`. A short single line shown in the status bar (`Step 3 / 24, rotate left at node 5`) and as the scrubber tooltip. Whitespace is stripped. The label is truncated to 200 characters.
- `note`. A longer description (multiple lines permitted) shown in a collapsible panel below the controls. The note is hidden on frames where no note was recorded.

```python
with spytial.sequence() as seq:
    seq.record(tree, label="initial state")
    rotate_left(tree, node)
    seq.record(tree, label="left-rotate at root",
               note="Promotes the right child so the new tree is height-balanced.")
    seq.record(tree)  # no label and no note; viewer falls back to "Step 3 / 3"
seq.diagram()
```

Both arguments are optional and independent. A frame can have a label, a note, both, or neither. The form with no keyword arguments (`seq.record(obj)`) continues to work unchanged.

This method is recommended to narrate algorithms. A typical pattern wraps `record()` in a helper that takes the label as its first argument:

```python
class RBTree:
    def __init__(self, seq):
        self._seq = seq
        self.root = NIL

    def _snap(self, label):
        self._seq.record(self.root, label=label)

    def insert(self, key):
        ...
        self._snap(f"BST insert: {key} (color=RED)")
        self._insert_fixup(z)
```

See [`demos/balancing.ipynb`](https://github.com/sidprasad/spytial/blob/main/demos/balancing.ipynb) for a full Red-Black tree example with labelled fixup cases.

## Sequence policies

The `sequence_policy` controls how the frontend positions atoms across frames:

| Policy | Behaviour |
|---|---|
| `stability` | Atoms stay anchored to their previous position (default for sequences) |
| `change_emphasis` | Changed atoms are visually highlighted |
| `ignore_history` | Each frame is laid out independently |
| `random_positioning` | Random placement each frame |

The `sequence_policy=` argument sets the **initial** policy. Viewers can switch policy with a dropdown in the header. This switch helps to compare how each policy presents the same algorithm. A switch mid-sequence re-applies the previous to current transition with the new policy. On step 0, which has no transition, the change takes effect on the next navigation.

## In-place mutation (most common)

When the **same Python objects** are mutated between frames, atom IDs are stable automatically. No configuration is needed. The recorder uses a single shared builder with a persistent ID table. The table survives across `.record()` calls.

```python
class Node:
    def __init__(self, val, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

root = Node(5, Node(3), Node(7))

with spytial.sequence(sequence_policy="stability") as seq:
    seq.record(root)
    root.val = 99          # mutate in place
    seq.record(root)
    root.left.val = 11
    seq.record(root)
seq.diagram()
```

This pattern works well for BST insertion, sorting algorithms, and graph BFS/DFS. It works for any algorithm that operates on a shared mutable structure.

## Snapshot / deepcopy workflow

If each frame is a fresh object (e.g. `copy.deepcopy`), pass `identity=` so the recorder can match conceptually equivalent nodes across frames. The callable receives each object and should return a stable string key or `None`.

```python
import copy, spytial

snapshots = [copy.deepcopy(root) for _ in range(3)]

with spytial.sequence(
    identity=lambda obj: str(obj.node_id) if hasattr(obj, "node_id") else None,
    sequence_policy="stability",
) as seq:
    for snap in snapshots:
        seq.record(snap)
seq.diagram()
```

`identity` shall return a `str` or `None`. Objects that share the same key across frames are rendered as the same atom and animated smoothly between positions.

## Passing `as_type`

Class-level spatial annotations can be applied to every recorded object via `as_type`:

```python
seq = spytial.sequence(as_type=MyAnnotatedType, sequence_policy="stability")
```

## Display options

```python
seq.diagram()                    # auto-detect (inline in Jupyter, browser otherwise)
seq.diagram(method="file")       # save as spytial_sequence_visualization.html
seq.diagram(method="browser")    # open in a new browser tab
seq.diagram(method="inline")     # force Jupyter inline output
seq.diagram(width=1200, height=800, title="My algorithm")
```

Defaults can also be set at construction time and overridden at render time:

```python
seq = spytial.sequence(method="file", auto_open=False)
# ... record frames ...
seq.diagram(title="Final render")
```

## Using without a context manager

`SequenceRecorder` does not require `with`. The context manager is only a readability convention. `__exit__` does nothing special.

```python
seq = spytial.sequence(sequence_policy="stability")
tree.insert(seq, 42)   # tree passes seq around internally and calls seq.record()
seq.diagram()
```

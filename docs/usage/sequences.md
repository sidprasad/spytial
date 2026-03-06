# Sequences of Diagrams

`spytial.sequence()` lets you record a series of snapshots of a data structure and play them back as an interactive step-by-step visualization. It is designed for two use cases:

- **Algorithm tracing** — call `.record()` inside an algorithm as each step completes.
- **Temporal snapshots** — record a structure at multiple points in time.

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

## Sequence policies

The `sequence_policy` controls how the frontend positions atoms across frames:

| Policy | Behaviour |
|---|---|
| `stability` | Atoms stay anchored to their previous position (default for sequences) |
| `change_emphasis` | Changed atoms are visually highlighted |
| `ignore_history` | Each frame is laid out independently |
| `random_positioning` | Random placement each frame |

## In-place mutation (most common)

When the **same Python objects** are mutated between frames, atom IDs are stable automatically — no configuration needed. The recorder uses a single shared builder whose persistent ID table survives across `.record()` calls.

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

This pattern works well for BST insertion, sorting algorithms, graph BFS/DFS — any algorithm that operates on a shared mutable structure.

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

`identity` must return a `str` or `None`. Objects that share the same key across frames are rendered as the same atom and animated smoothly between positions.

## Passing `as_type`

You can apply class-level spatial annotations to every recorded object via `as_type`:

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

You can also set defaults at construction time and override at render time:

```python
seq = spytial.sequence(method="file", auto_open=False)
# ... record frames ...
seq.diagram(title="Final render")
```

## Using without a context manager

`SequenceRecorder` does not require `with`. The context manager is purely a readability convention — `__exit__` does nothing special.

```python
seq = spytial.sequence(sequence_policy="stability")
tree.insert(seq, 42)   # tree passes seq around internally and calls seq.record()
seq.diagram()
```

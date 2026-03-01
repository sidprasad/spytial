# Planned Features

## Future: Live Sequence Viewer

`diagramSequence()` is the finite snapshot player for `spytial-py`. It should stay focused on rendering an explicit list of states with a sequence policy.

A future live-view API should be separate rather than overloading `diagramSequence()`.

### Proposed API sketch

```python
diagramLive(
    source,
    sequence_policy="stability",
    interval=0.5,
    method=None,
    auto_open=True,
    width=None,
    height=None,
    title=None,
)
```

### Candidate source models

- Polling callable that returns the current object snapshot
- Push-based handle or callback that supplies updates
- Notebook-specific transport later if richer interactive plumbing is needed

### Notes

- Live view is not implemented in the current change.
- For a true live view, default identity can usually follow live Python object identity when the same objects mutate over time.
- If the live source rebuilds fresh snapshots rather than mutating the same objects, explicit identity hooks may still be necessary.

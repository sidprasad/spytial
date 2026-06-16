# Authoring Workflow

Use this workflow to integrate sPyTial in a way that stays fast to iterate and easy to maintain.

## 1. Start with a serialization checkpoint

Use `evaluate()` before layout tuning:

```python
import spytial

spytial.evaluate(obj)
spytial.diagram(obj)
```

`evaluate()` confirms atoms/relations. `diagram()` confirms layout.

## 2. Choose output mode intentionally

- Notebook workflows: prefer default/`inline`.
- Script + local debugging: prefer `browser`.
- CI/docs artifacts: prefer `file` and commit generated screenshots only if needed.

```python
spytial.diagram(obj, method="browser")
spytial.diagram(obj, method="file", auto_open=False)
```

## 3. Layer operations gradually

Apply operations in this order unless a use case requires otherwise:

1. Structural constraints: `orientation`, `align`, `group`
2. Visibility controls: `hideField`, `hideAtom`
3. Readability directives: `attribute`, `tag`, `edgeColor`, `atomColor`
4. Derived edges: `inferredEdge`

After each layer, rerun `evaluate()` or inspect diagram output before adding more.

## 4. Sequence diagrams: decide identity policy early

Use `diagramSequence()` for state transitions.

- Reused mutable objects across frames: often no identity hook needed.
- Rebuilt objects per frame: pass `identity=...` to stabilize IDs.

```python
spytial.diagramSequence(
    states,
    sequence_policy="stability",
    identity=lambda obj: obj.id if hasattr(obj, "id") else None,
)
```

## 5. Introduce custom relationalizers only if built-ins miss semantics

Built-ins already cover primitives, `dict`/`list`/`tuple`/`set`, dataclasses, and generic objects.
Use a custom relationalizer when domain meaning is not captured.

Use priority `>=100` for custom relationalizers.

## 6. Acceptance checklist

- `evaluate()` output matches expected domain structure.
- Diagram uses at least one intentional structure cue (direction, alignment, grouping, or inferred edge).
- Selectors are valid and readable.
- Output mode matches user context (notebook/script/CI).
- If sequence: identity behavior is explicit and stable.

# Relationalizer Workflow

Use this only when built-in relationalizers cannot express domain semantics cleanly.

## Decision rule

Implement a custom relationalizer when at least one is true:

- Built-in output merges concepts that should be separate node types.
- Required domain edges do not exist in serialized output.
- You need stable, explicit IDs/labels not derivable from defaults.

Stay with built-ins when you only need visual/layout tuning.

## Minimal implementation

```python
from spytial import RelationalizerBase, relationalizer, Atom, Relation

@relationalizer(priority=100)
class WidgetRelationalizer(RelationalizerBase):
    def can_handle(self, obj):
        return hasattr(obj, "widget_id")

    def relationalize(self, obj, walker_func):
        widget_atom = Atom(
            id=f"widget:{obj.widget_id}",
            type="Widget",
            label=getattr(obj, "name", str(obj.widget_id)),
        )
        rels = []
        if getattr(obj, "parent", None) is not None:
            parent_id = walker_func._get_id(obj.parent)
            rels.append(Relation(name="parent", tuples=[(widget_atom.id, parent_id)]))
        return [widget_atom], rels
```

## Required checks

1. Import path registers class (decorator executes on import).
2. Priority is `>=100` (built-ins reserve lower range).
3. `spytial.evaluate(sample)` shows expected atoms/relations.
4. `spytial.diagram(sample)` renders without missing-edge surprises.

## Common mistakes

- Implementing relationalizer when selectors/operations were enough.
- Returning unstable IDs across runs, breaking sequence/view consistency.
- Skipping `evaluate()` and debugging only in diagram view.
- Forgetting to import module containing the decorated class.

## Handoff expectations

When adding a custom relationalizer, include:

- Why built-ins were insufficient.
- Chosen atom types and relation names.
- One or two selectors that rely on the new relations.

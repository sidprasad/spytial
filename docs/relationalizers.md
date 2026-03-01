# Custom Relationalizers

Relationalizers are plug-ins that teach sPyTial how to serialize your custom objects into atoms and relations.

## When to use a relationalizer

Use a relationalizer when:

- you want fine-grained control over how an object becomes nodes and edges
- your objects are not handled well by the built-in defaults
- you need domain-specific relations such as `depends_on` or `flows_to`

## Anatomy of a relationalizer

A relationalizer inherits from `RelationalizerBase` and implements two methods:

- `can_handle(obj)` returns `True` when the relationalizer should handle the object
- `relationalize(obj, walker_func)` returns `Atom` and `Relation` instances

```python
from spytial import RelationalizerBase, relationalizer, Atom, Relation

@relationalizer(priority=100)
class WidgetRelationalizer(RelationalizerBase):
    def can_handle(self, obj):
        return hasattr(obj, "widget_id")

    def relationalize(self, obj, walker_func):
        atom = Atom(
            id=f"widget:{obj.widget_id}",
            type="Widget",
            label=obj.label,
        )
        return [atom], []
```

## Built-in coverage first

Before you write a custom relationalizer, check whether the built-ins already cover your case. `spytial-py` already ships relationalizers for:

- primitives
- `dict`, `list`, `tuple`, and `set`
- dataclasses
- generic Python objects as a fallback

Most examples in `spytial-clrs` work without custom relationalizers because regular Python objects plus operations are usually enough.

## Priorities

Relationalizers with higher priorities are checked first. Priorities from **0-99** are reserved for built-ins, so custom relationalizers should use **100 or higher**.

## Registering and inspecting

The `@relationalizer` decorator registers the class automatically when the module is imported. You can inspect the active registry like this:

```python
from spytial import RelationalizerRegistry

print(RelationalizerRegistry.list_relationalizers())
```

## Next steps

Once your relationalizer is in place, use `spytial.evaluate()` first to validate the emitted structure, then `spytial.diagram()` to tune layout and directives.

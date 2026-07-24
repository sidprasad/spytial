# Custom Relationalizers


> Custom relationalizers are a work in progress.

Relationalizers are plug-ins. They define how Spytial serializes custom
objects into atoms and relations.

## When to use a relationalizer

Use a relationalizer when:

- fine-grained control over how an object becomes nodes and edges is
  necessary
- the built-in defaults do not handle the objects well
- domain-specific relations such as `depends_on` or `flows_to` are
  necessary

## Anatomy of a relationalizer

A relationalizer inherits from `RelationalizerBase` and implements two methods:

- `can_handle(obj)` returns `True` when the relationalizer can handle the object
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

Before writing a custom relationalizer, check whether the built-ins cover
the case. `spytial-py` includes relationalizers for:

- primitives
- `dict`, `list`, `tuple`, and `set`
- dataclasses
- generic Python objects as a fallback

Most examples in `spytial-clrs` work without custom relationalizers.
Regular Python objects plus operations are usually enough.

## Priorities

Spytial checks relationalizers with higher priority first. The built-ins
reserve priorities **0 to 99**. Custom relationalizers should use
**100 or higher**.

## Registering and inspecting

The `@relationalizer` decorator registers the class automatically when the
module is imported. The active registry can be inspected as follows:

```python
from spytial import RelationalizerRegistry

print(RelationalizerRegistry.list_relationalizers())
```

## Next steps

After the relationalizer is in place, use `spytial.evaluate()` first to
validate the emitted structure. Then use `spytial.diagram()` to adjust
layout and directives.

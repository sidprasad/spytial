# Custom Relationalizers

Relationalizers are plug-ins that teach sPyTial how to serialize your custom objects into atoms and relations.

## When to use a relationalizer

Use a relationalizer when:

- You want fine-grained control of how an object becomes nodes and edges.
- Your objects are not handled well by the built-in defaults.
- You need to emit domain-specific relations (e.g., `"depends_on"`, `"flows_to"`).

## Anatomy of a relationalizer

A relationalizer is a class that inherits from `RelationalizerBase` and implements two methods:

- `can_handle(obj)` — return `True` when the relationalizer should handle the object.
- `relationalize(obj, builder)` — return `Atom` and `Relation` instances for the object.

```python
from spytial import RelationalizerBase, relationalizer, Atom, Relation

@relationalizer(priority=100)
class WidgetRelationalizer(RelationalizerBase):
    def can_handle(self, obj):
        return hasattr(obj, "widget_id")

    def relationalize(self, obj, builder):
        atom = Atom(
            id=f"widget:{obj.widget_id}",
            type="Widget",
            name=obj.widget_id,
            attrs={"label": obj.label},
        )
        return [atom], []
```

## Priorities

Relationalizers with higher priorities are checked first. Priorities from **0–99** are reserved for built-ins, so custom relationalizers should use **100 or higher**.

## Registering at runtime

The `@relationalizer` decorator registers the class automatically when the module is imported. If you want to register manually, you can call `RelationalizerRegistry.register()`.

## Inspecting the registry

```python
from spytial import RelationalizerRegistry

print(RelationalizerRegistry.list_relationalizers())
```

## Next steps

Once your relationalizer is in place, use `spytial.diagram()` or `spytial.evaluate()` to test how it behaves.

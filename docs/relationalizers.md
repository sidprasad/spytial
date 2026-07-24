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

## Declared relations

`relationalize()` is extensional. It emits a tuple only where an instance
holds a value. A field that no instance populates therefore leaves no trace,
and a selector that names that field resolves to an atom literal rather than
to a relation.

A relationalizer may override `declared_relations(obj)` to name the relations
that the type declares, whether or not any instance populates them. Spytial
emits each declared name that no instance populated as a relation with no
tuples, so the data instance carries the shape of the type and not only its
contents.

```python
@relationalizer(priority=100)
class WidgetRelationalizer(RelationalizerBase):
    def declared_relations(self, obj):
        return ["label", "parent"]
```

The built-in relationalizers declare:

- dataclasses: every field returned by `dataclasses.fields()`
- generic objects: every name annotated or slotted across the method
  resolution order

Both include names with a single leading underscore. A field is schema, not a
privacy boundary: Python decides state by assignment alone, and `_next`
participates in the structure exactly as `next` does. Names that the language
itself hides are excluded — dunders, and name-mangled `__x` attributes stored
as `_Class__x`. To hide a field from a diagram, use a directive.

Containers and primitives declare nothing. The default implementation returns
an empty list, so a relationalizer that renames fields on output does not
declare names that it never populates.

A declared relation carries an arity of 2. Arity cannot be measured without a
tuple.

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

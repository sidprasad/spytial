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
            label=obj.label,
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

## Examples from demos

### Decision diagrams (dd / BDD)

The decision diagram demo defines a `BDDRelationalizer` for the `dd` library and shows a full end-to-end visualization. It:

- Emits `BDDNode` atoms for decision nodes and `Terminal` atoms for True/False.
- Adds `at_level` relations to connect nodes to level atoms.
- Adds `precedes` relations to order levels, plus `low`/`high` edges (including complemented variants).

Minimal excerpt (full demo in `demos/05-dds.ipynb` or https://github.com/sidprasad/spytial/blob/main/demos/05-dds.ipynb):

```python
from dd.autoref import BDD
from spytial import RelationalizerBase, relationalizer, Atom, Relation

@relationalizer(priority=101)
class BDDRelationalizer(RelationalizerBase):
    def can_handle(self, obj):
        return isinstance(obj, BDD)

    def relationalize(self, obj, walker_func):
        atoms = []
        relations = []
        # Emit Terminal + BDDNode atoms and attach at_level/precedes/low/high relations.
        return atoms, relations
```

### SMT/Z3 model relationalizer (FFI)

The Z3 case study builds a relationalizer for `z3.ModelRef`, treating Z3 as an FFI boundary and emitting pure-Python atoms/relations. It:

- Creates `Decl`, `Const`, `App` atoms for declarations, constants, and applications.
- Emits `defines`, `value_of`, `arg_N`, `result`, and `default` relations.
- Preserves sort information and avoids Python truthiness checks on Z3 ASTs.

Minimal excerpt (full demo in `demos/02-z3-case-study.ipynb` or https://github.com/sidprasad/spytial/blob/main/demos/02-z3-case-study.ipynb):

```python
import z3
from spytial import RelationalizerBase, relationalizer

@relationalizer(priority=100)
class Z3ModelRelationalizer(RelationalizerBase):
    def can_handle(self, obj):
        return isinstance(obj, z3.ModelRef)

    def relationalize(self, obj, walker_func=None):
        # Convert Z3 model into Atom/Relation lists.
        return [], []
```

## Next steps

Once your relationalizer is in place, use `spytial.diagram()` or `spytial.evaluate()` to test how it behaves.

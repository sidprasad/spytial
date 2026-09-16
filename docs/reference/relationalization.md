# Relationalization

Relationalization represents values as atoms and records their structure as
relation tuples. For example, if `node.value` is `7`, the node and the integer
`7` become atoms. The field name `value` names a relation containing the
tuple `(node atom, integer atom)`.

Spytial performs this conversion before evaluating selectors and laying out
a diagram. The data instance records structure. Constraints and directives
control its presentation.

The reverse operation, [`reify()`](reification.md), reconstructs a Python
value from the data instance. The [Python type coverage](python-types.md)
tables describe both directions for every standard type hierarchy category,
including cases that lose information or cannot be reconstructed.

This page describes the current built-in conversion rules. A
[custom relationalizer](../relationalizers.md) can replace the rule for a
value. The conversion does not promise a complete or lossless representation
of every Python object.

## What becomes an atom

Under the built-in rules, each value reached during traversal is represented
by an atom, unless the traversal rules exclude that value. This includes:

- **Primitive values:** integers, floating-point numbers, complex numbers,
  booleans, strings, bytes, bytearrays, `None`, `NotImplemented`, and `Ellipsis`.
- **Objects:** dataclass instances and other object instances. The object
  itself is an atom; each included attribute value is also represented by an
  atom.
- **Containers:** lists, tuples, dictionaries, sets, frozen sets, and ranges.
  The container itself is an atom, including when it is empty. Its included
  contents are represented by further atoms.
- **Dictionary keys:** a key is a value and is processed in the same way as
  any other value. A string key becomes a string atom; a tuple key becomes a
  tuple atom with its own contents.
- **List indices:** each included position introduces an integer atom for
  its zero-based index. Tuple positions are encoded in relation names instead.
- **Reference values:** enum members, functions, class objects, and modules,
  when reached through a path that includes them. These are represented by
  leaf atoms; their internal contents are not traversed.

An occurrence does not necessarily create a new atom. Shared objects reuse
the same atom. Primitive occurrences with the same identifier also reuse an
atom. For example, `[7, 7]` produces one list atom, one atom for `7`, and two
index atoms, `0` and `1`.

Variable names and field names do not themselves create atoms. A type name
classifies an atom; it does not create a separate atom for the class unless
the class object is itself an input value.

## What becomes a relation

A structural association contributes a tuple to a named relation. The
association can be a field holding a value, an element occupying a position,
a dictionary entry, or set membership.

The table specifies the built-in rules. Names inside tuple parentheses
stand for the atoms representing those values.

| Python structure | Relation name | Tuple contributed |
| --- | --- | --- |
| An included field or attribute `f` holds a value. | The field name `f` | `(owner, field value)` |
| A list has an element at index `i`. | `idx` | `(list, index, element)` |
| A tuple has an element at position `i`. | `t0`, `t1`, and so on | `(tuple, element)` |
| A dictionary maps a key to a value. | `kv` | `(dictionary, key, value)` |
| A set or frozen set contains an element. | `contains` | `(set, element)` |
| A range has start, stop, and step parameters. | `start`, `stop`, `step` | `(range, parameter value)` in each corresponding relation. |

For example, `node.value = 7` contributes one tuple to the relation `value`.
If several objects have a field named `value`, their tuples belong to the
same relation under the built-in rules. A field name is therefore a relation
name, and a particular field value contributes one tuple to that relation.

A dictionary key does not become a relation name. For `{"value": 7}`, the
dictionary, the string `"value"`, and the integer `7` become atoms. The entry
contributes a tuple to `kv`. It does not create a relation named `value`.

Primitive leaves, reference values, and values handled by the final fallback
contribute no tuples of their own. They can still occur in tuples emitted
by an enclosing object or container. A declared but unassigned field can
also produce an empty relation, as described below.

## Terms and notation

| Term | Meaning |
| --- | --- |
| Root value | The value passed to `build_instance()`. |
| Atom | A record with an identifier, a type name, and a display label. |
| Primary atom | The atom that represents a value being processed. |
| Auxiliary atom | An additional atom introduced by a conversion rule. List indices are an example. |
| Tuple | An ordered sequence of atom identifiers. |
| Arity | The number of positions in a tuple. A binary tuple has arity 2; a ternary tuple has arity 3. |
| Relation record | A record with an identifier, a name, and a set of tuples. |
| Relationalizer | The component that defines the conversion rule for a kind of value. |

Write the result of a successful conversion as:

```text
relationalize(v) = (A, R, T, r)
```

Here, `A` is the set of atom records, `R` is the set of relation records,
`T` is the type information, and `r` is the identifier of the root atom.
Atom identifiers are unique within `A`. Relation identifiers are unique
within `R`.

In the rules below, `a(v)` denotes the identifier of the primary atom for
`v`. The notation `f(a(v), a(w))` means that the tuple `(a(v), a(w))` belongs
to the relation named `f`. It does not denote a Python function call.

A tuple contains references to atoms, not copies of their values. Each tuple
position refers to an atom in `A`. An atom can occur in several tuples and
in several positions of one tuple.

For a relation of arity `k`, its tuples form a subset of `U^k`, where `U` is
the set of atom identifiers. The storage format also permits one relation
record to contain tuples of different arities. Such a record has no single
arity.

## Atom identity

Atom identity determines whether two references denote the same atom.
Labels do not determine identity.

### Objects and containers

By default, containers and other non-primitive objects use Python object
identity. Two references to the same object use the same atom identifier.
Two distinct objects use distinct identifiers even if they compare equal.
For example, two separate empty lists produce two list atoms.

The builder assigns identifiers such as `n0`, `n1`, and `n2` in encounter
order. It records an object's identifier before processing its contents.
A later reference to that object returns the recorded identifier without
processing its contents again. This rule preserves shared references and
permits cycles, including an object that refers to itself.

An object identifier assigned by Spytial annotations takes precedence over
an automatically assigned identifier. An optional identity resolver can
also map distinct objects to one atom. See
[Sequences](../usage/sequences.md) for identity across successive builds.
Automatically assigned identifiers in an ordinary build are local to that
build; they are not persistent identifiers for stored data.

### Primitive values

Most primitive values use identifiers derived from their textual value:

| Value kind | Identifier rule |
| --- | --- |
| `int`, `float`, `bool`, `complex`, `None` | `str(value)` |
| `str` | The string enclosed in double quotes. |
| `bytes` | `repr(value)` |
| `NotImplemented`, `Ellipsis` | `str(value)` |

Repeated occurrences with the same identifier produce one atom. For
example, two occurrences of the integer `7` refer to the atom with identifier
`7`. The string `"7"` has a different identifier, including the double quotes.
An integer used as a list index shares its atom with the same integer used
as data.

This rule is based on the identifier text, not Python equality. The values
`True`, `1`, and `1.0` have different identifiers. Conversely, the identifier
does not include the type, so values with the same identifier text can
collapse to one atom. Distinct floating-point NaN values are one example.
If atom records have the same identifier, the builder retains the first
record collected.

`bytearray` is a primitive leaf for conversion but uses object identity
because it is mutable. Enum members also use object identity and are handled
before numeric or string primitives.

## Structural details

A list rule also creates an integer atom for each included index. A tuple
rule records the position in the relation name and creates no index atom.
A dictionary processes both keys and values through the normal conversion
rules. A range records its three parameters without enumerating its members.

Containers are atoms in their own right. If `v.children` is a list `c`, the
field produces `children(a(v), a(c))`. Each element of `c` then produces an
`idx` tuple. The field does not directly relate `v` to the list elements.

Tuple order is significant: the three positions of `kv` mean dictionary,
key, and value, in that order. The order of tuples within a relation has no
structural meaning. List and tuple positions are explicit in the rules;
dictionary insertion order and set iteration order are not encoded as
separate facts.

### Attribute selection

The dataclass rule processes the fields returned by `dataclasses.fields()`.
It includes fields whose names start with an underscore. An unassigned field
whose access raises `AttributeError` produces no tuple.

The generic object rule enumerates members with `inspect.getmembers()`.
It can include inherited attributes, properties, and values exposed by
descriptors. It excludes dunder names, class-mangled private names such as
`_Node__cache`, methods, functions, modules, and built-in callables. A single
leading underscore does not exclude an attribute.

Attribute access can execute Python code. In particular, evaluating a
property can have side effects or raise an exception. Relationalization is
therefore not limited to reading stored instance fields. A function or
module supplied directly, or through a container, can become a reference
atom even though the generic attribute rule excludes it.

### Absent fields, `None`, and empty containers

These cases have different representations:

| State | Representation |
| --- | --- |
| A field holds `None`. | A field tuple points to the atom with identifier `None` and type `NoneType`. |
| A declared field has no assigned value. | No tuple is emitted for that field on that object. |
| A field holds an empty list. | A field tuple points to a list atom. That list has no `idx` tuples. |

Dataclasses declare every dataclass field name. Generic objects declare
included names from class annotations and slots throughout the inheritance
hierarchy. If a declared name has no emitted tuples anywhere in the build,
the builder creates an empty relation record with that name. Its default
arity is 2. If another object populates the name, the existing relation
already carries the declaration.

Containers and primitives declare no relation names. An empty list alone
therefore produces a list atom but no `idx` relation record. Declaring a
field records its name; it does not create a target atom from the field's
type annotation.

## Conversion procedure

`CnDDataInstanceBuilder.build_instance(v)` performs the following steps:

1. Clear the atoms, relations, visited-object map, and declarations for the
   new build.
2. Process the root value. For each value, check the depth limit and refusal
   rules. If its object identity is already recorded, return its identifier.
3. Select the first registered relationalizer whose `can_handle()` method
   accepts the value. Relationalizers are checked in descending priority
   order.
4. Collect its declared relation names. Invoke its conversion rule. Built-in
   rules reserve the primary identifier before recursively processing child
   values, then return atom records and relation tuples.
5. Collect the returned atoms and tuples. Use the first returned atom as the
   primary atom for that value.
6. Group tuples by relation identifier and remove duplicate tuples within
   each group. Add empty records for unpopulated declared names.
7. Remove duplicate atom records by identifier, retaining the first record.
   Build the type information and return the data instance with its root
   identifier.

The rules visit only values reached from the root through the selected
relationalizers. They do not enumerate every object in the Python process.
Custom relationalizers can introduce additional atoms and relations; they
must keep tuple references consistent with the atoms they emit. A custom
rule that follows cycles needs to reserve the primary identifier before
recursion, as the built-in rules do.

The current walker is recursive. A build that exceeds its depth limit raises
`RecursionError`; it does not return a truncated instance. Lists, dictionaries,
and sets are iterated through local snapshots. This does not make the whole
build an atomic snapshot if the underlying objects change during conversion.

The walker omits nested Spytial infrastructure objects, such as sequence
recorders. A refused value produces no reference tuple. It is distinct from
the Python value `None`, which produces an atom. The active builder and its
internal collections cannot be used as the root.

## Data instance format

The public entry point returns a Python dictionary:

```python
from spytial import CnDDataInstanceBuilder

instance = CnDDataInstanceBuilder().build_instance([7, 7])
```

| Key | Contents |
| --- | --- |
| `atoms` | Atom records with `id`, `type`, and `label`. |
| `relations` | Relation records with `id`, `name`, `types`, and `tuples`. |
| `types` | Type records with `id`, `types`, `atoms`, and `isBuiltin`. |
| `rootId` | The identifier of the root atom. |

Each relation tuple contains `atoms`, an ordered list of identifiers, and
`types`, the corresponding atom type names. For a relation whose tuples all
have arity `k`, the record-level `types` contains `k` copies of `"object"`.
It is not a declaration of the Python field types. For mixed arities, this
summary is an empty list.

Type records group atoms by their primary type name and record the type
hierarchy. For ordinary objects, these names come from Python class names
and the method resolution order. Type names are not qualified by module, so
unrelated classes with the same name share a type name in the instance.

Labels are display text. Primitive labels normally use `str(value)`;
bytes and bytearrays use a bytes literal. Lists use labels such as `list[2]`.
Other built-in rules can use a variable name, a generated label, or a
reference name. Labels are not required to be unique or stable across builds.
For primitives, the label also stores the value parsed by `reify()`; changing
it can change the reconstructed value.

Atoms can also carry metadata for
[reconstruction](../usage/structured-input.md#reify-directly), such as a
class's module and qualified name. Reference atoms record an importable
identity only when that identity resolves to the original value at build
time. This metadata is separate from the relation tuples.

### Relation identifiers and names

The built-in rules use the relation name as its identifier. All fields named
`next`, for example, contribute tuples to one `next` record, including fields
on different classes.

A custom rule can assign separate identifiers to records with the same name.
Selectors use the name and see the union of those records' tuples. Reusing
one identifier with different names raises `ValueError`. See
[Relation identity](../relationalizers.md#relation-identity) for the custom
API.

## Worked example

The following value contains a shared reference and a cycle:

```python
from dataclasses import dataclass
from spytial import CnDDataInstanceBuilder

@dataclass
class Node:
    value: int
    next: object = None

node = Node(7)
node.next = node
root = [node, node]

instance = CnDDataInstanceBuilder().build_instance(root)
```

With a fresh builder and the built-in rules, the atoms are as follows.
Labels and reconstruction metadata are omitted from this table.

| Identifier | Type | Meaning |
| --- | --- | --- |
| `n0` | `list` | The root list. |
| `n1` | `Node` | The shared node. |
| `7` | `int` | The node's value. |
| `0` | `int` | The first list index. |
| `1` | `int` | The second list index. |

The complete relation contents are:

```text
value = { (n1, 7) }
next  = { (n1, n1) }
idx   = { (n0, 0, n1), (n0, 1, n1) }
rootId = n0
```

The two list positions refer to one `Node` atom. The `next` tuple records
the self-reference. No `NoneType` atom is needed because the instance's
`next` field holds the node, despite its declared default of `None`.

For example, the stored `idx` record is:

```json
{
  "id": "idx",
  "name": "idx",
  "types": ["object", "object", "object"],
  "tuples": [
    {"atoms": ["n0", "0", "n1"], "types": ["list", "int", "Node"]},
    {"atoms": ["n0", "1", "n1"], "types": ["list", "int", "Node"]}
  ]
}
```

The reverse conversion preserves the shared node and its self-reference:

```python
from spytial import reify

restored = reify(instance)
assert restored[0] is restored[1]
assert restored[0].next is restored[0]
assert restored[0].value == 7
```

The full reconstruction procedure and its known failures are described in
[Reification](reification.md).

Use the [evaluator](../usage/evaluator.md) to inspect a data instance before
adding layout rules. See [Selectors](../selectors.md) for querying its atoms
and relations.

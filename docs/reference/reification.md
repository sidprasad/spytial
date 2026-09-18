# Reification

Reification converts a data instance back into a Python value. Together,
relationalization and reification provide the following two-way process:

```text
Python value  --build_instance()-->  atoms + relations + types + rootId
Python value  <------reify()-------  atoms + relations + types + rootId
```

`reify()` reconstructs the value represented by the selected root atom. It
uses atom types, labels, metadata, and relation tuples. The top-level `types`
table is not needed by the current reifier.

```python
import json
from spytial import CnDDataInstanceBuilder, reify

shared = [7]
original = [shared, shared]
instance = CnDDataInstanceBuilder().build_instance(original)
restored = reify(json.loads(json.dumps(instance)))

assert restored == original
assert restored is not original
assert restored[0] is restored[1]
```

The reconstructed lists are new objects. The two references to the inner
list still denote one object. The JSON step demonstrates that this example
uses the recorded data rather than a hidden reference to the original lists.

## Meaning of a round trip

Let `F(v)` be relationalization and `G(D)` be reification. For supported
values, `G(F(v))` preserves the represented values and structure, subject to
the identity rules and limits below. It need not be the original object.

A round trip has several independent properties:

| Property | Question |
| --- | --- |
| Value | Are primitive values and container contents recovered? |
| Type | Does each reconstructed value have the expected Python type? |
| Structure | Are included fields, positions, entries, and memberships recovered? |
| Sharing | Do references to one recorded object still denote one reconstructed object? |
| Behavior | Does the result support the operations of the original value? |
| Reference identity | For a named reference, does lookup still return the same external object? |

Equality and `repr()` do not establish all of these properties. A file can
have the right type and still lack a working handle. A proxy can display the
original type name without being an instance of that type. NaN values do not
compare equal to themselves.

Both conversions can fail, and some successful returns lose information.
They are not universal inverses over all Python values or all data instances.
See [Python type coverage](python-types.md) for each standard hierarchy
category. This page describes the implementation at version 1.13.2,
source revision `c1a9239`.

## Reconstruction procedure

1. Index atom records by identifier. Group relation tuples by their first
   atom and relation name.
2. Choose the root. Prefer a valid explicit `root_id`, then a valid stored
   `rootId`. Otherwise, use the topology heuristic described below.
3. If an atom already has a reconstructed value, return that value.
4. For a primitive type, parse or use its label. For a resolvable named
   reference, return the referenced object.
5. Otherwise, use a registered custom reifier, a built-in container reifier,
   or the generic object reifier, in that order.
6. Record the resulting value under its atom identifier and return it.

Mutable containers and generic objects register an empty object before
processing their children. A back-reference then resolves to that object.
Tuples and frozen sets are constructed after their children; they have no
mutable placeholder. This distinction determines which cycles retain
identity.

Reification groups relations by **name**, even when separate stored records
have different identifiers. Built-in dictionary and list reifiers retain
tuple boundaries. The generic object and custom reifier interfaces receive
a flattened list of targets for each source and relation name.

## Three reconstruction mechanisms

### Rebuild a value

Primitives are reconstructed from their labels. Built-in containers are
reconstructed from `idx`, `kv`, `contains`, or the tuple-position relations.
Ranges use `start`, `stop`, and `step`. These mechanisms do not require the
original value to remain alive.

Primitive labels are therefore part of the stored value, even though they
also serve as display text. Changing an integer atom's label from `"7"` to
`"8"` changes the integer that `reify()` returns. Changing its identifier
alone does not change that integer.

### Resolve a reference

Functions, class objects, modules, and enum members can carry verified import
metadata. Capture verifies that the recorded module and name resolve to the
original object. Reification resolves that name again.

This records a reference, not the object's implementation or state. The
receiving environment must provide the referenced definition. A name under
`__main__` can work in the originating session without being portable to
another process. Lambdas, local definitions, and names already rebound at
capture time generally lack verified reference metadata and become proxies.

There is no verification against the original object at reconstruction time.
If a name is rebound after capture, lookup can return its new value. A
module's current globals and a function's current environment are used;
their earlier state is not restored.

### Allocate and populate an instance

For a generic instance, the reifier resolves the recorded class and calls
`object.__new__(cls)`. It then uses `object.__setattr__()` to restore included
attributes. It does not call the class's constructor, `__init__()`,
`__post_init__()`, `__reduce__()`, or `__setstate__()`.

This supports ordinary and slotted classes, frozen dataclasses, and many
cycles. It also bypasses constructor validation and initialization. Native
state, excluded attributes, and invariants established by the constructor
may be missing. Property setters can still run during assignment. The
generic reifier suppresses assignment exceptions and keeps the partially
restored instance.

If the class cannot be resolved or allocated, the fallback is an attribute
proxy. Its generated class has the original type name for display, but it
does not inherit the original class or restore its methods and protocols.

Instance class metadata does not receive the identity verification used for
reference atoms. If the recorded class name has been rebound, generic
reconstruction can allocate an instance of a different class.

## Known failures

### Cycles through immutable containers

A tuple can participate in a cycle through a mutable object. If reconstruction
starts from the tuple, the current reifier can create two tuples for its one
atom:

```python
from spytial import CnDDataInstanceBuilder, reify

items = []
original = (items,)
items.append(original)
restored = reify(CnDDataInstanceBuilder().build_instance(original))

assert original[0][0] is original
assert restored[0][0] is not restored  # Current loss of sharing.
```

Starting from the list in this example closes the cycle correctly because
the list is registered first. A frozen set containing an object that refers
back to the frozen set has the same root-dependent limitation. A custom
reifier that descends before registering a placeholder can instead recurse
until it fails.

### Primitive identity and type names

Distinct primitives with the same textual identifier are merged before
reification. Two distinct NaN keys in a dictionary can therefore become one
key. Subclasses can collide with base values: an `int` subclass holding `7`
and a plain `7` share an identifier. The first collected atom determines
the type and label retained for both.

Reifier dispatch uses the atom's short type name. It does not infer a
constructor from the stored type hierarchy. Consequently, primitive and
container subclasses usually become proxies. A named tuple is included in
this limitation. A user class whose name matches a built-in dispatch name
can also select the wrong reconstruction rule. Custom reifier registrations
for unrelated classes with the same short name share one registry key.

### Missing state and unavailable behavior

The following losses cannot be repaired by the default reifier:

- Generic traversal omits class-mangled private attributes and selected
  callable or module attributes. Methods that depend on that state can fail.
- A function reference does not record code, defaults, or closure state.
  A bound method does not record its receiver/function binding.
- Generators, coroutines, frames, tracebacks, and code objects can produce
  inspectable attributes, but reconstruction does not restore execution.
- Files, buffers, and extension objects can require native state. Even a
  successfully allocated instance can be unusable.
- Generic properties describe observed values. A getter can raise during
  capture; a setter can reject a value during reconstruction.

These are distinct from outright exceptions. Receiving an object is not
evidence that a round trip succeeded. The [coverage tables](python-types.md)
state which paths return proxies or unusable values.

### Ordering and incomplete data

The dictionary reifier inserts entries in stored tuple order. A direct
round trip retains that order, but the relational meaning does not encode
insertion order independently. A system that treats the relation as an
unordered set and rearranges its tuples can change the reconstructed order.
Set display order is not preserved.

Reification builds only from the selected root and the relations used by its
reconstruction rule. Unreachable atoms and relations a rule does not use do
not appear in the result. A build after reification therefore need not
reproduce the original data instance or its identifiers.

## Compatibility mechanisms and implementation shortcuts

These mechanisms can produce a value from incomplete or older data. They
are not validation guarantees.

| Mechanism | Current behavior and consequence |
| --- | --- |
| Root inference | Without a valid root identifier, prefer a source that is never a target, then a source targeted only by itself, then the last atom. Multiple candidates and cycles make the choice ambiguous. An invalid explicit root identifier falls back rather than raising. |
| Primitive label parsing | Integers, floats, and complex numbers use their constructors; invalid labels can raise. Any Boolean label other than case-insensitive `true` becomes `False`. Bytes use `ast.literal_eval()` without a separate check that the result is bytes. |
| List indices | Convert indices with `int()`, skip invalid indices, sort, and append values. Gaps are compressed; repeated indices can add multiple elements. No original length is checked. |
| Tuple positions | Sort relations with numeric `t` suffixes. Missing positions are compressed, repeated targets can add elements, and unrelated names are ignored. |
| Dictionary keys | If assignment raises `TypeError`, retry using `str(key)`. This can change key types or merge entries. A failing string conversion can still raise. |
| Legacy dictionaries | Relations other than `kv` are interpreted as older per-key relations: the relation name becomes a string key. |
| Tuple shape | Short `idx` or `kv` tuples are skipped; extra targets are ignored by their dedicated reifiers. The generic/custom interface instead flattens targets. |
| Missing range parameters | Default `start` and `stop` to `0`, and `step` to `1`. Non-integer parameters use these defaults; zero step becomes `1`. |
| Generic field multiplicity | One target becomes one attribute value; several targets become a list. This does not recover the intended meaning of arbitrary n-ary relations. |
| Attribute assignment | The generic reifier suppresses all assignment exceptions. The returned object can therefore have missing fields. |
| Proxy fallback | A newly generated attribute class receives the original type name. It preserves captured attributes but not the original type or behavior. Its `repr()` has no cycle guard and can raise `RecursionError`. |
| Dataclass editor defaults | `edit()` registers special reifiers for the dataclass seed and dataclasses found through its field types. They apply declared defaults and factories before recorded fields. Plain `reify()` does not install this defaults pass. Required missing fields can remain unset. |
| `can_reify()` | Checks only a small part of the record shape. It does not check references, tuple validity, primitive labels, or whether the resulting value will work. |

Both traversal and reconstruction use recursion. The traversal has an
explicit depth guard. Reconstruction can encounter Python's recursion limit
independently.

## Custom reconstruction

A custom relationalizer does not automatically define its inverse. Register
a corresponding reifier on the builder used for reconstruction:

```python
from spytial import CnDDataInstanceBuilder

class Cell:
    def __init__(self, value):
        self.value = value

def restore_cell(atom, relations, reify_atom, register):
    cell = register(object.__new__(Cell))
    cell.value = reify_atom(relations["value"][0])
    return cell

builder = CnDDataInstanceBuilder()
builder.register_reifier("Cell", restore_cell)
restored = builder.reify(builder.build_instance(Cell(7)))
assert isinstance(restored, Cell) and restored.value == 7
```

`register()` stores the placeholder for the current atom before child
reconstruction. Use it when the type can participate in a cycle. The older
three-argument callback is still accepted, but has no placeholder callback.

The callback receives relation names mapped to flattened target identifier
lists. It does not receive stored relation identifiers or tuple boundaries.
Use a representation that this interface can reconstruct unambiguously.

Custom dispatch occurs after primitive parsing and successful reference
resolution. Registering a reifier for a built-in primitive type does not
override that earlier path. Registrations belong to the builder; the
top-level `spytial.reify()` creates a new builder and does not inherit them.

`replit(D)` is exactly `repr(reify(D))`. It is useful for inspecting a
reconstructed value, but inherits the failures above and is not a separate
serialization or validation mechanism.

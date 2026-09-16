# Reification after core 6.0.1

This is a design note for follow-up work, not a new reconstruction API.
The 6.0.1 update does not introduce `IAtom.metadata`: Python neither emits it
nor reads it. A user's Python attribute named `metadata` remains an ordinary
relation, just like any other attribute.

## What works today

`build_instance()` supplies atoms, stored relation records, and a `rootId`.
`reify()` rebuilds built-in containers and resolves importable classes from
the Python-specific top-level atom keys `__module__` and `__qualname__`.
Named references use `__ref_module__`, `__ref_qualname__`, or `__ref_import__`.
`Atom.meta` is only a helper for adding these keys; it is not core's removed
`IAtom.metadata` property.

Mutable placeholders preserve sharing and cycles. Dict and list reifiers
retain tuple boundaries for `kv` and `idx`; custom reifiers receive a legacy
name-to-targets mapping. When a class cannot be resolved or allocated, generic
reification falls back to a structural proxy.

The tests exercise Python export, JSON serialization, core 6.0.1
`JSONDataInstance` normalization/reification, and Python reconstruction with
no atom `metadata`. That path currently preserves the Python-specific keys.
This does not establish preservation through every editor, adapter, or
composition path: those keys are outside the `IAtom` interface. Core's
`reify()` output also omits Python's `rootId`, so the host must carry it separately.

## Gaps the next design must address

### Evaluation claim

The target is preservation of the information exposed by Python's standard
printed/debug output, **modulo dictionary and set ordering**. Dictionary
insertion order is deliberately outside this observation; key/value
associations remain significant. Lists and tuples retain positions and repeated
elements. Type distinctions and leaf representations remain significant too.

The test-only `inspection` comparator in `test/inspection.py` recursively
normalizes exact built-in dictionaries, sets, and frozensets. It preserves list
and tuple order, handles container cycles, and compares other values through
their native `repr` and qualified type name. It never parses arbitrary repr
strings or treats a string that looks like a dictionary as a dictionary.
Custom repr output remains exact: normalization inside user-written text would
need an explicit additional observation contract. Named-reference recovery is
still a separate capability, not evidence of rebuilding a value's state.

Generated round-trips cross JSON and reconstruct with a fresh builder. A
second property permutes stored atoms, relations, and tuples before reifying.
Passing these tests provides evidence over the stated generated domain, not a
proof for every Python object. Aliasing and unsupported cycles require their
own structural checks because ordinary printing need not expose identity.

The dedicated CI job `reify` runs reconstruction, relation-identity, inspection
oracle, type-corpus, and property-based tests using `python -m pytest -m reify`.
New tests for this contract should carry `@pytest.mark.reify`, or set
`pytestmark = pytest.mark.reify` for a whole module. The general CI job runs
`python -m pytest -m "not reify"`; plain `python -m pytest` still runs everything.

### Encoding consequences

Dictionary positions need not be encoded: `kv(dict, key, value)` suffices for
this observation. Relation IDs need not contain positional information. The
existing `idx(list, index, value)` encodes list order in relational data; tuple
positions currently use the `t0`, `t1`, ... relation names. Retain these until a
separate encoding change is justified. Do not infer semantic order from the
JSON arrays holding relation records or tuples.

| Case | Current behavior | Required decision |
| --- | --- | --- |
| Same name and different IDs on different source atoms | Attributes reconstruct separately | Preserve this behavior |
| Same name and different IDs on the same source atom | Targets concatenate; IDs are discarded | Let a reifier distinguish stored records and reject ambiguous scalar fields |
| Duplicate tuple under different IDs | Generic reconstruction can turn one scalar into a list | Define field cardinality and duplicate handling using the host encoding |
| Distinct classes with the same short name | Custom reifiers share a type-name registry key | Give the host schema a qualified type identity |
| Primitive display label edited | Reconstruction parses the label as the value | Specify which edits change values and how invalid values are reported |
| Tuple participating in a cycle through a mutable object | Immutable reconstruction has no early placeholder | Support a fix-up phase or reject unsupported cycles explicitly |
| Datum stripped to the core atom interface | Import hints are lost; generic objects become proxies | Define a portable host encoding or an explicit host schema |

## Proposed next increment

1. Specify an ID-aware reifier input that retains each record's ID, name, and
   complete tuples. Keep the existing custom callback mapping as a compatibility
   view. Reconstruction must consume the stored datum, not the selector's
   name-based union.
2. Define an explicit Python schema/codec contract for type identity, field
   cardinality, constructor needs, and literal values. Decide whether saved data
   must be self-contained or may require a supplied host schema. Do not introduce
   `IAtom.metadata`, put reconstruction data in display labels, or assume arbitrary
   extra atom keys are portable.
3. Keep meaningful order in relational data, with explicit indices or ordering
   relations where needed. Dictionary/set order needs no recovery for this
   observation. Keep relation IDs as identities rather than requiring positional
   encoding. Specify type identity, empty containers, and literal values as part
   of the host contract; preserve familiar query names such as `value`, `idx`,
   and `kv`.
4. Validate reference integrity, field cardinality, and tuple shape before
   reconstruction. Report unsupported or ambiguous cases instead of silently
   changing a scalar into a list, duplicating a list index, or overwriting a dict entry.
5. Test the contract through normalization, editor export, and atom-ID remapping,
   including sharing, cycles, missing fields, same-named records, and malformed
   edits. Separate value equality, type preservation, alias preservation, and
   display reproduction; success on one does not prove the others.

The first implementation should expose stored relation identity to custom
reifiers and define ambiguity handling. A broader portable encoding should
follow that contract rather than be hidden inside this dependency patch.

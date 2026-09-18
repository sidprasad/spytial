# Python type coverage

This page covers each type category in Python's
[standard type hierarchy](https://docs.python.org/3/reference/datamodel.html#the-standard-type-hierarchy).
The category names follow the Python 3.14 reference. The Spytial behavior
described here was checked against version 1.13.2, at source revision
`c1a9239`, using CPython 3.13.5. Interpreter-specific attributes can differ
on other Python versions.

This is a description of current behavior, including unsupported cases.
See [Relationalization](relationalization.md) for traversal and identity rules
and [Reification](reification.md) for reconstruction and its limitations.

## Reading the tables

The **Atoms** column states what is represented. The **Relations** column
states how those atoms are connected. In tuple notation, `x`, `k`, `v`, and
`i` stand for atom identifiers, not embedded Python values. Every referenced
value is processed recursively under its own rule.

The **Reification** column uses these outcomes:

| Outcome | Meaning |
| --- | --- |
| Value | Rebuilds the built-in value from its label or relations, subject to the listed limits. |
| Reference | Resolves an existing object by module and name. This depends on the receiving Python environment. |
| Instance | Allocates an instance of the resolved class and restores included attributes. Constructors do not run. |
| Proxy | Returns a plain object holding captured attributes. It does not implement the original type's behavior. |
| Unsupported | Does not restore the value's required behavior or state. Capture or reconstruction can also raise. |

Producing a data instance does not establish that a value can be reconstructed.
Returning the original type does not establish that its state is valid.

## Singletons and numbers

These rows cover hierarchy sections 3.2.1 through 3.2.4, including
`numbers.Integral`, `numbers.Real`, and `numbers.Complex` through their
built-in concrete types. Dispatch uses concrete Python types; implementing a
numeric abstract base class does not itself select a numeric relationalizer.

| Python value | Atoms | Relations | Reification |
| --- | --- | --- | --- |
| `None` | One `NoneType` atom. | None. | **Value:** returns `None`. |
| `NotImplemented` | One `NotImplementedType` atom. | None. | **Value:** returns the singleton. |
| `Ellipsis` | One `ellipsis` atom. | None. | **Value:** returns the singleton. |
| `int` | One atom; identifier and label use `str(x)`. | None. | **Value:** `int(label)`. Very large integers remain subject to Python's integer/string conversion limit. |
| `bool` | One atom for each encountered truth value. | None. | **Value:** compares the label with `"true"`, ignoring case. Boolean atoms are distinct from integer atoms. |
| `float` | One atom; identifier and label use `str(x)`. | None. | **Value:** `float(label)`. Supports infinities, NaN, and signed zero as text. Distinct NaNs can collapse to one atom. |
| `complex` | One atom for the whole number. | No separate `real` or `imag` relation. | **Value:** `complex(label)`. NaN components have the same identity limitation. |

Scalar identifiers do not include their types. A subclass can collide with
its base type's value. Float text does not preserve NaN payload bits. See
[identity loss](reification.md#primitive-identity-and-type-names).

## Sequences, sets, and mappings

These rows cover hierarchy sections 3.2.5 through 3.2.7. `range` is included
because Spytial has a dedicated rule for it.

| Python value | Atoms | Relations | Reification |
| --- | --- | --- | --- |
| `str` | One atom for the whole string. | No character or index relations. | **Value:** uses the label directly. |
| `tuple` | The tuple and its elements. | `t0(x, v)`, `t1(x, v)`, etc. | **Value:** sorts by the numeric suffix and constructs a tuple. Cycles through a tuple can lose identity. |
| `bytes` | One atom for the whole byte string. | No byte or index relations. | **Value:** parses the bytes literal in the label with `ast.literal_eval()`. |
| `list` | The list, its elements, and integer indices. | `idx(x, i, v)` | **Value:** sorts by index and fills a new list. Shared references and mutable cycles are supported. |
| `bytearray` | One atom for the whole byte array, using object identity. | No byte or index relations. | **Value:** parses the bytes literal and constructs a new bytearray. Equal but distinct arrays remain distinct. |
| `set` | The set and its elements. | `contains(x, v)` | **Value:** fills a new set. Elements must still be hashable after reconstruction. Display order is not preserved. |
| `frozenset` | The frozen set and its elements. | `contains(x, v)` | **Value:** reconstructs members and then freezes the set. Cycles through members can lose identity. |
| `dict` | The dictionary, its keys, and its values. | `kv(x, k, v)` | **Value:** inserts each reconstructed key/value pair. Original tuple order preserves insertion order on a direct round trip; reordering tuples changes it. |
| `range` | The range and its integer parameters. | `start(x, v)`, `stop(x, v)`, `step(x, v)` | **Value:** constructs a range from these parameters. Its elements are not enumerated. |

Each empty container still has an atom. It contributes no element tuples.
A repeated element can use the same atom at several list or tuple positions.
Dictionary keys use the same rules as other values, including compound keys.

These rules do not provide general sequence, mapping, or iterator support.
An object that implements `__iter__()` or `__getitem__()` does not acquire
list or dictionary semantics from that fact alone.

## Callable types

These rows cover every category in hierarchy section 3.2.8. They distinguish
a function from a running or suspended execution created by calling it.

| Python value | Atoms | Relations | Reification |
| --- | --- | --- | --- |
| User-defined function | One `function` atom with a qualified-name label. | None; code, defaults, globals, and closure cells are not captured. | **Reference** when the recorded name resolves to the function at capture time. A lambda or local function normally becomes a non-callable **proxy**. |
| Bound instance method, such as `obj.method` | A generic `method` atom, plus any included user attributes. | Generic attributes only. `__self__` and `__func__` are excluded. | **Proxy:** the receiver and function binding are not reconstructed. |
| Generator function | Same as a user-defined function. | None. | **Reference** under the same naming conditions. |
| Coroutine function | Same as a user-defined function. | None. | **Reference** under the same naming conditions. |
| Asynchronous generator function | Same as a user-defined function. | None. | **Reference** under the same naming conditions. |
| Built-in function, such as `len` or `math.sin` | One atom labelled with its qualified name; exported type is `function`. | None. | **Reference** if its module and name resolve to the original object; otherwise **proxy**. |
| Built-in bound method, such as `items.append` | Normally one `function` atom. | None; no receiver relation. | Normally a non-callable **proxy**. There is no dedicated method-binding reifier. |
| Class object | One `type` atom, with reference metadata when available. | None; no class namespace or base-class relations. | **Reference**, or **proxy** when the class has no verified importable name. |
| Callable class instance | The instance and its included attribute values. | Ordinary field relations. | **Instance** if the class resolves and can be allocated. Its callable behavior comes from that live class. A fallback **proxy** is not callable. |

An unbound user function obtained as `Class.method` uses the function rule.
A bound method uses the method rule. Generic attribute traversal excludes
functions and methods; the rows above describe values supplied as roots or
through paths, such as containers, that include them.

## Modules, custom classes, and class instances

These rows cover hierarchy sections 3.2.9 through 3.2.11.

| Python value | Atoms | Relations | Reification |
| --- | --- | --- | --- |
| Module | One `module` atom, with an import name when verified. | None; its namespace is not copied. | **Reference** to the imported module, or **proxy** if resolution fails. |
| Custom class object | One `type` atom, as in the callable table. | None. | **Reference** to the existing class, or **proxy**. The class definition is not recreated. |
| Ordinary class instance | The instance and included attribute values. | `field(instance, value)` for each included attribute. | **Instance** using `object.__new__(cls)` and attribute assignment, or **proxy** if class resolution or allocation fails. |
| Instance with `__slots__` | The instance and readable included slot values. | Relations named after the slots. | **Instance** under the same conditions. Missing or excluded slots are not restored. |
| Dataclass instance | The instance and readable dataclass field values. | Relations named after the fields. | **Instance** under the same conditions, including frozen dataclasses. The editor has an additional defaults mechanism. |
| Bare `object()` | One `object` atom. | None. | Currently a **proxy**, not an exact `object` instance. No built-in class metadata is recorded for this path. |

Generic traversal includes readable inherited and class attributes, as well
as properties. It excludes dunders, class-mangled private names, and certain
callable or module values. It therefore describes observable selected
attributes, not the complete object state. Dataclasses instead use their
declared fields. See [attribute selection](relationalization.md#attribute-selection).

## I/O objects

This row covers hierarchy section 3.2.12.

| Python value | Atoms | Relations | Reification |
| --- | --- | --- | --- |
| File or stream | A generic atom and included attribute values. | Readable attributes such as `name`, `mode`, `closed`, `encoding`, or `buffer`, when present. | **Unsupported:** no dedicated reconstruction of handles, stream contents, position, or buffering state. A proxy or an uninitialized instance can be returned. |

For example, an open text file returned a real `TextIOWrapper` instance in
the audited runtime, but `read()` raised `ValueError` because the instance
was uninitialized. `StringIO` returned a proxy without its text contents.
Capturing a file does not read its contents through `read()` or record its
position through `tell()`.

## Internal types

These rows cover every category in hierarchy section 3.2.13.

| Python value | Atoms | Relations | Reification |
| --- | --- | --- | --- |
| Code object | A generic `code` atom and readable attribute values. | Included `co_*` attributes, and other visible attributes on the runtime. | **Proxy:** captured code attributes are not assembled into executable code. |
| Frame object | A generic `frame` atom and readable attribute values. | Included `f_*` attributes, including links to code, namespaces, and other frames. | **Proxy:** execution position and stack state cannot be resumed. Traversal can expand far beyond the local value. |
| Traceback object | A generic `traceback` atom and readable attribute values. | `tb_frame`, `tb_lasti`, `tb_lineno`, and `tb_next`. | **Proxy:** does not reconstruct a Python traceback. Frame traversal has the same limits as above. |
| Slice object | A `slice` atom and atoms for its three parameters. | `start`, `stop`, and `step`. | **Proxy:** attributes survive, but it cannot be used as a Python slice. There is no slice reifier. |
| Raw `staticmethod` wrapper | A generic `staticmethod` atom and any included user attributes. | Wrapped-function metadata is excluded because its names are dunders. | **Proxy:** does not restore the wrapper or callability. |
| Raw `classmethod` wrapper | A generic `classmethod` atom and any included user attributes. | Wrapped-function metadata is excluded because its names are dunders. | **Proxy:** does not restore the descriptor or method binding. |

`Class.__dict__["method"]` can expose a raw wrapper. Accessing
`Class.method` can instead yield a function or a bound method; the applicable
row then changes. For example, a normal static method accessed through its
class can reify by reference, while a class method obtained that way becomes
a method proxy.

## Related values and subclass limits

These cases extend the hierarchy categories above. They prevent a broad
claim such as “all sequences” or “all callable values” from implying support
that the implementation does not provide.

| Python value | Atoms and relations | Reification |
| --- | --- | --- |
| Generator object | Generic attributes such as `gi_code`, `gi_frame`, and `gi_yieldfrom`, with their referenced atoms. | **Proxy:** no resumable iterator. Capture does not consume the generator. |
| Coroutine object | Generic attributes such as `cr_code`, `cr_frame`, and `cr_await`. | **Proxy:** no resumable or awaitable execution. |
| Asynchronous generator object | Generic attributes such as `ag_code`, `ag_frame`, and `ag_await`. | **Proxy:** no asynchronous iterator. |
| Built-in iterator, such as `iter([1, 2])` | Generic attributes only; commonly a single atom. No iteration over its elements. | **Proxy:** iteration state is lost. |
| `memoryview` | Generic buffer-description attributes and an `obj` relation to the backing value, when readable. | **Proxy:** no buffer/view semantics. A released view raises during capture in the audited runtime. |
| Dictionary views and `mappingproxy` | Generic attributes only; there is no `kv` rule. A keys view may expose its `mapping`. | **Proxy:** no live view or mapping contents are reconstructed through mapping operations. |
| Enum member, including `IntEnum` and `StrEnum` | One atom with the enum type and member-name label; no value relation. | **Reference** if the member has a verified importable name; otherwise **proxy**. The enum rule takes priority over primitive rules. |
| Primitive subclass, such as a user-defined `int` subclass | The base primitive rule emits a leaf, but uses the subclass's name as the atom type. Extra attributes are not captured. | Usually **proxy**: dispatch does not use the base type to reconstruct its value. |
| Container subclass, including a named tuple | The base container rule emits its usual tuples, but uses the subclass's name as the atom type. Extra attributes are not captured. | Usually **proxy**, with relations interpreted as attributes. A named tuple therefore does not automatically rebuild as a named tuple. |
| Other standard-library or extension type | Usually the generic attribute rule. There is no automatic support based on protocol conformance. | Requires individual assessment or a custom reifier; native or constructor-dependent state can be lost. |

## Evidence and scope

The audit passes data instances through JSON before reconstruction. It
checks type, value, reference identity, and selected operations separately;
matching `repr()` alone is insufficient. Tests in
`test/test_datamodel_inspection.py` and `test/test_reify.py` cover supported
forms. `test/test_reify_boundaries.py` records additional hierarchy cases
and known failures. Strict expected failures mark properties that the
current implementation does not satisfy.

Frame and execution-object probes use small, isolated namespaces. Their
results do not imply that arbitrary running interpreter state can be
captured successfully. The generic walker can execute properties, encounter
exceptions, or reach the depth limit.

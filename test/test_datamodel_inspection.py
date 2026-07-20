"""Python instance of the cross-language evaluation harness.

For each host language, the evaluation plan compares the textual inspection
output exposed by the language's own mechanism with a string reconstructed
from the corresponding Spytial datum. In Python the mechanism is runtime
introspection and the inspection output is ``repr`` — the REPL's echo::

    value ── repr ──────────────────────────────────────────► string
    value ── build_instance ─► datum ─► replit ─────────────► string

``test_reify_pbt.py`` asserts this property on *randomly generated* values;
this file is the systematic counterpart: one row per supported built-in form
in Python's standard type hierarchy
(https://docs.python.org/3/reference/datamodel.html#the-standard-type-hierarchy),
plus dataclasses and ordinary user-defined objects.

Every row is classified by its observed verdict, so the suite documents the
exact boundary of what the relational model reproduces:

* **supported** — the reconstructed string equals ``repr(value)``. This
  includes named singletons (enum members, functions, classes, modules):
  they reify by *reference* — the datum records an importable identity and
  reify returns the identical object — so even an address-bearing repr
  matches.
* **unsupported** (strict xfail) — the value's ``repr`` is deterministic, but
  the datum does not currently reproduce it. If support arrives, the XPASS
  fails the suite and the row must be promoted.
* **out of scope** (skip) — the inspection string is identity-bearing (memory
  address) *and* the value has no importable name to reference (lambdas,
  memoryviews, default-repr instances), so no reconstruction can match.

``set``/``frozenset`` rows are compared canonically (type + sorted element
reprs) rather than by raw ``repr``: a set's repr order is not a function of
its elements — see the rationale in ``test_reify_pbt.py``.
"""

import dataclasses
import enum
import json
import math

import pytest

from spytial import reify, replit
from spytial.provider_system import CnDDataInstanceBuilder


# ---------------------------------------------------------------------------
# Corpus classes — module-level so __module__/__qualname__ resolve in reify
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Point:
    x: int
    y: int


@dataclasses.dataclass
class Segment:
    label: str
    endpoints: list


@dataclasses.dataclass
class WithDefault:
    name: str
    count: int = 0


@dataclasses.dataclass(frozen=True)
class FrozenPoint:
    x: int
    y: int


@dataclasses.dataclass
class NoReprField:
    shown: int
    hidden: int = dataclasses.field(repr=False, default=3)


@dataclasses.dataclass
class HiddenField:
    shown: int
    _secret: int = 7


class Rect:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    @property
    def area(self):
        return self.width * self.height

    def __repr__(self):
        return f"Rect(width={self.width!r}, height={self.height!r})"


class Slotted:
    __slots__ = ("a", "b")

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __repr__(self):
        return f"Slotted(a={self.a!r}, b={self.b!r})"


class Team:
    def __init__(self, name, members):
        self.name = name
        self.members = members

    def __repr__(self):
        return f"Team(name={self.name!r}, members={self.members!r})"


class Opaque:
    """Ordinary object that keeps object's default (address-bearing) repr."""

    def __init__(self):
        self.x = 1


class Color(enum.Enum):
    RED = 1
    GREEN = 2


class MyInt(int):
    pass


class MyStr(str):
    pass


def module_level_function(x):
    return x


def _self_ref_list():
    l = [1, 2]
    l.append(l)
    return l


def _self_ref_dict():
    d = {"a": 1}
    d["self"] = d
    return d


def _shared_sublist():
    inner = [1, 2]
    return [inner, inner, [3]]


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def _datum(value):
    """Relationalize, then round-trip through JSON.

    The JSON hop proves the reconstruction reads only the relational payload —
    no live Python objects can be smuggled through the datum.
    """
    return json.loads(json.dumps(CnDDataInstanceBuilder().build_instance(value)))


def _unsupported(reason):
    return pytest.mark.xfail(strict=True, reason=reason)


_IDENTITY_REPR = pytest.mark.skip(
    reason="inspection string is identity-bearing (address) and the value "
    "has no importable name to reify by reference"
)


# Rows: pytest.param(value_factory, id=name). Factories, not values, so every
# run gets fresh objects. Grouped by section of the standard type hierarchy.
CASES = [
    # --- None / NotImplemented / Ellipsis ---------------------------------
    pytest.param(lambda: None, id="none"),
    pytest.param(lambda: NotImplemented, id="not_implemented"),
    pytest.param(lambda: ..., id="ellipsis"),
    # --- numbers.Number ---------------------------------------------------
    pytest.param(lambda: True, id="bool_true"),
    pytest.param(lambda: False, id="bool_false"),
    pytest.param(lambda: 0, id="int_zero"),
    pytest.param(lambda: -17, id="int_neg"),
    pytest.param(lambda: 2**100, id="int_big"),
    pytest.param(lambda: -(2**100), id="int_neg_big"),
    pytest.param(lambda: 1.5, id="float_simple"),
    pytest.param(lambda: -0.0, id="float_neg_zero"),
    pytest.param(lambda: 1e300, id="float_large"),
    pytest.param(lambda: 5e-324, id="float_tiny"),
    pytest.param(lambda: 1e22, id="float_sci"),
    pytest.param(lambda: math.inf, id="float_inf"),
    pytest.param(lambda: -math.inf, id="float_neg_inf"),
    pytest.param(lambda: math.nan, id="float_nan"),
    pytest.param(lambda: complex(1, 2), id="complex"),
    # --- immutable sequences ----------------------------------------------
    pytest.param(lambda: "", id="str_empty"),
    pytest.param(lambda: "hello", id="str_plain"),
    pytest.param(lambda: "it's \"quoted\" \\ back\nnew\ttab", id="str_quotes"),
    pytest.param(lambda: "héllo ✓ 🎉", id="str_unicode"),
    pytest.param(lambda: (), id="tuple_empty"),
    pytest.param(lambda: (1,), id="tuple_single"),
    pytest.param(lambda: (1, (2, "three"), None), id="tuple_nested"),
    pytest.param(lambda: b"abc\x00\xff", id="bytes"),
    # --- mutable sequences ------------------------------------------------
    pytest.param(lambda: [], id="list_empty"),
    pytest.param(lambda: [1, 2, 3], id="list_flat"),
    pytest.param(lambda: [1, "two", 3.0, None, True], id="list_hetero"),
    pytest.param(lambda: [[1, 2], [3, [4]]], id="list_nested"),
    pytest.param(lambda: [1, 1, 0], id="list_dup_values"),
    pytest.param(_self_ref_list, id="list_self_cycle"),
    pytest.param(_shared_sublist, id="list_shared_sublist"),
    pytest.param(lambda: bytearray(b"ba"), id="bytearray"),
    # --- mappings ---------------------------------------------------------
    pytest.param(lambda: {}, id="dict_empty"),
    pytest.param(lambda: {"a": 1, "b": 2}, id="dict_simple"),
    pytest.param(lambda: {"b": 2, "a": 1, "c": 3}, id="dict_insertion_order"),
    pytest.param(lambda: {2: "two", 1: "one"}, id="dict_int_keys"),
    pytest.param(lambda: {(1, "a"): "pair", None: "none-key"}, id="dict_tuple_key"),
    pytest.param(
        lambda: {"outer": {"inner": [1, {"deep": True}]}}, id="dict_nested"
    ),
    pytest.param(_self_ref_dict, id="dict_self_cycle"),
    # --- other builtin forms ----------------------------------------------
    pytest.param(lambda: range(1, 10, 2), id="range"),
    # Named singletons reify by reference: the datum records an importable
    # identity, reify returns the identical object, and even address-bearing
    # reprs match (function/module). Lambdas have no importable name.
    pytest.param(lambda: dict, id="type_object"),
    pytest.param(lambda: module_level_function, id="function"),
    pytest.param(lambda: len, id="builtin_function"),
    pytest.param(lambda: math, id="module"),
    pytest.param(lambda: memoryview(b"mv"), id="memoryview", marks=_IDENTITY_REPR),
    pytest.param(lambda: (lambda x: x), id="lambda", marks=_IDENTITY_REPR),
    # --- dataclasses ------------------------------------------------------
    pytest.param(lambda: Point(3, 4), id="dc_point"),
    pytest.param(
        lambda: Segment("s", [Point(0, 0), Point(1, 1)]), id="dc_nested"
    ),
    pytest.param(lambda: WithDefault("n"), id="dc_default"),
    pytest.param(lambda: FrozenPoint(1, 2), id="dc_frozen"),
    pytest.param(lambda: NoReprField(5), id="dc_norepr_field"),
    # Underscore-prefixed fields are ordinary declared fields. The override
    # case is the one that catches a name-based skip: with the default value
    # the class attribute would mask a missing field, but an instance value
    # of 99 cannot be recovered from the class default of 7.
    pytest.param(lambda: HiddenField(1), id="dc_underscore_default"),
    pytest.param(lambda: HiddenField(1, 99), id="dc_underscore_override"),
    # --- ordinary user-defined objects ------------------------------------
    pytest.param(lambda: Rect(3, 4), id="obj_with_property"),
    pytest.param(lambda: Slotted(1, "b"), id="obj_slotted"),
    pytest.param(
        lambda: Team("core", [Rect(1, 2), Slotted(3, "d")]), id="obj_composite"
    ),
    pytest.param(lambda: Opaque(), id="obj_default_repr", marks=_IDENTITY_REPR),
    # --- long tail of class-based values ----------------------------------
    pytest.param(lambda: Color.RED, id="enum_member"),
    pytest.param(
        lambda: MyInt(5),
        id="int_subclass",
        marks=_unsupported(
            "object.__new__ cannot allocate int subclasses; reifies to a proxy"
        ),
    ),
    pytest.param(
        lambda: MyStr("s"),
        id="str_subclass",
        marks=_unsupported(
            "object.__new__ cannot allocate str subclasses; reifies to a proxy"
        ),
    ),
    # --- deep mixed composition -------------------------------------------
    pytest.param(
        lambda: {
            "pts": [Point(0, 1), (2, {"k": [None, True]})],
            ("t", "k"): 3.5,
        },
        id="mixed_deep",
    ),
]


@pytest.mark.parametrize("factory", CASES)
def test_inspection_string_reproduced(factory):
    value = factory()
    assert replit(_datum(value)) == repr(value)


# ---------------------------------------------------------------------------
# Set types — canonical comparison (repr order is not a function of the value)
# ---------------------------------------------------------------------------

SET_CASES = [
    pytest.param(lambda: set(), id="set_empty"),
    pytest.param(lambda: {1, 2, 3}, id="set_ints"),
    pytest.param(lambda: {"a", "b", "c"}, id="set_strs"),
    pytest.param(lambda: {1, "a", (2, 3)}, id="set_mixed"),
    pytest.param(lambda: {(1, 2), (3, 4)}, id="set_tuple_elems"),
    pytest.param(lambda: frozenset(), id="frozenset_empty"),
    pytest.param(lambda: frozenset({1, 2}), id="frozenset_ints"),
]


@pytest.mark.parametrize("factory", SET_CASES)
def test_set_inspection_canonicalized(factory):
    value = factory()
    rebuilt = reify(_datum(value))
    assert type(rebuilt) is type(value)
    assert sorted(repr(e) for e in rebuilt) == sorted(repr(e) for e in value)

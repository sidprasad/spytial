"""Tests for CnDDataInstanceBuilder.reify — the inverse of build_instance.

These cover the regression reported as sidprasad/spytial#90:

* self-loops (``n.next = n``, ``lst.append(lst)``, ``d['self'] = d``)
* bidirectional references (``a.next = b; b.next = a``)
* longer cycles (``a -> b -> c -> a``)
* rootId survives a build -> reify round-trip
* rootId is honoured even when topology alone would pick a different atom
"""

import enum
import math
from dataclasses import dataclass, field
from typing import List, Optional

from spytial.provider_system import CnDDataInstanceBuilder
from spytial.structured_input import _make_dataclass_reifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_reifier_for(*dc_types):
    r = CnDDataInstanceBuilder()
    for t in dc_types:
        r.register_reifier(t.__name__, _make_dataclass_reifier(t))
    return r


# ---------------------------------------------------------------------------
# Happy path: acyclic reconstruction still works
# ---------------------------------------------------------------------------


@dataclass
class Point:
    x: int
    y: int


@dataclass
class Line:
    start: Optional[Point] = None
    end: Optional[Point] = None


def test_reify_acyclic_dataclass():
    line = Line(start=Point(1, 2), end=Point(3, 4))
    di = CnDDataInstanceBuilder().build_instance(line)
    out = _make_reifier_for(Line, Point).reify(di)
    assert isinstance(out, Line)
    assert out.start == Point(1, 2)
    assert out.end == Point(3, 4)


def test_reify_nested_list_and_dict():
    data = {"nums": [1, 2, 3], "meta": {"k": "v"}}
    di = CnDDataInstanceBuilder().build_instance(data)
    out = CnDDataInstanceBuilder().reify(di)
    assert out == data


# ---------------------------------------------------------------------------
# Self-loops
# ---------------------------------------------------------------------------


@dataclass
class Node:
    val: int = 0
    nxt: Optional["Node"] = None


def test_reify_dataclass_self_loop():
    n = Node(42)
    n.nxt = n
    di = CnDDataInstanceBuilder().build_instance(n)
    out = _make_reifier_for(Node).reify(di)

    assert isinstance(out, Node)
    assert out.val == 42
    assert out.nxt is out


def test_reify_list_self_loop():
    lst: list = [1, 2]
    lst.append(lst)
    di = CnDDataInstanceBuilder().build_instance(lst)
    out = CnDDataInstanceBuilder().reify(di)

    assert isinstance(out, list)
    assert len(out) == 3
    assert out[0] == 1
    assert out[1] == 2
    assert out[2] is out


def test_reify_dict_self_loop():
    d: dict = {"a": 1}
    d["self"] = d
    di = CnDDataInstanceBuilder().build_instance(d)
    out = CnDDataInstanceBuilder().reify(di)

    assert isinstance(out, dict)
    assert out["a"] == 1
    assert out["self"] is out


# ---------------------------------------------------------------------------
# Complex (non-primitive) dict keys are walked, so they keep their contents
# ---------------------------------------------------------------------------


def test_reify_tuple_dict_key():
    # Regression: a tuple key used to get a synthetic, un-walked key atom and
    # reified to an empty tuple ({('a', 'b'): 1} -> {(): 1}).
    d = {("a", "b"): 1, ("c",): 2}
    di = CnDDataInstanceBuilder().build_instance(d)
    out = CnDDataInstanceBuilder().reify(di)

    assert isinstance(out, dict)
    assert out[("a", "b")] == 1
    assert out[("c",)] == 2
    assert repr(out) == repr(d)


def test_reify_nested_tuple_dict_key():
    d = {("a",): {("b",): [1, 2]}}
    out = CnDDataInstanceBuilder().reify(CnDDataInstanceBuilder().build_instance(d))
    assert out[("a",)][("b",)] == [1, 2]
    assert repr(out) == repr(d)


def test_reify_object_dict_key():
    # A custom, importable object as a dict key rebuilds the real class (Vec
    # hashes by identity, so look the value up via the reconstructed key).
    d = {Vec(1, 2): "here"}
    out = CnDDataInstanceBuilder().reify(CnDDataInstanceBuilder().build_instance(d))

    assert isinstance(out, dict) and len(out) == 1
    out_key = next(iter(out))
    assert type(out_key) is Vec
    assert repr(out_key) == "Vec<1,2>"
    assert out[out_key] == "here"


def test_reify_frozenset_value():
    fs = frozenset({"a", "b"})
    out = CnDDataInstanceBuilder().reify(CnDDataInstanceBuilder().build_instance(fs))
    assert type(out) is frozenset
    assert out == fs


def test_reify_frozenset_dict_key():
    # The fix walks a frozenset key like any value, so its elements survive the
    # round-trip instead of collapsing to the empty shell the bug produced for
    # complex keys — and a frozenset now reifies to a real frozenset, so the key
    # is genuinely usable for lookup with an equal frozenset.
    fs = frozenset({"a", "b"})
    out = CnDDataInstanceBuilder().reify(
        CnDDataInstanceBuilder().build_instance({fs: 1})
    )

    assert isinstance(out, dict) and len(out) == 1
    key = next(iter(out))
    assert isinstance(key, frozenset)
    assert key == {"a", "b"}  # contents preserved, not an empty shell
    assert out[frozenset({"a", "b"})] == 1


def test_reify_frozenset_member_cycle_rebuilds_real_frozenset():
    # A frozenset whose member refers back to it (fs -> bag -> fs). A frozenset
    # is immutable, so it cannot be registered before its members exist; entered
    # via the frozenset, the member is built first and its back-reference rebuilds
    # a second, equal frozenset. Identity is not preserved here — this matches
    # copy.deepcopy (only pickle's deferred memo keeps it). Assert the real type
    # and structural equality, not `is`.
    bag = Bag()
    fs = frozenset({bag})
    bag.ref = fs

    out = CnDDataInstanceBuilder().reify(CnDDataInstanceBuilder().build_instance(fs))
    member = next(iter(out))
    assert type(out) is frozenset
    assert type(member) is Bag
    assert type(member.ref) is frozenset
    assert member.ref == out


def test_reify_frozenset_member_cycle_closes_via_member_entry():
    # Entering via the back-referencing member registers it before the frozenset
    # is built, so this path does close the cycle on a single object.
    bag = Bag()
    bag.ref = frozenset({bag})

    out = CnDDataInstanceBuilder().reify(CnDDataInstanceBuilder().build_instance(bag))
    assert type(out) is Bag
    assert type(out.ref) is frozenset
    assert next(iter(out.ref)) is out


# ---------------------------------------------------------------------------
# Multi-node cycles
# ---------------------------------------------------------------------------


def test_reify_bidirectional_cycle():
    a = Node(1)
    b = Node(2)
    a.nxt = b
    b.nxt = a
    di = CnDDataInstanceBuilder().build_instance(a)
    out = _make_reifier_for(Node).reify(di)

    assert isinstance(out, Node)
    assert out.val == 1
    assert out.nxt is not None
    assert out.nxt.val == 2
    # The cycle must close back onto the original root.
    assert out.nxt.nxt is out


@dataclass
class Triple:
    label: str = ""
    nxt: Optional["Triple"] = None


def test_reify_three_cycle():
    a = Triple("a")
    b = Triple("b")
    c = Triple("c")
    a.nxt = b
    b.nxt = c
    c.nxt = a
    di = CnDDataInstanceBuilder().build_instance(a)
    out = _make_reifier_for(Triple).reify(di)

    assert out.label == "a"
    assert out.nxt.label == "b"
    assert out.nxt.nxt.label == "c"
    assert out.nxt.nxt.nxt is out


# ---------------------------------------------------------------------------
# Generic (non-dataclass) object with self-loop
# ---------------------------------------------------------------------------


class Bag:
    pass


def test_reify_generic_object_self_loop():
    b = Bag()
    b.self_ref = b
    b.tag = "hello"
    di = CnDDataInstanceBuilder().build_instance(b)
    out = CnDDataInstanceBuilder().reify(di)

    # The atom carries Bag's module + qualname, so reify rebuilds the REAL
    # class (object.__new__ + setattr), not an attribute-bag proxy — and the
    # self-reference still resolves to the same object.
    assert type(out) is Bag
    assert getattr(out, "self_ref") is out
    assert getattr(out, "tag") == "hello"


# ---------------------------------------------------------------------------
# rootId handling
# ---------------------------------------------------------------------------


def test_build_instance_emits_root_id():
    n = Node(7)
    di = CnDDataInstanceBuilder().build_instance(n)
    assert "rootId" in di
    root_atom = next(a for a in di["atoms"] if a["id"] == di["rootId"])
    assert root_atom["type"] == "Node"


def test_reify_uses_stored_root_id_for_self_loop():
    """Without a cached root, topology can't pick the right atom in a self-loop."""
    n = Node(99)
    n.nxt = n
    di = CnDDataInstanceBuilder().build_instance(n)
    # Sanity: root is the Node atom.
    assert di["rootId"].startswith("n")
    out = _make_reifier_for(Node).reify(di)
    assert isinstance(out, Node) and out.val == 99


def test_reify_explicit_root_id_overrides_stored():
    # Graph with two disconnected components: a Node and a standalone int.
    # The stored rootId is the Node; we force reify to start from the int.
    n = Node(5)
    di = CnDDataInstanceBuilder().build_instance(n)
    # Feed the reifier an explicit root_id that is a different atom.
    int_atom_id = next(
        a["id"] for a in di["atoms"] if a["type"] == "int"
    )
    out = _make_reifier_for(Node).reify(di, root_id=int_atom_id)
    assert out == 5


def test_reify_falls_back_when_stored_root_is_missing():
    n = Node(3)
    di = CnDDataInstanceBuilder().build_instance(n)
    di["rootId"] = "does-not-exist"
    # Topology fallback still recovers the Node.
    out = _make_reifier_for(Node).reify(di)
    assert isinstance(out, Node) and out.val == 3


def test_reify_survives_stripped_root_id():
    """Simulates the widget round-trip where spytial-core drops rootId."""
    n = Node(11)
    n.nxt = n
    di = CnDDataInstanceBuilder().build_instance(n)
    cached_root = di.pop("rootId")
    # Without rootId in the dict, passing it explicitly still works.
    out = _make_reifier_for(Node).reify(di, root_id=cached_root)
    assert isinstance(out, Node)
    assert out.val == 11
    assert out.nxt is out


# ---------------------------------------------------------------------------
# Dataclass reifier details
# ---------------------------------------------------------------------------


@dataclass
class WithDefaults:
    a: int = 1
    b: int = 2
    tags: List[str] = field(default_factory=list)


def test_dataclass_reifier_fills_defaults_for_missing_fields():
    # Build an instance that only sets `a`; drop the relations for `b` and `tags`
    # to mimic a data instance that the frontend stripped fields from.
    inst = WithDefaults(a=7, b=9, tags=["x"])
    di = CnDDataInstanceBuilder().build_instance(inst)
    di["relations"] = [r for r in di["relations"] if r["name"] == "a"]

    out = _make_reifier_for(WithDefaults).reify(di)
    assert isinstance(out, WithDefaults)
    assert out.a == 7
    assert out.b == 2           # default
    assert out.tags == []        # default_factory


def test_dataclass_reifier_backcompat_3arg_signature():
    """Reifiers registered with the old (atom, relations, reify_atom) signature
    must keep working for acyclic data — we only fall back to the cycle-safe
    path if they opt in.
    """

    @dataclass
    class Simple:
        x: int = 0

    def old_style_reifier(atom, relations, reify_atom):
        kwargs = {}
        for name, targets in relations.items():
            kwargs[name] = reify_atom(targets[0])
        return Simple(**kwargs)

    r = CnDDataInstanceBuilder()
    r.register_reifier("Simple", old_style_reifier)

    di = CnDDataInstanceBuilder().build_instance(Simple(x=42))
    out = r.reify(di)
    assert out == Simple(x=42)


# ---------------------------------------------------------------------------
# Rebuilding the REAL object (object.__new__ via module/qualname) + replit
# ---------------------------------------------------------------------------


class Vec:
    """Plain (non-dataclass) class with a non-structural custom __repr__."""

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Vec<{self.x},{self.y}>"


def test_reify_rebuilds_real_class_with_custom_repr():
    v = Vec(1, 2)
    di = CnDDataInstanceBuilder().build_instance(v)
    out = CnDDataInstanceBuilder().reify(di)
    # The genuine class — so the real (custom, non-structural) __repr__ runs,
    # something an attribute-bag proxy could never reproduce.
    assert type(out) is Vec
    assert repr(out) == repr(v) == "Vec<1,2>"


def test_replit_matches_repr_for_custom_class():
    v = Vec(3, 4)
    di = CnDDataInstanceBuilder().build_instance(v)
    assert CnDDataInstanceBuilder().replit(di) == repr(v)


def test_replit_matches_repr_for_nested_builtins():
    value = {"nums": [1, 2, 3], "tag": "hi"}
    di = CnDDataInstanceBuilder().build_instance(value)
    assert CnDDataInstanceBuilder().replit(di) == repr(value)


# ---------------------------------------------------------------------------
# Property setters that reject the restored value (sidprasad/spytial#101 review)
# ---------------------------------------------------------------------------


class Account:
    """A validated setter that can reject the value the getter would report.

    The relationalizer records the public ``balance`` @property, so reify writes
    it back *through the setter* — which here refuses negative balances even
    though an overdrawn account reads one. Reconstruction must skip the rejected
    field, not abort.
    """

    def __init__(self, balance):
        self._balance = balance

    @property
    def balance(self):
        return self._balance

    @balance.setter
    def balance(self, value):
        if value < 0:
            raise ValueError("cannot set a negative balance")
        self._balance = value

    def __repr__(self):
        return f"Account({self._balance})"


def test_reify_skips_property_setter_that_rejects_value():
    a = Account(-50)  # overdrawn: balance reads -50, but the setter rejects -50
    di = CnDDataInstanceBuilder().build_instance(a)
    # 'balance' is recorded via the public @property, so reify routes it back
    # through the validating setter, which raises ValueError on -50.
    assert any(r["name"] == "balance" for r in di["relations"])
    # The raising setter must be skipped — reify still returns the real class
    # rather than aborting the whole reconstruction.
    out = CnDDataInstanceBuilder().reify(di)
    assert type(out) is Account


# ---------------------------------------------------------------------------
# Leaf primitives: complex, bytes, bytearray, range, NotImplemented, Ellipsis
# ---------------------------------------------------------------------------


def _rt(value):
    b = CnDDataInstanceBuilder()
    return b.reify(b.build_instance(value))


def test_reify_complex_value():
    assert _rt(complex(1, -2)) == complex(1, -2)
    assert _rt(complex(float("inf"), 1.5)) == complex(float("inf"), 1.5)


def test_reify_bytes_value():
    assert _rt(b"ab\x00\xff") == b"ab\x00\xff"
    assert _rt(b"") == b""


def test_reify_bytearray_is_fresh_mutable_copy():
    ba = bytearray(b"mut")
    out = _rt(ba)
    assert isinstance(out, bytearray) and out == ba and out is not ba


def test_reify_equal_bytearrays_stay_distinct_objects():
    # Mutable: two equal bytearrays must not collapse onto one atom/object.
    pair = [bytearray(b"x"), bytearray(b"x")]
    out = _rt(pair)
    assert out == pair and out[0] is not out[1]


def test_reify_singletons():
    assert _rt(NotImplemented) is NotImplemented
    assert _rt(...) is ...


def test_reify_range():
    assert _rt(range(5)) == range(5)
    assert _rt(range(1, 10, 2)) == range(1, 10, 2)
    assert _rt(range(10, 0, -3)) == range(10, 0, -3)


# ---------------------------------------------------------------------------
# Reference semantics: enum members, functions, classes, modules reify to the
# identical object, not a reconstruction.
# ---------------------------------------------------------------------------


class Fruit(enum.Enum):
    APPLE = 1
    BANANA = 2


class Priority(enum.IntEnum):
    LOW = 1
    HIGH = 2


def top_level_helper(x):
    return x


def test_reify_enum_member_is_singleton():
    assert _rt(Fruit.APPLE) is Fruit.APPLE


def test_reify_intenum_routes_to_enum_not_int():
    # IntEnum members are isinstance(int); the enum relationalizer must
    # outrank the primitive one or they'd come back as plain ints.
    out = _rt(Priority.HIGH)
    assert out is Priority.HIGH and type(out) is Priority


def test_reify_function_by_reference():
    assert _rt(top_level_helper) is top_level_helper


def test_reify_builtin_function_by_reference():
    assert _rt(len) is len
    assert _rt(math.sqrt) is math.sqrt


@dataclass
class UnderscoreNode:
    value: int
    _next: Optional["UnderscoreNode"] = None


@dataclass
class WithUnderscoreDefault:
    shown: int
    _secret: int = 7


def test_underscore_dataclass_fields_are_relationalized():
    # A `_`-prefixed field is declared schema, not a privacy boundary. Skipping
    # it used to erase the whole chain: this list drew as one node, no edges.
    head = UnderscoreNode(1, UnderscoreNode(2, UnderscoreNode(3)))
    di = CnDDataInstanceBuilder().build_instance(head)
    assert {r["name"] for r in di["relations"]} == {"value", "_next"}
    assert sum(1 for a in di["atoms"] if a["type"] == "UnderscoreNode") == 3


def test_reify_recovers_underscore_field_instance_value():
    # The class default (7) must not stand in for the instance's value (99).
    obj = WithUnderscoreDefault(1, 99)
    out = _rt(obj)
    assert out._secret == 99
    assert repr(out) == repr(obj)


def test_reify_builtin_bound_method_falls_back_to_proxy():
    # [].append has __module__ = None; resolving its qualname would return the
    # unbound descriptor, so it gets no reference metadata and proxies instead.
    lst = [1]
    out = _rt(lst.append)
    assert out is not lst.append and not callable(out)


def test_reify_class_object_by_reference():
    assert _rt(dict) is dict
    assert _rt(Fruit) is Fruit


def test_reify_module_by_reference():
    assert _rt(math) is math


def test_reify_lambda_falls_back_to_proxy():
    # No importable name — reference metadata is withheld and the structural
    # proxy fallback still returns *something* rather than raising.
    fn = lambda x: x  # noqa: E731
    out = _rt(fn)
    assert out is not fn and not callable(out)
    assert type(out).__name__ == "function"

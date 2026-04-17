"""Tests for CnDDataInstanceBuilder.reify — the inverse of build_instance.

These cover the regression reported as sidprasad/spytial#90:

* self-loops (``n.next = n``, ``lst.append(lst)``, ``d['self'] = d``)
* bidirectional references (``a.next = b; b.next = a``)
* longer cycles (``a -> b -> c -> a``)
* rootId survives a build -> reify round-trip
* rootId is honoured even when topology alone would pick a different atom
"""

from dataclasses import dataclass, field
from typing import List, Optional

import pytest

from spytial.provider_system import CnDDataInstanceBuilder
from spytial.dataclass_builder import _make_dataclass_reifier


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

    # _reify_generic_object produces an attribute-bag, not the original class,
    # but the self-reference should still resolve to the same object.
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

"""What the decorators entail, checked by spytial-core's conformance harness.

Each test here is a claim about a decorator, not about a drawing. ``must.leftOf``
means *in every layout the spec permits*, so nothing depends on where the force
simulation happened to put a node, and nothing needs a browser. See
:mod:`conformance` for why that is the only stable thing to assert.

The suite skips whole when there is no ``node`` runtime, so a plain
``pip install`` still tests clean.
"""

from __future__ import annotations

import subprocess

import pytest

import spytial
import conformance
from conformance import check, codes, explain, run_case, run_cases
from conformance import CHECK_BIN, NODE, requires_harness
from spytial.core_assets import SPYTIAL_CORE_VERSION

pytestmark = requires_harness


# --------------------------------------------------------------------------- #
# Fixtures: small annotated shapes.
# --------------------------------------------------------------------------- #


@spytial.orientation(
    selector="{x : TreeNode, y : TreeNode | x.left = y}", directions=["left", "below"]
)
@spytial.orientation(
    selector="{x : TreeNode, y : TreeNode | x.right = y}", directions=["right", "below"]
)
class TreeNode:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right


@spytial.orientation(
    selector="{x : DagNode, y : DagNode | y in x.kids.idx[int]}", directions=["below"]
)
class DagNode:
    """A node whose children live in a *list*, reached through ``idx``."""

    def __init__(self, name, kids=None):
        self.name = name
        self.kids = kids or []


@spytial.orientation(
    selector="{x : NaiveNode, y : NaiveNode | y in x.kids}", directions=["below"]
)
class NaiveNode:
    """The same shape, with the selector everyone writes first. It matches nothing."""

    def __init__(self, name, kids=None):
        self.name = name
        self.kids = kids or []


@spytial.cyclic(
    selector="{x : RingNode, y : RingNode | x.next = y}", direction="clockwise"
)
class RingNode:
    """A ring. ``tag`` hangs a node off the ring without joining it."""

    def __init__(self, name, tag=None):
        self.name = name
        self.next = None
        self.tag = tag


@spytial.cyclic(
    selector="{x : NoRing, y : NoRing | x.next = y}",
    direction="clockwise",
    hold="never",
)
class NoRing:
    """The same ring, asserted *not* to be drawn as one."""

    def __init__(self, name):
        self.name = name
        self.next = None


_CONFLICT_SELECTOR = "{x : Conflict, y : Conflict | x.next = y}"


@spytial.cyclic(selector=_CONFLICT_SELECTOR, direction="clockwise")
@spytial.cyclic(selector=_CONFLICT_SELECTOR, direction="counterclockwise")
class Conflict:
    """One selector told to turn both ways."""

    def __init__(self, name):
        self.name = name
        self.next = None


@spytial.hideAtom(selector="Bookkeeping")
@spytial.orientation(selector="{x : Row, y : Row | x.next = y}", directions=["below"])
class Row:
    """Rows stack downward. ``meta`` is a node meant to stay out of the picture."""

    def __init__(self, name, nxt=None, meta=None):
        self.name = name
        self.next = nxt
        self.meta = meta


class Bookkeeping:
    """A node the author wants in the data but not in the diagram."""

    def __init__(self, note):
        self.note = note


@spytial.hideAtom(selector="{n : Tidy | n.internal = True}")
@spytial.orientation(selector="{x : Tidy, y : Tidy | x.next = y}", directions=["below"])
class Tidy:
    """Both forms read the same ``internal`` flag off the data.

    So which atoms get hidden is a property of the *datum*, not of the
    decorators -- which is what lets the two cases below differ by one boolean
    and still be the same spec.
    """

    def __init__(self, name, internal=False, nxt=None):
        self.name = name
        self.internal = internal
        self.next = nxt


@spytial.hideAtom(selector="{n : BareFlag | n.internal}")
class BareFlag:
    """A field used as if it were a boolean. It is a set of atoms, so this errors."""

    def __init__(self, name, internal=False):
        self.name = name
        self.internal = internal


@spytial.hideAtom(selector="{n : Linked | some n.link}")
class Linked:
    """``some n.link`` reads as "has a link". Every atom has one."""

    def __init__(self, name, link=None):
        self.name = name
        self.link = link


@spytial.hideAtom(selector="{n : LinkedStrict | n.link = None}")
class LinkedStrict:
    """The same question, asked in the form that distinguishes."""

    def __init__(self, name, link=None):
        self.name = name
        self.link = link


@spytial.size(selector="Card", width=140, height=60)
class Card:
    def __init__(self, name, child=None):
        self.name = name
        self.child = child


class Plain:
    """An unsized neighbour, so ``sized()`` has something to not match."""

    def __init__(self, name):
        self.name = name


class Item:
    """Boxed by both groups below: keyed by its shelf, and by its type."""

    def __init__(self, name):
        self.name = name


class Shelf:
    def __init__(self, name, contents=None):
        self.name = name
        self.contents = contents or []


@spytial.group(
    selector="{s : Shelf, i : Item | i in s.contents.idx[int]}", name="shelf"
)
@spytial.group(selector="Item", name="stock")
class Store:
    """One box per shelf, plus one box holding every item.

    The binary selector keys a box on its first column and fills it from the
    last; the unary one has no key, so its box is named `stock` outright. That
    pair is what replaced the by-field form spytial-core 5.0 removed.
    """

    def __init__(self, shelves):
        self.shelves = shelves


def _ring(cls, n):
    """A cycle of ``n`` nodes, returned at its head."""
    nodes = [cls(f"r{i}") for i in range(n)]
    for i, node in enumerate(nodes):
        node.next = nodes[(i + 1) % n]
    return nodes[0]


def _tree():
    """n0 -> (n1 -> (n2, n3), n4). Ids are assigned in walk order."""
    return TreeNode(0, TreeNode(1, TreeNode(2), TreeNode(3)), TreeNode(4))


def _diamond(cls):
    """root -> (a, b), and both a and b -> leaf. One leaf, reachable two ways."""
    leaf = cls("leaf")
    return cls("root", [cls("a", [leaf]), cls("b", [leaf])])


def _atom_ids(obj, type_name):
    """The ids ``build_instance`` emitted for atoms of ``type_name``."""
    datum = spytial.CnDDataInstanceBuilder().build_instance(obj)
    return [a["id"] for a in datum["atoms"] if a["type"] == type_name]


# --------------------------------------------------------------------------- #
# Identity. The one no format check can catch: a walker that loses sharing
# still emits a perfectly well-formed graph.
# --------------------------------------------------------------------------- #


def test_sharing_survives_the_walk():
    """A node reachable by two paths is one atom, and the spec still lays out."""
    root = _diamond(DagNode)
    assert len(_atom_ids(root, "DagNode")) == 4, "the shared leaf was copied"

    check(
        "diamond",
        root,
        [
            {
                "query": "must.below(n0)",
                "count": 3,
                "because": "every other node is a descendant of the root",
            }
        ],
    )


def test_one_object_as_both_children_is_unsatisfiable():
    """Identity is load-bearing, and the solver is what proves it was kept.

    Using one object as both ``left`` and ``right`` asks for a single node to sit
    on both sides of its parent. spytial keeps it as one atom, so the spec is
    contradictory and the harness says so. A walker that had quietly copied the
    object would produce two atoms, two consistent constraints, and a diagram
    drawn as if nothing were wrong -- which is exactly the bug this catches.
    """
    shared = TreeNode(9)
    degenerate = TreeNode(0, shared, shared)
    assert len(_atom_ids(degenerate, "TreeNode")) == 2, "the shared child was copied"

    result = run_case("both children are one object", degenerate)
    assert not result["ok"]
    assert "layout/unsatisfiable" in codes(result)

    # The counterfactual, which is what makes the above evidence of anything:
    # two distinct children holding equal values are three atoms and lay out
    # fine. Same values, same decorators -- only identity differs.
    distinct = TreeNode(0, TreeNode(9), TreeNode(9))
    assert len(_atom_ids(distinct, "TreeNode")) == 3
    check("distinct children with equal values", distinct)


# --------------------------------------------------------------------------- #
# Orientation: the decorators say what their author meant.
# --------------------------------------------------------------------------- #


def test_tree_children_land_on_the_side_they_were_given():
    check(
        "tree sides",
        _tree(),
        [
            {"query": "must.leftOf(n0)", "contains": ["n1"]},
            {"query": "must.rightOf(n0)", "contains": ["n4"]},
            {
                "query": "must.leftOf(n0)",
                "excludes": ["n4"],
                "because": "a right child never lands left of its parent",
            },
            {
                "query": "must.below(n0)",
                "contains": ["n1", "n4"],
                "because": "both directions lists carry 'below'",
            },
        ],
    )


def test_orientation_is_transitive_through_the_solver():
    """``must`` is closed under the constraints, not just the tuples that matched.

    ``n2`` is the left child of ``n1``, and nothing names it and ``n0`` together.
    It is still entailed to be left of ``n0``.
    """
    check(
        "tree transitivity",
        _tree(),
        [
            {
                "query": "must.leftOf(n0)",
                "contains": ["n2"],
                "because": "n2 is left of n1, which is left of n0",
            }
        ],
    )


# --------------------------------------------------------------------------- #
# List-valued fields. A list relationalizes to an intermediate `list` atom plus
# a ternary `idx` relation, so the obvious selector reaches nothing.
# --------------------------------------------------------------------------- #


def test_list_field_reaches_its_elements_through_idx():
    check(
        "list via idx",
        _diamond(DagNode),
        [
            {
                "query": "must.below(n0)",
                "count": 3,
                "because": "kids.idx[int] projects the list back to its elements",
            }
        ],
    )


def test_the_obvious_list_selector_silently_constrains_nothing():
    """``y in x.kids`` matches no pair, and nothing anywhere says so.

    ``x.kids`` is the intermediate ``list`` atom, never a ``NaiveNode``, so the
    comprehension is empty. It is not an error: the spec parses, the datum is
    well formed, the diagram renders -- with the decorator doing nothing. This
    test exists to pin that behaviour down as the reason ``idx`` is documented.
    """
    result = run_case(
        "list without idx",
        _diamond(NaiveNode),
        [{"query": "must.below(n0)", "empty": True}],
    )
    assert result["ok"], "expected a quiet no-op, not a reported failure"
    assert result["errors"] == []
    # "Silently" is the whole claim: not even a selector warning names it.
    assert result["warnings"] == []


# --------------------------------------------------------------------------- #
# Cyclic. A ring entails no pair's left/right, so `must` cannot see it at all;
# `cyclic()` (spytial-core 4.4.2) reports fragment membership instead.
# --------------------------------------------------------------------------- #


def test_a_ring_entails_membership_but_no_direction():
    """The claim @cyclic makes, and the one it does not.

    Rotating a ring gives another drawing that satisfies the same spec, so no
    pair is entailed to be left of, right of, above or below any other -- every
    ``must`` query comes back empty, with nothing wrong. What the spec does fix
    is who is *on* the ring, which is what ``cyclic()`` reports.
    """
    check(
        "ring of three",
        _ring(RingNode, 3),
        [
            {
                "query": "cyclic(n0)",
                "equals": ["n0", "n1", "n2"],
                "because": "all three nodes are on the one ring",
            },
            {
                "query": "must.leftOf(n0)",
                "empty": True,
                "because": "a rotation of the ring satisfies the spec equally",
            },
            {"query": "must.rightOf(n0)", "empty": True},
            {"query": "must.above(n0)", "empty": True},
            {"query": "must.below(n0)", "empty": True},
            {
                "query": "can.leftOf(n0)",
                "nonEmpty": True,
                "because": "not entailed is not impossible -- some layout allows it",
            },
        ],
    )


def test_a_two_node_cycle_is_still_a_fragment():
    """Membership is settled when the constraint selects, not when drawing needs it.

    Two atoms need no disjunction to place -- there is only one way round a
    two-cycle -- so an implementation that recorded fragments as it emitted
    disjunctions would report nothing here.
    """
    check(
        "ring of two",
        _ring(RingNode, 2),
        [{"query": "cyclic(n0)", "equals": ["n0", "n1"]}],
    )


def test_a_node_hanging_off_the_ring_is_not_on_it():
    """``cyclic()`` reports the fragment, not everything reachable from it."""
    ring = _ring(RingNode, 3)
    ring.tag = RingNode("outsider")

    result = check(
        "ring with an outsider",
        ring,
        [
            {"query": "cyclic(n0)", "equals": ["n0", "n1", "n2"]},
            {
                "query": "nodes()",
                "contains": ["n3"],
                "because": "the outsider is drawn, it is just not on the ring",
            },
        ],
    )
    assert result["ok"]


def test_hold_never_contributes_no_fragment():
    """``hold='never'`` asserts a ring is *absent*, so there is no ring to report."""
    check(
        "cycle asserted never to hold",
        _ring(NoRing, 3),
        [
            {
                "query": "cyclic(n0)",
                "empty": True,
                "because": "a negated cyclic constraint selects no fragment",
            }
        ],
    )


def test_two_directions_for_one_ring_is_refused():
    """The only consequence of ``direction`` this harness can see.

    Which way a ring turns is not entailed -- the mirrored drawing satisfies
    the same spec -- so no query distinguishes clockwise from counterclockwise,
    and swapping one for the other in the fixtures above changes no result. It
    is still load-bearing: two constraints that disagree about one selector are
    refused rather than silently resolved, which is what this pins down.
    """
    ring = _ring(Conflict, 3)
    result = run_case("a ring told to turn both ways", ring)
    assert not result["ok"]
    assert "spec/parse-failed" in codes(result)


# --------------------------------------------------------------------------- #
# Hiding. `hidden()` (spytial-core 4.4.2) names what @hideAtom removed, which
# `nodes()` can only show by absence.
# --------------------------------------------------------------------------- #


def test_hidden_atoms_leave_the_diagram_and_the_rest_still_lays_out():
    check(
        "hidden bookkeeping node",
        Row("a", Row("b"), Bookkeeping("internal")),
        [
            {
                "query": "hidden()",
                "equals": ["n1"],
                "because": "the Bookkeeping node, which walk order reached first",
            },
            {
                "query": "nodes()",
                "excludes": ["n1"],
                "because": "hidden() and nodes() are complements, not two views",
            },
            {
                "query": "must.below(n0)",
                "contains": ["n2"],
                "because": "hiding is surgical: the other constraints still hold",
            },
        ],
    )


def test_hiding_an_atom_a_constraint_needs_is_unsatisfiable():
    """The contradiction @hideAtom's docstring warns about, made checkable.

    Asking for an atom to be absent and for a constraint over it to hold cannot
    both be honoured. The counterfactual is the same spec on a datum with the
    flag cleared, so the difference is one boolean of data and not two
    different sets of decorators.
    """
    result = run_case("hide a constrained atom", Tidy("a", False, Tidy("b", True)))
    assert not result["ok"]
    assert "layout/unsatisfiable" in codes(result)

    check(
        "same spec, nothing flagged",
        Tidy("a", False, Tidy("b", False)),
        [
            {"query": "hidden()", "empty": True},
            {"query": "must.below(n0)", "contains": ["n1"]},
        ],
    )


def test_a_field_is_not_a_boolean_and_the_selector_says_so():
    """The counterpart to the quiet ``y in x.kids`` no-op: this one is reported.

    ``n.internal`` is the *set of atoms* the field points at, never a truth
    value, so a selector that uses it as a condition is rejected outright.
    Comparing it is the form that works, and the pair is here together because
    the difference between them is three characters.
    """
    result = run_case("field used as a condition", BareFlag("x", True))
    assert not result["ok"]
    assert "layout/selector-error" in codes(result)

    check(
        "field compared against a value",
        Tidy("a", True),
        [
            {
                "query": "hidden()",
                "equals": ["n0"],
                "because": "n.internal = True is the form that selects",
            }
        ],
    )


def test_none_is_an_atom_so_a_declared_field_is_never_empty():
    """``some n.link`` reads as "has a link" and matches everything, quietly.

    A field left at Python ``None`` still relates its object to the ``None``
    atom, so the multiplicity holds. Nothing reports this -- the selector is
    well formed and names only relations that exist -- and the whole diagram
    disappears. Asking whether a field is unset means comparing it.
    """
    result = run_case(
        "some, on an optional field",
        Linked("head", Linked("tail")),
        [{"query": "hidden()", "equals": ["n0", "n1"]}],
    )
    assert result["ok"], explain(result)
    assert result["errors"] == []
    assert result["warnings"] == []

    check(
        "the same question, compared",
        LinkedStrict("head", LinkedStrict("tail")),
        [
            {
                "query": "hidden()",
                "equals": ["n1"],
                "because": "only the tail's link is actually unset",
            }
        ],
    )


# --------------------------------------------------------------------------- #
# Size. `sized()` (spytial-core 4.4.2) matches the box exactly, so it answers
# @size without going anywhere near a rendered pixel.
# --------------------------------------------------------------------------- #


def test_size_fixes_the_box_exactly():
    check(
        "sized cards",
        Card("a", Card("b")),
        [
            {"query": "sized(140, 60)", "equals": ["n0", "n1"]},
            {
                "query": "sized(141, 60)",
                "empty": True,
                "because": "the constraint produces exactly the dimensions asked for",
            },
            {"query": "sized(140, 61)", "empty": True},
        ],
    )


def test_size_reaches_only_what_its_selector_names():
    """An auto-sized node can coincide with the numbers; this one cannot."""
    check(
        "one sized type beside an unsized one",
        Card("a", Plain("b")),
        [
            {"query": "sized(140, 60)", "equals": ["n0"]},
            {
                "query": "nodes()",
                "contains": ["n1"],
                "because": "the unsized neighbour is drawn, just not at that size",
            },
        ],
    )


# --------------------------------------------------------------------------- #
# Group. spytial-core 5.0 removed the by-field form and left the selector one
# as the only spelling, so what a `group` now boxes is worth asserting rather
# than assuming.
# --------------------------------------------------------------------------- #


def _store():
    """Two shelves, three items. Ids are assigned in walk order."""
    return Store([Shelf("top", [Item("mug"), Item("jar")]), Shelf("low", [Item("tin")])])


def test_a_keyed_group_boxes_its_members_and_not_its_key():
    check(
        "shelves box their items",
        _store(),
        [
            {
                "query": "groups()",
                "count": 3,
                "because": "one box per shelf, plus the single unkeyed `stock` box",
            },
            {
                "query": "grouped(n4)",
                "count": 2,
                "because": "the first item is in its shelf's box and in `stock`",
            },
            {
                "query": "grouped(n2)",
                "empty": True,
                "because": "a key is what the box is named for, not something inside it",
            },
        ],
    )


def test_a_unary_group_is_one_box_named_outright():
    """No key means no `name[key]` suffix, so the box can be named in a query."""
    check(
        "every item in one box",
        _store(),
        [
            {
                "query": "contains(stock)",
                "equals": ["n4", "n5", "n8"],
                "because": "the unary selector matched every Item and nothing else",
            },
            {
                "query": "contains(stock)",
                "excludes": ["n2", "n6"],
                "because": "the shelves are Shelf atoms; the selector named Item",
            },
        ],
    )


# --------------------------------------------------------------------------- #
# Datum well-formedness, checked on the raw dict -- before JSONDataInstance
# normalizes the evidence away.
# --------------------------------------------------------------------------- #


def _linked_pair_datum():
    class Cell:
        def __init__(self, value, nxt=None):
            self.value = value
            self.next = nxt

    return spytial.CnDDataInstanceBuilder().build_instance(Cell(1, Cell(2)))


def _datum_case(name, datum):
    return run_cases([{"name": name, "datum": datum, "spec": "constraints: []"}])[
        "cases"
    ][0]


def test_a_real_datum_is_well_formed():
    """The baseline the two corruptions below are corruptions of."""
    result = _datum_case("clean", _linked_pair_datum())
    assert result["ok"], explain(result)


def test_duplicate_atom_id_is_reported_rather_than_deduped():
    """The data instance would dedupe this and quietly lose a value."""
    datum = _linked_pair_datum()
    datum["atoms"].append(dict(datum["atoms"][-1]))

    result = _datum_case("duplicate id", datum)
    assert "datum/duplicate-atom-id" in codes(result)


def test_dangling_tuple_reference_is_located():
    """Checked raw, the report names the tuple; checked later, it names only the id."""
    datum = _linked_pair_datum()
    datum["relations"][0]["tuples"][0]["atoms"][-1] = "ghost"

    result = _datum_case("dangling ref", datum)
    assert "datum/dangling-tuple-atom" in codes(result)
    assert any(
        e.get("where", "").startswith("relations[0].tuples[0]")
        for e in result["errors"]
    ), "the report should name the tuple, not just the missing id"


# --------------------------------------------------------------------------- #
# The harness itself has to be the release whose specs it is checking.
# --------------------------------------------------------------------------- #


def test_vendored_harness_matches_the_pin():
    """Stated directly, so a stale bin fails once by name instead of everywhere."""
    reported = subprocess.run(
        [NODE, CHECK_BIN, "--version"], capture_output=True, text=True, timeout=60
    )
    assert reported.stdout.strip() == SPYTIAL_CORE_VERSION, (
        f"vendored spytial-check is {reported.stdout.strip()}, core_assets.py pins "
        f"{SPYTIAL_CORE_VERSION}. Run ./update-spytial-core.sh."
    )


def test_a_result_from_the_wrong_release_is_refused():
    """The provenance guard is the point; check it actually trips."""
    with pytest.raises(RuntimeError, match="pins"):
        conformance._check_provenance(
            {
                "formatVersion": conformance.SUPPORTED_FORMAT_VERSION,
                "spytialCoreVersion": "0.0.0-not-a-release",
            }
        )
    with pytest.raises(RuntimeError, match="conformance format"):
        conformance._check_provenance(
            {"formatVersion": 999, "spytialCoreVersion": "0.0.0"}
        )

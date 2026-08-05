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

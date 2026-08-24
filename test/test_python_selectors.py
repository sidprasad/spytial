#!/usr/bin/env python3
"""Tests for selectors written in Python (``spytial.selectors``).

A selector may be a Python function instead of an sgq expression. Three steps
turn one into the other: the function returns the values to select, each value
is translated to the ID of its atom, and the IDs are joined with ``->`` inside
a tuple and ``+`` between rows.

The timing is the design. The function runs during :func:`spytial.diagram`,
after the walk and before the spec is written, so the IDs it translates against
are the ones the relationalizer assigned to the instance about to be drawn.
:class:`TestTiming` is what pins that.

:class:`TestAgainstSgq` evaluates the compiled text through the headless bridge
and skips when ``node`` is absent. It is what keeps the emitter honest, because
the rules it encodes are properties of sgq rather than of this module, and none
of them is visible from Python.
"""

from __future__ import annotations

import pathlib
import warnings
from dataclasses import dataclass, field
from typing import Any, List

import pytest

import spytial
from spytial.provider_system import CnDDataInstanceBuilder
from spytial.selectors import (
    AtomNotInInstance,
    SelectorError,
    _literal,
    emit,
    materialise,
    refuse_python_selectors,
    resolve_decorators,
)
from spytial.suggest import _eval

requires_bridge = pytest.mark.skipif(
    not _eval.is_available(),
    reason="headless evaluator bridge unavailable (need a node runtime on PATH)",
)


@dataclass
class Node:
    val: int
    kids: List["Node"] = field(default_factory=list)


def tree():
    return Node(0, [Node(1), Node(2, [Node(3)])])


def built(obj):
    builder = CnDDataInstanceBuilder()
    return builder, builder.build_instance(obj)


def child_edges(values):
    """The flagship form: a comprehension over the walked values."""
    return [(n, k) for n in values if isinstance(n, Node) for k in n.kids]


def odd_nodes(values):
    return [n for n in values if isinstance(n, Node) and n.val % 2]


def terms(selector):
    return sorted(t.strip() for t in selector.split("+"))


# --------------------------------------------------------------------------- #
class TestTranslate:
    def test_tuples_become_a_union_of_products(self):
        root = tree()
        builder, instance = built(root)
        out = materialise(child_edges, root, builder, instance)
        assert len(terms(out)) == 3
        assert all("->" in t for t in terms(out))

    def test_values_become_a_union(self):
        root = tree()
        builder, instance = built(root)
        assert len(terms(materialise(odd_nodes, root, builder, instance))) == 2

    def test_primitives_translate_by_value(self):
        root = tree()
        builder, instance = built(root)
        out = materialise(
            lambda values: {n.val for n in values if isinstance(n, Node) and n.val % 2},
            root,
            builder,
            instance,
        )
        assert terms(out) == ["1", "3"]

    def test_a_list_value_is_a_value_not_a_row(self):
        # A list is an atom in its own right. Selecting the container atoms is
        # how the relationalizer's scaffolding gets hidden, and reading them as
        # rows would make an empty list a zero-width row.
        root = tree()
        builder, instance = built(root)
        out = materialise(
            lambda values: [v for v in values if isinstance(v, list)],
            root,
            builder,
            instance,
        )
        assert len(terms(out)) == 4  # one `kids` list per node
        assert "->" not in out

    def test_an_empty_result_is_the_empty_relation(self):
        root = tree()
        builder, instance = built(root)
        assert materialise(lambda values: [], root, builder, instance) == "none"

    def test_a_single_row_is_written_twice(self):
        # A lone primitive literal evaluates at arity 0; the slots need 1 or 2.
        assert emit([("1",)]) == "1 + 1"
        assert emit([("n0", "n2")]) == "n0 -> n2 + n0 -> n2"

    def test_no_parentheses_are_needed(self):
        assert emit([("n0", "n2"), ("n0", "n4")]) == "n0 -> n2 + n0 -> n4"

    def test_a_value_with_no_atom_is_dropped_with_a_warning(self):
        # sgq cannot report this -- a literal naming no atom evaluates non-empty
        # there -- but it need not be fatal: the rest of the selector still holds.
        root = tree()
        builder, instance = built(root)
        with pytest.warns(AtomNotInInstance, match="no atom for"):
            out = materialise(
                lambda values: odd_nodes(values) + [Node(99)], root, builder, instance
            )
        assert len(terms(out)) == 2  # the two real nodes survive

    def test_the_warning_can_be_made_fatal(self):
        root = tree()
        builder, instance = built(root)
        with warnings.catch_warnings():
            warnings.simplefilter("error", AtomNotInInstance)
            with pytest.raises(AtomNotInInstance):
                materialise(lambda values: [Node(99)], root, builder, instance)

    def test_rows_of_differing_length_are_an_error(self):
        root = tree()
        builder, instance = built(root)
        with pytest.raises(SelectorError, match="differing length"):
            materialise(lambda values: [(root,), (root, root)], root, builder, instance)


    def test_a_wrong_width_for_the_slot_is_an_error(self):
        # Core's selection helpers silently discard rows of the wrong width, so
        # an orientation fed unary rows would quietly stop applying.
        root = tree()
        builder, instance = built(root)
        with pytest.raises(SelectorError, match="rows of length"):
            materialise(odd_nodes, root, builder, instance, widths={2},
                        slot="orientation.selector")
        with pytest.raises(SelectorError, match="rows of length"):
            materialise(child_edges, root, builder, instance, widths={1},
                        slot="hideAtom.selector")

    def test_group_accepts_unary_rows(self):
        # The one binary slot that also takes unary rows: a unary selector
        # builds a single unkeyed group (language manifest).
        root = tree()
        builder, instance = built(root)
        entry = {"group": {"selector": odd_nodes, "name": "odd"}}
        out = resolve_decorators(
            {"constraints": [entry], "directives": []}, root, builder, instance
        )
        assert "->" not in out["constraints"][0]["group"]["selector"]

    def test_an_atom_with_no_literal_spelling_is_an_error(self):
        # bytes and complex IDs -- b'..' and (1+2j) -- do not parse as sgq, so
        # emitting them verbatim would fail in the browser instead of here.
        for value in (b"x", complex(1, 2)):
            builder, instance = built([value])
            with pytest.raises(SelectorError, match="no sgq literal spelling"):
                materialise(
                    lambda values, v=value: [v], [value], builder, instance
                )


    def test_a_sequence_unions_the_rows_of_every_frame(self):
        # A sequence rebuilds each frame in Python through one shared builder
        # with preserve_object_ids, so an atom ID names the same value in every
        # frame and the per-frame rows can be unioned into one entry.
        @spytial.orientation(selector=child_edges, directions=["below"])
        @dataclass
        class Tree(Node):
            pass

        root = Tree(0, [Tree(1)])
        seq = spytial.sequence(auto_open=False)
        seq.__enter__()
        seq.record(root)
        root.kids.insert(0, Tree(9))          # mutate in place, at the front
        seq.record(root)

        spec = seq._resolved_decorators()
        entries = spec["constraints"]
        assert len(entries) == 1, "one entry, not one per frame: %r" % (entries,)
        selector = entries[0]["orientation"]["selector"]
        assert len(terms(selector)) == 2, selector

    def test_a_sequence_keeps_atom_ids_stable_across_frames(self):
        # The premise the union rests on. Without it a term would name a
        # different value in each frame.
        builder = CnDDataInstanceBuilder(preserve_object_ids=True)
        kid = Node(1)
        root = Node(0, [kid])
        builder.build_instance(root)
        before = builder.atom_id_for(kid)
        root.kids.insert(0, Node(9))          # everything after would shift
        builder.build_instance(root)
        assert builder.atom_id_for(kid) == before

    def test_the_editor_refuses_one(self):
        # Unlike a sequence, the editor writes the specification once and the
        # browser changes the data afterwards; the function cannot run again.
        root = tree()
        spytial.annotate_atomStyle(
            root, selector=odd_nodes, borderStyle=spytial.BorderStyle(color="coral")
        )
        with pytest.raises(SelectorError, match="spytial.edit"):
            spytial.edit_html(root, method="browser", auto_open=False)

    def test_the_guard_ignores_sgq_selectors(self):
        refuse_python_selectors(
            {"constraints": [{"orientation": {"selector": "kids", "directions": ["below"]}}],
             "directives": []},
            "spytial.sequence()",
        )


# --------------------------------------------------------------------------- #
class TestTiming:
    """The IDs shall be the ones the relationalizer assigned to this instance."""

    def test_the_domain_is_exactly_what_has_atoms(self):
        # Why the function needs no separate walk: the values it is handed are
        # the values with atoms, so a comprehension over them always translates.
        root = tree()
        builder, instance = built(root)
        ids = {a["id"] for a in instance["atoms"]}
        for value in builder.walked_objects():
            assert builder.atom_id_for(value) in ids

    def test_the_first_walked_value_is_the_root(self):
        # values[0] is the diagrammed object, so a root-anchored selector needs
        # no extra parameter.
        root = tree()
        builder, instance = built(root)
        assert builder.walked_objects()[0] is root
        out = materialise(
            lambda values: [(values[0], k) for k in values[0].kids],
            root,
            builder,
            instance,
        )
        assert len(terms(out)) == 2

    def test_the_lookup_mints_nothing(self):
        # _get_id would invent an ID for an unwalked value, and the selector
        # would name an atom the instance does not contain.
        builder, _ = built(tree())
        before = dict(builder._seen)
        assert builder.atom_id_for(Node(99)) is None
        assert builder._seen == before

    def test_a_rebuild_reassigns_and_the_selector_follows(self):
        # An atom ID is a walk-order position. The same function run against two
        # builds gives each build's own IDs, which is the point of running it
        # during the diagram rather than before it.
        first_root = tree()
        b1, i1 = built(first_root)
        second_root = Node(0, [Node(9), Node(1), Node(2, [Node(3)])])
        b2, i2 = built(second_root)
        one = materialise(child_edges, first_root, b1, i1)
        two = materialise(child_edges, second_root, b2, i2)
        assert len(terms(one)) == 3 and len(terms(two)) == 4
        # Each is valid against its own instance and names only its own atoms.
        for selector, instance in ((one, i1), (two, i2)):
            ids = {a["id"] for a in instance["atoms"]}
            for term in terms(selector):
                assert all(part.strip() in ids for part in term.split("->"))


# --------------------------------------------------------------------------- #
class TestWiring:
    def test_deprecated_selector_slots_are_recognized(self):
        # icon/atomColor/edgeColor are deprecated and absent from
        # SELECTOR_ARITY, but their `selector` is still a selector slot.
        root = tree()
        builder, instance = built(root)
        entry = {"icon": {"selector": odd_nodes, "path": "person", "showLabels": True}}
        out = resolve_decorators(
            {"constraints": [], "directives": [entry]}, root, builder, instance
        )
        assert isinstance(out["directives"][0]["icon"]["selector"], str)

    def test_the_slot_arity_is_enforced_through_resolve(self):
        root = tree()
        builder, instance = built(root)
        entry = {"orientation": {"selector": odd_nodes, "directions": ["below"]}}
        with pytest.raises(SelectorError, match="orientation.selector"):
            resolve_decorators(
                {"constraints": [entry], "directives": []}, root, builder, instance
            )

    def test_a_function_in_a_non_selector_keyword_is_an_error(self):
        root = tree()
        builder, instance = built(root)
        decorators = {
            "constraints": [],
            "directives": [{"atomColor": {"selector": "Node", "value": odd_nodes}}],
        }
        with pytest.raises(SelectorError, match="not a selector"):
            resolve_decorators(decorators, root, builder, instance)

    def test_the_input_is_not_modified(self):
        root = tree()
        builder, instance = built(root)
        entry = {"orientation": {"selector": child_edges, "directions": ["below"]}}
        out = resolve_decorators(
            {"constraints": [entry], "directives": []}, root, builder, instance
        )
        assert entry["orientation"]["selector"] is child_edges
        assert isinstance(out["constraints"][0]["orientation"]["selector"], str)

    def test_sgq_selectors_pass_through_unchanged(self):
        root = tree()
        builder, instance = built(root)
        entry = {"orientation": {"selector": "kids", "directions": ["below"]}}
        out = resolve_decorators(
            {"constraints": [entry], "directives": []}, root, builder, instance
        )
        assert out["constraints"][0]["orientation"] == entry["orientation"]

    def test_two_annotations_on_one_object_both_survive(self):
        # The whole annotate path, function selectors included: collection on
        # the object, the walk, and resolution against the built instance.
        root = tree()
        spytial.annotate_orientation(root, selector=child_edges, directions=["below"])
        spytial.annotate_atomStyle(
            root, selector=odd_nodes, borderStyle=spytial.BorderStyle(color="coral")
        )
        builder, instance = built(root)
        out = resolve_decorators(
            builder.get_collected_decorators(), root, builder, instance
        )
        assert len(out["constraints"]) == 1
        assert len(out["directives"]) == 1
        assert "->" in out["constraints"][0]["orientation"]["selector"]

    def test_a_class_decorator_takes_the_same_function(self):
        # Nothing about the instance is known where this is written; the
        # function runs later, during the diagram.
        @spytial.orientation(selector=child_edges, directions=["below"])
        @dataclass
        class Tree:
            val: int
            kids: List["Tree"] = field(default_factory=list)

        root = Tree(0, [Tree(1), Tree(2)])
        builder, instance = built(root)
        out = resolve_decorators(
            builder.get_collected_decorators(), root, builder, instance
        )
        # child_edges filters on Node, which Tree is not -- the point is only
        # that the function was stored and ran; select Tree's own edges too.
        sel = out["constraints"][0]["orientation"]["selector"]
        assert isinstance(sel, str)

    def test_diagram_writes_the_translated_selector(self, tmp_path, monkeypatch):
        root = tree()
        spytial.annotate_orientation(root, selector=child_edges, directions=["below"])
        monkeypatch.chdir(tmp_path)
        html = pathlib.Path(
            spytial.diagram(root, method="file", auto_open=False)
        ).read_text()
        builder, instance = built(root)
        for term in terms(materialise(child_edges, root, builder, instance)):
            assert term in html or term.replace(">", "&gt;") in html
        assert "child_edges" not in html


# --------------------------------------------------------------------------- #
@requires_bridge
class TestAgainstSgq:
    """Every atom shall be reachable by the literal this module emits for it.

    The existence check differs by kind. A number or an object atom survives
    ``& univ``, and a literal naming no atom does not, which is what makes
    ``& univ`` a test of existence. A **string** literal is a value rather than a
    member of ``univ`` (``"plain" & str`` is empty even though ``str`` holds that
    atom), so a string is checked by the value it prints back.
    """

    VALUES = [
        0, 7, -3, True, False, None,
        1.5, -2.5, 1e30, 1e-10, -2.5e20, 1e16,
        float("inf"), float("-inf"), float("nan"),
        "plain", "", 'he said "hi"', "back\\slash", "a -> b", "x + y",
        "n0", "univ", "none",
    ]

    def _instance(self):
        @dataclass
        class Box:
            items: list
            child: Any = None

        box = Box(list(self.VALUES), Node(1))
        builder, instance = built(box)
        return box, builder, instance

    def _one(self, value, box, builder, instance):
        return materialise(lambda values, v=value: [v], box, builder, instance)

    def test_every_value_round_trips(self):
        box, builder, instance = self._instance()
        sels = [self._one(v, box, builder, instance) for v in self.VALUES]
        for value, verdict in zip(self.VALUES, _eval.evaluate_selectors(instance, sels)):
            assert verdict.ok, "%r emitted %r: %s" % (
                value,
                verdict.selector,
                verdict.error,
            )
            assert not verdict.empty, "%r emitted %r, which matched nothing" % (
                value,
                verdict.selector,
            )
            if isinstance(value, str):
                assert value in (verdict.pretty or ""), "%r printed back as %r" % (
                    value,
                    verdict.pretty,
                )

    def test_negative_infinity_takes_a_type_binding(self):
        # `-inf + -inf` is a parse error: a leading `-` before a name is not an
        # expression, though bare `inf` and `nan` are. Dropped from VALUES in an
        # earlier rewrite, which is how it got through.
        box, builder, instance = self._instance()
        sel = self._one(float("-inf"), box, builder, instance)
        assert sel.startswith("{f : float |")
        bare, bound = _eval.evaluate_selectors(
            instance, ["-inf + -inf", "(%s) & univ" % sel]
        )
        assert not bare.ok, "bare -inf is expected to be a parse error"
        assert bound.ok and not bound.empty

    def test_an_int_does_not_select_an_equal_float(self):
        # sgq's `&` compares numbers by value, so `(1 + 1) & float` is non-empty
        # even against a distinct float atom. That is not how core resolves an
        # atom selector: the render styles the int alone (verified in a browser).
        @dataclass
        class Pair:
            items: list

        box = Pair([1, 1.0])
        builder, instance = built(box)
        sel = materialise(lambda values: [1], box, builder, instance)
        assert sel == "1 + 1"
        ids = {a["id"]: a["type"] for a in instance["atoms"]}
        assert ids.get("1") == "int" and ids.get("1.0") == "float"

    def test_a_string_selects_the_atom_not_the_value(self):
        # A quoted str is a value in sgq: `"x" & univ` is empty, and a hideAtom
        # given one silently draws the atom anyway. Caught by the CLRS red-black
        # demo, whose colour strings would not hide.
        box, builder, instance = self._instance()
        sel = self._one("plain", box, builder, instance)
        assert sel.startswith("{s : str |")
        plain, intersected = _eval.evaluate_selectors(
            instance, ['"plain" & univ', "(%s) & univ" % sel]
        )
        assert plain.empty, "a bare quoted string is expected to be a value"
        assert not intersected.empty, "the emitted form shall be an atom"

    def test_numbers_are_real_atoms_not_free_literals(self):
        box, builder, instance = self._instance()
        cases = list(self.VALUES)
        sels = ["(%s) & univ" % self._one(v, box, builder, instance) for v in cases]
        for value, verdict in zip(cases, _eval.evaluate_selectors(instance, sels)):
            assert verdict.ok and not verdict.empty, (
                "%r did not survive & univ, so it is a literal and not an atom"
                % (value,)
            )

    def test_a_phantom_number_is_not_an_atom(self):
        # Why the membership check cannot be left to the evaluator: a numeric
        # literal naming no atom is non-empty.
        box, builder, instance = self._instance()
        free, intersected = _eval.evaluate_selectors(
            instance, ["999999 + 999999", "(999999 + 999999) & univ"]
        )
        assert not free.empty
        assert intersected.empty
        with pytest.warns(AtomNotInInstance):
            assert self._one(999999, box, builder, instance) == "none"

    def test_equal_but_distinct_objects_are_two_atoms(self):
        a, b = Node(1), Node(1)
        assert a == b and a is not b
        root = Node(0, [a, b])
        builder, instance = built(root)
        sel_a = materialise(lambda values: [a], root, builder, instance)
        sel_b = materialise(lambda values: [b], root, builder, instance)
        assert sel_a != sel_b
        va, vb = _eval.evaluate_selectors(instance, [sel_a, sel_b])
        assert va.pretty != vb.pretty

    def test_a_translated_selector_matches_the_structural_one(self):
        # End to end: the function ran against the render's own walk, and the
        # same atoms come out as sgq's own selector for those edges.
        root = tree()
        builder, instance = built(root)
        translated = materialise(child_edges, root, builder, instance)
        structural = "{ p : Node, c : Node | c in p.kids.idx[int] }"
        a, s = _eval.evaluate_selectors(instance, [translated, structural])
        normalise = lambda p: sorted(t.strip() for t in (p or "").split(","))
        assert normalise(a.pretty) == normalise(s.pretty)

    def test_literals_that_need_rewriting(self):
        assert "e" not in _literal(1e30, "1e+30")
        assert _literal(1.5, "1.5") == "1.5"
        assert _literal('he said "hi"', "x") == '{s : str | @:s = "he said \\"hi\\""}'
        assert _literal("back\\slash", "x") == '{s : str | @:s = "back\\\\slash"}'

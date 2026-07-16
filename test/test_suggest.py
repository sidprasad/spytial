#!/usr/bin/env python3
"""Tests for ``spytial.suggest`` — deterministic spec scaffolding.

Fixtures mirror the real structures in the repo (binary tree, red-black node,
linked list, n-ary tree, array heap). ``from __future__ import annotations``
makes every dataclass annotation a *string*, exercising the forward-reference
path the introspector has to handle.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import pytest

import spytial
from spytial.suggest import (
    HeuristicRegistry,
    Suggestion,
    build_class_info,
    suggest,
)
from spytial.suggest.rules import _LIST_HIDE


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


class Color(Enum):
    RED = "red"
    BLACK = "black"


@dataclass
class BTreeNode:
    value: int = 0
    left: Optional["BTreeNode"] = None
    right: Optional["BTreeNode"] = None


@dataclass
class LinkedNode:
    val: int = 0
    nxt: Optional["LinkedNode"] = None


@dataclass
class Point:
    x: int = 0
    y: int = 0


@dataclass
class NaryDC:
    value: int = 0
    children: List["NaryDC"] = field(default_factory=list)


class TreeNode:  # plain class — read via __init__ AST
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right


class RBNode:
    def __init__(self, key=None, color=Color.BLACK, left=None, right=None, parent=None):
        self.key = key
        self.color = color
        self.left = left
        self.right = right
        self.parent = parent


class NaryNode:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []


class ParentOnly:
    def __init__(self, val, parent=None):
        self.val = val
        self.parent = parent


class SlotsNode:  # __slots__ class, no __dict__ — graph walk must stay slots-aware
    __slots__ = ("sym", "freq", "zero_", "one_")

    def __init__(self, freq, sym=None, zero_=None, one_=None):
        self.sym = sym
        self.freq = freq
        self.zero_ = zero_
        self.one_ = one_


class MaxHeap:  # array/index-encoded — the ceiling case
    def __init__(self, data=None):
        self.a = [0]
        if data:
            self.a.extend(data)
        self.n = len(self.a) - 1


class AnnotatedNode:  # class-level annotations, not a dataclass
    next: Optional["AnnotatedNode"]
    weight: int


class PartlyAnnotated:  # one class annotation + __init__-only structural fields
    value: int

    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right


@dataclass
class PrivateChild:
    value: int = 0
    _next: Optional["PrivateChild"] = None


_FACTORY_CALLS = []


def _tracking_factory():
    _FACTORY_CALLS.append(1)
    return []


@dataclass
class WithFactory:
    value: int = 0
    items: list = field(default_factory=_tracking_factory)


@dataclass
class OptNoDefault:  # Optional self-ref fields with NO default value
    value: int
    left: Optional["OptNoDefault"]
    right: Optional["OptNoDefault"]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _entries(registry, name):
    """All payloads for a directive ``name`` across constraints + directives."""
    out = []
    for entry in registry["constraints"] + registry["directives"]:
        if name in entry:
            out.append(entry[name])
    return out


def _has(registry, name, **must):
    for payload in _entries(registry, name):
        if isinstance(payload, dict) and all(
            payload.get(k) == v for k, v in must.items()
        ):
            return True
    return False


def _edge(field):
    """The None-excluding selector emitted for a nullable edge."""
    return "%s - (univ -> NoneType)" % field


def _child_edge(cls_name, field):
    """The element-edge selector for a container of child nodes."""
    return "{ p : %s, c : %s | c in p.%s.idx[int] }" % (cls_name, cls_name, field)


def _rb_instance():
    root = RBNode(10, Color.BLACK)
    root.left = RBNode(5, Color.RED)
    root.left.parent = root
    root.right = RBNode(15, Color.RED)
    root.right.parent = root
    return root


# --------------------------------------------------------------------------- #
# 1. Introspection
# --------------------------------------------------------------------------- #


def test_introspect_dataclass_forward_ref():
    ci = build_class_info(BTreeNode)
    left = ci.get("left")
    assert left.is_self_ref and left.container is None
    assert ci.get("value").is_scalar
    assert set(ci.self_ref_fields) == {"left", "right"}


def test_introspect_container_of_self():
    ci = build_class_info(NaryDC)
    children = ci.get("children")
    assert children.is_self_ref and children.container == "list"


def test_introspect_plain_class_via_ast():
    ci = build_class_info(TreeNode, instance=TreeNode(1, TreeNode(2), TreeNode(3)))
    assert set(ci.self_ref_fields) == {"left", "right"}
    assert ci.get("value").is_scalar


def test_introspect_class_level_annotations():
    ci = build_class_info(AnnotatedNode)
    assert ci.get("next").is_self_ref
    assert ci.get("weight").is_scalar


def test_introspect_enum_member_detected_statically():
    # color has no annotation, only a default of Color.BLACK
    ci = build_class_info(RBNode)
    assert ci.get("color").enum_members == ["RED", "BLACK"]


def test_partial_annotations_merge_with_init_and_instance():
    # Only `value` is annotated; left/right exist solely in __init__. The
    # discovery must merge all sources, not stop at __annotations__.
    n = PartlyAnnotated(1)
    n.left, n.right = PartlyAnnotated(2), PartlyAnnotated(3)
    ci = build_class_info(PartlyAnnotated, instance=n)
    assert set(ci.self_ref_fields) == {"left", "right"}
    assert ci.get("value").is_scalar
    reg = suggest(PartlyAnnotated, instance=n).to_registry()
    assert _has(reg, "orientation", selector=_edge("left"))
    assert _has(reg, "attribute", field="value")


def test_dataclass_default_factory_not_executed():
    # A static pass must not invoke arbitrary user code.
    before = len(_FACTORY_CALLS)
    suggest(WithFactory)
    build_class_info(WithFactory)
    assert len(_FACTORY_CALLS) == before


# --------------------------------------------------------------------------- #
# 2. Semantic golden specs
# --------------------------------------------------------------------------- #


def test_binary_tree_spec():
    # left/right are Optional (nullable) -> None-excluding selector form
    reg = suggest(BTreeNode).to_registry()
    assert _has(
        reg,
        "orientation",
        selector=_edge("left"),
        directions=["below", "left"],
    )
    assert _has(
        reg,
        "orientation",
        selector=_edge("right"),
        directions=["below", "right"],
    )
    assert _has(reg, "attribute", field="value")


def test_linked_list_spec():
    reg = suggest(LinkedNode).to_registry()
    assert _has(reg, "orientation", selector=_edge("nxt"), directions=["right"])
    assert _has(reg, "attribute", field="val")


def test_nary_tree_spec_static():
    # The container orientation reaches the elements through idx, not the bare
    # `children` relation (which targets the intermediate list atom).
    reg = suggest(NaryDC).to_registry()
    assert _has(
        reg,
        "orientation",
        selector=_child_edge("NaryDC", "children"),
        directions=["below"],
    )
    assert not _has(reg, "orientation", selector="children")


def test_nary_tree_spec_via_instance():
    # plain class whose children default to None — needs instance sampling.
    # The render-verified combo: a direct child edge + below orientation + hide
    # the node->list edge + hide the intermediate list atoms (these coexist; the
    # orientation and hideField are not treated as alternatives).
    n = NaryNode("root", [NaryNode("a"), NaryNode("b")])
    sel = _child_edge("NaryNode", "children")
    reg = suggest(NaryNode, instance=n).to_registry()
    assert _has(reg, "orientation", selector=sel, directions=["below"])
    assert any(
        p.get("selector") == sel and p.get("name") == "children"
        for p in _entries(reg, "inferredEdge")
    )
    assert _has(reg, "hideField", field="children")
    assert _has(reg, "hideAtom", selector="list")
    assert _has(reg, "attribute", field="value")
    # children is always a list (never None) -> no NoneType atoms to hide
    assert not _has(reg, "hideAtom", selector="NoneType")


def test_hide_disconnected_enabled_for_structures():
    # folded-in scalar atoms (values/indices) float as disconnected nodes; the
    # flag clears them, so it is enabled by default once a structure exists.
    reg = suggest(BTreeNode).to_registry()  # enabled-only
    assert {"flag": "hideDisconnected"} in reg["constraints"] + reg["directives"]


def test_list_sequence_orders_elements_by_index():
    # A plain list of non-node elements (a stack/array) gets a positional
    # orientation over the idx relation — render-tested CLRS form.
    class ArrayStack:
        def __init__(self):
            self.A = []
            self.top = -1

    s = ArrayStack()
    s.A = [10, 20, 30]
    s.top = 2
    draft = suggest(ArrayStack, instance=s)
    reg = draft.to_registry(enabled_only=False)
    seq = [
        p
        for p in _entries(reg, "orientation")
        if p.get("directions") == ["directlyRight"]
    ]
    assert seq and "idx[object][object]" in seq[0]["selector"]
    assert _has(reg, "attribute", field="top")
    # the idx-hiding atom is offered but speculative (broad effect)
    assert _has(draft.to_registry(enabled_only=False), "hideAtom", selector=_LIST_HIDE)
    assert not _has(draft.to_registry(), "hideAtom", selector=_LIST_HIDE)


def test_nested_list_matrix_emits_note_not_malformed_selector():
    class Grid:
        def __init__(self):
            self.cells = [[1, 2], [3, 4]]

    draft = suggest(Grid, instance=Grid())
    # no guessed 2D selector — just a note
    assert not _entries(draft.to_registry(enabled_only=False), "orientation")
    assert any("nested container" in n for n in draft.notes)


def test_slots_class_discovers_self_ref_via_instance():
    # A __slots__ class has no __dict__, so the graph walk must read slots
    # directly; vars(obj) would raise and silently drop every node, yielding
    # zero directives even for a fully populated pointer tree (CLRS huffman).
    root = SlotsNode(
        8,
        zero_=SlotsNode(5, sym="a"),
        one_=SlotsNode(3, zero_=SlotsNode(2, sym="b"), one_=SlotsNode(1, sym="c")),
    )
    ci = build_class_info(SlotsNode, instance=root)
    assert set(ci.self_ref_fields) == {"zero_", "one_"}

    reg = suggest(SlotsNode, instance=root).to_registry(enabled_only=False)
    assert _has(reg, "orientation", selector=_edge("zero_"), directions=["below"])
    assert _has(reg, "orientation", selector=_edge("one_"), directions=["below"])
    assert _has(reg, "attribute", field="sym")
    assert _has(reg, "attribute", field="freq")
    assert _has(reg, "hideAtom", selector="NoneType")


def test_rbnode_matches_handwritten_spec():
    reg = suggest(RBNode, instance=_rb_instance()).to_registry()
    assert _has(
        reg,
        "orientation",
        selector=_edge("left"),
        directions=["below", "left"],
    )
    assert _has(
        reg,
        "orientation",
        selector=_edge("right"),
        directions=["below", "right"],
    )
    assert _has(reg, "attribute", field="key")
    assert _has(reg, "hideField", field="parent")
    assert _has(reg, "hideAtom", selector="NoneType")


def test_enum_color_is_speculative():
    draft = suggest(RBNode, instance=_rb_instance())
    enabled = draft.to_registry(enabled_only=True)
    full = draft.to_registry(enabled_only=False)
    # off by default (palette is a guess), but present when speculative shown
    assert not _entries(enabled, "atomStyle")
    entries = _entries(full, "atomStyle")
    assert len(entries) == 2
    # spytial-core 3.0 form: the palette color lands on the border block,
    # matching the look legacy atomColor produced.
    assert all(e["borderStyle"]["color"] for e in entries)


def test_enum_selector_joins_through_name_relation():
    # @:(x.color) reads the enum atom's display label, not the member name; the
    # selector must join through the member's `name` relation to match.
    full = suggest(RBNode, instance=_rb_instance()).to_registry(enabled_only=False)
    selectors = [p["selector"] for p in _entries(full, "atomStyle")]
    assert selectors and all(".color.name) =" in s for s in selectors)


def test_no_directive_for_private_fields():
    # MaxHeap.a is structural-looking but underscore fields would never be hidden;
    # here we assert a private field on a normal class yields no hideField.
    @dataclass
    class WithPrivate:
        value: int = 0
        _cache: Optional[dict] = None

    reg = suggest(WithPrivate).to_registry(enabled_only=False)
    assert not _has(reg, "hideField", field="_cache")


def test_private_self_ref_emits_no_structural_directive():
    # A private self-reference (_next) is skipped by the relationalizers, so no
    # structural directive should target it — and nothing else (hideAtom/flag).
    reg = suggest(PrivateChild).to_registry(enabled_only=False)
    assert not _has(reg, "orientation", selector="_next")
    assert not _has(reg, "orientation", selector=_edge("_next"))
    assert not _entries(reg, "hideAtom")
    assert _has(reg, "attribute", field="value")


# --------------------------------------------------------------------------- #
# 3. Legality + selector-form guard
# --------------------------------------------------------------------------- #


def test_apply_roundtrips_through_real_decorators():
    @dataclass
    class ApplyTree:
        value: int = 0
        left: Optional["ApplyTree"] = None
        right: Optional["ApplyTree"] = None

    suggest(ApplyTree).apply()  # calls the real spytial.* decorators (validates)
    collected = spytial.collect_decorators(ApplyTree(1))
    assert any("orientation" in c for c in collected["constraints"])
    assert any("attribute" in d for d in collected["directives"])


def test_nullable_edges_exclude_none():
    # left/right can be None and NoneType is hidden, so the orientation must NOT
    # use the bare 'left' relation (which includes the (leaf, None) pairs); it
    # uses the typed comprehension that restricts both ends to the node type.
    reg = suggest(RBNode, instance=_rb_instance()).to_registry(enabled_only=False)
    assert _has(reg, "hideAtom", selector="NoneType")
    assert not _has(reg, "orientation", selector="left")
    assert _has(
        reg,
        "orientation",
        selector=_edge("left"),
        directions=["below", "left"],
    )


def test_non_nullable_edge_uses_bare_relation():
    # A required (non-Optional) self-reference has no None target, so the simpler
    # bare relation selector is used.
    @dataclass
    class Cell:
        val: int
        nxt: "Cell"

    reg = suggest(Cell).to_registry()
    assert _has(reg, "orientation", selector="nxt", directions=["right"])


def test_optional_without_default_is_nullable():
    # Optional[...] with NO default still means the edge can be None, so it uses
    # the None-excluding form and hides NoneType — even with no instance.
    assert build_class_info(OptNoDefault).get("left").has_none_default
    reg = suggest(OptNoDefault).to_registry()
    assert _has(
        reg, "orientation", selector=_edge("left"), directions=["below", "left"]
    )
    assert _has(reg, "hideAtom", selector="NoneType")


def test_registry_serializes():
    reg = suggest(BTreeNode).to_registry()
    out = spytial.serialize_to_yaml_string(reg)
    assert isinstance(out, str) and "orientation" in out


# --------------------------------------------------------------------------- #
# 4. Ceiling case
# --------------------------------------------------------------------------- #


def test_array_encoded_structure_lays_out_the_backing_array():
    # A heap stores its tree in a flat list via index math. We don't fabricate
    # the implied tree, but we DO lay the backing array out as a sequence — a
    # well-formed scaffold over the idx relation rather than nothing.
    draft = suggest(MaxHeap, instance=MaxHeap([4, 2, 7, 1]))
    reg = draft.to_registry(enabled_only=False)
    seq = [
        p
        for p in _entries(reg, "orientation")
        if p.get("directions") == ["directlyRight"]
    ]
    assert seq and "idx[object][object]" in seq[0]["selector"]
    # no fabricated node-to-node tree edges
    assert not any(
        "(univ -> NoneType)" in p.get("selector", "")
        or "below" in p.get("directions", [])
        for p in _entries(reg, "orientation")
    )


# --------------------------------------------------------------------------- #
# 5. parent context-sensitivity
# --------------------------------------------------------------------------- #


def test_parent_only_orients_above():
    root = ParentOnly(1)
    child = ParentOnly(2)
    child.parent = root
    reg = suggest(ParentOnly, instance=child).to_registry()
    assert _has(
        reg,
        "orientation",
        selector=_edge("parent"),
        directions=["above"],
    )
    assert not _has(reg, "hideField", field="parent")


def test_parent_with_children_hides_and_offers_alternative():
    draft = suggest(RBNode, instance=_rb_instance())
    reg = draft.to_registry()
    assert _has(reg, "hideField", field="parent")
    # the 'above' orientation is retained as a toggled-off alternative
    alts = [
        s
        for s in draft.alternatives
        if s.directive == "orientation" and s.kwargs.get("selector") == _edge("parent")
    ]
    assert alts and alts[0].kwargs["directions"] == ["above"]


# --------------------------------------------------------------------------- #
# 6. Extensibility
# --------------------------------------------------------------------------- #


def test_empty_registry_yields_no_suggestions():
    draft = suggest(BTreeNode, registry=HeuristicRegistry())
    assert draft.suggestions == []


def test_custom_heuristic_supersedes_builtin():
    from spytial.suggest import DEFAULT_REGISTRY

    # Start from the built-ins so the user rule has something to supersede.
    reg = DEFAULT_REGISTRY.copy()

    @reg.heuristic(scope="field", priority=100)
    def tag_scalars(fld, ci):
        if fld.is_scalar:
            return [
                Suggestion(
                    "attribute",
                    {"field": fld.name, "filter": "CUSTOM"},
                    "high",
                    "custom rule",
                    fld.name,
                )
            ]
        return []

    draft = suggest(Point, registry=reg)
    # built-in scalar_attribute (priority 10) and the custom rule (100) both fire
    # on x/y; the custom one wins, the built-in lands in alternatives.
    payloads = _entries(draft.to_registry(), "attribute")
    assert payloads and all(p.get("filter") == "CUSTOM" for p in payloads)
    assert any(
        s.directive == "attribute" and "filter" not in s.kwargs
        for s in draft.alternatives
    )


def test_custom_registry_is_isolated_from_default():
    reg = HeuristicRegistry()
    draft = suggest(BTreeNode, registry=reg)
    # nothing registered -> nothing suggested, proving the default registry
    # didn't leak in.
    assert draft.suggestions == []


# --------------------------------------------------------------------------- #
# 7. Optional LLM enrichment (mocked — never touches a network or the llm dep)
# --------------------------------------------------------------------------- #


class _FakeProvider:
    """A test provider — a callable ``(prompt, *, schema) -> dict``.

    Returns a fixed payload dict; records each call in ``calls`` if given.
    """

    def __init__(self, payload, calls=None):
        self._payload = payload
        self._calls = calls

    def __call__(self, prompt, *, schema):
        if self._calls is not None:
            self._calls.append({"prompt": prompt, "schema": schema})
        return self._payload


def _llm_rows(draft):
    return [s for s in draft.suggestions if s.source == "llm"]


def _of(draft, directive):
    return [
        s for s in draft.suggestions if s.directive == directive and s.source == "llm"
    ]


# An unfamiliar-named structure: `escalation` is a single self-ref pointer whose
# name is outside the built-in vocabulary (the rules only manage a flat 'below'),
# and `related` is a self-ref collection. Both are read statically — no instance.
@dataclass
class Ticket:
    id: int = 0
    escalation: Optional["Ticket"] = None
    related: List["Ticket"] = field(default_factory=list)


def _shape(field, constraint, **extra):
    return {"field": field, "constraint": constraint, "why": "test", **extra}


def test_enrich_bad_spec_degrades_with_note():
    # enrich must be a model-id string or a provider object; a bad spec is a clean
    # no-op with a note, never a crash.
    draft = suggest(Ticket, enrich=123)
    assert not _llm_rows(draft)
    assert any("enrich skipped" in n for n in draft.notes)


def test_enrich_orientation_for_unfamiliar_field():
    # The provider picks a direction (above); spytial supplies the field-form selector.
    # The model is the primary shape author, so its pick is enabled by default.
    payload = {"shapes": [_shape("escalation", "orientation", directions=["above"])]}
    draft = suggest(Ticket, enrich=_FakeProvider(payload))
    assert any(
        s.kwargs == {"selector": _edge("escalation"), "directions": ["above"]}
        and s.source == "llm"
        and s.enabled_by_default
        for s in _of(draft, "orientation")
    )


def test_enrich_shape_wins_and_demotes_rule_to_backup():
    # LLM `above` beats the deterministic `below` for `escalation`: the model's row is
    # the enabled suggestion, and the built-in `below` steps down to a backup
    # alternative (kept, disabled) rather than vanishing.
    payload = {"shapes": [_shape("escalation", "orientation", directions=["above"])]}
    draft = suggest(Ticket, enrich=_FakeProvider(payload))
    enabled = [s for s in draft.suggestions if s.directive == "orientation"
               and s.source_field == "escalation"]
    assert [(s.source, s.kwargs["directions"]) for s in enabled] == [("llm", ["above"])]
    demoted = [s for s in draft.alternatives
               if s.directive == "orientation" and s.source == "rule"
               and s.kwargs["directions"] == ["below"]]
    assert demoted and demoted[0].enabled_by_default is False


def test_enrich_abstain_demotes_rule_shape():
    # A deliberate `none` means the model owns the field and chose no shape — the
    # built-in `below` is demoted to a backup, and nothing is enabled in its place.
    payload = {"shapes": [_shape("escalation", "none")]}
    draft = suggest(Ticket, enrich=_FakeProvider(payload))
    assert not any(s.directive == "orientation" and s.source_field == "escalation"
                   for s in draft.suggestions)
    assert any(s.directive == "orientation" and s.source == "rule"
               and s.source_field == "escalation" for s in draft.alternatives)


def test_enrich_agreement_keeps_builtin_no_duplicate():
    # When the model agrees with the deterministic rule (`below` == `below`), keep the
    # built-in enabled — no relabelled llm duplicate, no demotion.
    payload = {"shapes": [_shape("escalation", "orientation", directions=["below"])]}
    draft = suggest(Ticket, enrich=_FakeProvider(payload))
    assert not _of(draft, "orientation")  # no llm orientation row added
    kept = [s for s in draft.suggestions if s.directive == "orientation"
            and s.source_field == "escalation"]
    assert [(s.source, s.enabled_by_default) for s in kept] == [("rule", True)]
    assert not draft.alternatives  # nothing demoted


def test_enrich_orientation_over_container_uses_children_selector():
    payload = {"shapes": [_shape("related", "orientation", directions=["right"])]}
    draft = suggest(Ticket, enrich=_FakeProvider(payload))
    # The derived (parent, child) edge carries source_field=None — matching
    # rules.child_container — so it de-dups and groups like the deterministic one.
    assert any(
        s.kwargs
        == {"selector": _child_edge("Ticket", "related"), "directions": ["right"]}
        and s.source_field is None
        for s in _of(draft, "orientation")
    )


def test_enrich_container_orientation_dedups_against_deterministic():
    # The rules already orient `related` children below (derived edge, source_field
    # None); an identical model suggestion must collapse, not slip past _key().
    payload = {"shapes": [_shape("related", "orientation", directions=["below"])]}
    assert not _of(suggest(Ticket, enrich=_FakeProvider(payload)), "orientation")


def test_enrich_cyclic_over_single_pointer():
    payload = {"shapes": [_shape("nxt", "cyclic", direction="clockwise")]}
    draft = suggest(LinkedNode, enrich=_FakeProvider(payload))
    assert any(
        s.kwargs == {"selector": _edge("nxt"), "direction": "clockwise"}
        for s in _of(draft, "cyclic")
    )


def test_enrich_group_only_for_containers():
    # group on a scalar pointer is dropped; on a collection it emits the
    # field-based group form.
    payload = {"shapes": [_shape("escalation", "group"), _shape("related", "group")]}
    draft = suggest(Ticket, enrich=_FakeProvider(payload))
    assert [s.kwargs for s in _of(draft, "group")] == [
        {"field": "related", "groupOn": 0, "addToGroup": 1}
    ]


def test_enrich_rejects_unknown_field():
    # A field we never analyzed can't be targeted — so the model can't drive a
    # selector for something off-schema.
    payload = {"shapes": [_shape("nope", "orientation", directions=["below"])]}
    assert not _llm_rows(suggest(Ticket, enrich=_FakeProvider(payload)))


def test_enrich_filters_out_of_vocab_directions():
    payload = {
        "shapes": [
            _shape("escalation", "orientation", directions=["sideways", "above"])
        ]
    }
    draft = suggest(Ticket, enrich=_FakeProvider(payload))
    assert any(s.kwargs["directions"] == ["above"] for s in _of(draft, "orientation"))


def test_enrich_keeps_the_directly_variants():
    # The vocabulary is sourced from the canonical set rather than restated; it
    # used to omit directlyAbove/directlyBelow, so a model proposing either had
    # a direction core handles filtered out from under it.
    payload = {
        "shapes": [
            _shape("escalation", "orientation", directions=["directlyAbove"])
        ]
    }
    draft = suggest(Ticket, enrich=_FakeProvider(payload))
    assert any(
        s.kwargs["directions"] == ["directlyAbove"] for s in _of(draft, "orientation")
    )


def test_enrich_vocabulary_is_the_canonical_one():
    from spytial.annotations import ORIENTATION_DIRECTIONS, ROTATION_DIRECTIONS
    from spytial.suggest._enrich import _ORIENT_DIRS, _CYCLIC_DIRS

    assert _ORIENT_DIRS == ORIENTATION_DIRECTIONS
    assert _CYCLIC_DIRS == ROTATION_DIRECTIONS


def test_enrich_honors_falsy_callable_provider():
    # A provider whose __bool__/__len__ is falsy must still resolve — "off" is None or
    # False only, not truthiness. Regression for the callable provider slot.
    payload = {"shapes": [_shape("escalation", "orientation", directions=["above"])]}

    class _FalsyProvider(_FakeProvider):
        def __len__(self):
            return 0  # makes the instance falsy

    prov = _FalsyProvider(payload)
    assert not prov  # falsy...
    draft = suggest(Ticket, enrich=prov)
    assert any(  # ...yet honored, not silently skipped
        s.kwargs["directions"] == ["above"] for s in _of(draft, "orientation")
    )


def test_enrich_none_and_false_are_off():
    # The only two "off" values — neither runs a provider nor leaves an enrich note.
    for off in (None, False):
        draft = suggest(Ticket, enrich=off)
        assert not _llm_rows(draft)
        assert not any("enrich" in n.lower() for n in draft.notes)


def test_enrich_dedups_against_deterministic():
    # The rules already orient `escalation` below; an identical model suggestion is
    # not added a second time.
    payload = {"shapes": [_shape("escalation", "orientation", directions=["below"])]}
    assert not _of(suggest(Ticket, enrich=_FakeProvider(payload)), "orientation")


def test_enrich_works_at_type_level_without_instance():
    payload = {"shapes": [_shape("escalation", "orientation", directions=["above"])]}
    assert _of(suggest(Ticket, enrich=_FakeProvider(payload)), "orientation")


def test_enrich_no_structural_fields_never_calls_provider():
    calls = []
    suggest(Point, enrich=_FakeProvider({"shapes": []}, calls))
    assert calls == []  # only scalars — nothing structural to shape


def test_enrich_provider_error_degrades():
    # A provider that raises degrades to the static draft with a note, never crashes.
    def boom(prompt, *, schema):
        raise RuntimeError("model unreachable")

    draft = suggest(Ticket, enrich=boom)
    assert not _llm_rows(draft)  # never raises
    assert any("shape enrichment skipped" in n for n in draft.notes)


# --- the provider slot itself ------------------------------------------------- #


def test_as_provider_accepts_callables_and_rejects_non_callables():
    from spytial.suggest import EnrichProvider, providers

    fn = _FakeProvider({"shapes": []})
    assert isinstance(fn, EnrichProvider)  # a callable satisfies the protocol
    assert providers.as_provider(fn) is fn  # passes straight through
    assert callable(providers.as_provider(lambda prompt, *, schema: {}))
    with pytest.raises(providers.EnrichError):
        providers.as_provider(123)  # not a model id, not callable


def test_llmmodel_unresolvable_raises_enrich_error():
    # No llm installed OR an unknown id both surface as EnrichError — which suggest()
    # catches and turns into a note.
    from spytial.suggest import providers

    with pytest.raises(providers.EnrichError):
        providers.LlmModel("definitely-not-a-real-model-xyz")


def test_llmmodel_passes_id_and_returns_dict(monkeypatch):
    # A model-id string resolves the *named* model (no ambient default); the adapter
    # parses llm's response text into a dict.
    llm = pytest.importorskip("llm")
    seen = []

    class _Resp:
        def text(self):
            return json.dumps({"shapes": []})

    class _Model:
        def prompt(self, prompt, *, schema):
            return _Resp()

    def _fake_get_model(model_id):
        seen.append(model_id)
        return _Model()

    monkeypatch.setattr(llm, "get_model", _fake_get_model)
    from spytial.suggest import providers

    prov = providers.LlmModel("claude-x")
    assert seen == ["claude-x"]
    assert prov("hi", schema={}) == {"shapes": []}


def test_extract_json_handles_plain_fenced_and_noisy():
    from spytial.suggest import providers

    assert providers.extract_json('{"a": 1}') == {"a": 1}
    assert providers.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert providers.extract_json('Sure, here:\n{"a": 1}\nHope that helps.') == {"a": 1}
    with pytest.raises(providers.EnrichError):
        providers.extract_json("no json object here")


def test_claudecode_builds_command_and_parses(monkeypatch):
    # Injects the schema into the prompt and parses the (fenced) reply.
    from spytial.suggest import providers

    captured = {}

    class _Proc:
        returncode = 0
        stdout = '```json\n{"shapes": []}\n```'
        stderr = ""

    monkeypatch.setattr(providers.shutil, "which", lambda b: "/usr/bin/" + b)
    monkeypatch.setattr(
        providers.subprocess, "run", lambda cmd, **kw: captured.update(cmd=cmd) or _Proc()
    )

    out = providers.ClaudeCode(model="opus")("hi", schema={"type": "object"})
    assert out == {"shapes": []}
    assert captured["cmd"][:4] == ["/usr/bin/claude", "-p", "--model", "opus"]
    assert "JSON Schema" in captured["cmd"][-1]  # schema injected into the prompt


def test_codex_uses_native_output_schema(monkeypatch):
    # Passes --output-schema pointing at a real temp file present during the call.
    from spytial.suggest import providers

    captured = {}

    class _Proc:
        returncode = 0
        stdout = '{"selectors": []}'
        stderr = ""

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        i = cmd.index("--output-schema")
        captured["schema_exists"] = os.path.exists(cmd[i + 1])
        return _Proc()

    monkeypatch.setattr(providers.shutil, "which", lambda b: "/usr/bin/" + b)
    monkeypatch.setattr(providers.subprocess, "run", fake_run)

    out = providers.Codex()("author selectors", schema={"type": "object"})
    assert out == {"selectors": []}
    assert "--output-schema" in captured["cmd"]
    assert captured["schema_exists"]  # temp schema file present during the call

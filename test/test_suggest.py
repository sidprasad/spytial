#!/usr/bin/env python3
"""Tests for ``spytial.suggest`` — deterministic spec scaffolding.

Fixtures mirror the real structures in the repo (binary tree, red-black node,
linked list, n-ary tree, array heap). ``from __future__ import annotations``
makes every dataclass annotation a *string*, exercising the forward-reference
path the introspector has to handle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

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
    # plain class whose children default to None — needs instance sampling
    n = NaryNode("root", [NaryNode("a"), NaryNode("b")])
    reg = suggest(NaryNode, instance=n).to_registry()
    assert _has(
        reg,
        "orientation",
        selector=_child_edge("NaryNode", "children"),
        directions=["below"],
    )
    assert _has(reg, "attribute", field="value")
    # children is always a list (never None) -> no NoneType atoms to hide
    assert not _has(reg, "hideAtom", selector="NoneType")


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
    assert not _entries(enabled, "atomColor")
    assert len(_entries(full, "atomColor")) == 2


def test_enum_selector_joins_through_name_relation():
    # @:(x.color) reads the enum atom's display label, not the member name; the
    # selector must join through the member's `name` relation to match.
    full = suggest(RBNode, instance=_rb_instance()).to_registry(enabled_only=False)
    selectors = [p["selector"] for p in _entries(full, "atomColor")]
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

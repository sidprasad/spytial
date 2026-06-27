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


class MaxHeap:  # array/index-encoded — the ceiling case
    def __init__(self, data=None):
        self.a = [0]
        if data:
            self.a.extend(data)
        self.n = len(self.a) - 1


class AnnotatedNode:  # class-level annotations, not a dataclass
    next: Optional["AnnotatedNode"]
    weight: int


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


# --------------------------------------------------------------------------- #
# 2. Semantic golden specs
# --------------------------------------------------------------------------- #


def test_binary_tree_spec():
    reg = suggest(BTreeNode).to_registry()
    assert _has(reg, "orientation", selector="left", directions=["below", "left"])
    assert _has(reg, "orientation", selector="right", directions=["below", "right"])
    assert _has(reg, "attribute", field="value")


def test_linked_list_spec():
    reg = suggest(LinkedNode).to_registry()
    assert _has(reg, "orientation", selector="nxt", directions=["right"])
    assert _has(reg, "attribute", field="val")


def test_nary_tree_spec_static():
    reg = suggest(NaryDC).to_registry()
    assert _has(reg, "orientation", selector="children", directions=["below"])


def test_nary_tree_spec_via_instance():
    # plain class whose children default to None — needs instance sampling
    n = NaryNode("root", [NaryNode("a"), NaryNode("b")])
    reg = suggest(NaryNode, instance=n).to_registry()
    assert _has(reg, "orientation", selector="children", directions=["below"])
    assert _has(reg, "attribute", field="value")
    # children is always a list (never None) -> no NoneType atoms to hide
    assert not _has(reg, "hideAtom", selector="NoneType")


def test_rbnode_matches_handwritten_spec():
    reg = suggest(RBNode, instance=_rb_instance()).to_registry()
    assert _has(reg, "orientation", selector="left", directions=["below", "left"])
    assert _has(reg, "orientation", selector="right", directions=["below", "right"])
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


def test_no_directive_for_private_fields():
    # MaxHeap.a is structural-looking but underscore fields would never be hidden;
    # here we assert a private field on a normal class yields no hideField.
    @dataclass
    class WithPrivate:
        value: int = 0
        _cache: Optional[dict] = None

    reg = suggest(WithPrivate).to_registry(enabled_only=False)
    assert not _has(reg, "hideField", field="_cache")


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


def test_structural_selectors_are_field_form():
    # orientation/align/cyclic must use field selectors (e.g. 'left'), never a
    # bare type-name comprehension, which can trip the absent-type arity error.
    reg = suggest(RBNode, instance=_rb_instance()).to_registry(enabled_only=False)
    for name in ("orientation", "align", "cyclic"):
        for payload in _entries(reg, name):
            assert "{" not in payload["selector"], payload


def test_registry_serializes():
    reg = suggest(BTreeNode).to_registry()
    out = spytial.serialize_to_yaml_string(reg)
    assert isinstance(out, str) and "orientation" in out


# --------------------------------------------------------------------------- #
# 4. Ceiling case
# --------------------------------------------------------------------------- #


def test_array_encoded_structure_bails_gracefully():
    draft = suggest(MaxHeap, instance=MaxHeap([4, 2, 7, 1]))
    reg = draft.to_registry(enabled_only=False)
    # no fabricated structural edges
    assert not _entries(reg, "orientation")
    assert any("structure could not be inferred" in n for n in draft.notes)


# --------------------------------------------------------------------------- #
# 5. parent context-sensitivity
# --------------------------------------------------------------------------- #


def test_parent_only_orients_above():
    root = ParentOnly(1)
    child = ParentOnly(2)
    child.parent = root
    reg = suggest(ParentOnly, instance=child).to_registry()
    assert _has(reg, "orientation", selector="parent", directions=["above"])
    assert not _has(reg, "hideField", field="parent")


def test_parent_with_children_hides_and_offers_alternative():
    draft = suggest(RBNode, instance=_rb_instance())
    reg = draft.to_registry()
    assert _has(reg, "hideField", field="parent")
    # the 'above' orientation is retained as a toggled-off alternative
    alts = [
        s
        for s in draft.alternatives
        if s.directive == "orientation" and s.kwargs.get("selector") == "parent"
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

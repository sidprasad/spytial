#!/usr/bin/env python3
"""Tests for Hypothesis-backed witnesses in ``spytial.suggest``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest
from hypothesis import strategies as st

from spytial.suggest import AskError, build_class_info, suggest
from spytial.suggest import _eval, _strategy
from spytial.suggest._strategy import StrategyError, find_witness


@dataclass
class AutoTree:
    value: int
    left: Optional["AutoTree"] = None
    right: Optional["AutoTree"] = None


@dataclass
class PrivateLink:
    """A recursive class whose only self-ref field is private (``_next``)."""

    value: int
    _next: Optional["PrivateLink"] = None


@dataclass
class Cell:
    """A node-like sibling that Head points at (heterogeneous graph)."""

    tag: int
    cell: Optional["Cell"] = None


@dataclass
class Head:
    """Its only self-ref field points at the *sibling* node type Cell, not Head."""

    name: int
    cell: Optional["Cell"] = None


def _nodes(root):
    if root is None:
        return []
    return [root] + _nodes(root.left) + _nodes(root.right)


class _Router:
    """Serve shape, selector, and ask calls from one deterministic provider."""

    def __init__(self):
        self.prompts = []

    def __call__(self, prompt, *, schema):
        self.prompts.append(prompt)
        props = schema.get("properties", {})
        if "candidates" in props:
            return {
                "candidates": [
                    {
                        "directive": "orientation",
                        "selector": "left + right",
                        "directions": ["below"],
                        "why": "children belong below parents",
                    }
                ]
            }
        if "selectors" in props:
            return {"selectors": []}
        return {"shapes": []}


def _stub_evaluator(monkeypatch):
    def evaluate(_datum, selectors):
        return [
            _eval.SelectorVerdict(selector=s, ok=True, empty=False, arity=2)
            for s in selectors
        ]

    monkeypatch.setattr(_eval, "is_available", lambda: True)
    monkeypatch.setattr(_eval, "evaluate_selectors", evaluate)


def test_auto_strategy_finds_a_non_leaf_recursive_witness():
    witness = find_witness(AutoTree, build_class_info(AutoTree), "auto")

    assert isinstance(witness, AutoTree)
    assert witness.left is not None
    assert witness.right is not None
    assert len(_nodes(witness)) >= 3


def test_private_only_self_ref_still_gets_a_non_leaf_witness():
    # The recursive-branch gate (ClassInfo.self_ref_fields) counts the private
    # `_next`, so this class enters witness population; the fully-populated tier
    # has no *non-private* field to check and is skipped, but the nontrivial tier
    # must still keep it from shrinking to a single-node leaf.
    ci = build_class_info(PrivateLink)
    assert ci.self_ref_fields == ["_next"]

    witness = find_witness(PrivateLink, ci, "auto")

    datum = _strategy.CnDDataInstanceBuilder().build_instance(witness)
    link_atoms = sum(a.get("type") == "PrivateLink" for a in datum.get("atoms", []))
    assert link_atoms >= 2  # not the degenerate one-node leaf


def test_heterogeneous_sibling_node_gets_a_populated_witness():
    # Head's only self-ref field points at the *sibling* node type Cell. The old
    # root-only predicates could never satisfy fully_populated/nontrivial for such
    # a graph and fell back to a leaf (Head(cell=None)); node_names now counts Cell
    # atoms too, so the child relation is populated.
    ci = build_class_info(Head)
    assert ci.self_ref_fields == ["cell"]

    witness = find_witness(Head, ci, "auto")

    assert witness.cell is not None  # the sibling-typed child is populated


def test_builder_failure_reads_as_a_builder_error_not_an_empty_search(monkeypatch):
    class BrokenBuilder:
        def build_instance(self, _obj):
            raise RuntimeError("builder exploded")

    monkeypatch.setattr(_strategy, "CnDDataInstanceBuilder", BrokenBuilder)

    with pytest.raises(StrategyError) as excinfo:
        find_witness(AutoTree, build_class_info(AutoTree), "auto")

    message = str(excinfo.value)
    assert "builder error" in message
    assert "builder exploded" in message  # the real cause is carried, not masked
    assert "within the search budget" not in message


def test_explicit_strategy_supplies_the_witness():
    wanted = AutoTree(7, left=AutoTree(8))

    witness = find_witness(AutoTree, build_class_info(AutoTree), st.just(wanted))

    assert witness is wanted


def test_empty_strategy_says_it_generated_nothing_not_budget_exhaustion():
    # st.nothing() generates no values at all — an empty strategy, not a search
    # that ran out of budget. The error should say so, not point at the budget.
    with pytest.raises(StrategyError) as excinfo:
        find_witness(AutoTree, build_class_info(AutoTree), st.nothing())

    message = str(excinfo.value)
    assert "generated no usable values" in message
    assert "within the search budget" not in message


def test_non_strategy_argument_names_the_real_problem():
    # Passing something that isn't a strategy must not be reported as a failed
    # search over the type — the argument itself is wrong.
    with pytest.raises(StrategyError) as excinfo:
        find_witness(AutoTree, build_class_info(AutoTree), 42)

    message = str(excinfo.value)
    assert "not a valid Hypothesis strategy" in message
    assert "within the search budget" not in message


def test_wrong_type_strategy_genuinely_exhausts_the_search_budget():
    # A valid strategy that simply never yields a buildable AutoTree is a real
    # exhausted search — here the budget wording is the accurate one.
    with pytest.raises(StrategyError, match="within the search budget"):
        find_witness(AutoTree, build_class_info(AutoTree), st.integers())


def test_unknown_strategy_string_has_a_clear_error():
    with pytest.raises(StrategyError, match="use 'auto'"):
        find_witness(AutoTree, build_class_info(AutoTree), "magic")


def test_class_only_ask_implicitly_derives_a_strategy(monkeypatch):
    _stub_evaluator(monkeypatch)
    provider = _Router()

    draft = suggest(
        AutoTree,
        ask="put every child below its parent",
        enrich=provider,
    )

    assert any(
        s.directive == "orientation"
        and s.kwargs == {"selector": "left + right", "directions": ["below"]}
        and s.enabled_by_default
        for s in draft.suggestions
    )
    assert any("auto-derived strategy" in note for note in draft.notes)
    ask_prompt = next(p for p in provider.prompts if "The user's request" in p)
    assert "AutoTree (#3)" in ask_prompt


@pytest.mark.skipif(not _eval.is_available(), reason="headless evaluator unavailable")
def test_class_only_ask_works_with_the_real_evaluator():
    draft = suggest(
        AutoTree,
        ask="put every child below its parent",
        enrich=_Router(),
    )

    enabled = [
        s
        for s in draft.suggestions
        if s.directive == "orientation" and s.enabled_by_default
    ]
    assert len(enabled) == 1
    assert enabled[0].kwargs == {
        "selector": "left + right",
        "directions": ["below"],
    }


def test_fixed_examples_and_strategy_are_both_validation_witnesses(monkeypatch):
    _stub_evaluator(monkeypatch)
    provider = _Router()
    fixed = AutoTree(1, left=AutoTree(2))
    generated = AutoTree(3, right=AutoTree(4))

    draft = suggest(
        AutoTree,
        examples=[fixed],
        strategy=st.just(generated),
        ask="put every child below its parent",
        enrich=provider,
    )

    ask_prompt = next(p for p in provider.prompts if "The user's request" in p)
    assert "validated against 2 example instance(s)" in ask_prompt
    assert any("supplied strategy" in note for note in draft.notes)


def test_failed_implicit_strategy_is_loud_for_ask(monkeypatch):
    def fail(*_args, **_kwargs):
        raise StrategyError("no family can be generated")

    monkeypatch.setattr("spytial.suggest._strategy.find_witness", fail)

    with pytest.raises(AskError, match="no family can be generated"):
        suggest(AutoTree, ask="children below", enrich=_Router())


def test_failed_strategy_degrades_to_a_note_without_ask(monkeypatch):
    def fail(*_args, **_kwargs):
        raise StrategyError("no family can be generated")

    monkeypatch.setattr("spytial.suggest._strategy.find_witness", fail)

    draft = suggest(AutoTree, strategy="auto")

    assert any("strategy skipped: no family can be generated" in n for n in draft.notes)

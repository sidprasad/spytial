#!/usr/bin/env python3
"""Tests for Hypothesis-backed witnesses in ``spytial.suggest``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest
from hypothesis import strategies as st

from spytial.suggest import AskError, build_class_info, suggest
from spytial.suggest import _eval
from spytial.suggest._strategy import StrategyError, find_witness


@dataclass
class AutoTree:
    value: int
    left: Optional["AutoTree"] = None
    right: Optional["AutoTree"] = None


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


def test_explicit_strategy_supplies_the_witness():
    wanted = AutoTree(7, left=AutoTree(8))

    witness = find_witness(AutoTree, build_class_info(AutoTree), st.just(wanted))

    assert witness is wanted


def test_strategy_without_a_buildable_value_has_a_clear_error():
    with pytest.raises(StrategyError, match="buildable AutoTree witness"):
        find_witness(AutoTree, build_class_info(AutoTree), st.nothing())


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

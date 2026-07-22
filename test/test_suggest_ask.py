#!/usr/bin/env python3
"""Tests for the user-directed ``ask=`` tier (``spytial.suggest._ask``).

Same strategy as the tier-2 tests: the admission logic runs against a fake model
and a *stubbed* evaluator, so everything is deterministic with no node and no
network. One end-to-end test uses the real headless evaluator and skips when the
bridge isn't present. The loud-failure contract is the point of half these tests:
where enrichment degrades with a note, ask must raise :class:`AskError`.
"""

from __future__ import annotations

import pytest

import spytial
from spytial.suggest import AskError, SpecDraft, Suggestion, build_class_info, suggest
from spytial.suggest import _ask
from spytial.suggest import _eval


# --------------------------------------------------------------------------- #
# Fixtures / fakes
# --------------------------------------------------------------------------- #


class LL:
    """A singly linked list node: relations `next` and `value`, both arity 2."""

    def __init__(self, value, nxt=None):
        self.value = value
        self.next = nxt


def _instance(n=3):
    head = node = LL(0)
    for i in range(1, n):
        node.next = LL(i)
        node = node.next
    return head


def _ci():
    return build_class_info(LL, instance=_instance())


def _draft(suggestions=None, alternatives=None):
    return SpecDraft(LL, list(suggestions or []), alternatives=list(alternatives or []))


class FakeAsk:
    """A provider returning one fixed response; records the prompts it saw."""

    def __init__(self, response):
        self.response = response
        self.prompts = []

    def __call__(self, prompt, *, schema):
        self.prompts.append(prompt)
        return self.response


class RepairAsk:
    """A provider answering with a different response per call (a repair queue)."""

    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.prompts = []

    def __call__(self, prompt, *, schema):
        self.prompts.append(prompt)
        idx = min(len(self.prompts) - 1, len(self.rounds) - 1)
        return self.rounds[idx]


def _v(selector, ok=True, empty=False, arity=2):
    return _eval.SelectorVerdict(selector=selector, ok=ok, empty=empty, arity=arity)


def _stub_eval(monkeypatch, spec, available=True):
    """Stub the evaluator: ``spec`` maps selector -> (ok, empty, arity), same for
    every example. Unlisted selectors default to a clean arity-2 result."""

    def fake_evaluate(datum, selectors):
        return [_v(s, *spec.get(s, (True, False, 2))) for s in selectors]

    monkeypatch.setattr(_eval, "is_available", lambda: available)
    monkeypatch.setattr(_eval, "evaluate_selectors", fake_evaluate)


def _llm(draft):
    return [s for s in draft.suggestions if s.source == "llm"]


def _cand(directive="orientation", selector="next", **extra):
    base = {"directive": directive, "selector": selector, "why": "test"}
    base.update(extra)
    return base


# --------------------------------------------------------------------------- #
# Admission (fake model + stubbed evaluator)
# --------------------------------------------------------------------------- #


def test_orientation_ask_is_admitted(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    model = FakeAsk(
        {"candidates": [_cand(directions=["below"], why="children read downward")]}
    )
    draft = _draft()
    _ask.ask_draft(
        draft, _ci(), "children below parents", provider=model, examples=[_instance()]
    )

    (sug,) = _llm(draft)
    assert sug.directive == "orientation"
    assert sug.kwargs == {"selector": "next", "directions": ["below"]}
    assert sug.enabled_by_default is True
    assert sug.confidence == "high"
    assert sug.rationale == "ask: children read downward"
    assert any('ask: "children below parents"' in n for n in draft.notes)
    # The statement and the vocabulary both reached the model.
    assert "children below parents" in model.prompts[0]
    assert "next/2" in model.prompts[0]


def test_unary_kinds_are_admitted(monkeypatch):
    _stub_eval(monkeypatch, {"int": (True, False, 1)})
    model = FakeAsk(
        {
            "candidates": [
                _cand("hideAtom", "int"),
                _cand("atomStyle", "int", fill="green"),
            ]
        }
    )
    draft = _draft()
    _ask.ask_draft(draft, _ci(), "hide and tint ints", provider=model, examples=[_instance()])

    out = {s.directive: s for s in _llm(draft)}
    assert set(out) == {"hideAtom", "atomStyle"}
    assert out["hideAtom"].kwargs == {"selector": "int"}
    assert out["atomStyle"].kwargs == {
        "selector": "int",
        "fillStyle": {"color": "green"},
    }


def test_ask_confirms_existing_row_instead_of_duplicating(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    existing = Suggestion(
        "orientation",
        {"selector": "next", "directions": ["below"]},
        "medium",
        "rule",
        "next",
        enabled_by_default=False,
    )
    draft = _draft([existing])
    model = FakeAsk({"candidates": [_cand(directions=["below"])]})
    _ask.ask_draft(draft, _ci(), "next below", provider=model, examples=[_instance()])

    assert draft.suggestions == [existing]  # no twin row appended
    assert existing.enabled_by_default is True  # the ask turned it on
    assert existing.source == "rule"


def test_ask_promotes_matching_alternative(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    alt = Suggestion(
        "orientation",
        {"selector": "next", "directions": ["below"]},
        "medium",
        "rule",
        "next",
        enabled_by_default=False,
    )
    draft = _draft([], alternatives=[alt])
    model = FakeAsk({"candidates": [_cand(directions=["below"])]})
    _ask.ask_draft(draft, _ci(), "next below", provider=model, examples=[_instance()])

    assert draft.alternatives == []
    assert draft.suggestions == [alt]
    assert alt.enabled_by_default is True


def test_multi_part_ask_admits_several_directives(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2), "int": (True, False, 1)})
    model = FakeAsk(
        {
            "candidates": [
                _cand(directions=["below"]),
                _cand("atomStyle", "int", fill="green"),
            ]
        }
    )
    draft = _draft()
    _ask.ask_draft(
        draft, _ci(), "nodes below, ints green", provider=model, examples=[_instance()]
    )

    assert {s.directive for s in _llm(draft)} == {"orientation", "atomStyle"}
    assert any("2 directive(s)" in n for n in draft.notes)


def test_partial_success_still_repairs_the_failed_half(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    good = _cand(directions=["below"])
    bad = _cand("cyclic", "next", direction="widdershins")  # out-of-vocab slip
    fixed = _cand("cyclic", "next", direction="clockwise")
    model = RepairAsk([{"candidates": [good, bad]}, {"candidates": [fixed]}])
    draft = _draft()
    _ask.ask_draft(
        draft, _ci(), "below, and a clockwise ring", provider=model,
        examples=[_instance()],
    )

    assert {s.directive for s in _llm(draft)} == {"orientation", "cyclic"}
    assert any("2 directive(s)" in n for n in draft.notes)
    assert len(model.prompts) == 2
    assert "already accepted" in model.prompts[1]
    assert "cyclic needs direction" in model.prompts[1]


def test_partial_success_notes_the_unvalidated_remainder(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    good = _cand(directions=["below"])
    bad = _cand("cyclic", "next", direction="widdershins")
    model = FakeAsk({"candidates": [good, bad]})  # the repair gets the same slip back
    draft = _draft()
    _ask.ask_draft(
        draft, _ci(), "below, and a ring", provider=model, examples=[_instance()]
    )

    (sug,) = _llm(draft)  # the accepted half stands, exactly once
    assert sug.directive == "orientation"
    assert any("part of the request could not be validated" in n for n in draft.notes)
    assert any("cyclic needs direction" in n for n in draft.notes)


def test_ask_demotes_overlapping_geometry(monkeypatch):
    # The stub reports every selector — including the "(a) & (b)" overlap probe —
    # as non-empty, so the enabled rule row competes with the ask and steps down.
    _stub_eval(monkeypatch, {"^next": (True, False, 2)})
    rule_row = Suggestion(
        "orientation",
        {"selector": "next", "directions": ["right"]},
        "high",
        "rule",
        "next",
        enabled_by_default=True,
    )
    draft = _draft([rule_row])
    model = FakeAsk({"candidates": [_cand(selector="^next", directions=["below"])]})
    _ask.ask_draft(
        draft, _ci(), "everything below", provider=model, examples=[_instance()]
    )

    assert rule_row not in draft.suggestions
    assert rule_row in draft.alternatives
    assert rule_row.enabled_by_default is False
    (ask_row,) = _llm(draft)
    assert ask_row.enabled_by_default is True
    assert any("1 overlapping row(s) demoted" in n for n in draft.notes)


def test_ask_leaves_disjoint_geometry_alone(monkeypatch):
    # The overlap probe for this rival evaluates to the empty set: no fight, no
    # demotion — orthogonal constraints coexist.
    _stub_eval(
        monkeypatch,
        {"^next": (True, False, 2), "(^next) & (prev)": (True, True, 2)},
    )
    rule_row = Suggestion(
        "orientation",
        {"selector": "prev", "directions": ["left"]},
        "high",
        "rule",
        "prev",
        enabled_by_default=True,
    )
    draft = _draft([rule_row])
    model = FakeAsk({"candidates": [_cand(selector="^next", directions=["below"])]})
    _ask.ask_draft(
        draft, _ci(), "everything below", provider=model, examples=[_instance()]
    )

    assert rule_row in draft.suggestions
    assert rule_row.enabled_by_default is True
    assert not any("demoted" in n for n in draft.notes)


def test_repair_round_salvages_a_bad_first_translation(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    model = RepairAsk(
        [
            {"candidates": [_cand(directions=["diagonal"])]},  # out-of-vocab slip
            {"candidates": [_cand(directions=["below"])]},
        ]
    )
    draft = _draft()
    _ask.ask_draft(draft, _ci(), "next below", provider=model, examples=[_instance()])

    (sug,) = _llm(draft)
    assert sug.kwargs == {"selector": "next", "directions": ["below"]}
    assert len(model.prompts) == 2
    assert "went wrong" in model.prompts[1]
    assert "orientation needs 1-2 directions" in model.prompts[1]


# --------------------------------------------------------------------------- #
# The loud-failure contract
# --------------------------------------------------------------------------- #


def test_cannot_reply_raises_with_the_models_reason(monkeypatch):
    _stub_eval(monkeypatch, {})
    model = FakeAsk({"candidates": [], "cannot": "the request is not spatial"})
    with pytest.raises(AskError, match="the request is not spatial"):
        _ask.ask_draft(
            _draft(), _ci(), "make it pretty", provider=model, examples=[_instance()]
        )


def test_unvalidatable_translation_raises_with_diagnostics(monkeypatch):
    # `value` resolves at arity 2 is the default; force arity 1 so orientation fails.
    _stub_eval(monkeypatch, {"int": (True, False, 1)})
    model = FakeAsk({"candidates": [_cand("orientation", "int", directions=["below"])]})
    with pytest.raises(AskError, match="arity"):
        _ask.ask_draft(
            _draft(), _ci(), "ints below", provider=model, examples=[_instance()]
        )
    # Both rounds ran (the repair got the same bad answer back).
    assert len(model.prompts) == 2


def test_provider_exception_raises(monkeypatch):
    _stub_eval(monkeypatch, {})

    def boom(prompt, *, schema):
        raise RuntimeError("no tokens")

    with pytest.raises(AskError, match="provider call failed"):
        _ask.ask_draft(
            _draft(), _ci(), "next below", provider=boom, examples=[_instance()]
        )


def test_evaluator_unavailable_raises(monkeypatch):
    _stub_eval(monkeypatch, {}, available=False)
    model = FakeAsk({"candidates": [_cand(directions=["below"])]})
    with pytest.raises(AskError, match="node"):
        _ask.ask_draft(
            _draft(), _ci(), "next below", provider=model, examples=[_instance()]
        )


def test_no_buildable_example_raises(monkeypatch):
    _stub_eval(monkeypatch, {})
    model = FakeAsk({"candidates": []})
    with pytest.raises(AskError, match="example"):
        _ask.ask_draft(_draft(), _ci(), "next below", provider=model, examples=[])


def test_suggest_ask_requires_enrich():
    with pytest.raises(AskError, match="enrich"):
        suggest(_instance(), ask="next below")


def test_suggest_ask_rejects_empty_statement():
    with pytest.raises(AskError, match="non-empty"):
        suggest(_instance(), ask="   ", enrich=lambda p, *, schema: {})


def test_suggest_ask_with_unresolvable_provider_raises():
    with pytest.raises(AskError, match="provider"):
        suggest(_instance(), ask="next below", enrich=123)


# --------------------------------------------------------------------------- #
# Through suggest(), and the spytial.suggest(...) call form
# --------------------------------------------------------------------------- #


class SchemaRouter:
    """One provider serving all three tiers, keyed by the schema each requests."""

    def __init__(self, ask_response):
        self.ask_response = ask_response

    def __call__(self, prompt, *, schema):
        props = schema.get("properties", {})
        if "candidates" in props:
            return self.ask_response
        if "selectors" in props:
            return {"selectors": []}
        return {"shapes": []}


def test_suggest_threads_ask_through(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    provider = SchemaRouter(
        {"candidates": [_cand(directions=["below"], why="user asked")]}
    )
    draft = suggest(_instance(), ask="children below parents", enrich=provider)

    assert any(
        s.directive == "orientation"
        and s.kwargs == {"selector": "next", "directions": ["below"]}
        and s.enabled_by_default
        for s in _llm(draft)
    )


def test_spytial_suggest_is_callable():
    # The natural spelling: spytial.suggest(obj, ...) — module-as-function.
    draft = spytial.suggest(_instance())
    assert isinstance(draft, SpecDraft)
    # The module facets still behave.
    assert spytial.suggest.SpecDraft is SpecDraft
    from spytial.suggest import suggest as fn

    assert fn is suggest


# --------------------------------------------------------------------------- #
# End-to-end with the real headless evaluator (skips without node)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not _eval.is_available(), reason="headless evaluator unavailable")
def test_ask_end_to_end_real_evaluator():
    model = FakeAsk(
        {"candidates": [_cand(directions=["below"], why="list reads downward")]}
    )
    draft = _draft()
    _ask.ask_draft(
        draft, _ci(), "each node below the previous", provider=model,
        examples=[_instance()],
    )
    (sug,) = _llm(draft)
    assert sug.kwargs == {"selector": "next", "directions": ["below"]}


@pytest.mark.skipif(not _eval.is_available(), reason="headless evaluator unavailable")
def test_ask_wins_its_ground_real_evaluator():
    """The motivating scenario: the ask's plain `below` replaces the rules'
    below-left/below-right — real datum, real intersection check."""

    class BT:
        def __init__(self, value, left=None, right=None):
            self.value, self.left, self.right = value, left, right

    tree = BT(1, BT(2, BT(4)), BT(3))
    provider = SchemaRouter(
        {
            "candidates": [
                _cand(
                    selector="left + right",
                    directions=["below"],
                    why="children hang below their parent",
                )
            ]
        }
    )
    draft = suggest(
        tree, ask="all binary tree children should be below their parents",
        enrich=provider,
    )

    enabled_orients = [
        s
        for s in draft.suggestions
        if s.directive == "orientation" and s.enabled_by_default
    ]
    assert len(enabled_orients) == 1
    assert enabled_orients[0].kwargs == {
        "selector": "left + right",
        "directions": ["below"],
    }
    # The rules' two per-field orientation rows stepped down, still one toggle away.
    assert (
        sum(1 for s in draft.alternatives if s.directive == "orientation") >= 2
    )


@pytest.mark.skipif(not _eval.is_available(), reason="headless evaluator unavailable")
def test_ask_end_to_end_rejects_unknown_relation():
    model = FakeAsk(
        {"candidates": [_cand(selector="children", directions=["below"])]}
    )
    with pytest.raises(AskError):
        _ask.ask_draft(
            _draft(), _ci(), "children below", provider=model, examples=[_instance()]
        )

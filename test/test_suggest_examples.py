#!/usr/bin/env python3
"""Tests for tier-2 example-validated selectors (``_enrich_from_examples``).

The loop logic is exercised with a fake model and a *stubbed* evaluator, so these run
deterministically with no node and no network. Two end-to-end tests use the real
headless evaluator and skip when the bridge isn't present.
"""

from __future__ import annotations

import json

import pytest

from spytial.suggest import _enrich
from spytial.suggest import _enrich_from_examples as sel
from spytial.suggest import _eval
from spytial.suggest import build_class_info
from spytial.suggest._model import SpecDraft, Suggestion


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


def _draft(suggestions=None):
    return SpecDraft(LL, list(suggestions or []))


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def text(self):
        return json.dumps(self._payload)


class FakeModel:
    """Returns a fixed ``{"selectors": [...]}`` payload; records prompts seen."""

    def __init__(self, candidates):
        self.candidates = candidates
        self.prompts = []

    def prompt(self, prompt, schema=None):
        self.prompts.append(prompt)
        return _Resp({"selectors": self.candidates})


def _v(selector, ok=True, empty=False, arity=2):
    return _eval.SelectorVerdict(selector=selector, ok=ok, empty=empty, arity=arity)


def _stub_eval(monkeypatch, spec, available=True):
    """Stub the evaluator: ``spec`` maps selector -> (ok, empty, arity), same for every
    example. Unlisted selectors default to a clean arity-2 result."""

    def fake_evaluate(datum, selectors):
        return [_v(s, *spec.get(s, (True, False, 2))) for s in selectors]

    monkeypatch.setattr(_eval, "is_available", lambda: available)
    monkeypatch.setattr(_eval, "evaluate_selectors", fake_evaluate)


def _stub_examples(monkeypatch, verdict_fn):
    """Stub build_instance to emit tagged minimal datums (tag = build order) and the
    evaluator to answer via ``verdict_fn(tag, selector)`` — so a test can make a
    selector resolve on some examples but not others."""
    counter = {"i": 0}

    class _Builder:
        def build_instance(self, obj):
            tag = counter["i"]
            counter["i"] += 1
            return {
                "_tag": tag,
                "atoms": [{"type": "LL"}],
                "relations": [{"name": "next", "types": ["o", "o"]}],
            }

    monkeypatch.setattr(sel, "CnDDataInstanceBuilder", lambda: _Builder())
    monkeypatch.setattr(_eval, "is_available", lambda: True)
    monkeypatch.setattr(
        _eval,
        "evaluate_selectors",
        lambda datum, selectors: [verdict_fn(datum["_tag"], s) for s in selectors],
    )


def _llm(draft):
    return [s for s in draft.suggestions if s.source == "llm"]


# --------------------------------------------------------------------------- #
# Admission logic (fake model + stubbed evaluator, single example)
# --------------------------------------------------------------------------- #


def test_valid_selectors_are_admitted(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2), "^next": (True, False, 2)})
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "fwd",
            },
            {
                "directive": "inferredEdge",
                "selector": "^next",
                "name": "reaches",
                "why": "reach",
            },
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])

    out = {s.directive: s for s in _llm(draft)}
    assert set(out) == {"orientation", "inferredEdge"}
    assert out["orientation"].kwargs == {"selector": "next", "directions": ["right"]}
    assert out["inferredEdge"].kwargs == {"name": "reaches", "selector": "^next"}
    assert all(
        s.source == "llm" and s.enabled_by_default is False for s in out.values()
    )
    assert any("added 2 model-authored selector" in n for n in draft.notes)


def test_wrong_arity_is_dropped(monkeypatch):
    _stub_eval(monkeypatch, {"unary": (True, False, 1)})
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "unary",
                "directions": ["right"],
                "why": "x",
            }
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    assert _llm(draft) == []


def test_hallucinated_and_empty_are_dropped(monkeypatch):
    # 'frends' -> arity-0 echo (not error, not empty, but does NOT resolve);
    # 'none'   -> empty set. Both must be rejected.
    _stub_eval(monkeypatch, {"frends": (True, False, 0), "none": (True, True, 0)})
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "frends",
                "directions": ["right"],
                "why": "x",
            },
            {"directive": "inferredEdge", "selector": "none", "name": "x", "why": "y"},
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    assert _llm(draft) == []


def test_parse_error_is_dropped(monkeypatch):
    _stub_eval(monkeypatch, {"bad ..": (False, False, 0)})  # ok=False -> errored
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "bad ..",
                "directions": ["right"],
                "why": "x",
            }
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    assert _llm(draft) == []


def test_orientation_without_direction_is_dropped(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    model = FakeModel(
        [{"directive": "orientation", "selector": "next", "directions": [], "why": "x"}]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    assert _llm(draft) == []


def test_dedup_against_existing_suggestions(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    existing = Suggestion(
        "orientation",
        {"selector": "next", "directions": ["right"]},
        "low",
        "rule",
        None,
        source="rule",
    )
    draft = _draft([existing])
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "x",
            }
        ]
    )
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    # The candidate collides with the existing suggestion's dedup_key -> not re-added.
    assert len(draft.suggestions) == 1


def test_inferred_edge_name_is_sanitized(monkeypatch):
    _stub_eval(monkeypatch, {"^next": (True, False, 2)})
    model = FakeModel(
        [
            {
                "directive": "inferredEdge",
                "selector": "^next",
                "name": "my edge!",
                "why": "x",
            }
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    (s,) = _llm(draft)
    assert s.kwargs["name"] == "myedge"


def test_inferred_edge_name_avoids_vocab_collision(monkeypatch):
    # 'next' is a real relation on LL; an inferredEdge named 'next' must be mangled so
    # it can't shadow the relation in the rendered diagram.
    _stub_eval(monkeypatch, {"^next": (True, False, 2)})
    model = FakeModel(
        [{"directive": "inferredEdge", "selector": "^next", "name": "next", "why": "x"}]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    (s,) = _llm(draft)
    assert s.kwargs["name"] == "next_"


# --------------------------------------------------------------------------- #
# Instance-set: a selector must resolve on EVERY example
# --------------------------------------------------------------------------- #


def test_selector_must_resolve_on_all_examples(monkeypatch):
    def verdict(tag, selector):
        if selector == "common":
            return _v(selector)  # resolves on both examples
        # 'onlyA' resolves on example 0, empties out on example 1
        return _v(selector) if tag == 0 else _v(selector, empty=True, arity=0)

    _stub_examples(monkeypatch, verdict)
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "common",
                "directions": ["right"],
                "why": "x",
            },
            {
                "directive": "orientation",
                "selector": "onlyA",
                "directions": ["right"],
                "why": "y",
            },
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [object(), object()])
    kept = {s.kwargs["selector"] for s in _llm(draft)}
    assert kept == {"common"}  # 'onlyA' dropped — did not resolve on example 1
    assert any("all 2 example instances" in n for n in draft.notes)


def test_unbuildable_example_skipped_others_proceed(monkeypatch):
    counter = {"i": 0}

    class _Builder:
        def build_instance(self, obj):
            i = counter["i"]
            counter["i"] += 1
            if i == 0:
                raise ValueError("bad example")
            return {
                "_tag": i,
                "atoms": [{"type": "LL"}],
                "relations": [{"name": "next", "types": ["o", "o"]}],
            }

    monkeypatch.setattr(sel, "CnDDataInstanceBuilder", lambda: _Builder())
    monkeypatch.setattr(_eval, "is_available", lambda: True)
    monkeypatch.setattr(
        _eval, "evaluate_selectors", lambda datum, selectors: [_v(s) for s in selectors]
    )
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "x",
            }
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [object(), object()])
    # First example failed to build, but the second succeeded -> tier still runs.
    assert [s.kwargs["selector"] for s in _llm(draft)] == ["next"]


# --------------------------------------------------------------------------- #
# Degradation paths
# --------------------------------------------------------------------------- #


def test_evaluator_unavailable_degrades(monkeypatch):
    _stub_eval(monkeypatch, {}, available=False)
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "x",
            }
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    assert _llm(draft) == []
    assert model.prompts == []  # never even prompted the model
    assert any("evaluator unavailable" in n for n in draft.notes)


def test_all_examples_unbuildable_degrades(monkeypatch):
    class _Boom:
        def build_instance(self, obj):
            raise ValueError("no relationalizer")

    monkeypatch.setattr(sel, "CnDDataInstanceBuilder", lambda: _Boom())
    monkeypatch.setattr(_eval, "is_available", lambda: True)
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "x",
            }
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [object()])
    assert _llm(draft) == []
    assert any("any example" in n for n in draft.notes)


def test_inner_evaluator_unavailable_degrades(monkeypatch):
    # is_available() passes, but evaluate_selectors raises AFTER the model is prompted.
    monkeypatch.setattr(_eval, "is_available", lambda: True)

    def boom(datum, selectors):
        raise _eval.EvaluatorUnavailable("node bridge failed to run: x")

    monkeypatch.setattr(_eval, "evaluate_selectors", boom)
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "x",
            }
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])  # must not raise
    assert _llm(draft) == []
    assert (
        model.prompts != []
    )  # model WAS prompted — distinguishes from the is_available gate
    assert any("selector tier skipped" in n for n in draft.notes)


def test_no_relations_is_silent_noop(monkeypatch):
    _stub_eval(monkeypatch, {}, available=True)
    monkeypatch.setattr(
        sel, "_vocabulary", lambda datums: {"types": [("LL", 3)], "relations": []}
    )
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "x",
            }
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    assert _llm(draft) == []
    assert model.prompts == []  # returned before prompting the model
    assert draft.notes == []  # silent — no relations is not an error worth noting


# --------------------------------------------------------------------------- #
# Robustness against malformed model output
# --------------------------------------------------------------------------- #


def test_non_string_selector_drops_candidate_not_batch(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": 42,
                "directions": ["right"],
                "why": "bad",
            },
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "ok",
            },
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])  # must not raise
    out = _llm(draft)
    assert len(out) == 1 and out[0].kwargs["selector"] == "next"


def test_non_list_directions_drops_candidate(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": "right",
                "why": "x",
            }
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])  # must not raise
    assert _llm(draft) == []


def test_non_dict_candidates_ignored(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    model = FakeModel(
        [
            "junk",
            None,
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "ok",
            },
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    assert [s.kwargs["selector"] for s in _llm(draft)] == ["next"]


def test_unknown_directive_is_dropped(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    model = FakeModel(
        [
            {"directive": "bogus", "selector": "next", "why": "x"},
            {"directive": "inferredEdge", "selector": "next", "name": "e", "why": "ok"},
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    assert {s.directive for s in _llm(draft)} == {"inferredEdge"}


def test_intra_batch_dedup(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    dup = {
        "directive": "orientation",
        "selector": "next",
        "directions": ["right"],
        "why": "x",
    }
    model = FakeModel([dup, dict(dup)])
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    assert len(_llm(draft)) == 1


def test_shared_selector_across_directives(monkeypatch):
    _stub_eval(monkeypatch, {"^next": (True, False, 2)})
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "^next",
                "directions": ["right"],
                "why": "x",
            },
            {
                "directive": "inferredEdge",
                "selector": "^next",
                "name": "reaches",
                "why": "y",
            },
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    assert {s.directive for s in _llm(draft)} == {"orientation", "inferredEdge"}


def test_vocabulary_unions_populated_types_across_examples():
    d0 = sel.CnDDataInstanceBuilder().build_instance(_instance(3))
    d1 = sel.CnDDataInstanceBuilder().build_instance(_instance(2))
    vocab = sel._vocabulary([d0, d1])
    type_names = {t for t, _ in vocab["types"]}
    assert "LL" in type_names  # populated node type present
    assert ("next", 2) in vocab["relations"] and ("value", 2) in vocab["relations"]
    assert all(n > 0 for _, n in vocab["types"])  # populated only


# --------------------------------------------------------------------------- #
# enrich_draft seam: examples threading + the "pass examples" note
# --------------------------------------------------------------------------- #


class _FakeLLM:
    def get_model(self, *a, **k):
        return _ShapeModel()


class _ShapeModel:
    def prompt(self, prompt, schema=None):
        return _Resp({"shapes": []})  # shape tier no-op


def test_enrich_draft_notes_when_no_examples(monkeypatch):
    monkeypatch.setattr(_enrich, "_import_llm", lambda: _FakeLLM())
    draft = _draft()
    _enrich.enrich_draft(draft, _ci(), model=None, examples=None)
    assert any("pass examples" in n for n in draft.notes)


def test_enrich_draft_runs_selector_tier_with_examples(monkeypatch):
    monkeypatch.setattr(_enrich, "_import_llm", lambda: _FakeLLM())
    calls = []
    monkeypatch.setattr(
        sel,
        "enrich_from_examples",
        lambda draft, ci, model, examples: calls.append(examples),
    )
    objs = [_instance(), _instance(2)]
    draft = _draft()
    _enrich.enrich_draft(draft, _ci(), model=None, examples=objs)
    assert calls == [objs]  # selector tier invoked with the full example set


# --------------------------------------------------------------------------- #
# End-to-end with the REAL evaluator (skips without the bridge)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not _eval.is_available(),
    reason="headless evaluator bridge unavailable (need a node runtime on PATH)",
)
def test_end_to_end_single_example():
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "fwd",
            },
            {
                "directive": "inferredEdge",
                "selector": "^next",
                "name": "reaches",
                "why": "reach",
            },
            {
                "directive": "orientation",
                "selector": "bogusRel",
                "directions": ["right"],
                "why": "no",
            },
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance()])
    kept = {s.kwargs.get("selector") for s in _llm(draft)}
    assert "next" in kept and "^next" in kept  # real relations resolve at arity 2
    assert "bogusRel" not in kept  # unknown name does not resolve -> dropped


@pytest.mark.skipif(
    not _eval.is_available(),
    reason="headless evaluator bridge unavailable (need a node runtime on PATH)",
)
def test_end_to_end_instance_set():
    # 'next' resolves on lists of both lengths; a bogus relation resolves on neither.
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "fwd",
            },
            {
                "directive": "orientation",
                "selector": "bogusRel",
                "directions": ["right"],
                "why": "no",
            },
        ]
    )
    draft = _draft()
    sel.enrich_from_examples(draft, _ci(), model, [_instance(4), _instance(2)])
    kept = {s.kwargs.get("selector") for s in _llm(draft)}
    assert kept == {"next"}
    assert any("all 2 example instances" in n for n in draft.notes)

#!/usr/bin/env python3
"""Tests for tier-2 LLM selector authoring (``spytial.suggest._enrich_selectors``).

The loop logic is exercised with a fake model and a *stubbed* evaluator, so these
run deterministically with no node and no network. One end-to-end test uses the
real headless evaluator and skips when the bridge isn't present.
"""

from __future__ import annotations

import json

import pytest

from spytial.suggest import _enrich
from spytial.suggest import _eval
from spytial.suggest import _enrich_selectors as sel
from spytial.suggest import build_class_info
from spytial.suggest._model import SpecDraft, Suggestion


# --------------------------------------------------------------------------- #
# Fixtures / fakes
# --------------------------------------------------------------------------- #


class LL:
    """A 3-element singly linked list: relations `next` and `value`, both arity 2."""

    def __init__(self, value, nxt=None):
        self.value = value
        self.next = nxt


def _instance():
    a, b, c = LL(1), LL(2), LL(3)
    a.next, b.next = b, c
    return a


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


def _stub_eval(monkeypatch, spec, available=True):
    """Stub the evaluator: ``spec`` maps selector -> (ok, empty, arity).

    Unlisted selectors default to a clean arity-2 result, so a test only spells out
    the verdicts it cares about.
    """

    def fake_evaluate(datum, selectors):
        out = []
        for s in selectors:
            ok, empty, arity = spec.get(s, (True, False, 2))
            out.append(
                _eval.SelectorVerdict(selector=s, ok=ok, empty=empty, arity=arity)
            )
        return out

    monkeypatch.setattr(_eval, "is_available", lambda: available)
    monkeypatch.setattr(_eval, "evaluate_selectors", fake_evaluate)


def _llm(draft):
    return [s for s in draft.suggestions if s.source == "llm"]


# --------------------------------------------------------------------------- #
# Admission logic (fake model + stubbed evaluator)
# --------------------------------------------------------------------------- #


def test_valid_selectors_are_admitted(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2), "^next": (True, False, 2)})
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "forward link",
            },
            {
                "directive": "inferredEdge",
                "selector": "^next",
                "name": "reaches",
                "why": "reachability",
            },
        ]
    )
    draft = _draft()
    sel.enrich_selectors(draft, _ci(), model, _instance())

    out = {s.directive: s for s in _llm(draft)}
    assert set(out) == {"orientation", "inferredEdge"}
    assert out["orientation"].kwargs == {"selector": "next", "directions": ["right"]}
    assert out["inferredEdge"].kwargs == {"name": "reaches", "selector": "^next"}
    assert all(
        s.source == "llm" and s.enabled_by_default is False for s in out.values()
    )
    assert any("added 2 model-authored selector" in n for n in draft.notes)


def test_wrong_arity_is_dropped(monkeypatch):
    # orientation needs an arity-2 (edge) selector; a unary result must be rejected.
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
    sel.enrich_selectors(draft, _ci(), model, _instance())
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
    sel.enrich_selectors(draft, _ci(), model, _instance())
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
    sel.enrich_selectors(draft, _ci(), model, _instance())
    assert _llm(draft) == []


def test_orientation_without_direction_is_dropped(monkeypatch):
    _stub_eval(monkeypatch, {"next": (True, False, 2)})
    model = FakeModel(
        [{"directive": "orientation", "selector": "next", "directions": [], "why": "x"}]
    )
    draft = _draft()
    sel.enrich_selectors(draft, _ci(), model, _instance())
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
    sel.enrich_selectors(draft, _ci(), model, _instance())
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
    sel.enrich_selectors(draft, _ci(), model, _instance())
    (s,) = _llm(draft)
    assert s.kwargs["name"] == "myedge"


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
    sel.enrich_selectors(draft, _ci(), model, _instance())
    assert _llm(draft) == []
    assert model.prompts == []  # never even prompted the model
    assert any("evaluator unavailable" in n for n in draft.notes)


def test_build_instance_failure_degrades(monkeypatch):
    class _Boom:
        def build_instance(self, obj):
            raise ValueError("no relationalizer")

    monkeypatch.setattr(sel, "CnDDataInstanceBuilder", lambda: _Boom())
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
    sel.enrich_selectors(draft, _ci(), model, _instance())
    assert _llm(draft) == []
    assert any("couldn't build a datum" in n for n in draft.notes)


def test_vocabulary_lists_only_populated_types():
    datum = sel.CnDDataInstanceBuilder().build_instance(_instance())
    vocab = sel._vocabulary(datum)
    type_names = {t for t, _ in vocab["types"]}
    assert "LL" in type_names  # the node type is present and populated
    assert ("next", 2) in vocab["relations"] and ("value", 2) in vocab["relations"]
    # every listed type has a positive population count
    assert all(n > 0 for _, n in vocab["types"])


# --------------------------------------------------------------------------- #
# Robustness against malformed model output
# --------------------------------------------------------------------------- #


def test_non_string_selector_drops_candidate_not_batch(monkeypatch):
    # A truthy non-string selector must not crash the batch — the good candidate
    # next to it is still admitted.
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
    sel.enrich_selectors(draft, _ci(), model, _instance())  # must not raise
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
    sel.enrich_selectors(draft, _ci(), model, _instance())  # must not raise
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
    sel.enrich_selectors(draft, _ci(), model, _instance())
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
    sel.enrich_selectors(draft, _ci(), model, _instance())
    assert {s.directive for s in _llm(draft)} == {"inferredEdge"}


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
    sel.enrich_selectors(draft, _ci(), model, _instance())  # must not raise
    assert _llm(draft) == []
    assert (
        model.prompts != []
    )  # model WAS prompted — distinguishes from the is_available gate
    assert any("selector tier skipped" in n for n in draft.notes)


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
    sel.enrich_selectors(draft, _ci(), model, _instance())
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
    sel.enrich_selectors(draft, _ci(), model, _instance())
    assert {s.directive for s in _llm(draft)} == {"orientation", "inferredEdge"}


def test_no_relations_is_silent_noop(monkeypatch):
    _stub_eval(monkeypatch, {}, available=True)
    monkeypatch.setattr(
        sel, "_vocabulary", lambda datum: {"types": [("LL", 3)], "relations": []}
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
    sel.enrich_selectors(draft, _ci(), model, _instance())
    assert _llm(draft) == []
    assert model.prompts == []  # returned before prompting the model
    assert draft.notes == []  # silent — no relations is not an error worth noting


# --------------------------------------------------------------------------- #
# enrich_draft seam: instance threading + the "pass an instance" note
# --------------------------------------------------------------------------- #


class _FakeLLM:
    def get_model(self, *a, **k):
        return _ShapeModel()


class _ShapeModel:
    def prompt(self, prompt, schema=None):
        return _Resp({"shapes": []})  # shape tier no-op


def test_enrich_draft_notes_when_no_instance(monkeypatch):
    monkeypatch.setattr(_enrich, "_import_llm", lambda: _FakeLLM())
    draft = _draft()
    _enrich.enrich_draft(draft, _ci(), model=None, instance=None)
    assert any("pass an instance" in n for n in draft.notes)


def test_enrich_draft_runs_selector_tier_with_instance(monkeypatch):
    monkeypatch.setattr(_enrich, "_import_llm", lambda: _FakeLLM())
    calls = []
    monkeypatch.setattr(
        sel,
        "enrich_selectors",
        lambda draft, ci, model, instance: calls.append(instance),
    )
    obj = _instance()
    draft = _draft()
    _enrich.enrich_draft(draft, _ci(), model=None, instance=obj)
    assert calls == [obj]  # selector tier invoked with the instance


# --------------------------------------------------------------------------- #
# End-to-end with the REAL evaluator (skips without the bridge)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not _eval.is_available(),
    reason="headless evaluator bridge unavailable (need node + SPYTIAL_CORE_NODE_PATH)",
)
def test_end_to_end_real_evaluator():
    model = FakeModel(
        [
            {
                "directive": "orientation",
                "selector": "next",
                "directions": ["right"],
                "why": "forward",
            },
            {
                "directive": "inferredEdge",
                "selector": "^next",
                "name": "reaches",
                "why": "reachability",
            },
            {
                "directive": "orientation",
                "selector": "bogusRel",
                "directions": ["right"],
                "why": "nope",
            },
        ]
    )
    draft = _draft()
    sel.enrich_selectors(draft, _ci(), model, _instance())
    kept = {s.kwargs.get("selector") for s in _llm(draft)}
    assert "next" in kept and "^next" in kept  # real relations resolve at arity 2
    assert "bogusRel" not in kept  # unknown name does not resolve -> dropped

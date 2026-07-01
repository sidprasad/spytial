#!/usr/bin/env python3
"""Tests for ``spytial.suggest._eval`` — the headless selector-evaluation bridge.

The bridge shells out to ``node`` over the windowless spytial-core evaluator. The
evaluator is normally the vendored self-contained copy, so the real-evaluation
tests run whenever ``node`` is on PATH; they skip cleanly otherwise, so CI stays
green with no network. The degradation path is always exercised.
"""

from __future__ import annotations

import pytest

from spytial.provider_system import CnDDataInstanceBuilder
from spytial.suggest import _eval

requires_bridge = pytest.mark.skipif(
    not _eval.is_available(),
    reason="headless evaluator bridge unavailable (need a node runtime on PATH)",
)


class LLNode:
    """A 3-element singly linked list: n0 -> n1 -> n2 -> None."""

    def __init__(self, value, nxt=None):
        self.value = value
        self.next = nxt


def _linked_list_datum():
    a, b, c = LLNode(1), LLNode(2), LLNode(3)
    a.next, b.next = b, c
    return CnDDataInstanceBuilder().build_instance(a)


# --------------------------------------------------------------------------- #
# Degradation path — always runs (no node required).
# --------------------------------------------------------------------------- #


def _force_unavailable(monkeypatch, tmp_path):
    """Disable both resolution paths: invalid env override AND no vendored file."""
    monkeypatch.setenv("SPYTIAL_CORE_NODE_PATH", str(tmp_path))  # no node_modules here
    monkeypatch.setattr(_eval, "_VENDORED_EVALUATOR", tmp_path / "absent.js")


def test_resolution_prefers_env_override_then_vendored(monkeypatch, tmp_path):
    """A valid SPYTIAL_CORE_NODE_PATH wins; otherwise the vendored file (no node needed)."""
    # No override + the shipped vendored file present -> require it by absolute path.
    monkeypatch.delenv("SPYTIAL_CORE_NODE_PATH", raising=False)
    core = _eval._resolve_core()
    assert core == {"SPYTIAL_EVALUATOR_MODULE": str(_eval._VENDORED_EVALUATOR)}

    # A valid override takes precedence -> bare specifier resolved via NODE_PATH.
    install = tmp_path / "install"
    (install / "node_modules" / "spytial-core").mkdir(parents=True)
    monkeypatch.setenv("SPYTIAL_CORE_NODE_PATH", str(install))
    assert _eval._resolve_core() == {"NODE_PATH": str(install / "node_modules")}


def test_unavailable_raises(monkeypatch, tmp_path):
    """With no resolvable evaluator at all, evaluate_selectors raises (never hangs)."""
    _force_unavailable(monkeypatch, tmp_path)
    assert _eval._node_modules_dir() is None
    assert _eval._resolve_core() is None
    assert _eval.is_available() is False
    with pytest.raises(_eval.EvaluatorUnavailable):
        _eval.evaluate_selectors({"atoms": [], "relations": [], "types": []}, ["Node"])


def test_empty_selector_list_is_noop(monkeypatch, tmp_path):
    """An empty batch returns [] before any bridge work — even when unavailable."""
    _force_unavailable(monkeypatch, tmp_path)
    assert _eval.is_available() is False
    assert _eval.evaluate_selectors({}, []) == []  # still a clean no-op


# --------------------------------------------------------------------------- #
# Real evaluation — runs only when the bridge is present.
# --------------------------------------------------------------------------- #


@requires_bridge
def test_valid_selectors_resolve():
    datum = _linked_list_datum()
    by_sel = {
        v.selector: v
        for v in _eval.evaluate_selectors(datum, ["LLNode", "next", "LLNode.next"])
    }

    assert by_sel["LLNode"].resolves and by_sel["LLNode"].arity == 1
    assert by_sel["next"].resolves and by_sel["next"].arity == 2
    assert by_sel["LLNode.next"].resolves  # navigation/join


@requires_bridge
def test_hallucinated_name_does_not_resolve():
    """An invented relation name evaluates cleanly but must NOT count as resolving.

    The evaluator parses an unknown bareword as an atom literal echoing itself: it
    is not an error and not empty, but it is arity 0. ``resolves`` rejects it.
    """
    (v,) = _eval.evaluate_selectors(_linked_list_datum(), ["frends"])
    assert v.ok is True and v.empty is False  # neither errors nor empties
    assert v.arity == 0 and v.resolves is False  # ...yet does not resolve


@requires_bridge
def test_empty_and_malformed_do_not_resolve():
    datum = _linked_list_datum()
    by_sel = {
        v.selector: v
        for v in _eval.evaluate_selectors(datum, ["LLNode - LLNode", "LLNode .. next"])
    }

    assert (
        by_sel["LLNode - LLNode"].empty is True
        and by_sel["LLNode - LLNode"].resolves is False
    )
    assert by_sel["LLNode .. next"].ok is False  # parse error surfaced as a verdict
    assert by_sel["LLNode .. next"].resolves is False


@requires_bridge
def test_vocabulary_is_reachable_for_grounding():
    """The datum carries the closed type/relation vocabulary tier-2 grounds on."""
    datum = _linked_list_datum()
    # 'value' and 'next' are the relations build_instance emits for LLNode.
    (v,) = _eval.evaluate_selectors(datum, ["value"])
    assert v.ok and v.arity == 2  # value is a binary relation

"""Using accepted requirements through the real Python diagram integration."""

from pathlib import Path
import os

import pytest
import yaml
from hypothesis import strategies as st

import spytial
from spytial.annotations import collect_decorators
from spytial.suggest import (
    suggest,
    SuggestSession,
    FixedExamples,
    FixedProposals,
    HypothesisSearch,
    LivingSpec,
    SpecUnavailableError,
)
from test_suggest_session import (
    Tree,
    tree,
    proposal,
    Provider,
    session,
    state,
    accept_below,
    clean_tree_binding,
)
from test_suggest_living import refined_session, accept_alignment


@pytest.fixture
def live_session():
    with refined_session() as s:
        accept_below(s)
        yield s


@pytest.fixture
def emitted_spec(monkeypatch):
    import spytial.visualizer as visualizer

    monkeypatch.setattr(
        visualizer, "_generate_visualizer_html", lambda data, spec, *a, **kw: spec
    )
    monkeypatch.setattr(visualizer, "_deliver_html_content", lambda html, **kw: html)
    return lambda obj, **kw: yaml.safe_load(
        spytial.diagram(obj, method="file", auto_open=False, **kw)
    )


def test_same_bound_handle_uses_new_accepted_requirement_on_next_diagram(
    live_session, emitted_spec
):
    s = live_session
    spec = s.apply()
    before = emitted_spec(tree())
    snapshot = spec.snapshot()
    assert isinstance(spec, LivingSpec) and spec is s.spec
    prop = s.add_requirement("Align siblings")
    assert prop.status == "draft"
    assert (
        emitted_spec(tree()) == before
    )  # A pending requirement does not enter the live spec.
    s.judge(
        "left",
        layout_states=[
            state(-120, 150, other_x=120, other_y=150),
            state(-120, 150, other_x=-120, other_y=250),
        ],
    )
    assert prop.status == "accepted"
    assert emitted_spec(tree()) != before
    assert emitted_spec(tree()) == spec.to_registry()
    assert emitted_spec(tree(), spec=spec) == spec.to_registry()
    assert snapshot.to_registry() == before


def test_print_reads_current_rules_from_the_same_living_object(live_session, capsys):
    s = live_session
    spec = s.spec
    print(spec)
    before = capsys.readouterr().out
    assert before == spec.to_source(with_comments=False) + "\n"
    assert "spytial.orientation" in before and "LivingSpec" not in before
    accept_alignment(s)
    print(spec)
    after = capsys.readouterr().out
    assert after != before and "spytial.align" in after
    assert repr(spec).startswith("<LivingSpec")
    s.close()
    assert str(spec) == spec.to_source(with_comments=False)


def test_losing_last_accepted_requirement_blocks_drawing_until_corrected(
    live_session, emitted_spec
):
    s = live_session
    spec = s.apply()
    q = s.history[0]["id"]
    s.reclassify(q, 0, "unsure")
    assert spec.status == "empty"
    with pytest.raises(SpecUnavailableError, match="Accept a requirement"):
        emitted_spec(tree())
    assert s._datum(tree())["atoms"]
    s.reclassify(q, 0, "upvote")
    s.done()
    assert emitted_spec(tree()) == spec.to_registry()


def test_explicit_spec_needs_no_binding_and_snapshot_is_independent(
    live_session, emitted_spec
):
    s = live_session
    assert not s.spec.applied
    assert emitted_spec(tree(), spec=s.spec) == s.spec.to_registry()
    snap = s.spec.snapshot()
    snap.suggestions.clear()
    assert s.spec.to_registry()["constraints"]
    assert not s.spec.applied


def test_done_is_separate_from_apply_and_close(live_session, emitted_spec):
    s = live_session
    checkpoint = s.done()
    assert checkpoint["status"] == "accepted" and s.paused
    assert not s.spec.applied
    spec = s.apply()
    s.close()
    assert emitted_spec(tree()) == spec.to_registry()
    with pytest.raises(RuntimeError, match="closed"):
        s.resume()
    spec.unapply()
    assert not spec.applied


def test_unapply_preserves_manual_annotations(live_session):
    s = live_session
    spytial.orientation(selector="right - (univ -> NoneType)", directions=["right"])(
        Tree
    )
    before = collect_decorators(tree())
    spec = s.apply()
    assert spec.applied
    assert len(collect_decorators(tree())["constraints"]) > len(before["constraints"])
    spec.unapply()
    assert collect_decorators(tree()) == before


def test_loading_requires_explicit_rebinding_and_old_unapply_is_safe(
    live_session, tmp_path, emitted_spec
):
    old = live_session.apply()
    path = tmp_path / "spec.json"
    live_session.save(path)
    with SuggestSession.load(Tree, path, search=FixedExamples()).wait() as restored:
        assert not restored.spec.applied and old.applied
        new = restored.apply()
        old.unapply()
        assert new.applied
        assert emitted_spec(tree()) == new.to_registry()
    assert new.to_registry() == old.to_registry()


@pytest.mark.parametrize("supplied_examples", [False, True])
def test_replacement_generates_data_while_old_binding_is_unavailable(
    live_session, supplied_examples
):
    old = live_session.apply()
    live_session.reclassify(live_session.history[0]["id"], 0, "downvote")
    assert old.status == "empty"
    witness = Tree(1, Tree(2))
    with suggest(
        Tree,
        examples=[tree()] if supplied_examples else None,
        strategy=st.sampled_from([Tree(), witness]),
        proposer=FixedProposals([proposal(["below"]), proposal(["right"])]),
        max_examples=3,
    ).wait() as replacement:
        assert replacement.examples[-1] is witness
        assert not replacement.requirements
        replacement.add_requirement("Parents above children")
        assert replacement.next() is not None
        assert old.applied and not replacement.spec.applied


def test_generated_conflict_prevents_acceptance_and_retains_counterexample():
    with session(proposer=Provider()) as s:
        prop = s.add_requirement("Parents above children")
        cyclic = tree()
        cyclic.left = cyclic
        s.search = HypothesisSearch(st.just(cyclic))
        s.judge("left", layout_states=[state(-120, 150), state(120, -150)])
        assert prop.status == "conflict"
        assert any(example is cyclic for example in s.examples)
        with pytest.raises(SpecUnavailableError):
            s.apply()


def test_generated_checks_do_not_recurse_into_class_binding(live_session):
    s = live_session
    spec = s.apply()
    calls = []

    class Search:
        def find(self, cls, predicate, *, max_examples):
            calls.append(True)
            assert not predicate(tree())
            return None

    s.search = Search()
    s._invalidate_result()
    assert spec.to_registry() and len(calls) == 1
    assert spec.to_registry() and len(calls) == 1


@pytest.mark.skipif(
    os.environ.get("SPYTIAL_BROWSER_TESTS") != "1", reason="opt-in real browser test"
)
def test_real_diagram_call_uses_new_requirement_without_redrawing_old_output(
    live_session, tmp_path, monkeypatch
):
    from playwright.sync_api import sync_playwright

    monkeypatch.setenv("SPYTIAL_ASSETS", "embedded")
    monkeypatch.chdir(tmp_path)
    s = live_session
    s.apply()
    first = Path(spytial.diagram(tree(), method="file", auto_open=False)).rename(
        tmp_path / "first.html"
    )
    original = first.read_bytes()
    accept_alignment(s)
    second = Path(spytial.diagram(tree(), method="file", auto_open=False))
    assert first.read_bytes() == original
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("http://**/*", lambda route: route.abort())
        page.route("https://**/*", lambda route: route.abort())
        page.goto(second.as_uri())
        page.wait_for_function(
            "document.querySelector('webcola-cnd-graph')?.getNodePositions().length > 0"
        )
        assert not errors
        browser.close()

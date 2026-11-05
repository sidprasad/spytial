"""Using a living spec through normal Python annotation and diagram APIs."""

from copy import deepcopy
import os
from pathlib import Path

import pytest
import yaml

import spytial
from spytial.annotations import LIVE_SPEC_ATTR, collect_decorators
from spytial.provider_system import CnDDataInstanceBuilder
from spytial.suggest import (
    FixedExamples,
    LivingSpec,
    SpecUnavailableError,
    SuggestSession,
)
from test_suggest_living import session, state
from test_suggest_session import Tree, tree, proposal


@pytest.fixture
def live_session():
    previous = Tree.__dict__.get(LIVE_SPEC_ATTR)
    with session(elimination_threshold=1) as s:
        s.judge("right", layout_states=[state(-120, 150), state(120, -150)])
        try:
            yield s
        finally:
            if previous is None:
                if LIVE_SPEC_ATTR in Tree.__dict__:
                    delattr(Tree, LIVE_SPEC_ATTR)
            else:
                setattr(Tree, LIVE_SPEC_ATTR, previous)


@pytest.fixture
def emitted_spec(monkeypatch):
    """Exercise diagram's real data/annotation path, capture its emitted YAML."""
    import spytial.visualizer as visualizer

    monkeypatch.setattr(
        visualizer, "_generate_visualizer_html", lambda data, spec, *args, **kw: spec
    )
    monkeypatch.setattr(visualizer, "_deliver_html_content", lambda html, **kw: html)
    return lambda obj, **kw: yaml.safe_load(
        spytial.diagram(obj, method="file", auto_open=False, **kw)
    )


def add_above(s):
    s.proposer = lambda prompt, schema: {
        "rules": [],
        "programs": [proposal(["right", "above"])],
    }
    s.revise("Also keep that child above")


def test_apply_returns_stable_object_and_future_diagrams_follow_revision(
    live_session, emitted_spec
):
    s = live_session
    spec = s.apply()
    assert isinstance(spec, LivingSpec)
    assert spec is s.spec is s.apply()
    assert spec.applied and not s.paused
    obj = tree()
    before = emitted_spec(obj)
    snapshot = spec.snapshot()
    add_above(s)
    assert s.spec is spec
    after = emitted_spec(obj)
    assert before != after
    assert after == spec.to_registry()
    assert snapshot.to_registry() == before
    snapshot.suggestions.clear()
    assert spec.to_registry() == after
    assert ["right", "above"] in [
        row["orientation"]["directions"]
        for row in after["constraints"]
        if "orientation" in row
    ]
    assert not any(
        "below" in row.get("orientation", {}).get("directions", [])
        for row in after["constraints"]
    )


def test_losing_all_candidates_blocks_drawing_and_correction_restores_it(
    live_session, emitted_spec
):
    s = live_session
    spec = s.apply()
    question = s.history[0]["id"]
    s.reclassify(question, 1, "downvote")
    assert spec.status == "empty"
    with pytest.raises(SpecUnavailableError, match="No candidates remain"):
        emitted_spec(tree())
    # Search/revision can still serialize data while the bound spec is empty.
    assert s._datum(tree())["atoms"]
    s.reclassify(question, 1, "upvote")
    assert spec.status == "supported"
    assert emitted_spec(tree()) == spec.to_registry()


def test_apply_without_support_leaves_class_unchanged():
    with session() as s:
        with pytest.raises(SpecUnavailableError, match="positive evidence"):
            s.apply()
        assert not s.spec.applied


def test_explicit_spec_updates_without_class_binding(live_session, emitted_spec):
    s = live_session
    spec = s.spec
    before = emitted_spec(tree(), spec=spec)
    assert not spec.applied
    add_above(s)
    assert emitted_spec(tree(), spec=spec) != before
    assert not spec.applied
    # A snapshot remains an ordinary usable spec.
    snapshot = spec.snapshot()
    assert emitted_spec(tree(), spec=snapshot) == snapshot.to_registry()


def test_explicit_program_bypasses_an_unavailable_class_binding(
    live_session, emitted_spec
):
    s = live_session
    s.apply()
    s.reclassify(s.history[0]["id"], 1, "downvote")
    program = {"constraints": [], "directives": []}
    assert emitted_spec(tree(), spec=program) == program
    with pytest.raises(TypeError, match="constraints and directives"):
        emitted_spec(tree(), spec={"constraints": "bad", "directives": []})


def test_unapply_preserves_manual_annotations(live_session, monkeypatch):
    monkeypatch.setattr(
        Tree,
        "__spytial_registry__",
        {"constraints": [], "directives": [{"flag": "hideDisconnected"}]},
        raising=False,
    )
    manual = deepcopy(Tree.__spytial_registry__)
    spec = live_session.apply()
    assert {"flag": "hideDisconnected"} in collect_decorators(tree())["directives"]
    assert Tree.__spytial_registry__ == manual
    spec.unapply()
    assert collect_decorators(tree()) == manual
    assert not spec.applied


def test_bindings_follow_inheritance_controls(live_session):
    spec = live_session.apply()

    class Child(Tree):
        pass

    @spytial.dont_inherit_constraints
    class NoConstraints(Tree):
        pass

    @spytial.dont_inherit_annotations
    class NoAnnotations(Tree):
        pass

    assert collect_decorators(Child()) == spec.to_registry()
    assert collect_decorators(NoConstraints())["constraints"] == []
    assert (
        collect_decorators(NoConstraints())["directives"]
        == spec.to_registry()["directives"]
    )
    assert collect_decorators(NoAnnotations()) == {"constraints": [], "directives": []}


def test_each_data_build_resolves_a_live_binding_once(live_session, monkeypatch):
    spec = live_session.apply()
    read = spec.to_registry
    calls = []

    def counted():
        calls.append(True)
        return read()

    monkeypatch.setattr(spec, "to_registry", counted)
    builder = CnDDataInstanceBuilder()
    builder.build_instance(tree())
    assert len(calls) == 1  # Three instances, one consistent program version.
    builder.build_instance(tree())
    assert len(calls) == 2  # A later call refreshes that version.


def test_generated_checks_are_cached_and_do_not_recurse_through_binding(live_session):
    s = live_session
    calls = []

    class Search:
        def find(self, cls, predicate, *, max_examples):
            calls.append(True)
            assert not predicate(tree())
            return None

    s.search = Search()
    spec = s.apply()
    assert spec.to_registry()
    assert len(calls) == 1
    s.reclassify(s.history[0]["id"], 0, "unsure")
    assert spec.to_registry()
    assert len(calls) == 2


def test_generated_conflicts_prevent_application(live_session):
    s = live_session
    cyclic = tree()
    cyclic.left = cyclic

    class Search:
        def find(self, cls, predicate, *, max_examples):
            assert predicate(cyclic)
            return cyclic

    s.search = Search()
    with pytest.raises(SpecUnavailableError, match="Generated data"):
        s.apply()
    assert not s.spec.applied


def test_load_is_explicit_and_new_binding_is_not_removed_by_old_handle(
    live_session, tmp_path, emitted_spec
):
    s = live_session
    old = s.apply()
    path = tmp_path / "tree.json"
    s.save(path)
    with SuggestSession.load(Tree, path, search=FixedExamples()).wait() as restored:
        assert not restored.spec.applied
        assert old.applied
        new = restored.apply()
        old.unapply()
        assert new.applied
        assert emitted_spec(tree()) == new.to_registry()
    # Closing the exploration server does not discard the usable spec.
    assert new.to_registry() == old.to_registry()


@pytest.mark.skipif(
    os.environ.get("SPYTIAL_BROWSER_TESTS") != "1", reason="opt-in real browser test"
)
def test_real_diagram_call_uses_revised_bound_program(
    live_session, monkeypatch, tmp_path
):
    from playwright.sync_api import sync_playwright

    monkeypatch.setenv("SPYTIAL_ASSETS", "embedded")
    monkeypatch.chdir(tmp_path)
    s = live_session
    spec = s.apply()
    obj = tree()
    first = Path(spytial.diagram(obj, method="file", auto_open=False)).rename(
        tmp_path / "first.html"
    )
    original_html = first.read_bytes()
    add_above(s)
    second = Path(spytial.diagram(obj, method="file", auto_open=False))
    assert s.spec is spec
    assert first.read_bytes() == original_html
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("http://**/*", lambda route: route.abort())
        page.route("https://**/*", lambda route: route.abort())
        page.goto(second.as_uri())
        page.wait_for_function(
            """() => {
            const g = document.querySelector('webcola-cnd-graph');
            const nodes = g?.getNodePositions?.() || [];
            const root = nodes.find(n => n.id === 'n0');
            const child = nodes.find(n => n.id === 'n1');
            return root && child && child.x > root.x && child.y < root.y;
        }"""
        )
        assert not errors
        browser.close()

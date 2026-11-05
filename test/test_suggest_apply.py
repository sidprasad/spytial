"""Using a living spec through normal Python annotation and diagram APIs."""

from copy import deepcopy
import os
from pathlib import Path

import pytest
import yaml
from hypothesis import strategies as st

import spytial
from spytial.annotations import LIVE_SPEC_ATTR, collect_decorators
from spytial.provider_system import CnDDataInstanceBuilder
from spytial.suggest import (
    FixedExamples,
    HypothesisSearch,
    LivingSpec,
    SpecUnavailableError,
    SuggestSession,
)
from test_suggest_living import session, state
from test_suggest_session import Tree, tree, proposal


@pytest.fixture(autouse=True)
def restore_class_binding():
    previous = Tree.__dict__.get(LIVE_SPEC_ATTR)
    yield
    if previous is None:
        if LIVE_SPEC_ATTR in Tree.__dict__:
            delattr(Tree, LIVE_SPEC_ATTR)
    else:
        setattr(Tree, LIVE_SPEC_ATTR, previous)


@pytest.fixture
def live_session():
    with session(elimination_threshold=1) as s:
        s.judge("right", layout_states=[state(-120, 150), state(120, -150)])
        yield s


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


def orientation_directions(program):
    return [
        row["orientation"]["directions"]
        for row in program["constraints"]
        if "orientation" in row
    ]


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


def test_done_with_multiple_unreviewed_candidates_does_not_allow_application(
    emitted_spec,
):
    with session() as s:
        spec = s.spec
        assert len(s.survivors) == 2
        inspection = s.draft
        assert orientation_directions(inspection.to_registry()) == [
            ["below"],
            ["right"],
        ]
        # A caller can explicitly use an editable copy. That is separate from
        # live application and supplies no evidence to the session.
        assert emitted_spec(tree(), spec=inspection) == inspection.to_registry()
        assert not s.history
        checkpoint = s.done()
        assert checkpoint["status"] == "draft"
        assert len(checkpoint["candidate_ids"]) == 2
        assert s.paused and not spec.applied
        with pytest.raises(SpecUnavailableError, match="positive evidence"):
            s.apply()
        assert not spec.applied
        s.resume()
        assert s.spec is spec
        assert not s.paused
        assert spec.status == "draft"


@pytest.mark.parametrize("minimum", [1, 2])
def test_apply_combines_multiple_survivors_after_shared_positive_evidence(
    minimum, emitted_spec
):
    with session(min_positive_votes=minimum) as s:
        # Leave the two contrasts unclassified; the next pair asks for
        # confirmation of below AND right on the same datum.
        s.judge("unsure")
        assert s.next()["kind"] == "confirmation"
        s.vote(0, "upvote", layout_state=state(120, 150))
        if minimum == 2:
            with pytest.raises(SpecUnavailableError, match="positive evidence"):
                s.apply()
            # Moving nodes without changing their qualitative order cannot
            # supply the second distinct example required by this threshold.
            s.vote(0, "upvote", layout_state=state(140, 170))
            assert s.spec.result["positive_votes"] == 1
            with pytest.raises(SpecUnavailableError, match="positive evidence"):
                s.apply()
            moved = state(120, 150)
            moved["positions"][2]["y"] = -200
            s.vote(0, "upvote", layout_state=moved)

        assert len(s.survivors) == 2
        assert all(c.positive_votes == minimum for c in s.survivors)
        checkpoint = s.done()
        assert checkpoint["status"] == "supported"
        assert checkpoint["positive_votes"] == minimum
        assert not s.spec.applied  # I'm done does not apply even a ready spec.
        spec = s.apply()
        program = emitted_spec(tree())
        assert spec.result["candidate_ids"] == [c.id for c in s.survivors]
        assert orientation_directions(program) == [["below"], ["right"]]
        assert emitted_spec(tree(), spec=spec) == program
        assert s.finish().to_registry() == program


def test_live_spec_excludes_unsupported_survivor_then_blocks_conflicting_combination(
    emitted_spec,
):
    with session() as s:
        question = s.next()["id"]
        s.vote(0, "upvote", layout_state=state(-120, 150))
        spec = s.apply()
        assert len(s.survivors) == 2
        assert [(c.positive_votes, c.negative_votes) for c in s.survivors] == [
            (1, 0),
            (0, 1),
        ]
        assert spec.result["candidate_ids"] == [s.candidates[0].id]
        before = emitted_spec(tree())
        assert before == s.candidates[0].program

        # Both programs now have support, but their conjunction excludes
        # both approved layouts. Neither candidate has been eliminated.
        s.vote(1, "upvote", layout_state=state(120, -150))
        assert len(s.survivors) == 2
        assert all(c.positive_votes == 1 for c in s.survivors)
        assert spec.status == "conflict"
        assert len(spec.result["conflicts"]) == 2
        assert orientation_directions(s.draft.to_registry()) == [
            ["below"],
            ["right"],
        ]  # Inspection only.
        with pytest.raises(SpecUnavailableError, match="judgments"):
            s.apply()
        with pytest.raises(SpecUnavailableError, match="judgments"):
            spec.snapshot()
        with pytest.raises(SpecUnavailableError, match="judgments"):
            emitted_spec(tree())
        with pytest.raises(SpecUnavailableError, match="judgments"):
            emitted_spec(tree(), spec=spec)

        s.reclassify(question, 1, "unsure")
        assert s.spec is spec and spec.applied
        assert spec.status == "supported"
        assert emitted_spec(tree()) == before


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

    # Exercise the real Hypothesis backend: the approved tree is satisfiable,
    # but a self-loop cannot be oriented to the right of itself.
    s.search = HypothesisSearch(st.just(cyclic))
    with pytest.raises(SpecUnavailableError, match="Generated data"):
        s.apply()
    assert not s.spec.applied
    assert s.spec.status == "conflict"
    assert any(example is cyclic for example in s.examples)


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

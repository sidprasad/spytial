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
    DEFAULT_REGISTRY,
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
    assert before == spec.to_source() + "\n"
    assert "spytial.orientation" in before and "LivingSpec" not in before
    assert "Parents above children" in before and "Presentation inferred" not in before
    assert "Requirement" not in spec.to_source(with_comments=False)
    accept_alignment(s)
    print(spec)
    after = capsys.readouterr().out
    assert after != before and "spytial.align" in after
    assert repr(spec).startswith("<LivingSpec")
    s.close()
    assert str(spec) == spec.to_source()


def test_provenance_tracks_accepted_prompts_and_survives_save_load(
    live_session, tmp_path
):
    s = live_session
    first = s.active_requirement
    spec = s.spec
    initial = spec.provenance
    (rule,) = initial
    assert rule["origin"] == "requirement"
    assert rule["rule"] in spec.to_registry()["constraints"]
    assert {source["requirement_id"] for source in rule["sources"]} == {first.id}
    assert all(
        source["prompt"] == first.prompt and source["revision"] == 1
        for source in rule["sources"]
    )
    pending = s.add_requirement("Align siblings")
    assert spec.provenance == initial  # Unaccepted interpretations have no provenance.
    s.judge(
        "left",
        layout_states=[
            state(-120, 150, other_x=120, other_y=150),
            state(-120, 150, other_x=-120, other_y=250),
        ],
    )
    assert pending.status == "accepted"
    assert {
        source["prompt"] for row in spec.provenance for source in row["sources"]
    } == {
        first.prompt,
        pending.prompt,
    }
    snapshot = spec.snapshot().to_source()
    path = tmp_path / "explained.json"
    s.save(path)
    with SuggestSession.load(Tree, path, search=FixedExamples()).wait() as restored:
        assert restored.spec.provenance == spec.provenance
        assert str(restored.spec) == snapshot
    s.reclassify(first.history[0]["id"], 0, "unsure")
    assert first.prompt not in str(spec)
    assert first.prompt in snapshot


def test_explicit_registry_keeps_presentation_separate_from_accepted_rules(tmp_path):
    with session(registry=DEFAULT_REGISTRY, proposer=Provider()) as s:
        base = s._poll()["question"]["sides"][0]["program"]
        assert base["constraints"] == [{"hideAtom": {"selector": "NoneType"}}]
        assert {"attribute": {"field": "value"}} in base["directives"]
        assert s.spec.status == "empty"

        s.add_requirement("Parents above children")
        s.vote(0, "upvote", layout_state=state(-120, 150, other_atoms=()))
        assert s.done()["status"] == "accepted"
        spec = s.apply()
        presentation = [
            r["rule"] for r in spec.provenance if r["origin"] == "presentation"
        ]
        assert presentation == base["constraints"] + base["directives"]
        path = tmp_path / "with-presentation.json"
        s.save(path)
        with SuggestSession.load(Tree, path, search=FixedExamples()).wait() as restored:
            assert restored.history == s.history
            assert restored.spec.provenance == spec.provenance


def test_shared_rule_keeps_both_prompt_sources(live_session):
    s = live_session
    s.proposer = Provider([proposal(["below"])])
    second = s.add_requirement("Keep each parent higher")
    s.judge("both", layout_states=[state(-120, 150), state(120, 150)])
    second.done()
    assert second.status == "accepted"
    rules = [row for row in s.spec.provenance if row["origin"] == "requirement"]
    assert len(rules) == 1
    assert {source["prompt"] for source in rules[0]["sources"]} == {
        "Parents above children",
        "Keep each parent higher",
    }


def test_each_operation_quotes_its_prompt_fragment_and_revision(tmp_path):
    prompt = "Left children below; right children below"
    operations = []
    for field, fragment in (
        ("left", "Left children below"),
        ("right", "right children below"),
    ):
        operations.append(
            {
                "kind": "orientation",
                "selector": f"{field} - (univ -> NoneType)",
                "directions": ["below"],
                "prompt_fragment": fragment,
            }
        )
    provider = Provider(
        [{"summary": "Each child below its parent", "operations": operations}]
    )
    with session(proposer=provider) as s:
        requirement = s.add_requirement(prompt)
        s.vote(0, "upvote", layout_state=state(-120, 150, other_x=120, other_y=150))
        requirement.done()
        sources = [row["sources"][0] for row in s.spec.provenance if row["sources"]]
        assert {tuple(source["prompt_fragments"]) for source in sources} == {
            ("Left children below",),
            ("right children below",),
        }
        assert "prompt_fragment" not in str(s.spec.to_registry())
        before = str(s.spec)
        requirement.revise(prompt + "; keep these orders")
        requirement.done()
        assert all(
            source["revision"] == 2
            for row in s.spec.provenance
            for source in row["sources"]
        )
        assert str(s.spec) != before
        path = tmp_path / "fragments.json"
        s.save(path)
        with SuggestSession.load(Tree, path, search=FixedExamples()).wait() as restored:
            assert restored.spec.provenance == s.spec.provenance


def test_invented_prompt_fragment_is_rejected():
    item = proposal(["below"])
    item["operations"][0]["prompt_fragment"] = "words the person did not write"
    with session(proposer=Provider([item])) as s:
        with pytest.raises(ValueError, match="quote the requested requirement"):
            s.add_requirement("Parents above children")
        assert not s.requirements


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

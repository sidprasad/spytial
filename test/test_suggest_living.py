"""Accepted properties compose; judgments remain local when the spec is refined."""

from copy import deepcopy
import json

import pytest

from spytial.suggest import suggest, SuggestSession, FixedExamples, SpecUnavailableError
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


def alignment(direction):
    return {
        "summary": f"Siblings align {direction}",
        "operations": [
            {
                "kind": "align",
                "selector": "(~left.right) - (NoneType -> univ) - (univ -> NoneType)",
                "direction": direction,
            }
        ],
    }


def refined_session(**kwargs):
    return session(
        proposer=Provider(
            [proposal(["below"]), proposal(["right"])],
            [alignment("horizontal"), alignment("vertical")],
            [proposal(["below", "left"])],
        ),
        **kwargs,
    )


def accept_alignment(s):
    prop = s.add_property("Align siblings")
    s.judge(
        "left",
        layout_states=[
            state(-120, 150, other_x=120, other_y=150),
            state(-120, 150, other_x=-120, other_y=250),
        ],
    )
    assert prop.status == "accepted"
    return prop


def test_additive_refinement_retains_background_and_local_positive_evidence():
    with refined_session() as s:
        first = accept_below(s)
        first_history = deepcopy(first.history)
        old = s.spec.to_registry()
        second = s.add_property("Align siblings")
        q = s.next()
        assert q["property_id"] == second.id
        assert q["context"] == old
        for side in q["sides"]:
            assert all(c in side["program"]["constraints"] for c in old["constraints"])
        # An unresolved new property contributes no rules to the live spec.
        assert s.spec.to_registry() == old
        s.judge(
            "left",
            layout_states=[
                state(-120, 150, other_x=120, other_y=150),
                state(-120, 150, other_x=-120, other_y=250),
            ],
        )
        assert first.status == second.status == "accepted"
        assert [
            (c["positive_votes"], c["negative_votes"]) for c in first.candidates
        ] == [(1, 0), (0, 2)]
        assert first.history == first_history
        combined = s.spec.to_registry()
        assert any("align" in c for c in combined["constraints"])
        # The first upvote had unaligned siblings. It remains valid evidence for
        # the first property, although the new whole spec excludes that picture.
        observation = s._history.effective(first.id)[0][0]["observations"][0]
        assert not s._checks.memberships(q["datum"], [combined], observation)[0]
        assert s.spec.status == "supported"
        assert s.history[-1]["context"] == old


def test_revision_replaces_one_property_and_replays_its_enduring_history():
    with refined_session() as s:
        first = accept_below(s)
        second = accept_alignment(s)
        handle = s.apply()
        history = deepcopy(s.history)
        first.revise("Left children below and left of their parent")
        assert s.spec is handle and second.status == "accepted"
        assert first.status == "ready"
        # The old definition is withdrawn while this property is edited.
        assert not any("orientation" in c for c in handle.to_registry()["constraints"])
        q = s.next()
        assert q["property_revision"] == 2 and q["property_id"] == first.id
        assert any("align" in c for c in q["context"]["constraints"])
        assert len(first.candidates) == 1 and first.candidates[0]["positive_votes"] == 1
        assert first.history == history[:1]
        checkpoint = first.done()
        assert checkpoint["status"] == "accepted"
        program = handle.to_registry()
        assert any(
            c.get("orientation", {}).get("directions") == ["below", "left"]
            for c in program["constraints"]
        )
        assert not any(
            c.get("orientation", {}).get("directions") == ["below"]
            for c in program["constraints"]
        )
        assert any("align" in c for c in program["constraints"])
        assert s.history == history
        assert "Parents above children" in s.proposer.prompts[-1]
        assert "Property judgment history" in s.proposer.prompts[-1]
        assert (
            "Align siblings" not in s.proposer.prompts[-1]
        )  # Its program is fixed context.


def test_history_correction_withdraws_only_affected_property():
    with refined_session() as s:
        first = accept_below(s)
        second = accept_alignment(s)
        spec = s.apply()
        s.reclassify(first.history[0]["id"], 0, "unsure")
        assert first.status == "draft"
        assert second.status == "accepted"
        assert s.active_property.id == first.id
        assert spec.result["property_ids"] == [second.id]
        s.reclassify(first.history[0]["id"], 0, "upvote")
        first.done()
        assert first.status == "accepted"
        assert len(spec.result["property_ids"]) == 2


def test_same_arrangement_counts_separately_for_different_properties():
    with session(proposer=Provider()) as s:
        first = accept_below(s)
        second = s.add_property("Keep the left branch below")
        s.vote(0, "upvote", layout_state=state(-120, 150))
        assert second.candidates[0]["positive_votes"] == 1
        assert first.candidates[0]["positive_votes"] == 1
        assert len(s._history.effective()) == 3  # Two earlier ratings plus this one.


def test_accept_excludes_unreviewed_survivors():
    with session(proposer=Provider()) as s:
        prop = s.add_property("Parents above children")
        s.vote(0, "upvote", layout_state=state(-120, 150))
        assert len(s.survivors) == 2
        prop.accept()
        assert prop.status == "accepted"
        assert s.spec.to_registry() == s.candidates[0].program
        assert s.candidates[1].positive_votes == 0


def test_classification_cannot_be_erased_by_reprompting():
    provider = Provider(
        [proposal(["below"]), proposal(["right"])], [proposal(["above"])]
    )
    with session(proposer=provider) as s:
        prop = accept_below(s)
        prop.revise("Actually above")
        assert prop.candidates[0]["negative_votes"] == 2
        assert prop.status == "empty"
        assert len(prop.history) == 1
        with pytest.raises(SpecUnavailableError):
            prop.accept()


def test_saved_session_retains_property_versions_context_and_votes(tmp_path):
    with refined_session() as s:
        first = accept_below(s)
        second = accept_alignment(s)
        first.revise("Left children below and left")
        first.done()
        path = tmp_path / "spec.json"
        s.save(path)
        before = json.loads(path.read_text())
        assert before["format_version"] == 2
        assert (
            before["properties"][0]["revisions"][0]["prompt"]
            == "Parents above children"
        )

        def no_model(*args, **kwargs):
            raise AssertionError("Loading called the model")

        with SuggestSession.load(
            Tree, path, proposer=no_model, search=FixedExamples()
        ).wait() as loaded:
            assert loaded.history == s.history and not loaded.spec.applied
            assert loaded.spec.to_registry() == s.spec.to_registry()
            loaded.save(path)
            assert json.loads(path.read_text()) == before
            restored = loaded.properties[1]
            restored.resume()
            assert loaded.active_property.id == second.id


def test_partial_votes_and_data_only_sessions_roundtrip(tmp_path):
    with session(proposer=Provider()) as s:
        path = tmp_path / "spec.json"
        s.save(path)
        with SuggestSession.load(Tree, path, search=FixedExamples()).wait() as loaded:
            assert loaded._poll()["status"] == "idle" and not loaded.properties
        p = s.add_property("Parents above children")
        s.vote(1, "upvote", layout_state=state(120, -150))
        s.save(path)
        with SuggestSession.load(Tree, path, search=FixedExamples()).wait() as loaded:
            assert loaded.current["votes"] == [None, "upvote"]
            assert loaded.current["property_id"] == p.id
            loaded.judge("left", layout_states=[state(-120, 150), state(120, -150)])
            assert loaded.active_property.status == "accepted"


def test_legacy_save_is_rejected_explicitly(tmp_path):
    path = tmp_path / "old.json"
    path.write_text('{"format_version":1}')
    with pytest.raises(ValueError, match="version 2"):
        SuggestSession.load(Tree, path)


@pytest.mark.parametrize("minimum", [1, 2])
def test_done_combines_all_supported_survivors_with_shared_positive_evidence(minimum):
    with session(proposer=Provider(), min_positive_votes=minimum) as s:
        prop = s.add_property("Parents above children")
        s.judge("unsure")
        assert s.next()["kind"] == "confirmation"
        # This arrangement supports both interpretations of the requested property.
        s.vote(0, "upvote", layout_state=state(120, 150))
        if minimum == 2:
            assert s.done()["status"] == "draft"
            prop.resume()
            s.vote(0, "upvote", layout_state=state(140, 170))
            assert all(c.positive_votes == 1 for c in s.candidates)
            s.vote(0, "upvote", layout_state=state(120, 150, other_y=-200))
        checkpoint = s.done()
        assert checkpoint["status"] == "accepted"
        assert len(s.survivors) == 2
        assert checkpoint["accepted_ids"] == [c.id for c in s.candidates]
        directions = [
            c["orientation"]["directions"]
            for c in s.spec.to_registry()["constraints"]
            if "orientation" in c
        ]
        assert directions == [["below"], ["right"]]
        assert not s.spec.applied  # Completing the round does not bind the class.


def test_done_does_not_accept_a_combination_that_rejects_its_own_upvotes():
    with session(proposer=Provider()) as s:
        prop = s.add_property("Parents above children")
        s.judge("both", layout_states=[state(-120, 150), state(120, -150)])
        assert all(c.positive_votes == 1 for c in s.candidates)
        checkpoint = s.done()
        assert checkpoint["status"] == "conflict"
        assert not checkpoint["accepted_ids"]
        assert prop.status == "conflict" and s.spec.status == "empty"


def test_eliminated_member_leaves_an_accepted_combination():
    with session(proposer=Provider()) as s:
        prop = s.add_property("Parents above children")
        s.judge("unsure")
        s.next()
        s.vote(0, "upvote", layout_state=state(120, 150))
        s.done()
        assert len(prop.result["accepted_ids"]) == 2
        spec = s.spec
        prop.resume()
        # The combined definition already excludes this rejected arrangement.
        # One component permitting it need not invalidate the whole definition.
        s.vote(1, "downvote", layout_state=state(120, -150))
        assert len(prop.result["accepted_ids"]) == 2
        s.next()
        s.vote(0, "downvote", layout_state=state(120, -150, other_y=-200))
        assert s.candidates[1].eliminated
        assert prop.result["accepted_ids"] == [s.candidates[0].id]
        directions = [
            c["orientation"]["directions"]
            for c in spec.to_registry()["constraints"]
            if "orientation" in c
        ]
        assert directions == [["below"]]

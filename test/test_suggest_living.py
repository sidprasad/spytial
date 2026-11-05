"""PICK evidence, elimination, conjunction, and resumable checkpoints."""

import json
import pytest

from spytial.suggest import (
    suggest,
    SuggestSession,
    FixedExamples,
    FixedProposals,
    SpecUnavailableError,
)
from test_suggest_session import Tree, tree, proposal, Provider


def state(x, y):
    return {
        "positions": [
            {"id": "n0", "x": 0, "y": 0},
            {"id": "n1", "x": x, "y": y},
            {"id": "n2", "x": 300, "y": 250},
        ]
    }


def session(**kwargs):
    return suggest(
        tree(),
        search=FixedExamples(),
        proposer=FixedProposals(
            [
                proposal(["below"]),
                proposal(["right"]),
            ]
        ),
        **kwargs,
    ).wait()


def test_all_candidates_scored_asymmetrically_and_eliminated_rules_removed():
    with session() as s:
        question = s.next()
        # Below-only is rejected; right-only is approved. Both observations
        # count against below, while correctly excluding below earns no support.
        s.vote(0, "downvote", layout_state=state(-120, 150))
        assert [(c.positive_votes, c.negative_votes) for c in s.candidates] == [
            (0, 1),
            (0, 0),
        ]
        assert not any(c.eliminated for c in s.candidates)
        s.vote(1, "upvote", layout_state=state(120, -150))
        assert [(c.positive_votes, c.negative_votes) for c in s.candidates] == [
            (0, 2),
            (1, 0),
        ]
        assert s.candidates[0].eliminated
        assert s.draft.to_registry() == s.candidates[1].program
        assert s.finish().to_registry() == s.candidates[1].program
        assert s.paused and s.checkpoints[-1]["status"] == "supported"
        assert s.history[0]["layout_states"][1] == state(120, -150)
        assert s.history[0]["memberships"][0] == {
            s.candidates[0].id: True,
            s.candidates[1].id: False,
        }
        assert s.checkpoints[-1]["history"][0]["id"] == question["id"]


def test_reclassification_replays_and_revives_without_changing_old_checkpoint():
    with session() as s:
        question = s.next()
        s.judge("right", layout_states=[state(-120, 150), state(120, -150)])
        checkpoint = s.done()
        s.reclassify(question["id"], 0, "unsure")
        assert not s.candidates[0].eliminated
        assert s.candidates[0].negative_votes == 1
        assert s.checkpoints[-1] == checkpoint
        assert s.history[0]["changes"][-1]["from"] == "downvote"
        s.reclassify(question["id"], 1, "downvote")
        assert s.candidates[1].positive_votes == 0


def test_rejecting_everything_does_not_positively_support_remaining_candidate():
    with session(elimination_threshold=1) as s:
        s.vote(0, "downvote", layout_state=state(-120, 150))
        s.vote(1, "unsure", layout_state=state(120, -150))
        assert len(s.survivors) == 1
        assert s.survivors[0].positive_votes == 0
        assert s.next()["kind"] == "confirmation"
        with pytest.raises(ValueError, match="positive evidence"):
            s.finish()
        s.resume()
        assert s.next()["kind"] == "confirmation"


def test_two_supported_candidates_need_shared_positive_evidence_for_combination():
    with session(elimination_threshold=3) as s:
        s.judge("both", layout_states=[state(-120, 150), state(120, -150)])
        assert all(c.positive_votes == 1 for c in s.candidates)
        result = s.done()
        assert result["status"] == "conflict"
        assert result["positive_votes"] == 0
        assert len(result["conflicts"]) == 2
        assert s._poll()["status"] == "paused"


def test_common_approved_layout_supports_combination_of_complementary_rules():
    with session() as s:
        # Generate a confirmation of the conjunction instead of either directed
        # difference, then approve a shared layout.
        s.judge("unsure")
        q = s.next()
        assert q["kind"] == "confirmation"
        s.vote(0, "upvote", layout_state=state(120, 150))
        assert all(c.positive_votes == 1 for c in s.candidates)
        result = s.done()
        assert result["status"] == "supported"
        assert result["positive_votes"] == 1
        directions = [
            c["orientation"]["directions"]
            for c in result["program"]["constraints"]
            if "orientation" in c
        ]
        assert ["below"] in directions and ["right"] in directions


def test_opposing_survivors_are_not_silently_combined_into_a_usable_spec():
    with suggest(
        tree(),
        proposer=FixedProposals([proposal(["below"]), proposal(["above"])]),
        search=FixedExamples(),
    ).wait() as s:
        with pytest.raises(ValueError, match="remaining rules conflict"):
            _ = s.draft
        with pytest.raises(SpecUnavailableError, match="remaining rules conflict"):
            s.apply()
        assert s.done()["status"] == "conflict"


def test_zero_survivors_can_be_saved_but_not_exported_as_a_spec():
    with session(elimination_threshold=1) as s:
        s.judge("neither", layout_states=[state(-120, 150), state(120, -150)])
        assert not s.survivors
        assert s.next() is None
        with pytest.raises(SpecUnavailableError, match="No candidates remain"):
            s.apply()
        assert not s.spec.applied
        with pytest.raises(ValueError, match="No candidates remain"):
            s.finish()
        assert s.checkpoints[-1]["program"] is None


def test_generated_conflict_blocks_finish_after_positive_support():
    with session() as s:
        s.judge("right", layout_states=[state(-120, 150), state(120, -150)])
        cyclic = tree()
        cyclic.left = cyclic

        class Search:
            def find(self, cls, predicate, *, max_examples):
                assert predicate(cyclic)
                return cyclic

        s.search = Search()
        with pytest.raises(ValueError, match="Generated data"):
            s.finish()
        assert s.checkpoints[-1]["status"] == "conflict"


def test_repeated_click_or_qualitatively_identical_layout_counts_once():
    with session() as s:
        s.vote(0, "upvote", layout_state=state(-120, 150))
        s.vote(0, "upvote", layout_state=state(-140, 170))
        assert s.candidates[0].positive_votes == 1
        assert s.candidates[1].negative_votes == 1
        s.vote(0, "unsure", layout_state=state(-140, 170))
        assert all(c.negative_votes == c.positive_votes == 0 for c in s.candidates)


def test_invalid_or_missing_layout_cannot_eliminate_candidates():
    with session() as s:
        with pytest.raises(ValueError, match="layout_state"):
            s.vote(0, "upvote")
        with pytest.raises(ValueError, match="violates"):
            s.vote(0, "downvote", layout_state=state(120, -150))
        assert not s.history
        assert all(c.negative_votes == 0 for c in s.candidates)


def test_new_proposals_replay_existing_layout_evidence():
    with suggest(
        tree(), proposer=Provider(), search=FixedExamples(), elimination_threshold=1
    ).wait() as s:
        s.judge("right", layout_states=[state(120, 150), state(-120, 150)])
        s.proposer = lambda prompt, schema: {
            "rules": [],
            "programs": [proposal(["above"])],
        }
        s.revise("Consider putting children above")
        assert s.candidates[-1].eliminated
        assert s.candidates[-1].negative_votes == 1
        assert s.candidates[-1].id not in s.spec.result["candidate_ids"]


def test_checkpoint_export_keeps_evidence_and_thresholds(tmp_path):
    with session(min_positive_votes=2) as s:
        s.judge("right", layout_states=[state(-120, 150), state(120, -150)])
        s.done()
        path = tmp_path / "spec.json"
        s.save(path)
        saved = json.loads(path.read_text())
        assert saved["settings"]["min_positive_votes"] == 2
        assert saved["history"][0]["votes"] == ["downvote", "upvote"]
        assert saved["history"][0]["layout_states"]
        assert saved["candidates"][0]["eliminated"]
        assert saved["datums"]
        assert saved["checkpoints"][-1]["status"] == "draft"

        def no_model(*args, **kwargs):
            pytest.fail("Restoring history must not call the LLM")

        with SuggestSession.load(
            Tree, path, proposer=no_model, search=FixedExamples()
        ).wait() as restored:
            assert restored.paused
            assert restored.history == s.history
            assert restored.candidates[0].eliminated
            assert restored.candidates[1].positive_votes == 1
            restored.resume()
            assert restored.next()["kind"] == "confirmation"
            restored.reclassify(restored.history[0]["id"], 0, "unsure")
            assert not restored.candidates[0].eliminated


def test_exploring_and_voting_on_a_new_arrangement_retains_previous_evidence():
    with session() as s:
        s.vote(0, "upvote", layout_state=state(-120, 150))
        # Move the unrelated third node above the others: a new qualitative
        # arrangement, while the witness constraint remains satisfied.
        moved = state(-120, 150)
        moved["positions"][2]["y"] = -200
        s.vote(0, "upvote", layout_state=moved)
        assert len(s.history) == 2
        assert s.history[0]["layout_states"][0] == state(-120, 150)
        assert s.history[1]["layout_states"][0] == moved
        assert s.candidates[0].positive_votes == 2


def test_per_batch_candidate_limit_includes_repair_attempt():
    calls = []

    def provider(prompt, *, schema):
        calls.append(prompt)
        if len(calls) == 1:
            return {"rules": [], "programs": [proposal(["below"]), proposal(["bogus"])]}
        return {
            "rules": [],
            "programs": [
                proposal(["above"]),
                proposal(["right"]),
                proposal(["left"]),
                proposal(["below", "left"]),
            ],
        }

    with suggest(
        tree(), proposer=provider, search=FixedExamples(), max_candidates=3
    ).wait() as s:
        assert len(calls) == 2
        assert len(s.candidates) == 3

"""Property sessions use real core checks and deterministic proposal responses."""

from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Optional

import pytest
from hypothesis import strategies as st

from spytial.suggest import (
    suggest,
    SuggestSession,
    FixedExamples,
    FixedProposals,
    HypothesisSearch,
    SpecUnavailableError,
)


@dataclass
class Tree:
    value: int = 0
    left: Optional["Tree"] = None
    right: Optional["Tree"] = None


@pytest.fixture(autouse=True)
def clean_tree_binding():
    from spytial.annotations import LIVE_SPEC_ATTR

    previous = Tree.__dict__.get(LIVE_SPEC_ATTR)
    registry = deepcopy(Tree.__dict__.get("__spytial_registry__"))
    yield
    for name, value in ((LIVE_SPEC_ATTR, previous), ("__spytial_registry__", registry)):
        if value is None:
            if name in Tree.__dict__:
                delattr(Tree, name)
        else:
            setattr(Tree, name, value)


def tree():
    return Tree(8, Tree(3), Tree(10))


def proposal(directions, summary="Property interpretation"):
    return {
        "summary": summary,
        "operations": [
            {
                "kind": "orientation",
                "selector": "left - (univ -> NoneType)",
                "directions": directions,
            }
        ],
    }


class Provider:
    def __init__(self, *batches):
        self.prompts = []
        self.batches = batches or ([proposal(["below"]), proposal(["right"])],)

    def __call__(self, prompt, *, schema):
        self.prompts.append(prompt)
        return {
            "programs": deepcopy(
                self.batches[min(len(self.prompts) - 1, len(self.batches) - 1)]
            )
        }


def session(**kwargs):
    return suggest(tree(), search=FixedExamples(), **kwargs).wait()


def state(x, y, *, other_x=300, other_y=250):
    return {
        "positions": [
            {"id": "n0", "x": 0, "y": 0},
            {"id": "n1", "x": x, "y": y},
            {"id": "n2", "x": other_x, "y": other_y},
        ]
    }


def accept_below(s):
    prop = s.add_property("Parents above children")
    s.judge("left", layout_states=[state(-120, 150), state(120, -150)])
    assert prop.status == "accepted"
    return prop


def test_startup_prepares_data_without_model_or_class_binding():
    provider = Provider()
    with session(proposer=provider) as s:
        assert not provider.prompts
        assert not s.properties and not s.history
        assert s._poll()["status"] == "idle"
        assert s._poll()["question"]["kind"] == "preview"
        assert len(s._poll()["question"]["sides"]) == 1
        with pytest.raises(SpecUnavailableError, match="Accept a property"):
            s.apply()
        prop = s.add_property("Parents above children")
        assert len(provider.prompts) == 1
        assert prop.id == s.active_property.id
        assert s.next()["property_id"] == prop.id
        assert not s.spec.applied


def test_default_combines_real_hypothesis_with_lazy_model(monkeypatch):
    provider = Provider()
    derived = []

    def from_type(cls):
        derived.append(cls)
        return st.just(tree())

    monkeypatch.setattr(st, "from_type", from_type)
    with suggest(Tree, proposer=provider, max_examples=3).wait() as s:
        assert derived and not provider.prompts
        assert isinstance(s.search, HypothesisSearch)
        s.add_property("Parents above children")
        assert len(derived) >= 3 and provider.prompts
        assert s.next() is not None


@pytest.mark.parametrize(
    "first,second,expected,status",
    [
        ("upvote", "upvote", [(1, 1), (1, 1)], "conflict"),
        ("upvote", "downvote", [(1, 0), (0, 2)], "accepted"),
        ("upvote", "unsure", [(1, 0), (0, 1)], "ready"),
        ("downvote", "upvote", [(0, 2), (1, 0)], "accepted"),
        ("downvote", "downvote", [(0, 1), (0, 1)], "draft"),
        ("downvote", "unsure", [(0, 1), (0, 0)], "draft"),
        ("unsure", "upvote", [(0, 1), (1, 0)], "ready"),
        ("unsure", "downvote", [(0, 0), (0, 1)], "draft"),
        ("unsure", "unsure", [(0, 0), (0, 0)], "draft"),
    ],
)
def test_vote_matrix_and_acceptance(first, second, expected, status):
    with session(proposer=Provider()) as s:
        prop = s.add_property("Parents above children")
        s.vote(0, first, layout_state=state(-120, 150))
        s.vote(1, second, layout_state=state(120, -150))
        assert [(c.positive_votes, c.negative_votes) for c in s.candidates] == expected
        assert prop.status == status
        assert s.paused == (status == "accepted")
        assert s.history[0]["property_id"] == prop.id
        assert s.history[0]["prompt"] == prop.prompt
        assert s.history[0]["context"]["directives"]


def test_done_keeps_multiple_or_zero_survivors_unfinished():
    with session(proposer=Provider(), elimination_threshold=1) as s:
        prop = s.add_property("Parents above children")
        result = s.done()
        assert result["status"] == "draft" and s.paused
        assert len(s.survivors) == 2 and s.spec.status == "empty"
        prop.resume()
        s.judge("neither", layout_states=[state(-120, 150), state(120, -150)])
        result = s.done()
        assert result["status"] == "empty" and prop.status == "empty"
        assert s.spec.status == "empty"
        s.reclassify(s.history[0]["id"], 0, "upvote")
        prop.done()
        assert prop.status == "accepted"


def test_a_single_survivor_still_needs_positive_evidence():
    with session(proposer=Provider(), elimination_threshold=1) as s:
        prop = s.add_property("Parents above children")
        s.judge("unsure")
        s.resume()
        # Rate a fresh confirmation, rejecting its displayed instance.
        q = s.next()
        assert q is not None
        # A direct correction demonstrates that exclusion alone gives no support.
        s.vote(0, "downvote", layout_state=state(-120, 150))
        assert len(s.survivors) == 1
        assert all(c.positive_votes == 0 for c in s.candidates)
        assert s.done()["status"] == "draft"
        with pytest.raises(SpecUnavailableError, match="positive evidence"):
            prop.accept()


@pytest.mark.parametrize("previous_side", [None, 0, 1])
def test_batch_updates_both_votes_before_advancing(previous_side):
    with session(proposer=Provider()) as s:
        prop = s.add_property("Parents above children")
        q = s.next()
        states = [state(-120, 150), state(120, -150)]
        if previous_side is not None:
            s.vote(
                previous_side,
                "downvote" if previous_side == 0 else "upvote",
                layout_state=states[previous_side],
            )
        record = s.judge(
            "left", "Below is intended", question_id=q["id"], layout_states=states
        )
        assert record["votes"] == ["upvote", "downvote"] and record["complete"]
        assert record["explanation"] == "Below is intended"
        assert prop.status == "accepted" and len(s.history) == 1
        record["votes"][0] = "unsure"
        assert s.history[0]["votes"][0] == "upvote"


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("invalid", ["coordinates", "program", "nodes"])
def test_invalid_second_layout_does_not_change_evidence(partial, invalid, tmp_path):
    with session(proposer=Provider()) as s:
        s.add_property("Parents above children")
        states = [state(-120, 150), state(120, -150)]
        if partial:
            s.vote(0, "downvote", layout_state=states[0])
        path = tmp_path / "session.json"
        s.save(path)
        before = path.read_text()
        if invalid == "coordinates":
            states[1]["positions"][0]["x"] = "bad"
        elif invalid == "program":
            states[1] = states[0]
        else:
            states[1]["positions"].pop()
        with pytest.raises(ValueError):
            s.judge("left", layout_states=states)
        s.save(path)
        assert path.read_text() == before


def test_positive_threshold_and_distinct_dragged_arrangements():
    with session(proposer=Provider(), min_positive_votes=2) as s:
        prop = s.add_property("Parents above children")
        s.vote(0, "upvote", layout_state=state(-120, 150))
        s.vote(0, "upvote", layout_state=state(-140, 170))
        assert s.candidates[0].positive_votes == 1
        s.vote(0, "upvote", layout_state=state(-120, 150, other_y=-200))
        s.vote(1, "downvote", layout_state=state(120, -150))
        assert prop.status == "accepted"
        assert s.candidates[0].positive_votes == 2
        assert len(s.history) == 2


def test_property_proposal_failure_leaves_previous_round_usable(tmp_path):
    provider = Provider()
    with session(proposer=provider) as s:
        prop = accept_below(s)
        path = tmp_path / "before.json"
        s.save(path)
        before = path.read_text()

        def broken(prompt, *, schema):
            raise RuntimeError("model unavailable")

        s.proposer = broken
        with pytest.raises(RuntimeError, match="unavailable"):
            s.add_property("Align siblings")
        s.save(path)
        assert path.read_text() == before
        with pytest.raises(RuntimeError, match="unavailable"):
            prop.revise("Below and left")
        s.save(path)
        assert path.read_text() == before


def test_bad_whole_interpretation_is_repaired():
    bad = proposal(["below"])
    bad["operations"].append(proposal(["above"])["operations"][0])
    provider = Provider([bad], [proposal(["below"]), proposal(["right"])])
    with session(proposer=provider) as s:
        s.add_property("Parents above children")
        assert len(provider.prompts) == 2
        assert "conflict" in provider.prompts[1]
        assert len(s.candidates) == 2


def test_additional_data_and_stale_question_do_not_lose_evidence():
    with session(proposer=Provider()) as s:
        prop = s.add_property("Parents above children")
        q = s.next()
        s.vote(0, "upvote", layout_state=state(-120, 150))
        history = deepcopy(s.history)
        extra = Tree(9, Tree(2), Tree(7))
        s.add_examples([extra])
        assert s.history == history and prop.id == s.active_property.id
        assert extra in s.examples
        with pytest.raises(ValueError, match="no longer current"):
            s.vote(1, "downvote", question_id=q["id"], layout_state=state(120, -150))
        assert s.history == history

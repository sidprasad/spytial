"""Behavioral tests for the critique loop, using the real core comparison bridge."""

from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pathlib import Path
import hashlib

import pytest
from hypothesis import strategies as st

from spytial.suggest import (
    suggest as start_session,
    suggest_draft,
    SuggestSession,
    SpecDraft,
    Suggestion,
    FixedExamples,
    FixedProposals,
    HypothesisSearch,
)
from spytial.suggest._session import ProgramCandidate


def suggest(*args, **kwargs):
    """Most behavioral tests need the prepared session; startup is tested separately."""
    return start_session(*args, **kwargs).wait()


@dataclass
class Tree:
    value: int = 0
    left: Optional["Tree"] = None
    right: Optional["Tree"] = None


def tree():
    return Tree(8, Tree(3), Tree(10))


def test_comparison_bundle_has_matching_provenance():
    from spytial.core_assets import SPYTIAL_CORE_VERSION

    root = Path(__file__).resolve().parents[1] / "spytial/suggest/_vendor"
    metadata = json.loads((root / "comparison-build.json").read_text())
    assert metadata["spytialCoreVersion"] == SPYTIAL_CORE_VERSION
    assert (
        metadata["sha256"]
        == hashlib.sha256((root / metadata["artifact"]).read_bytes()).hexdigest()
    )


def proposal(directions, summary="Children below their parent"):
    return {
        "summary": summary,
        "operations": [
            {
                "kind": "orientation",
                "selector": "left - (univ -> NoneType)",
                "directions": directions,
            },
        ],
    }


class Provider:
    def __init__(self):
        self.prompts = []

    def __call__(self, prompt, *, schema):
        self.prompts.append(prompt)
        return {
            "rules": [{"text": "Keep children below", "origin": "user"}],
            "programs": [
                proposal(["below"]),
                proposal(["below", "left"], "Left children below and left"),
            ],
        }


def test_draft_is_explicit_and_session_does_not_decorate():
    draft = suggest_draft(tree())
    session = suggest(tree(), search=FixedExamples(), proposer=Provider())
    assert isinstance(draft, SpecDraft)
    assert isinstance(session, SuggestSession)
    question = session.next()
    assert question is not None
    assert any(s["excludes"] is not None for s in question["sides"])
    assert question["datum"]["atoms"]
    assert suggest_draft(tree()).to_registry() == draft.to_registry()


def test_whole_programs_and_one_sided_difference():
    session = suggest(tree(), search=FixedExamples(), proposer=Provider())
    question = session.next()
    assert [s["excludes"] for s in question["sides"]] == ["b", None]
    # Common presentation stays fixed, including the hidden None atom.
    assert (
        question["sides"][0]["program"]["directives"]
        == question["sides"][1]["program"]["directives"]
    )
    assert any(
        row.get("orientation", {}).get("hold") == "never"
        for row in question["sides"][0]["program"]["constraints"]
    )
    assert (
        session.rules[0]["origin"] == "suggested"
    )  # model cannot invent a user request


def test_judgments_preserve_evidence_without_eliminating_candidates():
    session = suggest(tree(), search=FixedExamples(), proposer=Provider())
    question = session.next()
    count = len(session.candidates)
    record = session.judge(
        "right", "Keep the entire branch on the left", question_id=question["id"]
    )
    assert record["datum"] == question["datum"]
    assert record["programs"] == question["programs"]
    assert session.active_id == question["candidate_ids"][1]
    assert len(session.candidates) == count
    with pytest.raises(ValueError, match="no longer current"):
        session.judge("both", question_id=question["id"])
    assert session.next() is None


def test_revisions_carry_judgments_forward():
    provider = Provider()
    session = suggest(tree(), search=FixedExamples(), proposer=provider)
    session.next()
    session.judge("neither", "The entire subtree must stay left")
    original = deepcopy(session.history)
    session.revise("The entire subtree must stay left")
    assert session.history == original
    assert '"choice": "neither"' in provider.prompts[-1]
    assert "The entire subtree must stay left" in provider.prompts[-1]


def test_judging_one_example_does_not_suppress_other_data_for_the_same_programs():
    session = suggest(
        Tree,
        search=FixedExamples(),
        proposer=Provider(),
        examples=[tree(), Tree(8, Tree(3, Tree(1)), Tree(10))],
    )
    first = session.next()
    session.judge("both")
    second = session.next()
    assert second is not None
    assert set(first["candidate_ids"]) == set(second["candidate_ids"])
    assert first["datum"] != second["datum"]


def test_contradictory_program_is_rejected_as_a_whole_and_repaired():
    calls = []

    def provider(prompt, *, schema):
        calls.append(prompt)
        if len(calls) == 1:
            bad = proposal(["left"])
            bad["operations"].append(proposal(["right"])["operations"][0])
            return {"rules": [], "programs": [bad]}
        return {
            "rules": [],
            "programs": [proposal(["below"]), proposal(["below", "left"])],
        }

    session = suggest(tree(), search=FixedExamples(), proposer=provider)
    assert len(calls) == 2
    assert "conflicting constraints" in calls[1]
    assert len(session.candidates) == 2


def test_search_varies_data_when_fixed_example_does_not_distinguish():
    session = suggest(
        Tree(),
        search=FixedExamples(),
        proposer=FixedProposals([{"summary": "Free arrangement", "operations": []}]),
    )
    # No left edges in the initial leaf. The outer search must find one.
    session.candidates = [
        ProgramCandidate("a", "Free", SpecDraft(Tree, [])),
        ProgramCandidate(
            "b",
            "Child below",
            SpecDraft(
                Tree,
                [
                    Suggestion(
                        "orientation",
                        {
                            "selector": "left - (univ -> NoneType)",
                            "directions": ["below"],
                        },
                        "high",
                    )
                ],
            ),
        ),
    ]
    session.active_id = "a"
    session.search = HypothesisSearch(
        st.integers(0, 3).map(lambda n: Tree(n, Tree(n + 1)) if n else Tree())
    )
    session.max_examples = 10
    question = session.next()
    assert question is not None
    assert any(
        r["name"] == "left" and r["tuples"] for r in question["datum"]["relations"]
    )
    assert question["sides"][0]["excludes"] == "b"


def test_bad_inputs_are_explicit():
    with pytest.raises(ValueError, match="list"):
        suggest(tree(), rules="Align children")
    with pytest.raises(ValueError, match="not both"):
        suggest(tree(), proposer=Provider(), search=FixedExamples(), strategy="auto")
    with pytest.raises(TypeError, match="initial"):
        suggest(tree(), proposer=Provider(), search=False)
    with pytest.raises(ValueError, match="Supply examples"):
        suggest(Tree, proposer=Provider(), search=FixedExamples())


def test_generated_data_can_reject_a_program_that_passes_fixed_examples():
    session = suggest(tree(), search=FixedExamples(), proposer=Provider())
    cyclic = Tree(1)
    cyclic.left = cyclic
    session.search = HypothesisSearch(st.just(cyclic))
    before = len(session.candidates)
    with pytest.raises(ValueError, match="Generated data exposed"):
        session._add(
            "Every left child below",
            [
                Suggestion(
                    "orientation",
                    {"selector": "left - (univ -> NoneType)", "directions": ["above"]},
                    "high",
                )
            ],
        )
    assert len(session.candidates) == before


def test_finish_returns_copy_without_applying_it():
    session = suggest(tree(), search=FixedExamples(), proposer=Provider())
    original = session.draft.to_registry()
    result = session.finish()
    result.suggestions.clear()
    assert session.draft.to_registry() == original
    if len(session.candidates) > 1:
        chosen = session.candidates[1]
        session.finish(chosen.id)
        assert session.finish().to_registry() == chosen.program


def test_server_gates_mutations_and_rejects_stale_questions():
    with suggest(tree(), search=FixedExamples(), proposer=Provider()) as session:
        url = session._url()
        state = json.load(urlopen(url + "state"))
        question = state["question"]
        payload = json.dumps(
            {"question_id": question["id"], "side": 0, "value": "upvote"}
        ).encode()
        with pytest.raises(HTTPError) as exc:
            urlopen(
                Request(
                    url + "vote",
                    data=payload,
                    headers={"Origin": "https://example.com"},
                )
            )
        assert exc.value.code == 403
        origin = url.split("/" + session._server.token)[0]
        headers = {"Origin": origin, "Content-Type": "application/json"}
        assert json.load(urlopen(Request(url + "vote", data=payload, headers=headers)))[
            "recorded"
        ]
        assert session.history[0]["votes"] == ["upvote", None]
        payload = json.dumps(
            {"question_id": question["id"], "side": 1, "value": "unsure"}
        ).encode()
        assert json.load(urlopen(Request(url + "vote", data=payload, headers=headers)))[
            "complete"
        ]
        with pytest.raises(HTTPError) as exc:
            urlopen(Request(url + "vote", data=payload, headers=headers))
        assert exc.value.code == 400
        assert len(session.history) == 1


def test_default_combines_model_and_hypothesis_even_with_fixed_examples(monkeypatch):
    import spytial
    from spytial.suggest import _session

    provider = Provider()
    monkeypatch.setattr(_session, "Codex", lambda: provider)
    derived = []

    def from_type(cls):
        derived.append(cls)
        return st.just(tree())

    monkeypatch.setattr(st, "from_type", from_type)
    session = spytial.suggest(
        Tree, examples=[tree()], rules=["Align children"], max_examples=3
    ).wait()
    assert isinstance(session, SuggestSession)
    assert isinstance(session.search, HypothesisSearch)
    assert len(derived) >= 3  # seed, then whole-program checks for both candidates
    assert provider.prompts and "Align children" in provider.prompts[0]
    assert session.next() is not None


def test_hypothesis_finds_more_data_after_a_judgment():
    session = suggest(
        Tree,
        proposer=Provider(),
        strategy=st.integers(0, 2).map(lambda n: Tree(n, Tree(n + 3), Tree(9))),
        max_examples=10,
    )
    first = session.next()
    session.judge("both")
    second = session.next()
    assert second is not None
    assert first["datum"] != second["datum"]
    assert first["candidate_ids"] == second["candidate_ids"]


def test_alternative_search_and_proposer_still_use_formal_checks():
    class FiniteSearch:
        def initial(self, cls, *, max_examples):
            return tree()

        def find(self, cls, predicate, *, max_examples):
            values = [tree(), Tree(1, Tree(2), Tree(3))]
            return next((v for v in values[:max_examples] if predicate(v)), None)

    session = suggest(
        Tree,
        search=FiniteSearch(),
        proposer=FixedProposals([proposal(["below"]), proposal(["below", "left"])]),
    )
    first = session.next()
    assert any(s["excludes"] for s in first["sides"])
    session.judge("both")
    assert session.next()["datum"] != first["datum"]
    assert not session.can_revise
    with pytest.raises(ValueError, match="does not support"):
        session.revise("Children should be aligned")


def test_failed_revision_rolls_back_partial_proposals_and_keeps_question():
    calls = []

    def provider(prompt, *, schema):
        calls.append(prompt)
        if len(calls) == 1:
            return Provider()(prompt, schema=schema)
        if len(calls) == 2:
            bad = proposal(["left"])
            bad["operations"].append(proposal(["right"])["operations"][0])
            return {
                "rules": [{"text": "Extra rule", "origin": "suggested"}],
                "programs": [proposal(["above"]), bad],
            }
        raise RuntimeError("Model unavailable")

    session = suggest(tree(), proposer=provider, search=FixedExamples())
    session.vote(0, "upvote")
    question = session.next()
    original_history = deepcopy(session.history)

    def state():
        return deepcopy(
            (
                session.rules,
                session.requests,
                [(c.id, c.summary, c.program) for c in session.candidates],
                session.notes,
            )
        )

    before = state()
    with pytest.raises(RuntimeError, match="unavailable"):
        session.revise("Try above instead")
    assert state() == before
    assert session.history == original_history
    assert session.next() == question
    session.judge("both", question_id=question["id"])


def test_returned_judgment_and_draft_are_snapshots():
    session = suggest(tree(), proposer=Provider(), search=FixedExamples())
    original = session.draft.to_registry()
    session.draft.suggestions.clear()
    assert session.draft.to_registry() == original
    session.next()
    record = session.judge("both")
    record["datum"].clear()
    assert session.history[0]["datum"]["atoms"]


def test_falsey_provider_is_used_and_missing_model_does_not_fall_back():
    class FalseyProvider(Provider):
        def __bool__(self):
            return False

    provider = FalseyProvider()
    session = suggest(tree(), proposer=provider, search=FixedExamples())
    assert provider.prompts and session.can_revise

    def unavailable(prompt, *, schema):
        raise RuntimeError("Missing model")

    with pytest.raises(RuntimeError, match="Missing model"):
        suggest(tree(), proposer=unavailable, search=FixedExamples())


def test_missing_hypothesis_does_not_disable_search(monkeypatch):
    import builtins

    original = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "hypothesis":
            raise ImportError("Not installed")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(RuntimeError, match="needs Hypothesis"):
        suggest(tree(), proposer=Provider())
    assert suggest(tree(), proposer=Provider(), search=FixedExamples()).next()


@pytest.mark.parametrize("first", ["upvote", "downvote", "unsure"])
@pytest.mark.parametrize("second", ["upvote", "downvote", "unsure"])
def test_all_independent_vote_combinations(first, second):
    with suggest(tree(), proposer=Provider(), search=FixedExamples()) as session:
        question = session.next()
        candidates = [c.id for c in session.candidates]
        partial = session.vote(0, first, question_id=question["id"])
        assert partial["votes"] == [first, None]
        assert not partial["complete"]
        assert session._poll()["question"]["votes"] == [first, None]
        partial["votes"][0] = "tampered"
        result = session.vote(1, second, question_id=question["id"])
        assert result["votes"] == [first, second]
        assert result["complete"]
        assert len(session.history) == 1
        assert [c.id for c in session.candidates] == candidates
        with pytest.raises(ValueError, match="no longer current"):
            session.vote(0, first, question_id=question["id"])


def test_partial_votes_survive_revision_and_remain_in_model_context():
    provider = Provider()
    with suggest(tree(), proposer=provider, search=FixedExamples()) as session:
        question = session.next()
        session.vote(1, "unsure")
        session.revise("Keep whole branches together")
        assert session.next()["id"] == question["id"]
        assert session.next()["votes"] == [None, "unsure"]
        assert '"votes": [null, "unsure"]' in provider.prompts[-1]
        session.vote(1, "downvote")
        assert len(session.history) == 1
        assert session.history[0]["votes"] == [None, "downvote"]


def test_new_proposals_preserve_partial_votes():
    provider = Provider()
    with suggest(tree(), proposer=provider, search=FixedExamples()) as session:
        previous = session.vote(0, "upvote")
        session.proposer = lambda prompt, schema: {
            "rules": [],
            "programs": [proposal(["above"])],
        }
        session.revise("Children above")
        assert session.history == [previous]
        with pytest.raises(ValueError, match="no longer current"):
            session.vote(1, "downvote", question_id=previous["id"])
        assert session.next()["id"] != previous["id"]


def test_background_startup_and_failure_are_observable_without_waiting():
    import threading

    entered, release = threading.Event(), threading.Event()

    def slow_provider(prompt, *, schema):
        entered.set()
        assert release.wait(10)
        raise RuntimeError("Model unavailable")

    with start_session(
        tree(), proposer=slow_provider, search=FixedExamples()
    ) as session:
        try:
            assert entered.wait(5)
            assert session._poll()["status"] == "loading"
            assert session._poll()["message"] == "Drafting proposals…"
            with pytest.raises(TimeoutError, match="still preparing"):
                session.wait(timeout=0.01)
            release.set()
            with pytest.raises(RuntimeError, match="Model unavailable"):
                session.wait(timeout=5)
            assert session._poll() == {
                "status": "error",
                "message": "Model unavailable",
                "question": None,
            }
        finally:
            release.set()


@pytest.mark.parametrize("side", [True, 0.0, -1, 2, "0", None])
def test_invalid_image_vote_cannot_mutate_history(side):
    with suggest(tree(), proposer=Provider(), search=FixedExamples()) as session:
        with pytest.raises(ValueError, match="side must"):
            session.vote(side, "upvote")
        assert not session.history

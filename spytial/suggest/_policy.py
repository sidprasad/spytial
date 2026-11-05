"""Candidate scoring and combination policy, independent of session lifecycle.

Core supplies arrangement membership and feasibility. This module decides which
candidates survive and whether their conjunction agrees with the classifications.
"""

from copy import deepcopy

from ._model import SpecDraft


def replay_candidates(candidates, judgments, checks, elimination_threshold):
    """Recompute all scores, including eliminated candidates, from current evidence."""
    scores = {c.id: [0, 0] for c in candidates}
    for record, side in judgments:
        answers = checks.memberships(
            record["datum"],
            [c.program for c in candidates],
            record["observations"][side],
        )
        record.setdefault("memberships", [{}, {}])[side] = dict(
            zip((c.id for c in candidates), answers)
        )
        for candidate, accepts in zip(candidates, answers):
            if record["votes"][side] == "upvote":
                scores[candidate.id][0 if accepts else 1] += 1
            elif accepts:
                scores[candidate.id][1] += 1
    for candidate in candidates:
        candidate.positive_votes, candidate.negative_votes = scores[candidate.id]
        candidate.eliminated = candidate.negative_votes >= elimination_threshold


def resolve_spec(cls, survivors, judgments, datums, checks, min_positive_votes):
    """Resolve on retained data; generated-data search remains the caller's job."""
    supported = [c for c in survivors if c.positive_votes >= min_positive_votes]
    pool = supported or survivors
    result = {
        "status": "draft",
        "candidate_ids": [c.id for c in pool],
        "positive_votes": 0,
        "conflicts": [],
        "program": None,
        "message": "The spec needs positive evidence before use.",
    }
    if not pool:
        result.update(status="empty", message="No candidates remain.")
        return result, None

    unique = {
        suggestion.dedup_key(): deepcopy(suggestion)
        for candidate in pool
        for suggestion in candidate.draft.enabled()
    }
    draft = SpecDraft(cls, list(unique.values()))
    program = draft.to_registry()
    result["program"] = program
    for datum in datums:
        try:
            feasible = checks.feasible(datum, program)
        except ValueError:
            result.update(
                status="unsupported",
                message="Core cannot check this combination of rules.",
            )
            return result, None
        if not feasible:
            result.update(
                status="conflict", message="The remaining rules conflict on an example."
            )
            return result, None

    for record, side in judgments:
        accepts = checks.memberships(
            record["datum"], [program], record["observations"][side]
        )[0]
        positive = record["votes"][side] == "upvote"
        if positive and accepts:
            result["positive_votes"] += 1
        if accepts != positive:
            result["conflicts"].append({"question_id": record["id"], "side": side})
    if result["conflicts"]:
        result.update(
            status="conflict",
            message="Some earlier judgments still conflict with the combined spec.",
        )
    elif supported and result["positive_votes"] >= min_positive_votes:
        result.update(status="supported", message="Your spec is ready to use.")
    return result, draft

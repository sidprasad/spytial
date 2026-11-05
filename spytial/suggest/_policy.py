"""Property-local evidence and conjunction of explicitly accepted definitions."""

from copy import deepcopy

from ._model import SpecDraft


def combine(cls, *drafts):
    unique = {s.dedup_key(): deepcopy(s) for draft in drafts for s in draft.enabled()}
    return SpecDraft(cls, list(unique.values()))


def replay_candidates(candidates, judgments, checks, elimination_threshold):
    scores = {c.id: [0, 0] for c in candidates}
    for record, side in judgments:
        answers = checks.memberships(
            record["datum"],
            [c.program for c in candidates],
            record["observations"][side],
        )
        for candidate, accepts in zip(candidates, answers):
            if record["votes"][side] == "upvote":
                scores[candidate.id][0 if accepts else 1] += 1
            elif accepts:
                scores[candidate.id][1] += 1
    for candidate in candidates:
        candidate.positive_votes, candidate.negative_votes = scores[candidate.id]
        candidate.eliminated = candidate.negative_votes >= elimination_threshold


def supported(prop, minimum):
    return [c for c in prop.survivors if c.positive_votes >= minimum]


def consistent(program, judgments, checks, minimum):
    """A property definition must fit its judgments and share positive support."""
    positive = 0
    for record, side in judgments:
        permits = checks.memberships(
            record["datum"], [program], record["observations"][side]
        )[0]
        approved = record["votes"][side] == "upvote"
        if permits != approved:
            return False
        positive += permits and approved
    return positive >= minimum

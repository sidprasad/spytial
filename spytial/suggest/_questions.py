"""Compare interpretations under a fixed accepted background."""

from copy import deepcopy
import itertools
import json
import uuid

from ._policy import combine


def question_key(question):
    return json.dumps(
        [
            question["requirement_id"],
            question["requirement_revision"],
            question["context"],
            sorted(question["candidate_ids"]),
            question["datum"],
        ],
        sort_keys=True,
    )


def make_question(
    prop, background, ids, datum, programs, sides, summaries, *, kind="contrast"
):
    return {
        "id": uuid.uuid4().hex,
        "requirement_id": prop.id,
        "requirement_revision": prop.revision,
        "prompt": prop.prompt,
        "context": background.to_registry(),
        "candidate_ids": ids,
        "datum": datum,
        "programs": programs,
        "sides": sides,
        "summaries": summaries,
        "votes": [None, None],
        "kind": kind,
    }


def find_question(prop, background, checks, find_datum):
    """Return a contextual contrast, then try confirmation without assuming equivalence.

    ``find_datum(ids, predicate)`` supplies retained or generated data and avoids
    repeats in this requirement revision and context. All returned sides retain the
    background, including confirmation's alternative arrangement.
    """
    programs = {
        c.id: combine(c.draft.cls, background, c.draft).to_registry()
        for c in prop.survivors
    }
    for a, b in itertools.combinations(prop.survivors, 2):
        ids = [a.id, b.id]
        datum = find_datum(
            ids,
            lambda d: checks.compare(d, programs[a.id], programs[b.id])["status"]
            == "different",
        )
        if datum is not None:
            return make_question(
                prop,
                background,
                ids,
                datum,
                [programs[a.id], programs[b.id]],
                checks.compare(datum, programs[a.id], programs[b.id])["sides"],
                [a.summary, b.summary],
            )
    # Even a single candidate needs positive evidence. The accepted background
    # applies on both sides; only the pending requirement is varied.
    base = background.to_registry()
    for candidate in prop.survivors:
        ids, program = [candidate.id, "confirmation"], programs[candidate.id]
        datum = find_datum(ids, lambda d: checks.feasible(d, program))
        if datum is not None:
            contrast = checks.compare(datum, program, base)
            sides = contrast.get("sides", [{"program": program}, {"program": base}])
            return make_question(
                prop,
                background,
                ids,
                datum,
                [program, base],
                deepcopy(sides),
                [candidate.summary, "Another arrangement"],
                kind="confirmation",
            )
    return None

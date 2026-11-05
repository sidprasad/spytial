"""Contrast-search policy in Python, checked by the released core solver."""

from copy import deepcopy

import pytest

from spytial.suggest._compare import compare
from spytial._conformance import run_cases

DATUM = {
    "atoms": [{"id": n, "type": "Node", "label": n} for n in ("a", "b")],
    "relations": [
        {
            "id": "r",
            "name": "r",
            "types": ["Node", "Node"],
            "tuples": [{"atoms": ["a", "b"], "types": ["Node", "Node"]}],
        }
    ],
}
RIGHT = {"orientation": {"selector": "r", "directions": ["right"]}}
BELOW = {"orientation": {"selector": "r", "directions": ["below"]}}


def program(*constraints):
    return {"constraints": list(constraints), "directives": []}


def test_each_directed_witness_satisfies_its_origin_and_excludes_whole_rival():
    a, b = program(RIGHT), program(BELOW)
    original = deepcopy((DATUM, a, b))
    result = compare(DATUM, a, b)
    assert result["status"] == "different"
    assert [s["excludes"] for s in result["sides"]] == ["b", "a"]
    checks = []
    for side, origin, rival in zip(result["sides"], (a, b), (b, a)):
        witness = side["program"]
        assert all(c in witness["constraints"] for c in origin["constraints"])
        checks.extend(
            [
                {"name": f"witness-{side['origin']}", "datum": DATUM, "spec": witness},
                {
                    "name": f"overlap-{side['origin']}",
                    "datum": DATUM,
                    "spec": program(*(witness["constraints"] + rival["constraints"])),
                },
            ]
        )
    verdicts = run_cases(checks)["cases"]
    assert [r["ok"] for r in verdicts] == [True, False, True, False]
    for verdict in verdicts[1::2]:
        assert {e["code"] for e in verdict["errors"]} == {"layout/unsatisfiable"}
    assert (DATUM, a, b) == original
    result["sides"][0]["program"]["constraints"].clear()
    assert (DATUM, a, b) == original


def test_one_sided_difference_keeps_a_satisfying_counterpart():
    result = compare(DATUM, program(RIGHT), program(RIGHT, BELOW))
    assert result["status"] == "different"
    assert [s["excludes"] for s in result["sides"]] == ["b", None]
    assert result["sides"][1]["program"] == program(RIGHT, BELOW)


def test_combined_candidate_conflict_is_not_a_difference():
    left = {"orientation": {"selector": "r", "directions": ["left"]}}
    assert (
        compare(DATUM, program(RIGHT), program(RIGHT, left))["status"] == "infeasible"
    )


def test_identical_programs_still_check_feasibility_on_this_datum():
    assert compare(DATUM, program(RIGHT), program(RIGHT))["status"] == "no-difference"
    contradictory = program(
        RIGHT, {"orientation": {"selector": "r", "directions": ["left"]}}
    )
    assert compare(DATUM, contradictory, contradictory)["status"] == "infeasible"


def test_same_programs_can_be_indistinguishable_on_one_datum_and_different_on_another():
    leaf = deepcopy(DATUM)
    leaf["atoms"] = leaf["atoms"][:1]
    leaf["relations"][0]["tuples"] = []
    a, b = program(), program(RIGHT)
    assert compare(leaf, a, b)["status"] == "no-difference"
    assert compare(DATUM, a, b)["status"] == "different"


def test_flips_an_existing_never_constraint_to_always():
    result = compare(
        DATUM,
        program(),
        program({"orientation": {**RIGHT["orientation"], "hold": "never"}}),
    )
    assert (
        result["sides"][0]["program"]["constraints"][0]["orientation"]["hold"]
        == "always"
    )


def test_presentation_changes_are_outside_this_strategy():
    hidden = {**program(RIGHT), "directives": [{"hideAtom": {"selector": "Node"}}]}
    assert compare(DATUM, program(), hidden)["status"] == "unsupported"


def test_invalid_program_or_datum_is_not_evidence_of_incompatibility():
    assert compare(DATUM, program({"bogus": {}}), program())["status"] == "unsupported"
    with pytest.raises(ValueError, match="binary"):
        compare(
            DATUM,
            program({"orientation": {"selector": "Node", "directions": ["right"]}}),
            program(),
        )
    with pytest.raises(ValueError, match="Invalid orientation"):
        compare(
            DATUM,
            program({"orientation": {"selector": "r", "directions": ["diagonal"]}}),
            program(),
        )
    broken = deepcopy(DATUM)
    broken["relations"][0]["tuples"][0]["atoms"][0] = "missing"
    with pytest.raises(ValueError, match="missing"):
        compare(broken, program(), program(RIGHT))


def test_no_witness_is_not_even_an_equivalence_proof_on_the_same_datum():
    datum = deepcopy(DATUM)
    datum["atoms"].append({"id": "c", "type": "Node", "label": "c"})
    datum["relations"] += [
        {"name": "first", "tuples": [{"atoms": ["a", "b"]}]},
        {"name": "second", "tuples": [{"atoms": ["a", "c"]}]},
    ]
    datum["relations"][0]["tuples"].append(
        {"atoms": ["a", "c"], "types": ["Node", "Node"]}
    )
    first_right = {"orientation": {"selector": "first", "directions": ["right"]}}
    a, b = program(first_right), program(RIGHT)
    # Flipping all of r conflicts with A on the first pair, so this strategy
    # misses the real difference on the second pair. It must not say equivalent.
    assert compare(datum, a, b) == {"status": "no-difference"}
    witness = program(
        first_right,
        {
            "orientation": {
                "selector": "second",
                "directions": ["right"],
                "hold": "never",
            }
        },
    )
    results = run_cases(
        [
            {"name": "witness", "datum": datum, "spec": witness},
            {
                "name": "rival",
                "datum": datum,
                "spec": program(*(witness["constraints"] + b["constraints"])),
            },
        ]
    )["cases"]
    assert results[0]["ok"]
    assert {e["code"] for e in results[1]["errors"]} == {"layout/unsatisfiable"}


def test_uncheckable_cyclic_probe_does_not_invalidate_individual_candidates():
    datum = {
        "atoms": [{"id": n, "type": "Node", "label": n} for n in "abcd"],
        "relations": [
            {
                "name": "r",
                "types": ["Node", "Node"],
                "tuples": [
                    {"atoms": list(pair), "types": ["Node", "Node"]}
                    for pair in ["ab", "bc", "cd", "da"]
                ],
            }
        ],
    }
    a, b = [
        program({"cyclic": {"selector": "r", "direction": d}})
        for d in ("clockwise", "counterclockwise")
    ]
    assert compare(datum, a, a)["status"] == "no-difference"
    assert compare(datum, b, b)["status"] == "no-difference"
    assert compare(datum, a, b)["status"] == "unsupported"

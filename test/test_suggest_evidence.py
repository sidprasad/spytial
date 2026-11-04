"""Concrete layouts are classified by core, including negation and disjunction."""

from copy import deepcopy
import pytest

from spytial.suggest._evidence import observe, membership
from test_suggest_compare import DATUM, RIGHT, BELOW, program


def observation(bx=100, by=100):
    return observe(
        DATUM,
        {"positions": [{"id": "a", "x": 0, "y": 0}, {"id": "b", "x": bx, "y": by}]},
    )


def test_membership_uses_actual_arrangement_and_all_programs():
    proposals = [program(RIGHT), program(BELOW), program(RIGHT, BELOW), program()]
    assert membership(DATUM, proposals, observation()) == [True, True, True, True]
    assert membership(DATUM, proposals, observation(-100, 100)) == [
        False,
        True,
        False,
        True,
    ]
    assert membership(DATUM, proposals, observation(100, -100)) == [
        True,
        False,
        False,
        True,
    ]


def test_alignment_and_negated_compound_are_checked_by_core():
    aligned = {"align": {"selector": "r", "direction": "horizontal"}}
    negative = {
        "orientation": {
            "selector": "r",
            "directions": ["right", "below"],
            "hold": "never",
        }
    }
    proposals = [program(aligned), program(negative)]
    assert membership(DATUM, proposals, observation(100, 0)) == [True, True]
    assert membership(DATUM, proposals, observation(100, 100)) == [False, False]
    # Either failed conjunct is enough. Do not accidentally use the solver's
    # original choice of disjunct as a constraint on this observed arrangement.
    assert membership(DATUM, proposals, observation(-100, 100)) == [False, True]
    assert membership(DATUM, proposals, observation(100, -100)) == [False, True]


def test_observation_is_invariant_to_translation_and_scaling():
    a = observation()
    b = observe(
        DATUM,
        {"positions": [{"id": "b", "x": 220, "y": 230}, {"id": "a", "x": 20, "y": 30}]},
    )
    assert a == b
    assert observation(100, 0.1)["signature"] == observation(100, 0)["signature"]


@pytest.mark.parametrize(
    "positions",
    [
        [],
        [{"id": "a", "x": float("nan"), "y": 0}],
        [{"id": "a", "x": True, "y": 0}],
        [{"id": "missing", "x": 0, "y": 0}],
        [{"id": "a", "x": 0, "y": 0}, {"id": "a", "x": 1, "y": 1}],
    ],
)
def test_invalid_positions_are_not_negative_evidence(positions):
    with pytest.raises(ValueError):
        observe(DATUM, {"positions": positions})


def test_missing_nodes_and_invalid_programs_do_not_become_rejections():
    with pytest.raises(ValueError, match="visible nodes"):
        membership(
            DATUM,
            [program(RIGHT)],
            observe(DATUM, {"positions": [{"id": "a", "x": 0, "y": 0}]}),
        )
    bad = deepcopy(RIGHT)
    bad["orientation"]["selector"] = "nonexistent"
    with pytest.raises(ValueError):
        membership(DATUM, [program(bad)], observation())


def test_literal_atom_ids_cannot_change_observation_selectors():
    datum = deepcopy(DATUM)
    for atom in datum["atoms"]:
        atom["id"] = 'odd"name' if atom["id"] == "a" else "3"
    datum["relations"][0]["tuples"][0]["atoms"] = ['odd"name', "3"]
    obs = observe(
        datum,
        {
            "positions": [
                {"id": 'odd"name', "x": 0, "y": 0},
                {"id": "3", "x": 100, "y": 100},
            ]
        },
    )
    assert membership(datum, [program(RIGHT, BELOW)], obs) == [True]

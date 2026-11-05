"""Turn a displayed arrangement into observations for the released core checker.

Membership is qualitative: order and alignment of visible node centres, not
font sizes or solver spacing. We encode total orders/equalities as ordinary
Spytial constraints; core alone interprets selectors, negation and disjunctions.
Coordinates within half a layout-coordinate pixel share an alignment class. Groups are not
part of suggest's proposal language and cannot be checked by this adapter.
"""

from copy import deepcopy
import json
import math

from .._conformance import run_cases


def observe(datum, state):
    if not isinstance(state, dict) or not isinstance(state.get("positions"), list):
        raise ValueError("A definite vote needs the displayed layout_state.positions.")
    positions = state["positions"]
    atoms = {a["id"] for a in datum["atoms"]}
    seen = set()
    for p in positions:
        if not isinstance(p, dict) or not isinstance(p.get("id"), str):
            raise ValueError("Each position needs an atom ID.")
        if p["id"] not in atoms or p["id"] in seen:
            raise ValueError("Positions must name distinct atoms from this datum.")
        seen.add(p["id"])
        if any(
            isinstance(p.get(a), bool)
            or not isinstance(p.get(a), (int, float))
            or not math.isfinite(p[a])
            for a in ("x", "y")
        ):
            raise ValueError("Position coordinates must be finite numbers.")
    if not positions:
        raise ValueError("The displayed layout has no nodes to judge.")
    constraints, signature = [], []
    for axis, direction, alignment in (
        ("x", "right", "vertical"),
        ("y", "below", "horizontal"),
    ):
        groups = []
        for p in sorted(positions, key=lambda p: (p[axis], p["id"])):
            if not groups or p[axis] - groups[-1][0][axis] > 0.5:
                groups.append([])
            groups[-1].append(p)
        ids = [sorted(p["id"] for p in group) for group in groups]
        signature.append(ids)
        for group in ids:
            for other in group[1:]:
                constraints.append(
                    {
                        "align": {
                            "selector": f"{json.dumps(group[0])} -> {json.dumps(other)}",
                            "direction": alignment,
                        }
                    }
                )
        for before, after in zip(ids, ids[1:]):
            constraints.append(
                {
                    "orientation": {
                        "selector": f"{json.dumps(before[0])} -> {json.dumps(after[0])}",
                        "directions": [direction],
                    }
                }
            )
    return {"constraints": constraints, "nodes": sorted(seen), "signature": signature}


def membership(datum, programs, observation, *, runner=run_cases):
    """Return membership for every program; errors never become negative evidence."""
    cases = []
    for index, program in enumerate(programs):
        if any("group" in c for c in program["constraints"]):
            raise ValueError("Group membership is not supported in suggest judgments.")
        for mode in ("base", "observed"):
            spec = deepcopy(program)
            if mode == "observed":
                spec["constraints"].extend(observation["constraints"])
            cases.append(
                {
                    "name": f"{index}-{mode}",
                    "datum": datum,
                    "spec": spec,
                    "assertions": [
                        {"query": "nodes()", "equals": observation["nodes"]}
                    ],
                }
            )
    if not cases:
        return []
    results = runner(cases, timeout=20)["cases"]
    answers = []
    for base, observed in zip(results[::2], results[1::2]):
        for result in (base, observed):
            invalid = [
                e for e in result["errors"] if e["code"] != "layout/unsatisfiable"
            ]
            invalid += [w for w in result["warnings"] if w["code"] == "layout/warning"]
            if invalid:
                raise ValueError("; ".join(e["message"] for e in invalid))
            if not result["errors"] and not result["ok"]:
                raise ValueError(
                    "The saved positions do not match the program's visible nodes."
                )
        answers.append(base["ok"] and observed["ok"])
    return answers

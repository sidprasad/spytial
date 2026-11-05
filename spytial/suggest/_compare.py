"""Suggest's contrast-search policy for ONE datum and two complete programs.

Python chooses candidate witness programs. The released core conformance CLI
checks them; no constraint solving or layout semantics are implemented here.
Failure to find a witness is not equivalence, even on the supplied datum: flipping
hold for every selected pair can be stronger than negating the whole constraint.
"""

from copy import deepcopy
import json

from .._conformance import run_cases

_POSITIONAL = {"orientation", "align", "cyclic", "group"}


def _key(program):
    return json.dumps(program, sort_keys=True)


def _kind(entry):
    return next(iter(entry))


def _validate(program):
    """Guard the strategy's supported input before core's permissive parser."""
    if not isinstance(program, dict) or any(
        not isinstance(program.get(key), list) for key in ("constraints", "directives")
    ):
        raise ValueError("A program needs constraints and directives arrays.")
    for entry in program["constraints"]:
        if (
            not isinstance(entry, dict)
            or len(entry) != 1
            or _kind(entry) not in _POSITIONAL | {"hideAtom", "size"}
        ):
            return False
        kind = _kind(entry)
        if kind not in _POSITIONAL:
            continue
        body = entry[kind]
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("selector"), str)
            or not body["selector"].strip()
            or body.get("hold", "always") not in ("always", "never")
        ):
            raise ValueError(
                "Each positional constraint needs a selector and a valid hold mode."
            )
        if kind == "orientation":
            directions = body.get("directions")
            allowed = (
                "above",
                "below",
                "left",
                "right",
                "directlyAbove",
                "directlyBelow",
                "directlyLeft",
                "directlyRight",
            )
            if (
                not isinstance(directions, list)
                or not directions
                or any(d not in allowed for d in directions)
            ):
                raise ValueError("Invalid orientation directions.")
        if kind == "align" and body.get("direction") not in ("horizontal", "vertical"):
            raise ValueError("Invalid alignment direction.")
        if kind == "cyclic" and body.get("direction") not in (
            "clockwise",
            "counterclockwise",
        ):
            raise ValueError("Invalid cyclic direction.")
    return True


def compare(datum, a, b, *, runner=run_cases):
    """Find checked contrasts on this datum, never a global program verdict.

    Each witness retains its origin program and flips a positional constraint
    from its rival. Admit it only if core finds it feasible AND incompatible
    with the entire rival. Empty selectors therefore cannot fake a difference.
    Hypothesis and the session choose other data; this function never does.
    """
    if not all(_validate(program) for program in (a, b)):
        return {
            "status": "unsupported",
            "message": "Only positional constraints can be compared.",
        }

    def fixed(program):
        return [c for c in program["constraints"] if _kind(c) not in _POSITIONAL]

    if a["directives"] != b["directives"] or fixed(a) != fixed(b):
        return {
            "status": "unsupported",
            "message": "Keep presentation directives identical when comparing positions.",
        }

    # Batch distinct checks in a single core process, including both candidates.
    programs = {_key(p): p for p in (a, b)}

    def witnesses(origin, rival):
        choices = []
        for entry in rival["constraints"]:
            kind = _kind(entry)
            if kind not in _POSITIONAL or entry in origin["constraints"]:
                continue
            body = entry[kind]
            witness = {
                "constraints": origin["constraints"]
                + [
                    {
                        kind: {
                            **body,
                            "hold": (
                                "always" if body.get("hold") == "never" else "never"
                            ),
                        }
                    }
                ],
                "directives": origin["directives"],
            }
            overlap = {
                "constraints": witness["constraints"] + rival["constraints"],
                "directives": witness["directives"],
            }
            programs[_key(witness)] = witness
            programs[_key(overlap)] = overlap
            choices.append((witness, overlap))
        return choices

    ab = witnesses(a, b) if a != b else []
    ba = witnesses(b, a) if a != b else []
    keys = list(programs)
    results = runner(
        [
            {
                "name": str(index),
                "datum": datum,
                "spec": programs[key],
                # A vacuous membership assertion retrieves core's visible-node set.
                "assertions": [{"query": "nodes()", "contains": []}],
            }
            for index, key in enumerate(keys)
        ],
        timeout=20,
    )["cases"]
    verdicts = dict(zip(keys, results))

    def feasible(program):
        result = verdicts[_key(program)]
        errors = result["errors"]
        # A malformed/unchecked program is never evidence of incompatibility.
        invalid = [e for e in errors if e["code"] != "layout/unsatisfiable"]
        # The conformance API preserves warnings as advisory diagnostics. This
        # elicitation policy is conservative: do not show a partially checked
        # picture, including a selector core warned about but continued past.
        invalid += [w for w in result["warnings"] if w["code"] == "layout/warning"]
        if invalid:
            raise ValueError("; ".join(d["message"] for d in invalid))
        if errors:
            return False
        assertions = result["assertions"]
        if not result["ok"] or len(assertions) != 1 or not assertions[0].get("ok"):
            raise RuntimeError("Core could not report the comparison's visible nodes.")
        return True

    if not feasible(a) or not feasible(b):
        return {
            "status": "infeasible",
            "message": "A candidate has conflicting constraints on this example.",
        }

    unsupported = []

    def difference(choices):
        for witness, overlap in choices:
            try:
                if feasible(witness) and not feasible(overlap):
                    return witness
            except ValueError as exc:
                # Core may reject a synthetic conjunction at parse time (e.g.
                # clockwise + counterclockwise on one selector). The original
                # candidates were checked above; this probe gives no evidence.
                unsupported.append(str(exc))
        return None

    wa, wb = difference(ab), difference(ba)
    if wa is None and wb is None:
        if unsupported:
            return {"status": "unsupported", "message": unsupported[0]}
        return {"status": "no-difference"}
    sides = [
        {
            "program": wa if wa is not None else a,
            "origin": "a",
            "excludes": "b" if wa is not None else None,
        },
        {
            "program": wb if wb is not None else b,
            "origin": "b",
            "excludes": "a" if wb is not None else None,
        },
    ]
    visible = [
        verdicts[_key(side["program"])]["assertions"][0]["actual"] for side in sides
    ]
    if visible[0] != visible[1]:
        return {
            "status": "unsupported",
            "message": "These witness programs do not show the same nodes.",
        }
    return {"status": "different", "sides": deepcopy(sides)}

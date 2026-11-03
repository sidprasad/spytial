"""Proposal format, prompt, and authoring checks shared by all proposers."""

from copy import deepcopy
import json
import re

from ._ask import _authoring_gate
from ._eval import evaluate_selectors
from ._model import Suggestion
from .introspect import build_class_info


def _operation_schema(kind, parameter, values):
    value = {"type": "string", "enum": values}
    if parameter == "directions":
        value = {"type": "array", "items": value, "minItems": 1}
    return {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": [kind]},
            "selector": {"type": "string"},
            parameter: value,
            "hold": {"type": "string", "enum": ["always", "never"]},
        },
        "required": ["kind", "selector", parameter, "hold"],
        "additionalProperties": False,
    }


PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "origin": {"type": "string", "enum": ["user", "suggested"]},
                },
                "required": ["text", "origin"],
                "additionalProperties": False,
            },
        },
        "programs": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "operations": {
                        "type": "array",
                        "maxItems": 16,
                        "items": {
                            "anyOf": [
                                _operation_schema(
                                    "orientation",
                                    "directions",
                                    [
                                        "above",
                                        "below",
                                        "left",
                                        "right",
                                        "directlyAbove",
                                        "directlyBelow",
                                        "directlyLeft",
                                        "directlyRight",
                                    ],
                                ),
                                _operation_schema(
                                    "align", "direction", ["horizontal", "vertical"]
                                ),
                                _operation_schema(
                                    "cyclic",
                                    "direction",
                                    ["clockwise", "counterclockwise"],
                                ),
                            ]
                        },
                    },
                },
                "required": ["summary", "operations"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["rules", "programs"],
    "additionalProperties": False,
}


class FixedProposals:
    """Replay explicitly supplied proposals for experiments without an LLM.

    Programs use the same ``summary`` / ``operations`` format as model output
    and pass exactly the same validation. No natural-language revision is offered.
    """

    can_revise = False

    def __init__(self, programs, *, rules=None):
        self._response = deepcopy({"programs": programs, "rules": rules or []})

    def __call__(self, prompt, *, schema):
        return deepcopy(self._response)


def proposal_prompt(cls, vocab, requests, candidates, history, critique):
    return f"""Help a person develop diagramming rules without reading Spytial.
Return 2-4 COMPLETE alternative positional programs, not isolated rule fragments.
Keep requirements that are not disputed. Alternatives may change one or several rules.
Distinguish requested rules from optional rules suggested by domain knowledge.
Use short ordinary-language summaries. Do not claim a proposal is verified.
Available operations: orientation(selector, directions), align(selector, direction),
cyclic(selector, direction). Orientation directions: above, below, left, right,
directlyAbove, directlyBelow, directlyLeft, directlyRight. Align: horizontal or
vertical. Cyclic: clockwise or counterclockwise. Each selector returns node PAIRS.
Selectors use only names from the vocabulary, join '.', union '+', intersection '&',
difference '-', product '->', transpose '~', transitive closure '^', reflexive closure '*',
parentheses and index projections '[...]'; built-ins univ, iden, none.
hold is always (default) or never (logical negation, not an opposite direction).
Presentation is fixed separately; do not emit hiding, styles or inferred edges.
Class: {cls.__name__}
Fields: {[(f.name, f.type_repr) for f in build_class_info(cls).fields]}
Vocabulary: {json.dumps(vocab)}
User requests: {json.dumps(requests)}
Current programs: {json.dumps([dict(summary=c.summary, program=c.program) for c in candidates])}
Each history entry has votes in the same order as its two programs and sides.
Upvote means acceptable, downvote means unacceptable, unsure means undecided,
and null means not yet rated. Preserve these independent judgments.
Judgment history: {json.dumps(history)}
Latest critique: {critique}
Judgments apply only to the examples shown, not all data. Never invent an answer.
"""


def validate_operations(operations, vocab, datums):
    if not isinstance(operations, list) or len(operations) > 16:
        raise ValueError("A program must have at most 16 operations.")
    names = (
        {n for n, _ in vocab["types"]}
        | {n for n, _ in vocab["relations"]}
        | {"univ", "iden", "none"}
    )
    rows = []
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("Each operation must be an object.")
        kind = operation.get("kind")
        if kind not in {"orientation", "align", "cyclic"}:
            raise ValueError("Unsupported positional operation.")
        kwargs = {k: v for k, v in operation.items() if k != "kind"}
        selector = kwargs.get("selector")
        if not isinstance(selector, str) or not selector.strip():
            raise ValueError("An operation needs a selector.")
        unknown = set(re.findall(r"[A-Za-z_][A-Za-z_0-9/]*", selector)) - names
        if unknown:
            raise ValueError("Unknown selector names: " + ", ".join(sorted(unknown)))
        kind, kwargs = _authoring_gate(kind, kwargs)
        nonempty = False
        for datum in datums:
            verdict = evaluate_selectors(datum, [selector])[0]
            if not verdict.ok or (not verdict.empty and verdict.arity != 2):
                raise ValueError(
                    verdict.diagnostic or "The selector must return node pairs."
                )
            nonempty = nonempty or not verdict.empty
        if not nonempty:
            raise ValueError(f"No example exercises selector {selector!r}.")
        rows.append(
            Suggestion(kind, kwargs, "high", enabled_by_default=True, source="proposal")
        )
    return rows

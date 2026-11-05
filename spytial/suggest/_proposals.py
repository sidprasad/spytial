"""Proposal format, prompt, and authoring checks shared by all proposers."""

from copy import deepcopy
from dataclasses import dataclass
import json
import re

from ._ask import _authoring_gate
from ._eval import evaluate_selectors
from ._model import SpecDraft, Suggestion
from .introspect import build_class_info


@dataclass
class ProgramCandidate:
    id: str
    summary: str
    draft: SpecDraft
    positive_votes: int = 0
    negative_votes: int = 0
    eliminated: bool = False

    @property
    def program(self):
        return self.draft.to_registry()

    def to_record(self):
        return {
            "id": self.id,
            "summary": self.summary,
            "program": self.program,
            "positive_votes": self.positive_votes,
            "negative_votes": self.negative_votes,
            "eliminated": self.eliminated,
        }

    @classmethod
    def from_record(cls, target, record):
        # Saved scores are informational; the session replays layout evidence.
        rows = []
        for entry in record["program"]["constraints"] + record["program"]["directives"]:
            kind, kwargs = next(iter(entry.items()))
            rows.append(
                Suggestion(
                    kind,
                    {"name": kwargs} if kind == "flag" else deepcopy(kwargs),
                    "high",
                    enabled_by_default=True,
                    source="proposal",
                )
            )
        return cls(record["id"], record["summary"], SpecDraft(target, rows))


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
    "required": ["programs"],
    "additionalProperties": False,
}


class FixedProposals:
    """Replay explicitly supplied proposals for experiments without an LLM.

    Programs use the same ``summary`` / ``operations`` format as model output
    and pass exactly the same validation. No natural-language revision is offered.
    """

    can_revise = False

    def __init__(self, programs):
        self._response = deepcopy({"programs": programs})

    def __call__(self, prompt, *, schema):
        return deepcopy(self._response)


def proposal_prompt(cls, vocab, prop, background, history):
    return f"""Help a person refine ONE visualization property through concrete critique.
Return 2-4 alternative interpretations of ONLY the requested property. Each may
contain several positional operations. The accepted background applies to every
alternative automatically: do not repeat, weaken, or replace its rules. Do not
add unrelated requirements. Use short ordinary-language summaries.
Operations: orientation(selector, directions), align(selector, direction),
cyclic(selector, direction). Orientation: above, below, left, right,
directlyAbove, directlyBelow, directlyLeft, directlyRight. Alignment: horizontal
or vertical. Cyclic: clockwise or counterclockwise. Selectors return node PAIRS.
Use vocabulary names and join '.', union '+', intersection '&', difference '-',
product '->', transpose '~', closure '^' or '*', parentheses, projections '[...]';
built-ins univ, iden, none. hold is always or never (logical negation).
Presentation is fixed separately; do not emit hiding, styles or inferred edges.
Class: {cls.__name__}
Fields: {[(f.name, f.type_repr) for f in build_class_info(cls).fields]}
Vocabulary: {json.dumps(vocab)}
Property: {prop.prompt}
Earlier wordings: {json.dumps([r["prompt"] for r in prop.revisions])}
Accepted background (already applied): {json.dumps(background)}
Judgments concern THIS property only, on the saved datum and arrangement. The
context records what else was applied when they were made; it is not part of the
property being learned. Upvote: satisfies the intended property. Downvote: does
not. Unsure: undecided. Null: not rated. Never invent classifications. Preserve
these judgments when interpreting a revision; the person can correct history.
Property judgment history: {json.dumps(history)}
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

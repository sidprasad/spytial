"""Saved arrangements and classifications, independent of search and rendering."""

from copy import deepcopy
import json
import uuid

from ._evidence import observe


def validate_vote(side, value):
    if type(side) is not int or side not in (0, 1):
        raise ValueError("side must be 0 or 1")
    if not isinstance(value, str) or value not in {"upvote", "downvote", "unsure"}:
        raise ValueError("Choose upvote, downvote, or unsure.")


class JudgmentHistory:
    """Own vote revisions, explored arrangements, and duplicate evidence."""

    def __init__(self):
        self.records = []
        self.revision = 0

    def get(self, question_id):
        return next((r for r in self.records if r["id"] == question_id), None)

    def record(self, question, side, value, observation, layout_state):
        """Record an already validated arrangement without changing the question."""
        record = self.get(question["id"])
        if record is None:
            record = deepcopy(question)
            self.records.append(record)
        previous = record.get("observations", [None, None])[side]
        new_arrangement = (
            previous is not None
            and observation is not None
            and previous["signature"] != observation["signature"]
        )
        if new_arrangement:
            # Dragging can produce new evidence. Keep the earlier arrangement
            # independently editable, without duplicating the other side's vote.
            archived = deepcopy(record)
            archived["id"] = uuid.uuid4().hex
            archived["votes"][1 - side] = None
            archived["complete"] = False
            archived["explored_from"] = record["id"]
            self.records.insert(self.records.index(record), archived)
        changed = record["votes"][side] is not None and record["votes"][side] != value
        self._set_vote(record, side, value, log_change=changed and not new_arrangement)
        record.setdefault("observations", [None, None])[side] = observation
        if layout_state is not None:
            record.setdefault("layout_states", [None, None])[side] = deepcopy(
                layout_state
            )
        return record

    def reclassify(self, question_id, side, value):
        validate_vote(side, value)
        record = self.get(question_id)
        if record is None:
            raise ValueError("Unknown history entry.")
        if value != "unsure" and record.get("observations", [None, None])[side] is None:
            raise ValueError(
                "This example has no saved layout; judge it in the diagram view first."
            )
        self._set_vote(record, side, value, log_change=True)
        return record

    def _set_vote(self, record, side, value, *, log_change):
        self.revision += 1
        if log_change:
            record.setdefault("changes", []).append(
                {
                    "side": side,
                    "from": record["votes"][side],
                    "to": value,
                    "revision": self.revision,
                }
            )
        record["votes"][side] = value
        record.setdefault("vote_revisions", [0, 0])[side] = self.revision
        record["complete"] = all(v is not None for v in record["votes"])

    def effective(self, requirement_id=None):
        """Latest definite classification per datum and qualitative arrangement."""
        latest = {}
        for record in self.records:
            if (
                requirement_id is not None
                and record["requirement_id"] != requirement_id
            ):
                continue
            for side, value in enumerate(record["votes"]):
                observation = record.get("observations", [None, None])[side]
                if observation is None or value is None:
                    continue
                key = json.dumps(
                    [
                        record["requirement_id"],
                        record["datum"],
                        observation["signature"],
                    ],
                    sort_keys=True,
                )
                revision = record.get("vote_revisions", [0, 0])[side]
                if key not in latest or revision > latest[key][0]:
                    latest[key] = (revision, record, side)
        # An unsure revision supersedes earlier definite votes as well.
        return [
            (record, side)
            for _, record, side in latest.values()
            if record["votes"][side] != "unsure"
        ]

    @classmethod
    def restore(cls, records, revision):
        history = cls()
        history.records = deepcopy(records)
        history.revision = revision
        # Rebuild evidence from coordinates, not saved membership vectors.
        for record in history.records:
            for side, state in enumerate(record.get("layout_states", [None, None])):
                observation = (
                    observe(record["datum"], state) if state is not None else None
                )
                record.setdefault("observations", [None, None])[side] = observation
                if observation is None and record["votes"][side] in {
                    "upvote",
                    "downvote",
                }:
                    raise ValueError("A saved definite judgment is missing its layout.")
        return history

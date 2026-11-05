"""One editable requirement and the public handle used to revisit it."""

from dataclasses import dataclass, field
from copy import deepcopy

from ._proposals import ProgramCandidate


@dataclass
class RequirementState:
    id: str
    prompt: str
    revision: int = 1
    candidates: list = field(default_factory=list)
    accepted_ids: list = field(default_factory=list)
    revisions: list = field(default_factory=list)
    diagnostic: str = ""

    @property
    def survivors(self):
        return [c for c in self.candidates if not c.eliminated]

    @property
    def accepted(self):
        return [c for c in self.candidates if c.id in self.accepted_ids]

    def _revision_record(self):
        return {
            "prompt": self.prompt,
            "revision": self.revision,
            "candidates": [c.to_record() for c in self.candidates],
            "accepted_ids": list(self.accepted_ids),
        }

    def next_revision(self, prompt):
        return RequirementState(
            self.id,
            prompt,
            self.revision + 1,
            revisions=[*self.revisions, self._revision_record()],
        )

    def to_record(self):
        return {
            "id": self.id,
            **self._revision_record(),
            "revisions": deepcopy(self.revisions),
            "diagnostic": self.diagnostic,
        }

    @classmethod
    def from_record(cls, target, record):
        state = cls(record["id"], record["prompt"], record["revision"])
        state.candidates = [
            ProgramCandidate.from_record(target, c) for c in record["candidates"]
        ]
        state.accepted_ids = list(record["accepted_ids"])
        if set(state.accepted_ids) - {c.id for c in state.candidates}:
            raise ValueError("A saved requirement selects an unknown candidate.")
        state.revisions = deepcopy(record["revisions"])
        state.diagnostic = record.get("diagnostic", "")
        return state


class Requirement:
    """A requirement's identity survives revisions and classification corrections.

    Edit the wording in the session prompt to replace its candidates and replay
    its judgments. Continue judging to keep the existing candidates.
    """

    def __init__(self, session, requirement_id):
        self._session = session
        self.id = requirement_id

    @property
    def prompt(self):
        return self._session._requirement(self.id).prompt

    @property
    def result(self):
        self._session.wait()
        with self._session._operation_lock:
            return deepcopy(
                self._session._requirement_result(self._session._requirement(self.id))
            )

    @property
    def status(self):
        return self.result["status"]

    @property
    def candidates(self):
        self._session.wait()
        with self._session._operation_lock:
            return [
                c.to_record() for c in self._session._requirement(self.id).candidates
            ]

    @property
    def history(self):
        return deepcopy(
            [r for r in self._session.history if r["requirement_id"] == self.id]
        )

    def resume(self):
        self._session.resume(self.id)
        return self

    def accept(self):
        self._session.accept(self.id)
        return self

    def done(self):
        self.resume()
        return self._session.done()

    def __repr__(self):
        return f"<Requirement {self.prompt!r}>"

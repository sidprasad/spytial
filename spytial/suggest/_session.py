"""An example-first conversation over complete candidate Spytial programs.

Judgments belong to displayed scenarios. PICK scores all candidates against
those scenarios; bounded search never establishes equivalence.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import itertools
import json
import uuid
import threading
from functools import wraps

from ..provider_system import CnDDataInstanceBuilder
from ..core_assets import SPYTIAL_CORE_VERSION
from ._compare import compare
from ._evidence import observe, membership
from ._enrich_from_examples import _vocabulary
from ._model import SpecDraft
from ._living import LivingSpec
from ._search import HypothesisSearch
from ._proposals import PROPOSAL_SCHEMA, proposal_prompt, validate_operations
from .providers import Codex, as_provider


def _ready_method(method):
    """Serialize notebook calls and browser votes after background startup."""

    @wraps(method)
    def call(self, *args, **kwargs):
        self.wait()
        with self._operation_lock:
            if self._closed:
                raise RuntimeError("This session is closed.")
            return method(self, *args, **kwargs)

    return call


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


_POSITIONAL = {"orientation", "align", "cyclic", "group"}


class SuggestSession:
    """Keep proposed programs, concrete questions, and the user's critique together.

    Use ``suggest(...)`` to construct a session. ``show()``
    opens its UI; displaying it in Jupyter embeds the same local page.
    Startup runs in the background. ``wait()`` waits explicitly in scripts.
    ``next()``, ``vote()``, and ``revise()`` also work without a browser.
    """

    def __init__(
        self,
        target,
        *,
        rules=None,
        examples=None,
        instance=None,
        strategy=None,
        proposer=None,
        search=None,
        registry=None,
        max_examples=20,
        elimination_threshold=2,
        min_positive_votes=1,
        max_candidates=4,
        _saved=None,
    ):
        from ._draft import _coerce_examples

        if (
            not isinstance(max_examples, int)
            or isinstance(max_examples, bool)
            or not 1 <= max_examples <= 200
        ):
            raise ValueError("max_examples must be between 1 and 200")
        if rules is not None and (
            not isinstance(rules, (list, tuple))
            or any(not isinstance(r, str) or not r.strip() for r in rules)
        ):
            raise ValueError("rules must be a list of non-empty sentences")
        for name, value, maximum in (
            ("elimination_threshold", elimination_threshold, 100),
            ("min_positive_votes", min_positive_votes, 100),
            ("max_candidates", max_candidates, 4),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= maximum
            ):
                raise ValueError(f"{name} must be between 1 and {maximum}")
        self.elimination_threshold = elimination_threshold
        self.min_positive_votes = min_positive_votes
        self.max_candidates = max_candidates
        self._saved = _saved
        self.cls = target if isinstance(target, type) else type(target)
        self.requests = list(rules or [])
        self.rules = [{"text": r, "origin": "user"} for r in self.requests]
        self._proposer_spec = proposer
        self.proposer = None
        if search is not None and strategy is not None:
            raise ValueError("Pass search= or strategy=, not both.")
        self.search = (
            search
            if search is not None
            else HypothesisSearch("auto" if strategy is None else strategy)
        )
        if not callable(getattr(self.search, "initial", None)) or not callable(
            getattr(self.search, "find", None)
        ):
            raise TypeError("search must implement initial() and find()")
        self.max_examples = max_examples
        self.examples = _coerce_examples(examples, None)
        sample = (
            instance
            if instance is not None
            else (None if isinstance(target, type) else target)
        )
        if sample is not None:
            self.examples.insert(0, sample)
        self.notes = []
        self.history = []
        self.checkpoints = []
        self.paused = False
        self._revision = 0
        self._membership_cache = {}
        self._living_cache = None
        self._checked_living_cache = None
        self._spec = LivingSpec(self)
        self.candidates = []
        self.current = None
        self._asked = set()
        self._cache = {}
        self._server = None
        self.active_id = None
        self._registry = registry
        self._ready = threading.Event()
        self._operation_lock = threading.RLock()
        self._server_lock = threading.Lock()
        self._closed = False
        self._prepared = False
        self._search_pending = False
        self._error = None
        self._phase = "Preparing examples…"
        threading.Thread(target=self._initialize_job, daemon=True).start()

    def _initialize_job(self):
        with self._operation_lock:
            try:
                if self._closed:
                    return
                self._initialize()
                if not self._closed:
                    self._find_next()
            except Exception as exc:
                self._error = exc
            finally:
                self._ready.set()

    def _initialize(self):
        from ._draft import suggest_draft

        self.proposer = as_provider(
            Codex() if self._proposer_spec is None else self._proposer_spec
        )
        if self._saved is not None:
            self._restore(self._saved)
            self._saved = None
            return
        witness = self.search.initial(self.cls, max_examples=self.max_examples)
        if witness is not None:
            self.examples.append(witness)
        if not self.examples:
            raise ValueError("Supply examples or a strategy that can build this class.")
        self._datums = [self._datum(obj) for obj in self.examples]
        self.base = suggest_draft(
            self.cls, instance=self.examples[0], registry=self._registry
        )
        self._presentation = [
            deepcopy(s) for s in self.base.enabled() if s.directive not in _POSITIONAL
        ]
        self._propose()
        if not self.candidates:
            raise ValueError(
                "No usable candidate programs were produced. " + "; ".join(self.notes)
            )
        self.active_id = self.candidates[0].id

    def wait(self, timeout=None):
        """Wait for startup in a script; notebook display never needs to wait."""
        if not self._ready.wait(timeout):
            raise TimeoutError("The suggestion session is still preparing.")
        if self._error is not None:
            raise self._error
        return self

    def _search_job(self):
        with self._operation_lock:
            try:
                if not self._closed:
                    self._find_next()
            except Exception as exc:
                self._error = exc
            finally:
                self._search_pending = False

    def _poll(self):
        """Nonblocking state for the notebook: never run a model/search in GET."""
        if self._closed:
            return {"status": "closed", "message": "Session closed.", "question": None}
        if not self._ready.is_set() or not self._operation_lock.acquire(blocking=False):
            return {"status": "loading", "message": self._phase, "question": None}
        try:
            if self._error is not None:
                return {
                    "status": "error",
                    "message": str(self._error),
                    "question": None,
                }
            if self.paused:
                return {
                    "status": "paused",
                    "message": self.checkpoints[-1]["message"],
                    "question": deepcopy(self.current),
                }
            if not self._prepared:
                if not self._search_pending:
                    self._search_pending = True
                    self._phase = "Finding a comparison…"
                    threading.Thread(target=self._search_job, daemon=True).start()
                return {"status": "loading", "message": self._phase, "question": None}
            return {
                "status": "ready" if self.current is not None else "empty",
                "message": (
                    ""
                    if self.current is not None
                    else (
                        "No candidates remain. Revise the request or an earlier judgment."
                        if not self.survivors
                        else "No further comparison found."
                    )
                ),
                "question": deepcopy(self.current),
            }
        finally:
            self._operation_lock.release()

    def _datum(self, obj):
        if not isinstance(obj, self.cls):
            raise ValueError(f"Examples must be instances of {self.cls.__name__}.")
        # Data search must not resolve an applied living spec: validating that
        # spec itself generates data, and the current spec may be unresolved.
        return CnDDataInstanceBuilder(
            infer_variable_names=False, collect_annotations=False
        ).build_instance(obj)

    def _compare(self, datum, a, b):
        key = json.dumps([datum, a, b], sort_keys=True)
        if key not in self._cache:
            if len(self._cache) >= 512:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = compare(datum, a, b)
        return self._cache[key]

    def _add(self, summary, geometry):
        self._phase = "Checking examples…"
        draft = SpecDraft(self.cls, deepcopy(self._presentation + geometry))
        program = draft.to_registry()
        if any(c.program == program for c in self.candidates):
            return

        def broken(obj):
            datum = self._datum(obj)
            return self._compare(datum, program, program)["status"] != "no-difference"

        for datum in self._datums:
            check = self._compare(datum, program, program)
            if check["status"] != "no-difference":
                raise ValueError(check.get("message", "Candidate cannot be checked."))
        witness = self.search.find(self.cls, broken, max_examples=self.max_examples)
        if witness is not None:
            datum = self._datum(witness)
            if datum not in self._datums:
                self.examples.append(witness)
                self._datums.append(datum)
            raise ValueError(
                "Generated data exposed conflicting or unsupported constraints."
            )
        self.candidates.append(ProgramCandidate(uuid.uuid4().hex, summary, draft))

    def _propose(self, critique=""):
        vocab = _vocabulary(self._datums)
        prompt = proposal_prompt(
            self.cls, vocab, self.requests, self.candidates, self.history, critique
        )
        before = len(self.candidates)
        failures = []
        for attempt in range(2):
            self._phase = "Drafting proposals…"
            result = self.proposer(
                prompt + "\nValidation feedback: " + "; ".join(failures),
                schema=PROPOSAL_SCHEMA,
            )
            if not isinstance(result, dict) or not isinstance(
                result.get("programs"), list
            ):
                raise ValueError("The model did not return candidate programs.")
            for raw in result["programs"][:4]:
                if len(self.candidates) - before >= self.max_candidates:
                    break
                try:
                    geometry = validate_operations(
                        raw["operations"], vocab, self._datums
                    )
                    if (
                        not isinstance(raw["summary"], str)
                        or not raw["summary"].strip()
                    ):
                        raise ValueError("A program needs a readable summary.")
                    self._add(raw["summary"], geometry)
                except (ValueError, KeyError, TypeError) as exc:
                    failures.append(str(exc))
            for rule in result.get("rules", []):
                if (
                    isinstance(rule, dict)
                    and isinstance(rule.get("text"), str)
                    and rule["text"].strip()
                ):
                    # Only the human can establish that a rule was requested.
                    item = {
                        "text": rule["text"],
                        "origin": (
                            "user" if rule["text"] in self.requests else "suggested"
                        ),
                    }
                    if item not in self.rules:
                        self.rules.append(item)
            if (
                len(self.candidates) - before >= min(2, self.max_candidates)
                or not failures
            ):
                break
        self.notes.extend(failures)
        if len(self.candidates) == before:
            self.notes.append(
                "No new usable programs were produced; existing choices and judgments were kept."
            )
        self._replay()

    @property
    def spec(self):
        """The stable living spec; later judgments update what it resolves to."""
        return self._spec

    def apply(self):
        """Bind the living spec to the target class, returning the same object."""
        return self.spec.apply()

    @property
    def draft(self):
        """Return an editable inspection copy, without requiring positive support.

        The combination must be checkable and feasible on retained data. It can
        still conflict with classifications. Applying the returned SpecDraft
        bypasses living-spec checks and does not track subsequent feedback.
        """
        self.wait()
        with self._operation_lock:
            result, draft = self._living()
            if draft is None:
                raise ValueError(result["message"])
            return deepcopy(draft)

    @property
    def survivors(self):
        return [c for c in self.candidates if not c.eliminated]

    def _memberships(self, datum, programs, observation):
        answers, missing = {}, {}
        for program in programs:
            key = json.dumps([datum, program, observation["signature"]], sort_keys=True)
            if key in self._membership_cache:
                answers[key] = self._membership_cache[key]
            else:
                missing[key] = program
        if missing:
            values = membership(datum, list(missing.values()), observation)
            for key, answer in zip(missing, values):
                answers[key] = answer
                if len(self._membership_cache) >= 1024:
                    self._membership_cache.pop(next(iter(self._membership_cache)))
                self._membership_cache[key] = answer
        return [
            answers[json.dumps([datum, p, observation["signature"]], sort_keys=True)]
            for p in programs
        ]

    def _judgments(self):
        # Repeating a picture, clicking again, or moving it without changing its
        # qualitative arrangement must not manufacture independent evidence.
        latest = {}
        for record in self.history:
            for side, value in enumerate(record["votes"]):
                observation = record.get("observations", [None, None])[side]
                if observation is None or value is None:
                    continue
                key = json.dumps(
                    [record["datum"], observation["signature"]], sort_keys=True
                )
                entry = (record.get("vote_revisions", [0, 0])[side], record, side)
                if key not in latest or entry[0] > latest[key][0]:
                    latest[key] = entry
        return [
            (record, side)
            for _, record, side in latest.values()
            if record["votes"][side] != "unsure"
        ]

    def _replay(self):
        scores = {c.id: [0, 0] for c in self.candidates}
        for record, side in self._judgments():
            answers = self._memberships(
                record["datum"],
                [c.program for c in self.candidates],
                record["observations"][side],
            )
            record.setdefault("memberships", [{}, {}])[side] = dict(
                zip((c.id for c in self.candidates), answers)
            )
            for candidate, accepts in zip(self.candidates, answers):
                if record["votes"][side] == "upvote":
                    scores[candidate.id][0 if accepts else 1] += 1
                elif accepts:
                    scores[candidate.id][1] += 1
        for candidate in self.candidates:
            candidate.positive_votes, candidate.negative_votes = scores[candidate.id]
            candidate.eliminated = (
                candidate.negative_votes >= self.elimination_threshold
            )
        if not any(c.id == self.active_id for c in self.survivors):
            self.active_id = self.survivors[0].id if self.survivors else None
        self._living_cache = None

    def _living(self):
        if self._living_cache is not None:
            return deepcopy(self._living_cache)
        supported = [
            c for c in self.survivors if c.positive_votes >= self.min_positive_votes
        ]
        pool = supported or self.survivors
        result = {
            "status": "draft",
            "candidate_ids": [c.id for c in pool],
            "positive_votes": 0,
            "conflicts": [],
            "program": None,
            "message": "The spec needs positive evidence before use.",
        }
        if not pool:
            result.update(status="empty", message="No candidates remain.")
            self._living_cache = (result, None)
            return deepcopy(self._living_cache)
        unique = {}
        for candidate in pool:
            for suggestion in candidate.draft.enabled():
                unique[suggestion.dedup_key()] = deepcopy(suggestion)
        draft = SpecDraft(self.cls, list(unique.values()))
        program = draft.to_registry()
        result["program"] = program
        for datum in self._datums:
            try:
                verdict = self._compare(datum, program, program)
            except ValueError:
                result.update(
                    status="unsupported",
                    message="Core cannot check this combination of rules.",
                )
                self._living_cache = (result, None)
                return deepcopy(self._living_cache)
            if verdict["status"] != "no-difference":
                result.update(
                    status="conflict",
                    message="The remaining rules conflict on an example.",
                )
                self._living_cache = (result, None)
                return deepcopy(self._living_cache)
        for record, side in self._judgments():
            accepts = self._memberships(
                record["datum"], [program], record["observations"][side]
            )[0]
            positive = record["votes"][side] == "upvote"
            if positive and accepts:
                result["positive_votes"] += 1
            if accepts != positive:
                result["conflicts"].append({"question_id": record["id"], "side": side})
        if result["conflicts"]:
            result.update(
                status="conflict",
                message="Some earlier judgments still conflict with the combined spec.",
            )
        elif supported and result["positive_votes"] >= self.min_positive_votes:
            result.update(status="supported", message="Your spec is ready to use.")
        self._living_cache = (result, draft)
        return deepcopy(self._living_cache)

    @staticmethod
    def _question_key(candidate_ids, datum):
        return (tuple(sorted(candidate_ids)), json.dumps(datum, sort_keys=True))

    @_ready_method
    def next(self):
        """Find the next pair; bounded failure is never reported as equivalence."""
        return self._find_next()

    def _find_next(self):
        self._phase = "Finding a comparison…"
        self._prepared = True
        if self.paused:
            return None
        if self.current is not None:
            return deepcopy(self.current)
        ordered = sorted(self.survivors, key=lambda c: c.id != self.active_id)
        pairs = list(itertools.combinations(ordered, 2))
        # Give other program choices a turn before asking about more data for
        # an already-discussed pair. Judgments never settle that pair globally.
        pairs.sort(
            key=lambda pair: sum(
                set(record["candidate_ids"]) == {pair[0].id, pair[1].id}
                for record in self.history
            )
        )
        for a, b in pairs:

            def probe_datum(datum):
                if self._question_key((a.id, b.id), datum) in self._asked:
                    return False
                result = self._compare(datum, a.program, b.program)
                return result["status"] == "different"

            datum = next((d for d in self._datums if probe_datum(d)), None)
            if datum is None:
                obj = self.search.find(
                    self.cls,
                    lambda obj: probe_datum(self._datum(obj)),
                    max_examples=self.max_examples,
                )
                if obj is not None:
                    datum = self._datum(obj)
                    self.examples.append(obj)
                    self._datums.append(datum)
                    self._living_cache = None
            if datum is None:
                continue
            result = self._compare(datum, a.program, b.program)
            self.current = {
                "id": uuid.uuid4().hex,
                "candidate_ids": [a.id, b.id],
                "datum": datum,
                "programs": [a.program, b.program],
                "sides": result["sides"],
                "summaries": [a.summary, b.summary],
                "votes": [None, None],
            }
            return deepcopy(self.current)
        # PICK's confirmation fallback: one survivor is not a resolution without
        # positive evidence. Also seek support for a newly combined program.
        living, draft = self._living()
        confirmations = []
        if draft is not None and living["status"] != "supported":
            confirmations.append(
                ("combined:" + json.dumps(living["candidate_ids"]), draft.to_registry())
            )
        confirmations.extend(
            (c.id, c.program)
            for c in ordered
            if c.positive_votes < self.min_positive_votes
        )
        for identifier, program in confirmations:
            base = SpecDraft(self.cls, deepcopy(self._presentation)).to_registry()
            ids = [identifier, "confirmation"]

            def confirmation(datum):
                if self._question_key(ids, datum) in self._asked:
                    return False
                return (
                    self._compare(datum, program, program)["status"] == "no-difference"
                )

            datum = next((d for d in self._datums if confirmation(d)), None)
            if datum is None:
                obj = self.search.find(
                    self.cls,
                    lambda obj: confirmation(self._datum(obj)),
                    max_examples=self.max_examples,
                )
                if obj is not None:
                    datum = self._datum(obj)
                    self.examples.append(obj)
                    self._datums.append(datum)
                    self._living_cache = None
            if datum is None:
                continue
            contrast = self._compare(datum, program, base)
            sides = contrast.get("sides", [{"program": program}, {"program": program}])
            self.current = {
                "id": uuid.uuid4().hex,
                "candidate_ids": ids,
                "datum": datum,
                "programs": [program, base],
                "sides": sides,
                "summaries": ["Current proposal", "Alternative arrangement"],
                "votes": [None, None],
                "kind": "confirmation",
            }
            return deepcopy(self.current)
        return None

    @_ready_method
    def vote(self, side, value, *, question_id=None, layout_state=None):
        """Save one image's judgment immediately, including an unsure vote.

        A partial pair survives reloads and programmatic revision. Only after
        both images are rated does the session advance to another comparison.
        """
        if not isinstance(side, int) or isinstance(side, bool) or side not in (0, 1):
            raise ValueError("side must be 0 or 1")
        if not isinstance(value, str) or value not in {"upvote", "downvote", "unsure"}:
            raise ValueError("Choose upvote, downvote, or unsure.")
        if self.current is None or (
            question_id is not None and question_id != self.current["id"]
        ):
            raise ValueError(
                "This question is no longer current. Refresh the comparison."
            )
        if self.paused:
            raise ValueError("Resume the session before rating a new example.")
        existing = next(
            (r for r in self.history if r["id"] == self.current["id"]), None
        )
        if layout_state is None and value == "unsure" and existing is not None:
            layout_state = existing.get("layout_states", [None, None])[side]
        observation = None
        if layout_state is not None or value != "unsure":
            observation = observe(self.current["datum"], layout_state)
            # A vote must describe a valid displayed arrangement, not a failed
            # render, incomplete position list, or a different datum.
            if not self._memberships(
                self.current["datum"],
                [self.current["sides"][side]["program"]],
                observation,
            )[0]:
                raise ValueError(
                    "The displayed arrangement violates its rendering program."
                )
            self._memberships(
                self.current["datum"], [c.program for c in self.candidates], observation
            )
        record = next((r for r in self.history if r["id"] == self.current["id"]), None)
        if record is None:
            record = deepcopy(self.current)
            self.history.append(record)
        previous = record.get("observations", [None, None])[side]
        if (
            previous is not None
            and observation is not None
            and previous["signature"] != observation["signature"]
        ):
            # A newly explored arrangement is new evidence. Preserve the old
            # image and vote as a separate, editable history entry.
            archived = deepcopy(record)
            archived["id"] = uuid.uuid4().hex
            archived["votes"][1 - side] = None
            archived["complete"] = False
            archived["explored_from"] = record["id"]
            self.history.insert(self.history.index(record), archived)
        elif record["votes"][side] is not None and record["votes"][side] != value:
            record.setdefault("changes", []).append(
                {
                    "side": side,
                    "from": record["votes"][side],
                    "to": value,
                    "revision": self._revision + 1,
                }
            )
        record["votes"][side] = value
        self.current["votes"][side] = value
        self._revision += 1
        record.setdefault("vote_revisions", [0, 0])[side] = self._revision
        record.setdefault("observations", [None, None])[side] = observation
        if layout_state is not None:
            record.setdefault("layout_states", [None, None])[side] = deepcopy(
                layout_state
            )
            self.current.setdefault("layout_states", [None, None])[side] = deepcopy(
                layout_state
            )
        self._replay()
        record["complete"] = all(v is not None for v in record["votes"])
        if record["complete"]:
            self._asked.add(
                self._question_key(record["candidate_ids"], record["datum"])
            )
            self.current = None
            self._prepared = False
        return deepcopy(record)

    @_ready_method
    def reclassify(self, question_id, side, value):
        """Correct a saved judgment, replaying evidence and reviving candidates."""
        if type(side) is not int or side not in (0, 1):
            raise ValueError("side must be 0 or 1")
        if not isinstance(value, str) or value not in {"upvote", "downvote", "unsure"}:
            raise ValueError("Choose upvote, downvote, or unsure.")
        record = next((r for r in self.history if r["id"] == question_id), None)
        if record is None:
            raise ValueError("Unknown history entry.")
        if value != "unsure" and record.get("observations", [None, None])[side] is None:
            raise ValueError(
                "This example has no saved layout; judge it in the diagram view first."
            )
        record.setdefault("changes", []).append(
            {
                "side": side,
                "from": record["votes"][side],
                "to": value,
                "revision": self._revision + 1,
            }
        )
        record["votes"][side] = value
        self._revision += 1
        record.setdefault("vote_revisions", [0, 0])[side] = self._revision
        record["complete"] = all(v is not None for v in record["votes"])
        self._replay()
        self.current = None
        self._prepared = False
        self.paused = False
        return deepcopy(record)

    @_ready_method
    def judge(self, choice, explanation="", *, question_id=None, layout_states=None):
        """Programmatic convenience for rating both diagrams together."""
        choices = {
            "left": ["upvote", "downvote"],
            "right": ["downvote", "upvote"],
            "both": ["upvote", "upvote"],
            "neither": ["downvote", "downvote"],
            "unsure": ["unsure", "unsure"],
        }
        if not isinstance(choice, str) or choice not in choices:
            raise ValueError("Choose left, right, both, neither, or unsure.")
        if not isinstance(explanation, str) or len(explanation) > 10000:
            raise ValueError(
                "The explanation must be text of at most 10000 characters."
            )
        if layout_states is not None and (
            not isinstance(layout_states, list)
            or len(layout_states) != 2
            or any(not isinstance(s, dict) for s in layout_states)
        ):
            raise ValueError("Expected two displayed layout states.")
        for side, value in enumerate(choices[choice]):
            self.vote(
                side,
                value,
                question_id=question_id,
                layout_state=layout_states[side] if layout_states else None,
            )
        self.history[-1].update(choice=choice, explanation=explanation)
        return deepcopy(self.history[-1])

    @property
    def can_revise(self):
        return getattr(self.proposer, "can_revise", True)

    @_ready_method
    def revise(self, critique):
        if not self.can_revise:
            raise ValueError(
                "This proposer does not support natural-language revisions."
            )
        if (
            not isinstance(critique, str)
            or not critique.strip()
            or len(critique) > 10000
        ):
            raise ValueError("Write a correction of at most 10000 characters.")
        # A failed provider/repair call must leave a usable session and question.
        snapshot = (
            list(self.requests),
            deepcopy(self.rules),
            deepcopy(self.candidates),
            list(self.notes),
            list(self.examples),
            list(self._datums),
        )
        try:
            self.requests.append(critique.strip())
            self.rules.append({"text": critique.strip(), "origin": "user"})
            self._propose(critique.strip())
        except Exception:
            (
                self.requests,
                self.rules,
                self.candidates,
                self.notes,
                self.examples,
                self._datums,
            ) = snapshot
            self._replay()
            raise
        if len(self.candidates) > len(snapshot[2]):
            self.current = None
            self._prepared = False
        self.paused = False

    @_ready_method
    def finish(self, candidate_id=None):
        """Checkpoint and export a supported, consistent combined spec."""
        if candidate_id is not None:
            raise ValueError(
                "finish() combines supported survivors; it no longer selects a candidate ID."
            )
        result = self.done()
        if result["status"] != "supported":
            raise ValueError(result["message"])
        return self.draft

    @_ready_method
    def done(self):
        """End this round, retaining a resumable checkpoint even if unresolved."""
        if self.paused:
            return deepcopy(self.checkpoints[-1])
        result, _ = self._checked_living()
        result["message"] = "Saved. " + result["message"]
        result.update(
            revision=self._revision,
            history=deepcopy(self.history),
            candidates=[
                {
                    "id": c.id,
                    "summary": c.summary,
                    "program": c.program,
                    "positive_votes": c.positive_votes,
                    "negative_votes": c.negative_votes,
                    "eliminated": c.eliminated,
                }
                for c in self.candidates
            ],
        )
        self.checkpoints.append(deepcopy(result))
        self.paused = True
        return deepcopy(result)

    def _checked_living(self):
        """Check generated data once per living result, without ending the round."""
        result, draft = self._living()
        if (
            self._checked_living_cache is not None
            and self._checked_living_cache[0] is self._living_cache
        ):
            return deepcopy(self._checked_living_cache[1:])
        if draft is not None and result["status"] in {"supported", "draft"}:
            program = draft.to_registry()
            witness = self.search.find(
                self.cls,
                lambda obj: self._compare(self._datum(obj), program, program)["status"]
                != "no-difference",
                max_examples=self.max_examples,
            )
            if witness is not None:
                datum = self._datum(witness)
                if datum not in self._datums:
                    self.examples.append(witness)
                    self._datums.append(datum)
                result.update(
                    status="conflict",
                    message="Generated data exposed conflicting rules.",
                )
                draft = None
                self._living_cache = (result, draft)
        self._checked_living_cache = (self._living_cache, result, draft)
        return deepcopy((result, draft))

    @_ready_method
    def resume(self):
        """Continue this same spec and evidence after an 'I'm done' checkpoint."""
        self.paused = False
        self._prepared = self.current is not None
        return self

    @_ready_method
    def save(self, path):
        """Export the spec, candidates, datums, classifications and revisions as JSON."""
        from pathlib import Path

        result, _ = self._living()
        document = {
            "format_version": 1,
            "observation_version": 1,
            "spytial_core_version": SPYTIAL_CORE_VERSION,
            "target_name": self.cls.__name__,
            "current": result,
            "history": self.history,
            "checkpoints": self.checkpoints,
            "datums": self._datums,
            "question": self.current,
            "paused": self.paused,
            "revision": self._revision,
            "requests": self.requests,
            "rules": self.rules,
            "candidates": [
                {
                    "id": c.id,
                    "summary": c.summary,
                    "program": c.program,
                    "positive_votes": c.positive_votes,
                    "negative_votes": c.negative_votes,
                    "eliminated": c.eliminated,
                }
                for c in self.candidates
            ],
            "settings": {
                "elimination_threshold": self.elimination_threshold,
                "min_positive_votes": self.min_positive_votes,
                "max_candidates": self.max_candidates,
            },
        }
        Path(path).write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")

    @classmethod
    def load(
        cls, target, path, *, proposer=None, search=None, strategy=None, max_examples=20
    ):
        """Restore a saved living spec without asking the model for fresh drafts."""
        from pathlib import Path

        saved = json.loads(Path(path).read_text())
        if not isinstance(saved, dict) or saved.get("format_version") != 1:
            raise ValueError("Unsupported suggest session format.")
        if saved.get("observation_version") != 1:
            raise ValueError("Unsupported layout observation format.")
        target_cls = target if isinstance(target, type) else type(target)
        if saved.get("target_name") != target_cls.__name__:
            raise ValueError("The saved session belongs to a different class.")
        return cls(
            target,
            proposer=proposer,
            search=search,
            strategy=strategy,
            max_examples=max_examples,
            _saved=saved,
            **saved["settings"],
        )

    def _restore(self, saved):
        from ._model import Suggestion

        self._datums = deepcopy(saved["datums"])
        if not self._datums:
            raise ValueError("A saved session needs data instances.")
        self.candidates = []
        for item in saved["candidates"]:
            rows = []
            for entry in item["program"]["constraints"] + item["program"]["directives"]:
                kind, kwargs = next(iter(entry.items()))
                rows.append(
                    Suggestion(
                        kind,
                        {"name": kwargs} if kind == "flag" else kwargs,
                        "high",
                        enabled_by_default=True,
                        source="proposal",
                    )
                )
            self.candidates.append(
                ProgramCandidate(item["id"], item["summary"], SpecDraft(self.cls, rows))
            )
        if not self.candidates:
            raise ValueError("A saved session needs candidate programs.")
        self._presentation = deepcopy(
            [
                s
                for s in self.candidates[0].draft.enabled()
                if s.directive not in _POSITIONAL
            ]
        )
        self.base = SpecDraft(self.cls, deepcopy(self._presentation))
        self.history = deepcopy(saved["history"])
        # Rebuild observations from saved coordinates; never trust cached scores
        # or membership vectors as evidence after loading.
        for record in self.history:
            for side, state in enumerate(record.get("layout_states", [None, None])):
                record.setdefault("observations", [None, None])[side] = None
                if state is not None:
                    record["observations"][side] = observe(record["datum"], state)
                elif record["votes"][side] in {"upvote", "downvote"}:
                    raise ValueError("A saved definite judgment is missing its layout.")
            if record.get("complete"):
                self._asked.add(
                    self._question_key(record["candidate_ids"], record["datum"])
                )
        self._revision = saved["revision"]
        self.requests = list(saved["requests"])
        self.rules = deepcopy(saved["rules"])
        self.checkpoints = deepcopy(saved["checkpoints"])
        self.paused = bool(saved["paused"])
        self.current = deepcopy(saved["question"])
        self._replay()

    def show(self):
        import webbrowser

        webbrowser.open(self._url())
        return self

    def _url(self):
        with self._server_lock:
            if self._closed:
                raise RuntimeError("This session is closed.")
            if self._server is None:
                from ._session_server import SessionServer

                self._server = SessionServer(self)
            return self._server.url

    def _repr_html_(self):
        import html

        return f'<iframe title="Diagram comparisons" src="{html.escape(self._url(), quote=True)}" style="width:100%;height:450px;border:0"></iframe>'

    def close(self):
        with self._server_lock:
            self._closed = True
            if self._server is not None:
                self._server.close()
                self._server = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __repr__(self):
        state = "ready" if self._ready.is_set() else "preparing"
        return f"<SuggestSession {self.cls.__name__}: {state}>"

"""Coordinate requirement proposals, contextual diagrams, and enduring judgments."""

from __future__ import annotations

from copy import deepcopy
from functools import wraps
import json
import threading
import uuid

from ..core_assets import SPYTIAL_CORE_VERSION
from ..provider_system import CnDDataInstanceBuilder
from ..annotations import SpecUnavailableError
from ._checks import ProgramChecks
from ._evidence import observe
from ._history import JudgmentHistory, validate_vote
from ._living import LivingSpec
from ._model import SpecDraft
from ._policy import combine, consistent, replay_candidates, supported
from ._requirement import RequirementState, Requirement
from ._proposals import (
    ProgramCandidate,
    PROPOSAL_SCHEMA,
    proposal_prompt,
    validate_operations,
)
from ._search import HypothesisSearch
from ._questions import find_question, make_question, question_key
from ._enrich_from_examples import _vocabulary
from .providers import Codex, as_provider


def _ready_method(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        self.wait()
        with self._operation_lock:
            if self._closed:
                raise RuntimeError(
                    "This session is closed. Load a saved session to continue."
                )
            return method(self, *args, **kwargs)

    return call


def _text(prompt):
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 10000:
        raise ValueError("Describe one requirement in at most 10000 characters.")
    return prompt.strip()


class SuggestSession:
    """Start with data; add and revisit one visualization requirement at a time.

    Display the session before requesting a requirement. Startup prepares data only.
    Each requirement's candidates contain its own rules; comparisons render them
    together with all other accepted requirements. A completed round combines all supported survivors.
    """

    def __init__(
        self,
        target,
        *,
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

        for name, value, maximum in (
            ("max_examples", max_examples, 200),
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
        if search is not None and strategy is not None:
            raise ValueError("Pass search= or strategy=, not both.")
        self.cls = target if isinstance(target, type) else type(target)
        self.max_examples = max_examples
        self.elimination_threshold = elimination_threshold
        self.min_positive_votes = min_positive_votes
        self.max_candidates = max_candidates
        self.search = (
            search
            if search is not None
            else HypothesisSearch("auto" if strategy is None else strategy)
        )
        if not all(
            callable(getattr(self.search, m, None)) for m in ("initial", "find")
        ):
            raise TypeError("search must implement initial() and find()")
        self.examples = _coerce_examples(examples, None)
        sample = (
            instance
            if instance is not None
            else (None if isinstance(target, type) else target)
        )
        if sample is not None:
            self.examples.insert(0, sample)
        self._proposer_spec, self.proposer = proposer, None
        self._registry, self._saved = registry, _saved
        self._requirements = []
        self.active_requirement_id = None
        self._history = JudgmentHistory()
        self._checks = ProgramChecks()
        self._spec = LivingSpec(self)
        self._living_cache = None
        self._living_checked = False
        self.notes, self.checkpoints = [], []
        self.paused = False
        self.current = None
        self._asked = set()
        self._ready = threading.Event()
        self._operation_lock = threading.RLock()
        self._server_lock = threading.Lock()
        self._server = None
        self._closed = self._prepared = self._search_pending = False
        self._error = None
        self._phase = "Preparing examples…"
        threading.Thread(target=self._initialize_job, daemon=True).start()

    def _initialize_job(self):
        with self._operation_lock:
            try:
                if self._closed:
                    return
                self._initialize()
                self._find_next()
            except Exception as exc:
                self._error = exc
            finally:
                self._ready.set()

    def _initialize(self):
        if self._saved is not None:
            self._restore(self._saved)
            self._saved = None
            return
        from ._draft import suggest_draft

        witness = self.search.initial(self.cls, max_examples=self.max_examples)
        if witness is not None:
            self.examples.append(witness)
        if not self.examples:
            raise ValueError("Supply examples or a strategy that can build this class.")
        self._datums = [self._datum(obj) for obj in self.examples]
        draft = suggest_draft(
            self.cls, instance=self.examples[0], registry=self._registry
        )
        self._presentation = SpecDraft(
            self.cls,
            [
                deepcopy(s)
                for s in draft.enabled()
                if s.directive not in {"orientation", "align", "cyclic", "group"}
            ],
        )

    def wait(self, timeout=None):
        if not self._ready.wait(timeout):
            raise TimeoutError("The suggestion session is still preparing.")
        if self._error is not None:
            raise self._error
        return self

    @property
    def requirements(self):
        return [Requirement(self, p.id) for p in self._requirements]

    @property
    def active_requirement(self):
        return (
            Requirement(self, self.active_requirement_id)
            if self.active_requirement_id
            else None
        )

    def _requirement(self, requirement_id=None):
        identifier = (
            requirement_id if requirement_id is not None else self.active_requirement_id
        )
        prop = next((p for p in self._requirements if p.id == identifier), None)
        if prop is None:
            raise ValueError("Unknown requirement. Add a requirement first.")
        return prop

    @property
    def candidates(self):
        return self._requirement().candidates if self.active_requirement_id else []

    @property
    def survivors(self):
        return self._requirement().survivors if self.active_requirement_id else []

    @property
    def history(self):
        return self._history.records

    @property
    def spec(self):
        return self._spec

    def apply(self):
        return self.spec.apply()

    @property
    def draft(self):
        return self.spec.snapshot()

    def _background(self, excluding=None):
        return combine(
            self.cls,
            self._presentation,
            *(
                c.draft
                for p in self._requirements
                if p.id != excluding
                for c in p.accepted
            ),
        )

    def _judgments(self, prop):
        return self._history.effective(prop.id)

    def _choice(self, prop):
        pool = supported(prop, self.min_positive_votes)
        draft = combine(self.cls, self._presentation, *(c.draft for c in pool))
        return pool, draft

    def _requirement_result(self, prop):
        pool, draft = self._choice(prop)
        status, message = "draft", "Keep judging, or save this requirement for later."
        if prop.accepted:
            status, message = "accepted", "Requirement accepted."
        elif not prop.survivors:
            status, message = (
                "empty",
                "No candidates remain. Correct history or revise this requirement.",
            )
        elif pool:
            try:
                agrees = consistent(
                    draft.to_registry(),
                    self._judgments(prop),
                    self._checks,
                    self.min_positive_votes,
                )
            except ValueError as exc:
                status, message = "unsupported", str(exc)
            else:
                if agrees:
                    status, message = (
                        "ready",
                        "Supported interpretations are ready to combine.",
                    )
                else:
                    status, message = (
                        "conflict",
                        "The supported interpretations conflict with this requirement's judgments.",
                    )
        if prop.diagnostic:
            status, message = "conflict", prop.diagnostic
        return {
            "id": prop.id,
            "prompt": prop.prompt,
            "revision": prop.revision,
            "status": status,
            "message": message,
            "accepted_ids": list(prop.accepted_ids),
            "survivor_ids": [c.id for c in prop.survivors],
            "supported_ids": [c.id for c in pool],
        }

    def _reset_question(self):
        self.current = None
        self._prepared = False

    def _invalidate_result(self):
        self._living_cache = None
        self._living_checked = False

    def _replay(self):
        for prop in self._requirements:
            judgments = self._judgments(prop)
            replay_candidates(
                prop.candidates, judgments, self._checks, self.elimination_threshold
            )
            prop.diagnostic = ""
            eligible = {c.id for c in supported(prop, self.min_positive_votes)}
            prop.accepted_ids = [
                identifier for identifier in prop.accepted_ids if identifier in eligible
            ]
            if prop.accepted:
                draft = combine(
                    self.cls, self._presentation, *(c.draft for c in prop.accepted)
                )
                if not consistent(
                    draft.to_registry(),
                    judgments,
                    self._checks,
                    self.min_positive_votes,
                ):
                    prop.accepted_ids = []
        self._invalidate_result()

    def _check_program(self, program, *, generated):
        for datum in self._datums:
            if not self._checks.feasible(datum, program):
                raise SpecUnavailableError(
                    "These requirements conflict on a retained example."
                )
        if (
            generated
            and self._find_generated(lambda d: not self._checks.feasible(d, program))
            is not None
        ):
            raise SpecUnavailableError(
                "Generated data exposed conflicting requirements."
            )

    def _resolve(self, *, generated=False):
        if self._living_cache is None:
            draft = self._background()
            accepted = [p.id for p in self._requirements if p.accepted]
            result = {
                "status": "supported" if accepted else "empty",
                "requirement_ids": accepted,
                "program": draft.to_registry() if accepted else None,
                "message": (
                    "Accepted requirements are ready to use."
                    if accepted
                    else "Accept a requirement before using the living spec."
                ),
            }
            self._living_cache = result, draft if accepted else None
        if generated and not self._living_checked:
            result, draft = self._living_cache
            if draft is not None:
                try:
                    self._check_program(draft.to_registry(), generated=True)
                except (SpecUnavailableError, ValueError) as exc:
                    result.update(status="conflict", message=str(exc))
                    draft = None
            self._living_cache, self._living_checked = (result, draft), True
        return deepcopy(self._living_cache)

    def _datum(self, obj):
        if not isinstance(obj, self.cls):
            raise ValueError(f"Examples must be instances of {self.cls.__name__}.")
        return CnDDataInstanceBuilder(
            infer_variable_names=False, collect_annotations=False
        ).build_instance(obj)

    def _find_generated(self, predicate):
        obj = self.search.find(
            self.cls,
            lambda obj: predicate(self._datum(obj)),
            max_examples=self.max_examples,
        )
        if obj is None:
            return None
        datum = self._datum(obj)
        if datum not in self._datums:
            self.examples.append(obj)
            self._datums.append(datum)
            self._invalidate_result()
        return datum

    def _propose(self, prop):
        if self.proposer is None:
            self.proposer = as_provider(
                Codex() if self._proposer_spec is None else self._proposer_spec
            )
        vocab = _vocabulary(self._datums)
        background = self._background(prop.id)
        prompt = proposal_prompt(
            self.cls,
            vocab,
            prop,
            background.to_registry(),
            [r for r in self.history if r["requirement_id"] == prop.id],
        )
        failures = []
        for attempt in range(2):
            self._phase = "Drafting requirement interpretations…"
            response = self.proposer(
                prompt + "\nValidation feedback: " + "; ".join(failures),
                schema=PROPOSAL_SCHEMA,
            )
            if not isinstance(response, dict) or not isinstance(
                response.get("programs"), list
            ):
                raise ValueError(
                    "The model did not return requirement interpretations."
                )
            for raw in response["programs"][:4]:
                if len(prop.candidates) >= self.max_candidates:
                    break
                try:
                    geometry = validate_operations(
                        raw["operations"], vocab, self._datums
                    )
                    if (
                        not isinstance(raw["summary"], str)
                        or not raw["summary"].strip()
                    ):
                        raise ValueError("An interpretation needs a readable summary.")
                    draft = combine(
                        self.cls, self._presentation, SpecDraft(self.cls, geometry)
                    )
                    if any(c.program == draft.to_registry() for c in prop.candidates):
                        continue
                    self._phase = "Checking requirement interpretations…"
                    self._check_program(
                        combine(self.cls, background, draft).to_registry(),
                        generated=True,
                    )
                    prop.candidates.append(
                        ProgramCandidate(uuid.uuid4().hex, raw["summary"], draft)
                    )
                except (ValueError, KeyError, TypeError, SpecUnavailableError) as exc:
                    failures.append(str(exc))
            if len(prop.candidates) >= min(2, self.max_candidates) or not failures:
                break
        self.notes.extend(failures)
        if not prop.candidates:
            raise ValueError("No usable interpretations. " + "; ".join(failures))
        self._replay()

    @_ready_method
    def add_examples(self, examples):
        """Retain additional data without dropping requirements or classifications."""
        from ._draft import _coerce_examples

        values = _coerce_examples(examples, None)
        datums = [self._datum(obj) for obj in values]
        for obj, datum in zip(values, datums):
            if datum not in self._datums:
                self.examples.append(obj)
                self._datums.append(datum)
        self._invalidate_result()
        self._reset_question()
        return self

    @_ready_method
    def add_requirement(self, prompt):
        """Propose interpretations of one new requirement; keep accepted rules active."""
        prop = RequirementState(uuid.uuid4().hex, _text(prompt))
        self._requirements.append(prop)
        try:
            self._propose(prop)
        except Exception:
            self._requirements.remove(prop)
            self._invalidate_result()
            raise
        self.active_requirement_id, self.paused = prop.id, False
        self._reset_question()
        self._find_next()
        return Requirement(self, prop.id)

    @_ready_method
    def edit_requirement(self, requirement_id, prompt):
        """Replace this requirement's candidates and replay its enduring evidence.

        Its old definition is withdrawn while edited. Other accepted requirements
        remain in the live spec and in the comparison background.
        """
        prop = self._requirement(requirement_id)
        prompt = _text(prompt)
        if self.proposer is not None and not getattr(self.proposer, "can_revise", True):
            raise ValueError(
                "This proposer does not support natural-language revisions."
            )
        old = deepcopy(prop)
        prop.revisions.append(
            {
                "prompt": prop.prompt,
                "revision": prop.revision,
                "accepted_ids": list(prop.accepted_ids),
                "candidates": [c.to_record() for c in prop.candidates],
            }
        )
        prop.prompt, prop.revision = prompt, prop.revision + 1
        prop.candidates, prop.accepted_ids, prop.diagnostic = [], [], ""
        try:
            self._propose(prop)
        except Exception:
            self._requirements[self._requirements.index(prop)] = old
            self._invalidate_result()
            raise
        self.active_requirement_id, self.paused = prop.id, False
        self._reset_question()
        self._find_next()
        return Requirement(self, prop.id)

    def _accept(self, prop):
        # Completion replaces this requirement definition, including on failure.
        prop.accepted_ids = []
        self._invalidate_result()
        pool, draft = self._choice(prop)
        if not pool:
            raise SpecUnavailableError(
                "This requirement needs positive evidence before use."
            )
        if not consistent(
            draft.to_registry(),
            self._judgments(prop),
            self._checks,
            self.min_positive_votes,
        ):
            raise SpecUnavailableError(
                "The supported interpretations conflict with this requirement's judgments."
            )
        program = combine(self.cls, self._background(prop.id), draft).to_registry()
        self._check_program(program, generated=True)
        prop.accepted_ids, prop.diagnostic = [c.id for c in pool], ""
        self._invalidate_result()

    @_ready_method
    def accept(self, requirement_id=None):
        """Combine all supported survivors, after history and feasibility checks."""
        prop = self._requirement(requirement_id)
        self._accept(prop)
        self._reset_question()
        if self.active_requirement_id == prop.id:
            self.paused = True
        return Requirement(self, prop.id)

    def _try_accept(self, *, converged=False):
        prop = self._requirement()
        if converged and len(prop.survivors) != 1:
            return
        if not supported(prop, self.min_positive_votes):
            return
        try:
            self._accept(prop)
        except (SpecUnavailableError, ValueError) as exc:
            prop.diagnostic = str(exc)
        else:
            self.paused = True

    def _find_datum(self, prop, ids, predicate):
        def unasked(datum):
            question = make_question(
                prop, self._background(prop.id), ids, datum, [], [], []
            )
            return question_key(question) not in self._asked and predicate(datum)

        datum = next((d for d in self._datums if unasked(d)), None)
        return datum if datum is not None else self._find_generated(unasked)

    @_ready_method
    def next(self):
        return self._find_next()

    def _find_next(self):
        self._prepared = True
        if self.paused or not self.active_requirement_id:
            return None
        if self.current is not None:
            return deepcopy(self.current)
        prop = self._requirement()
        self.current = find_question(
            prop,
            self._background(prop.id),
            self._checks,
            lambda ids, predicate: self._find_datum(prop, ids, predicate),
        )
        return deepcopy(self.current)

    @_ready_method
    def vote(self, side, value, *, question_id=None, layout_state=None):
        """Save one image's judgment immediately, including an unsure vote.

        A partial pair survives reloads and programmatic revision. Only after
        both images are rated does the session advance to another comparison.
        """
        return deepcopy(self._record_votes([(side, value, layout_state)], question_id))

    def _record_votes(self, votes, question_id):
        """Validate the whole update, then record it and advance once."""
        for side, value, _ in votes:
            validate_vote(side, value)
        if self.current is None or (
            question_id is not None and question_id != self.current["id"]
        ):
            raise ValueError(
                "This question is no longer current. Refresh the comparison."
            )
        if self.paused:
            raise ValueError("Resume the session before rating a new example.")
        existing = self._history.get(self.current["id"])
        prepared = []
        for side, value, layout_state in votes:
            if layout_state is None and value == "unsure" and existing is not None:
                layout_state = existing.get("layout_states", [None, None])[side]
            observation = None
            if layout_state is not None or value != "unsure":
                observation = observe(self.current["datum"], layout_state)
                # No vote changes until every layout and membership check succeeds.
                if not self._checks.memberships(
                    self.current["datum"],
                    [self.current["sides"][side]["program"]],
                    observation,
                )[0]:
                    raise ValueError(
                        "The displayed arrangement violates its rendering program."
                    )
                self._checks.memberships(
                    self.current["datum"],
                    [c.program for c in self.candidates],
                    observation,
                )
            prepared.append((side, value, observation, layout_state))
        for side, value, observation, layout_state in prepared:
            record = self._history.record(
                self.current, side, value, observation, layout_state
            )
            self.current["votes"][side] = value
            if layout_state is not None:
                self.current.setdefault("layout_states", [None, None])[side] = deepcopy(
                    layout_state
                )
        self._replay()
        if record["complete"]:
            self._asked.add(question_key(record))
            self.current = None
            self._prepared = False
            self._try_accept(converged=True)
        return record

    @_ready_method
    def reclassify(self, question_id, side, value):
        """Correct a saved judgment, replaying evidence and reviving candidates."""
        record = self._history.reclassify(question_id, side, value)
        self._replay()
        self.active_requirement_id = record["requirement_id"]
        self._reset_question()
        self.paused = False
        return deepcopy(record)

    @_ready_method
    def judge(self, choice, explanation="", *, question_id=None, layout_states=None):
        """Validate both diagrams before saving either judgment or advancing."""
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
        record = self._record_votes(
            [
                (side, value, layout_states[side] if layout_states else None)
                for side, value in enumerate(choices[choice])
            ],
            question_id,
        )
        record.update(choice=choice, explanation=explanation)
        return deepcopy(record)

    @_ready_method
    def done(self):
        """End the round and combine all supported survivors when they agree with history."""
        if self.active_requirement_id:
            self._try_accept()
            result = self._requirement_result(self._requirement())
        else:
            result = {
                "status": "empty",
                "message": "No requirement has been requested.",
            }
        checkpoint = {
            **result,
            "history_revision": self._history.revision,
            "spec": self._resolve(generated=True)[0],
        }
        if not self.checkpoints or checkpoint != self.checkpoints[-1]:
            self.checkpoints.append(deepcopy(checkpoint))
        self.paused = True
        return deepcopy(checkpoint)

    @_ready_method
    def resume(self, requirement_id=None):
        identifier = (
            self._requirement(requirement_id).id
            if requirement_id is not None
            else self.active_requirement_id
        )
        if identifier != self.active_requirement_id:
            self._reset_question()
        self.active_requirement_id = identifier
        self.paused = False
        self._prepared = self.current is not None
        return self

    @_ready_method
    def finish(self):
        """Checkpoint the round and return a fixed copy of accepted requirements."""
        self.done()
        return self.spec.snapshot()

    def _preview(self):
        program = self._background().to_registry()
        return {
            "id": "preview:" + json.dumps(program, sort_keys=True),
            "kind": "preview",
            "datum": self._datums[0],
            "sides": [{"program": program}],
            "votes": [None, None],
        }

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
        if self._closed:
            return {"status": "closed", "message": "Controls closed.", "question": None}
        if not self._ready.is_set() or not self._operation_lock.acquire(blocking=False):
            return {"status": "loading", "message": self._phase, "question": None}
        try:
            if self._error is not None:
                return {
                    "status": "error",
                    "message": str(self._error),
                    "question": None,
                }
            state = {
                "requirements": [
                    self._requirement_result(p) for p in self._requirements
                ],
                "active_requirement_id": self.active_requirement_id,
            }
            if not self.active_requirement_id:
                return {
                    **state,
                    "status": "idle",
                    "message": "",
                    "question": self._preview(),
                }
            if self.paused:
                prop = self._requirement_result(self._requirement())
                return {
                    **state,
                    "status": "paused",
                    "message": prop["message"],
                    "question": (
                        deepcopy(self.current)
                        if self.current and not self._requirement().accepted
                        else self._preview()
                    ),
                }
            if not self._prepared:
                if not self._search_pending:
                    self._search_pending = True
                    self._phase = "Finding a comparison…"
                    threading.Thread(target=self._search_job, daemon=True).start()
                return {
                    **state,
                    "status": "loading",
                    "message": self._phase,
                    "question": None,
                }
            return {
                **state,
                "status": "ready" if self.current else "empty",
                "message": (
                    ""
                    if self.current
                    else "No further comparison found. Add data, revise this requirement, or save it for later."
                ),
                "question": deepcopy(self.current) if self.current else self._preview(),
            }
        finally:
            self._operation_lock.release()

    @_ready_method
    def save(self, path):
        from pathlib import Path

        document = {
            "format_version": 3,
            "observation_version": 1,
            "spytial_core_version": SPYTIAL_CORE_VERSION,
            "target_name": self.cls.__name__,
            "presentation": self._presentation.to_registry(),
            "requirements": [p.to_record() for p in self._requirements],
            "active_requirement_id": self.active_requirement_id,
            "history": self.history,
            "history_revision": self._history.revision,
            "checkpoints": self.checkpoints,
            "datums": self._datums,
            "question": self.current,
            "paused": self.paused,
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
        from pathlib import Path

        saved = json.loads(Path(path).read_text())
        if not isinstance(saved, dict) or saved.get("format_version") != 3:
            raise ValueError(
                "This session requires the requirement-based save format (version 3)."
            )
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
        self._datums = deepcopy(saved["datums"])
        if not self._datums:
            raise ValueError("A saved session needs data instances.")
        self._presentation = ProgramCandidate.from_record(
            self.cls,
            {"id": "presentation", "summary": "", "program": saved["presentation"]},
        ).draft
        self._requirements = [
            RequirementState.from_record(self.cls, p) for p in saved["requirements"]
        ]
        if len({p.id for p in self._requirements}) != len(self._requirements):
            raise ValueError("Saved requirement IDs must be unique.")
        self.active_requirement_id = saved["active_requirement_id"]
        if self.active_requirement_id is not None:
            self._requirement()
        self._history = JudgmentHistory.restore(
            saved["history"], saved["history_revision"]
        )
        if any(
            r["requirement_id"] not in {p.id for p in self._requirements}
            for r in self.history
        ):
            raise ValueError("A saved judgment refers to an unknown requirement.")
        self.checkpoints = deepcopy(saved["checkpoints"])
        self.paused = bool(saved["paused"])
        self._asked = {question_key(r) for r in self.history if r.get("complete")}
        self.current = deepcopy(saved["question"])
        self._replay()
        if self.current is not None:
            prop = self._requirement(self.current["requirement_id"])
            if (
                prop.id != self.active_requirement_id
                or prop.revision != self.current["requirement_revision"]
                or self.current["context"] != self._background(prop.id).to_registry()
            ):
                self.current = None

    def show(self):
        import webbrowser

        webbrowser.open(self._url())
        return self

    def _url(self):
        with self._server_lock:
            if self._closed:
                raise RuntimeError(
                    "This session is closed. Load a saved session to continue."
                )
            if self._server is None:
                from ._session_server import SessionServer

                self._server = SessionServer(self)
            return self._server.url

    def _repr_html_(self):
        import html

        return f'<iframe title="Diagram requirements" src="{html.escape(self._url(), quote=True)}" style="width:100%;height:560px;border:0"></iframe>'

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
        state = (
            "closed"
            if self._closed
            else "ready" if self._ready.is_set() else "preparing"
        )
        return f"<SuggestSession {self.cls.__name__}: {state}>"

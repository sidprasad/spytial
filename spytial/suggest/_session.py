"""An example-first conversation over complete candidate Spytial programs.

Judgments belong to displayed scenarios. They do not silently become universal
rules, eliminate programs, or establish equivalence after bounded search.
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
from ._compare import compare
from ._enrich_from_examples import _vocabulary
from ._model import SpecDraft
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
            if not self._prepared:
                if not self._search_pending:
                    self._search_pending = True
                    self._phase = "Finding a comparison…"
                    threading.Thread(target=self._search_job, daemon=True).start()
                return {"status": "loading", "message": self._phase, "question": None}
            return {
                "status": "ready" if self.current is not None else "empty",
                "message": (
                    "" if self.current is not None else "No further comparison found."
                ),
                "question": deepcopy(self.current),
            }
        finally:
            self._operation_lock.release()

    def _datum(self, obj):
        if not isinstance(obj, self.cls):
            raise ValueError(f"Examples must be instances of {self.cls.__name__}.")
        return CnDDataInstanceBuilder(infer_variable_names=False).build_instance(obj)

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
            if len(self.candidates) - before >= 2 or not failures:
                break
        self.notes.extend(failures)
        if len(self.candidates) == before:
            self.notes.append(
                "No new usable programs were produced; existing choices and judgments were kept."
            )

    @property
    def draft(self):
        return self.finish()

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
        if self.current is not None:
            return deepcopy(self.current)
        ordered = sorted(self.candidates, key=lambda c: c.id != self.active_id)
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

            def probe(obj):
                datum = self._datum(obj)
                if self._question_key((a.id, b.id), datum) in self._asked:
                    return False
                result = self._compare(datum, a.program, b.program)
                return result["status"] == "different"

            obj = next((obj for obj in self.examples if probe(obj)), None)
            if obj is None:
                obj = self.search.find(self.cls, probe, max_examples=self.max_examples)
            if obj is None:
                continue
            datum = self._datum(obj)
            if datum not in self._datums:
                self.examples.append(obj)
                self._datums.append(datum)
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
        if layout_state is not None and not isinstance(layout_state, dict):
            raise ValueError("Expected a displayed layout state.")
        record = next((r for r in self.history if r["id"] == self.current["id"]), None)
        if record is None:
            record = deepcopy(self.current)
            self.history.append(record)
        record["votes"][side] = value
        self.current["votes"][side] = value
        if layout_state is not None:
            record.setdefault("layout_states", [None, None])[side] = deepcopy(
                layout_state
            )
        record["complete"] = all(v is not None for v in record["votes"])
        if record["complete"]:
            self._asked.add(
                self._question_key(record["candidate_ids"], record["datum"])
            )
            if record["votes"] in (["upvote", "downvote"], ["downvote", "upvote"]):
                self.active_id = record["candidate_ids"][
                    record["votes"].index("upvote")
                ]
            self.current = None
            self._prepared = False
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
            list(self.candidates),
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
            raise
        if len(self.candidates) > len(snapshot[2]):
            self.current = None
            self._prepared = False

    @_ready_method
    def finish(self, candidate_id=None):
        """Return an explicitly chosen draft; does not decorate the class."""
        candidate = next(
            (c for c in self.candidates if c.id == (candidate_id or self.active_id)),
            None,
        )
        if candidate is None:
            raise ValueError("Unknown candidate program.")
        if candidate_id is not None:
            self.active_id = candidate.id
        return deepcopy(candidate.draft)

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

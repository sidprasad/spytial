"""Replaceable example search. Layout checking remains in spytial-core."""

from typing import Any, Callable, Optional, Protocol
import math
import time


class _SearchLimit(BaseException):
    """Stop Hypothesis without turning budget exhaustion into a failing example."""


class _CheckFailed(BaseException):
    def __init__(self, error):
        self.error = error


class ExampleSearch(Protocol):
    """Return a seed and search for a value satisfying a supplied predicate.

    Return None only when no value was found. Generation errors must propagate.
    Values must be instances of cls; max_examples bounds each search invocation.
    Implementations need not use Hypothesis or know any Spytial semantics.
    """

    def initial(self, cls: type, *, max_examples: int) -> Optional[Any]: ...

    def find(
        self, cls: type, predicate: Callable[[Any], bool], *, max_examples: int
    ) -> Optional[Any]: ...


class FixedExamples:
    """Explicit ablation: check and compare only the session's supplied examples."""

    def initial(self, cls, *, max_examples):
        return None

    def find(self, cls, predicate, *, max_examples):
        return None


class HypothesisSearch:
    """Generate and shrink examples, deriving a strategy from the class by default.

    find() bounds expensive predicate calls, including shrinking, by max_examples.
    max_seconds stops starting new checks; it does not interrupt a running predicate.
    A checked witness survives an unfinished shrink. last_run exposes this budget.
    """

    def __init__(self, strategy="auto", *, max_seconds=5):
        if (
            isinstance(max_seconds, bool)
            or not math.isfinite(max_seconds)
            or max_seconds <= 0
        ):
            raise ValueError("max_seconds must be a finite positive number.")
        self.strategy = strategy
        self.max_seconds = max_seconds
        self.last_run = None

    def _api(self):
        try:
            from hypothesis import find, settings, strategies
            from hypothesis.errors import NoSuchExample
        except ImportError as exc:
            raise RuntimeError(
                "suggest needs Hypothesis. Install spytial_diagramming[suggest-search] "
                "or explicitly supply another search backend, such as FixedExamples()."
            ) from exc
        return find, settings, strategies, NoSuchExample

    def _source(self, cls, strategies):
        if isinstance(self.strategy, str):
            if self.strategy != "auto":
                raise ValueError("strategy must be 'auto' or a Hypothesis strategy")
            return strategies.from_type(cls)
        return self.strategy

    def initial(self, cls, *, max_examples):
        from ._strategy import find_witness
        from .introspect import build_class_info

        _, _, strategies, _ = self._api()
        return find_witness(
            cls,
            build_class_info(cls),
            self._source(cls, strategies),
            max_examples=max_examples,
        )

    def find(self, cls, predicate, *, max_examples):
        find, settings, strategies, no_example = self._api()
        start, checks, witness, limited = time.monotonic(), 0, None, False

        def bounded(obj):
            nonlocal checks, witness, limited
            if checks >= max_examples or time.monotonic() - start >= self.max_seconds:
                limited = True
                raise _SearchLimit()
            checks += 1
            try:
                found = predicate(obj)
            except Exception as exc:
                # Hypothesis retries exceptions. A retry could exhaust our budget
                # and conceal the original checker failure, so leave immediately.
                raise _CheckFailed(exc) from exc
            if found:
                witness = obj
                return True
            return False

        try:
            return find(
                self._source(cls, strategies),
                bounded,
                settings=settings(
                    max_examples=max_examples,
                    database=None,
                    deadline=None,
                    derandomize=True,
                ),
            )
        except no_example:
            return None
        except _SearchLimit:
            # Keep a checked witness even if its shrinking did not finish.
            return witness
        except _CheckFailed as exc:
            raise exc.error
        finally:
            self.last_run = {
                "checks": checks,
                "seconds": time.monotonic() - start,
                "limited": limited,
                "found": witness is not None,
            }

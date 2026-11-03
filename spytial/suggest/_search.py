"""Replaceable example search. Layout checking remains in spytial-core."""

from typing import Any, Callable, Optional, Protocol


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
    """Generate and shrink examples, deriving a strategy from the class by default."""

    def __init__(self, strategy="auto"):
        self.strategy = strategy

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
        try:
            return find(
                self._source(cls, strategies),
                predicate,
                settings=settings(
                    max_examples=max_examples,
                    database=None,
                    deadline=None,
                    derandomize=True,
                ),
            )
        except no_example:
            return None

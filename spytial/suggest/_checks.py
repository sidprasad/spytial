"""Session-local caches around the released core checks. No voting policy."""

import json

from ._compare import compare
from ._evidence import membership
from ._runtime import CoreRuntime


def _store(cache, key, value, limit):
    if len(cache) >= limit:
        cache.pop(next(iter(cache)))
    cache[key] = value


class ProgramChecks:
    def __init__(self):
        self._comparisons = {}
        self._memberships = {}
        self._selectors = {}
        self._runtime = CoreRuntime()

    def _run(self, cases, *, timeout):
        from .._conformance import run_cases

        runner = self._runtime.run_cases if self._runtime else run_cases
        return runner(cases, timeout=timeout)

    def selectors(self, datum, selectors):
        from ._eval import evaluate_selectors

        keys = [json.dumps([datum, selector], sort_keys=True) for selector in selectors]
        missing = {
            key: selector
            for key, selector in zip(keys, selectors)
            if key not in self._selectors
        }
        if missing:
            evaluate = (
                self._runtime.evaluate_selectors
                if self._runtime
                else evaluate_selectors
            )
            for key, verdict in zip(missing, evaluate(datum, list(missing.values()))):
                _store(self._selectors, key, verdict, 512)
        return [self._selectors[key] for key in keys]

    def compare(self, datum, a, b):
        key = json.dumps([datum, a, b], sort_keys=True)
        if key not in self._comparisons:
            _store(self._comparisons, key, compare(datum, a, b, runner=self._run), 512)
        return self._comparisons[key]

    def feasible(self, datum, program):
        return self.compare(datum, program, program)["status"] == "no-difference"

    def memberships(self, datum, programs, observation):
        keys = [
            json.dumps([datum, program, observation["signature"]], sort_keys=True)
            for program in programs
        ]
        answers, missing = {}, {}
        for key, program in zip(keys, programs):
            if key in self._memberships:
                answers[key] = self._memberships[key]
            else:
                missing[key] = program
        if missing:
            values = membership(
                datum, list(missing.values()), observation, runner=self._run
            )
            for key, answer in zip(missing, values):
                answers[key] = answer
                _store(self._memberships, key, answer, 1024)
        return [answers[key] for key in keys]

    def close(self):
        if self._runtime is not None:
            self._runtime.close()
            self._runtime = None

"""Session-local caches around the released core checks. No voting policy."""

import json

from ._compare import compare
from ._evidence import membership


def _store(cache, key, value, limit):
    if len(cache) >= limit:
        cache.pop(next(iter(cache)))
    cache[key] = value


class ProgramChecks:
    def __init__(self):
        self._comparisons = {}
        self._memberships = {}

    def compare(self, datum, a, b):
        key = json.dumps([datum, a, b], sort_keys=True)
        if key not in self._comparisons:
            _store(self._comparisons, key, compare(datum, a, b), 512)
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
            values = membership(datum, list(missing.values()), observation)
            for key, answer in zip(missing, values):
                answers[key] = answer
                _store(self._memberships, key, answer, 1024)
        return [answers[key] for key in keys]

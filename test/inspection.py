"""Test oracle: Python inspection modulo dict/set ordering.

Normalize actual values, never parse or sort fragments of arbitrary repr text.
Exact built-in containers are traversed recursively; all other types retain
their native repr. In particular, custom __repr__ output is opaque: this does
not claim to normalize a dictionary embedded in a user-written string.
"""


def inspection(value):
    """Return a comparable observation, preserving leaf repr and type.

    Dictionary entries and set members are multisets of observations; sequence
    positions and multiplicity remain significant. An active-path marker makes
    built-in container cycles finite without treating shared acyclic values as
    cycles. This is a printing oracle, not a proof of object-identity recovery.
    """
    active = {}

    def observe(obj):
        cls = type(obj)
        tag = (cls.__module__, cls.__qualname__)
        if cls not in (dict, set, frozenset, list, tuple):
            return (tag, repr(obj))
        oid = id(obj)
        if oid in active:
            return (tag, ("cycle", len(active) - active[oid]))
        active[oid] = len(active)
        try:
            if cls is dict:
                contents = [(observe(k), observe(v)) for k, v in obj.items()]
            else:
                contents = [observe(v) for v in obj]
            if cls in (dict, set, frozenset):
                contents.sort(key=repr)
            return (tag, tuple(contents))
        finally:
            del active[oid]

    return observe(value)

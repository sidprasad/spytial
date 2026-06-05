"""Property-based tests for ``reify`` — the inverse of ``build_instance``.

The falsifiable property is whether, for a chosen set of values, the datum
Spytial receives can reproduce the language's textual inspection string. We
compare two paths and assert they end at the same string::

    value ── repr ─────────────────────────────────────────► string
    value ── build_instance ─► datum ─► reify ─► repr ──────► string

i.e. ``repr(reify(build_instance(v))) == repr(v)``.

``repr`` (not ``==``) is the oracle on purpose: it sidesteps ``float('nan')``,
which is never equal to itself, while still pinning down the reconstructed
value's textual form — exactly the inspection string a REPL would print.

Scope of the generated values (what the round-trip is *designed* to recover):

* Leaves: ``None``, ``bool``, ``int``, ``float`` (incl. ``nan``/``inf``), ``str``.
* Order-stable containers: ``list``, ``tuple``, and ``dict`` (insertion-ordered).
* ``dict`` keys: primitives, ``None``, and **tuples of those** all round-trip —
  ``DictRelationalizer`` walks every key structurally, so a complex key keeps
  its contents (``{('a', 'b'): 1}`` reifies back to ``{('a', 'b'): 1}``).
* ``set`` is covered separately: a set's ``repr`` order is not a function of its
  elements (the hash-table layout depends on insertion/resize history), so for
  sets we assert element recovery rather than ``repr``-string equality.
* ``bytes``/``frozenset`` and the documented long tail (enums, ``int``/``str``
  subclasses, numpy) are out of scope — they fall back to the attribute-bag
  proxy and are intentionally not generated here. (A ``frozenset`` *key* is
  therefore still out of scope, like a ``frozenset`` value.)
"""

from collections import Counter

from hypothesis import given, settings, strategies as st

from spytial.provider_system import CnDDataInstanceBuilder


def _roundtrip(value):
    """value ─► build_instance ─► datum ─► reify ─► reconstructed object."""
    builder = CnDDataInstanceBuilder()
    return builder.reify(builder.build_instance(value))


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Leaves whose repr is a pure function of the value. nan/inf are kept: their
# repr ('nan'/'inf') round-trips even though `==` would not.
atoms = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=True, allow_infinity=True),
    st.text(),
)

# Hashable values usable as dict keys and set elements: primitives, None, and
# tuples nested arbitrarily over those — DictRelationalizer walks every key, so
# tuple keys keep their contents. nan is excluded on purpose: as a key it is
# unlookupable, and because the datum memoizes equal atoms a dict or set holding
# several *distinct* nan objects cannot round-trip its entry count (two `nan`
# keys ── repr ── '{nan, nan}' collapse to one shared atom). inf is kept:
# inf == inf, so it behaves like any ordinary key.
hashable_atoms = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=True),
        st.text(),
    ),
    lambda children: st.lists(children).map(tuple),
    max_leaves=8,
)

# Recursive structures whose repr is order-stable: lists, tuples (as values),
# and insertion-ordered dicts. Sets are deliberately excluded here.
repr_stable = st.recursive(
    atoms,
    lambda children: st.one_of(
        st.lists(children),
        st.lists(children).map(tuple),
        st.dictionaries(keys=hashable_atoms, values=children),
    ),
    max_leaves=25,
)


# ---------------------------------------------------------------------------
# The core property: the two paths land on the same inspection string
# ---------------------------------------------------------------------------


@settings(max_examples=300, deadline=None)
@given(repr_stable)
def test_repr_roundtrip(value):
    assert repr(_roundtrip(value)) == repr(value)


@settings(max_examples=200, deadline=None)
@given(repr_stable)
def test_replit_equals_repr(value):
    # replit(datum) is defined as repr(reify(datum)) — the REPL-equivalent
    # string — so it must reproduce repr(value) over the same domain.
    builder = CnDDataInstanceBuilder()
    datum = builder.build_instance(value)
    assert builder.replit(datum) == repr(value)


# ---------------------------------------------------------------------------
# Sets: element recovery, since repr order isn't element-determined
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(st.sets(hashable_atoms))
def test_set_elements_roundtrip(value):
    out = _roundtrip(value)
    assert isinstance(out, set)
    # A set reprs in hash-table order, which depends on insertion history, so
    # two sets with identical elements can repr differently. Compare the
    # multiset of element reprs instead — order-independent, nan-safe.
    assert Counter(map(repr, out)) == Counter(map(repr, value))


# ---------------------------------------------------------------------------
# Real objects: reify rebuilds the genuine class, so the custom __repr__ runs
# ---------------------------------------------------------------------------


class Vec2:
    """Plain class with a non-structural custom __repr__."""

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Vec2(x={self.x!r}, y={self.y!r})"


class Pair:
    """Holds arbitrary objects — including other reified instances."""

    def __init__(self, first, second):
        self.first = first
        self.second = second

    def __repr__(self):
        return f"Pair({self.first!r}, {self.second!r})"


@settings(max_examples=200, deadline=None)
@given(repr_stable, repr_stable)
def test_custom_object_repr_roundtrip(a, b):
    obj = Vec2(a, b)
    # The atom carries Vec2's module + qualname, so reify rebuilds the real
    # class and its custom __repr__ runs — an attribute-bag proxy could not.
    out = _roundtrip(obj)
    assert type(out) is Vec2
    assert repr(out) == repr(obj)


@settings(max_examples=150, deadline=None)
@given(repr_stable, repr_stable, repr_stable)
def test_nested_custom_object_repr_roundtrip(a, b, c):
    # Object-in-object: exercises register-before-recurse so the inner instance
    # is rebuilt and reprs correctly inside the outer one's __repr__.
    obj = Pair(Vec2(a, b), c)
    out = _roundtrip(obj)
    assert type(out) is Pair
    assert repr(out) == repr(obj)


# ---------------------------------------------------------------------------
# Complex dict keys: now walked structurally, so they keep their contents
# ---------------------------------------------------------------------------


def test_complex_dict_key_roundtrip():
    # Regression for the build-side bug where a non-primitive dict key got a
    # synthetic, un-walked key atom and reified to an empty shell ({('a','b'): 1}
    # came back as {(): 1}). DictRelationalizer now walks every key.
    value = {("a", "b"): 1, ("c",): 2}
    assert repr(_roundtrip(value)) == repr(value)

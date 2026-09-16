"""Property-based evidence for inspection-preserving Python reconstruction.

The primary property compares native leaf representations and recursively
observed containers, modulo dictionary/set ordering. Lists and tuples retain
positions and multiplicity. The shared ``inspection`` oracle documents this
normalization; custom user-written repr strings remain exact.

Every round-trip crosses JSON and uses a fresh builder for reconstruction.
Permutation tests additionally discard incidental atom, relation and tuple
array order. No positional relation IDs or IAtom.metadata are required.

Generated built-ins include numeric/string/bytes leaves, recursive lists,
tuples and dictionaries, and sets/frozensets with recursively hashable members.
NaN values are included, but NaN keys/members remain excluded: the current
importer collapses distinct NaN atoms. Classes below exercise exact custom
repr separately; named references and unsupported types are covered by the
systematic corpus rather than counted as generated structural reconstruction.
"""

import json

from inspection import inspection

from hypothesis import given, settings, strategies as st

from spytial.provider_system import CnDDataInstanceBuilder


def _roundtrip(value):
    """value ─► build_instance ─► datum ─► reify ─► reconstructed object."""
    builder = CnDDataInstanceBuilder()
    datum = json.loads(json.dumps(builder.build_instance(value)))
    return CnDDataInstanceBuilder().reify(datum)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Leaves whose repr is a pure function of the value. nan/inf are kept: their
# repr ('nan'/'inf') round-trips even though `==` would not. complex parses
# its own str form back (including inf/nan components), and bytes travel as
# their b'...' literal in the atom label.
atoms = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=True, allow_infinity=True),
    st.complex_numbers(allow_nan=True, allow_infinity=True),
    st.text(),
    st.binary(),
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
        st.complex_numbers(allow_nan=False, allow_infinity=True),
        st.text(),
        st.binary(),
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


# Include unordered containers at arbitrary nesting depths. Their hashable
# members are generated separately so every generated value is constructible.
inspection_values = st.recursive(
    st.one_of(atoms, st.sets(hashable_atoms), st.frozensets(hashable_atoms)),
    lambda children: st.one_of(
        st.lists(children),
        st.lists(children).map(tuple),
        st.dictionaries(keys=hashable_atoms, values=children),
    ),
    max_leaves=25,
)


@settings(max_examples=300, deadline=None)
@given(inspection_values)
def test_inspection_roundtrip(value):
    assert inspection(_roundtrip(value)) == inspection(value)


@settings(max_examples=200, deadline=None)
@given(inspection_values, st.randoms())
def test_inspection_survives_record_permutations(value, random):
    datum = json.loads(json.dumps(CnDDataInstanceBuilder().build_instance(value)))
    random.shuffle(datum["atoms"])
    random.shuffle(datum["relations"])
    for relation in datum["relations"]:
        random.shuffle(relation["tuples"])
    out = CnDDataInstanceBuilder().reify(datum)
    assert inspection(out) == inspection(value)


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
    assert inspection(_roundtrip(value)) == inspection(value)

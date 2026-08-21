"""Selectors written in Python, translated to atom IDs at diagram time.

A ``selector`` may be a function instead of an sgq expression. It is handed the
values the walk reached (``values[0]`` is the diagrammed object) and returns
the values to select -- one per row, or a tuple per row for a higher arity::

    def child_edges(values):
        return [(n, k) for n in values if isinstance(n, Node) for k in n.kids]

    # compiles to:  n0 -> n2 + n0 -> n4 + n4 -> n6

Each returned value is translated to the ID of its atom (a value with no atom
is an error), and the IDs are joined with ``->`` within a tuple and ``+``
between rows. The function runs during :func:`spytial.diagram`, after the walk
and before the spec is written, so the IDs are the ones the relationalizer
assigned to the instance about to be drawn -- and the same function works on a
class decorator, where no instance exists yet. It reads the caller's own
objects (``n.kids``, not ``p.kids.idx[int]``), and a fault in it raises where
it was written.
"""

import decimal
import math

from ._spec_tables import SELECTOR_ARITY

__all__ = [
    "SelectorError",
    "AtomNotInInstance",
    "emit",
    "materialise",
    "resolve_decorators",
]


class SelectorError(ValueError):
    """A fault raised while translating a selector."""


class AtomNotInInstance(SelectorError):
    """The selector returned a value that the instance has no atom for."""


def _literal(value, atom_id):
    """The sgq text for *value*'s atom -- an atom ID is not always a literal.

    A str ID quotes without escaping. A float ID can use exponent notation,
    which does not parse; sgq matches numbers by value, so the exact decimal
    reaches the same atom. bytes/complex IDs (``b'..'``, ``(1+2j)``) have no
    spelling at all.
    """
    if isinstance(value, str):
        return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')
    if isinstance(value, bool):
        return atom_id
    if isinstance(value, float) and math.isfinite(value) and "e" in atom_id.lower():
        return format(decimal.Decimal(value), "f")
    if isinstance(value, (bytes, complex)):
        raise SelectorError(
            "%r has atom %s, which has no sgq literal spelling. Select the "
            "value that holds it instead." % (value, atom_id)
        )
    return atom_id


def emit(rows):
    """Join rows of atom IDs: ``->`` within a row, ``+`` between rows.

    ``->`` binds tighter than ``+``, so no parentheses. A single row is written
    twice: a lone primitive literal evaluates at arity 0 (``1`` is arity 0,
    ``1 + 1`` is arity 1), and ``X + none`` does not lift it.
    """
    if not rows:
        return "none"
    terms = [" -> ".join(row) for row in rows]
    return " + ".join(terms * 2 if len(terms) == 1 else terms)


def materialise(fn, root, builder, instance, *, widths=None, slot="selector"):
    """Run *fn* on the walked values and translate its result to sgq text.

    Only a ``tuple`` is a row; a ``list`` is a value, since container atoms are
    themselves selectable. *widths* is the set of row widths the slot accepts:
    core silently discards rows of the wrong width, so a mismatch is an error
    here rather than a directive that quietly stops applying. A value with no
    atom raises :class:`AtomNotInInstance` -- a check the evaluator cannot
    make, since a numeric literal naming no atom evaluates non-empty in sgq.
    """
    result = fn(builder.walked_objects())
    rows = [item if type(item) is tuple else (item,) for item in result or ()]
    if not rows:
        return "none"

    lengths = {len(row) for row in rows}
    if len(lengths) != 1 or 0 in lengths:
        raise SelectorError(
            "the selector returned rows of differing length %s." % sorted(lengths)
        )
    if widths is not None and not (lengths & widths):
        raise SelectorError(
            "'%s' takes rows of length %s, but the selector returned rows of "
            "length %d; spytial-core would silently drop them."
            % (slot, sorted(widths), next(iter(lengths)))
        )

    valid = {atom.get("id") for atom in instance.get("atoms", ())}
    translated = []
    for row in rows:
        literals = []
        for value in row:
            atom_id = builder.atom_id_for(value)
            if atom_id is None or atom_id not in valid:
                raise AtomNotInInstance(
                    "the selector returned %r, which the instance has no atom "
                    "for -- only values reached by the walk can be selected."
                    % (value,)
                )
            literals.append(_literal(value, atom_id))
        translated.append(tuple(literals))
    return emit(translated)


def resolve_decorators(decorators, root, builder, instance):
    """Return *decorators* with every function selector translated to sgq text.

    Called from :func:`spytial.diagram` between the walk and the spec -- the
    only moment the atom IDs exist and describe the instance about to be
    drawn. The input is not modified.
    """
    return {
        section: [_resolve_entry(e, root, builder, instance) for e in entries or ()]
        for section, entries in decorators.items()
    }


def _resolve_entry(entry, root, builder, instance):
    if not isinstance(entry, dict):
        return entry
    return {
        spec_type: (
            {
                key: _resolve_value(spec_type, key, value, root, builder, instance)
                for key, value in kwargs.items()
            }
            if isinstance(kwargs, dict) and any(callable(v) for v in kwargs.values())
            else kwargs
        )
        for spec_type, kwargs in entry.items()
    }


def _resolve_value(spec_type, key, value, root, builder, instance):
    if not callable(value):
        return value
    # Slots named selector/filter take one even where SELECTOR_ARITY omits them
    # (the deprecated icon/atomColor/edgeColor forms); the table membership
    # additionally admits tag's toTag/value slots, whose names say nothing.
    if key not in ("selector", "filter") and (spec_type, key) not in SELECTOR_ARITY:
        raise SelectorError(
            "'%s' of '%s' is not a selector, so it takes no function."
            % (key, spec_type)
        )
    # group is exempt from the width check: its binary selector also accepts
    # unary rows (a unary selector builds a single unkeyed group).
    widths = (
        None
        if spec_type == "group"
        else {"unary": {1}, "binary": {2}}.get(SELECTOR_ARITY.get((spec_type, key)))
    )
    return materialise(
        value, root, builder, instance,
        widths=widths, slot="%s.%s" % (spec_type, key),
    )

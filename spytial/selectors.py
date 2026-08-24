"""Selectors written in Python, translated to atom IDs at diagram time.

A ``selector`` may be a function instead of an sgq expression. It is handed the
values the walk reached (``values[0]`` is the diagrammed object) and returns
the values to select -- one per row, or a tuple per row for a higher arity::

    def child_edges(values):
        return [(n, k) for n in values if isinstance(n, Node) for k in n.kids]

    # compiles to:  n0 -> n2 + n0 -> n4 + n4 -> n6

Each returned value is translated to the ID of its atom, and the IDs are joined with ``->`` within a tuple and ``+``
between rows. The function runs during :func:`spytial.diagram`, after the walk
and before the spec is written, so the IDs are the ones the relationalizer
assigned to the instance about to be drawn -- and the same function works on a
class decorator, where no instance exists yet. It reads the caller's own
objects (``n.kids``, not ``p.kids.idx[int]``), and a fault in it raises where
it was written.
"""

import decimal
import math
import warnings

from ._spec_tables import SELECTOR_ARITY

__all__ = [
    "SelectorError",
    "rows_for",
    "slot_widths",
    "refuse_python_selectors",
    "AtomNotInInstance",
    "emit",
    "materialise",
    "resolve_decorators",
]


class SelectorError(ValueError):
    """A fault raised while translating a selector."""


class AtomNotInInstance(UserWarning):
    """The selector returned a value that the instance has no atom for.

    A warning, not an error: the rest of the selector still applies, and a
    diagram missing one styled node beats no diagram. It is not left silent,
    because sgq cannot report it -- a literal naming no atom evaluates
    non-empty there, so the rule would apply to a phantom atom instead.

    Raise it instead with
    ``warnings.simplefilter("error", spytial.AtomNotInInstance)``.
    """


def refuse_python_selectors(decorators, context):
    """Raise if *decorators* holds a function selector, naming *context*.

    For a context that renders the specification once and then lets the browser
    change the data. The function cannot run again there, so the selector would
    keep naming the atoms of the seed instance while the drawing moved on.

    A sequence is **not** such a context, and does not use this: it rebuilds
    each frame in Python through one shared builder, which keeps atom IDs
    stable, so each frame's rows can be translated and unioned.

    Without the check the function object reaches the YAML unchanged and is
    dumped as ``!!python/name:...``, which core reads as a nonsense selector.
    """
    for entries in decorators.values():
        for entry in entries or ():
            if not isinstance(entry, dict):
                continue
            for spec_type, kwargs in entry.items():
                if not isinstance(kwargs, dict):
                    continue
                for key, value in kwargs.items():
                    if callable(value):
                        raise SelectorError(
                            "'%s.%s' is a Python selector, which %s cannot use: "
                            "it writes the specification once and the browser "
                            "changes the data afterwards, so the function cannot "
                            "run again. Write this selector as an sgq expression."
                            % (spec_type, key, context)
                        )


def _literal(value, atom_id):
    """The sgq text for *value*'s atom -- an atom ID is not always a literal.

    A quoted str is a *value* in sgq, not a member of ``univ``: ``"x" & univ``
    is empty, and a directive given one selects no atom (a ``hideAtom`` on a
    string silently draws it anyway). The str **atom** is reached by binding
    over the type, which is also how the sgq-written CLRS notebooks spell it.
    A float ID can use exponent notation, which does not parse; sgq matches
    numbers by value, so the exact decimal reaches the same atom. ``-inf`` does
    not parse either -- a leading ``-`` before a name is not an expression,
    though bare ``inf`` and ``nan`` are -- so it takes the same type binding as
    a str. bytes/complex IDs (``b'..'``, ``(1+2j)``) have no spelling at all.
    """
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return '{s : str | @:s = "%s"}' % escaped
    if isinstance(value, bool):
        return atom_id
    if isinstance(value, float):
        if math.isinf(value) and value < 0:
            return '{f : float | @:f = "%s"}' % atom_id
        if math.isfinite(value) and "e" in atom_id.lower():
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


def rows_for(fn, root, builder, instance, *, widths=None, slot="selector"):
    """Run *fn* on the walked values and translate its result to rows of atom IDs.

    Only a ``tuple`` is a row; a ``list`` is a value, since container atoms are
    themselves selectable. *widths* is the set of row widths the slot accepts:
    core silently discards rows of the wrong width, so a mismatch is an error
    here rather than a directive that quietly stops applying. A row holding a
    value with no atom is dropped with an :class:`AtomNotInInstance` warning --
    a report the evaluator cannot make, since a literal naming no atom
    evaluates non-empty in sgq.
    """
    result = fn(builder.walked_objects())
    rows = [item if type(item) is tuple else (item,) for item in result or ()]
    if not rows:
        return []

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
                warnings.warn(
                    "'%s' returned %r, which the instance has no atom for; that "
                    "row is dropped. Only values reached by the walk can be "
                    "selected." % (slot, value),
                    AtomNotInInstance,
                    stacklevel=3,
                )
                literals = None
                break
            literals.append(_literal(value, atom_id))
        if literals is not None:
            translated.append(tuple(literals))
    return translated


def materialise(fn, root, builder, instance, *, widths=None, slot="selector"):
    """Run *fn* and emit its rows as sgq text. See :func:`rows_for`."""
    return emit(rows_for(fn, root, builder, instance, widths=widths, slot=slot))


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


def slot_widths(spec_type, key):
    """Row widths the slot accepts, or ``None`` for any.

    Raises if the keyword is not a selector at all. Slots named
    ``selector``/``filter`` are selectors even where SELECTOR_ARITY omits them
    (the deprecated icon/atomColor/edgeColor forms); the table membership
    additionally admits tag's toTag/value slots, whose names say nothing.

    ``group`` is exempt from the check: its binary selector also accepts unary
    rows, which build a single unkeyed group.
    """
    if key not in ("selector", "filter") and (spec_type, key) not in SELECTOR_ARITY:
        raise SelectorError(
            "'%s' of '%s' is not a selector, so it takes no function."
            % (key, spec_type)
        )
    if spec_type == "group":
        return None
    return {"unary": {1}, "binary": {2}}.get(SELECTOR_ARITY.get((spec_type, key)))


def _resolve_value(spec_type, key, value, root, builder, instance):
    if not callable(value):
        return value
    return materialise(
        value, root, builder, instance,
        widths=slot_widths(spec_type, key), slot="%s.%s" % (spec_type, key),
    )

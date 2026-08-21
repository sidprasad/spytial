"""Selectors written in Python, translated to atom IDs at diagram time.

A selector is normally an sgq expression, evaluated in the browser over the
relationalized instance. It may instead be a Python function:

1. The function is handed the values the walk reached and returns the ones to
   select. A value per row for a unary selector, a tuple per row for a higher
   arity.
2. Each value is translated to the ID of its atom. A value with no atom is an
   error.
3. The IDs become the selector text: ``->`` within a tuple, ``+`` between rows.

::

    def child_edges(values):
        return [(n, k) for n in values if isinstance(n, Node) for k in n.kids]

    # compiles to:  n0 -> n2 + n0 -> n4 + n4 -> n6

The timing is the design. The function runs during :func:`spytial.diagram`,
after the walk and before the spec is written, so the IDs it translates against
are the ones the relationalizer assigned to the instance about to be drawn.
Nothing is computed early or carried between builds, and the same function
works on a class decorator, where no instance exists yet.

The point of writing a selector this way is that it reads the caller's own
objects. ``n.kids`` replaces ``p.kids.idx[int]``, so the relationalization need
not be known. Nothing is intercepted, so a fault in the function raises where
it was written, with an ordinary traceback.
"""

from __future__ import annotations

import decimal
import math
from typing import Any, Dict, Sequence, Tuple

from ._spec_tables import SELECTOR_ARITY

__all__ = [
    "SelectorError",
    "AtomNotInInstance",
    "emit",
    "materialise",
    "resolve_decorators",
]


class SelectorError(ValueError):
    """Base class for every fault raised while translating a selector."""


class AtomNotInInstance(SelectorError):
    """The selector returned a value that the instance has no atom for."""


def _literal(value: Any, atom_id: str) -> str:
    """The sgq text that resolves to *value*'s atom.

    An atom ID names an atom inside the instance; a literal refers to one from a
    selector. Two kinds of value are written differently, and neither parses as
    it stands. A ``str`` ID quotes the value without escaping, so a value holding
    a quote gives ``"he said "hi""``; sgq accepts ``\\"`` inside a literal. A
    ``float`` ID is ``str(value)``, which uses exponent notation outside 1e-4 to
    1e16, and ``1e+30`` is not a literal; sgq matches a numeric literal by value,
    so the exact decimal expansion reaches the same atom.
    """
    if isinstance(value, str):
        return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')
    if isinstance(value, bool):
        return atom_id
    if isinstance(value, float) and math.isfinite(value) and "e" in atom_id.lower():
        return format(decimal.Decimal(value), "f")
    return atom_id


def emit(rows: Sequence[Sequence[str]]) -> str:
    """Join rows of atom IDs: ``->`` within a row, ``+`` between rows.

    sgq binds ``->`` tighter than ``+``, so no parentheses are needed.

    A single row is written twice. A lone primitive literal evaluates at arity 0
    (``1`` is arity 0, ``1 + 1`` is arity 1) and the directive slots need 1 or 2.
    ``X + none`` does not lift it. ``X + X`` does, and is idempotent.
    """
    if not rows:
        return "none"
    terms = [" -> ".join(row) for row in rows]
    if len(terms) == 1:
        terms = terms * 2
    return " + ".join(terms)


def materialise(fn, root: Any, builder, instance: Dict) -> str:
    """Run *fn* and translate its result to sgq text.

    Args:
        fn: The selector function. It is handed the values the walk reached --
            ``values[0]`` is the diagrammed object itself, the first value the
            walk saw. It returns the values to select; a row is one value, or a
            tuple of values for a higher arity. Only a ``tuple`` is a row: a
            ``list`` is a value, because a list is an atom in its own right
            (selecting the container atoms is how the relationalizer's
            scaffolding gets hidden).
        root: The object passed to
            :meth:`~spytial.CnDDataInstanceBuilder.build_instance`.
        builder: The builder that produced *instance*. Its walk supplies the IDs.
        instance: The built instance.

    Raises:
        AtomNotInInstance: The function returned a value the walk never reached.
            This check cannot be left to the evaluator: a numeric literal naming
            no atom evaluates non-empty in sgq, so a wrong value would apply the
            rule to a phantom atom rather than report anything.
        SelectorError: The rows are not all the same length.
    """
    result = fn(builder.walked_objects())
    rows = [item if type(item) is tuple else (item,) for item in result or ()]
    if not rows:
        return "none"

    widths = {len(row) for row in rows}
    if len(widths) != 1 or 0 in widths:
        raise SelectorError(
            "the selector returned rows of differing length %s. Every row shall "
            "have the same length." % sorted(widths)
        )

    valid = {atom.get("id") for atom in instance.get("atoms", ())}
    ids = []
    for row in rows:
        literals = []
        for value in row:
            atom_id = builder.atom_id_for(value)
            if atom_id is None or atom_id not in valid:
                raise AtomNotInInstance(
                    "the selector returned %r, which the instance has no atom "
                    "for. Only values reached by the walk from the diagrammed "
                    "object can be selected." % (value,)
                )
            literals.append(_literal(value, atom_id))
        ids.append(tuple(literals))
    return emit(ids)


def resolve_decorators(decorators: Dict, root: Any, builder, instance: Dict) -> Dict:
    """Return *decorators* with every function selector translated to sgq text.

    Called from :func:`spytial.diagram` between the walk and the spec, which is
    the only moment at which the atom IDs exist and still describe the instance
    about to be drawn. The input is not modified.
    """
    return {
        section: [
            _resolve_entry(entry, root, builder, instance) for entry in entries or ()
        ]
        for section, entries in decorators.items()
    }


def _resolve_entry(entry, root, builder, instance):
    if not isinstance(entry, dict):
        return entry
    resolved = {}
    for spec_type, kwargs in entry.items():
        if isinstance(kwargs, dict) and any(callable(v) for v in kwargs.values()):
            kwargs = {
                key: _resolve_value(spec_type, key, value, root, builder, instance)
                for key, value in kwargs.items()
            }
        resolved[spec_type] = kwargs
    return resolved


def _resolve_value(spec_type, key, value, root, builder, instance):
    if not callable(value):
        return value
    if (spec_type, key) not in SELECTOR_ARITY:
        raise SelectorError(
            "'%s' of '%s' is not a selector, so it takes no function."
            % (key, spec_type)
        )
    return materialise(value, root, builder, instance)

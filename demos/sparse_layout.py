"""
A layout-aware sPyTial relationalizer for ``scipy.sparse`` matrices.

A sparse matrix is not really a grid of numbers — it is a small *bundle of
parallel arrays* (the storage format) that together encode a grid. The
interesting thing to *see* is that bundle, and what an element-access has to
touch across it.

This module renders the **physical** layout for the three formats people
actually reason about:

* ``coo`` — the uncompressed baseline: parallel ``row[]``, ``col[]``, ``data[]``
  triplets.
* ``csr`` — compress the rows: ``indptr[]`` slices ``indices[]`` / ``data[]``.
* ``csc`` — the same idea, compressing columns instead.

``layout(A)`` draws the storage. ``access(A, i, j)`` draws the storage *and*
highlights the path an access to ``A[i, j]`` walks through it — answering "which
indices do I have to touch, across all the arrays, to read this one element?"
"""

from typing import Any, Callable, List, Optional, Tuple

import scipy.sparse as sp

import spytial
from spytial import Atom, Relation, RelationalizerBase, relationalizer


# ===========================================================================
# Public API
# ===========================================================================
def layout(matrix) -> "SparseLayout":
    """Visualize the physical storage layout of a sparse matrix."""
    return _decorated(SparseLayout(matrix))


def access(matrix, i: int, j: int) -> "SparseLayout":
    """Visualize the storage layout *and* highlight the access path to A[i, j]."""
    return _decorated(SparseLayout(matrix, i, j))


class SparseLayout:
    """Wrap a sparse matrix (and optionally a target ``[i, j]``) for diagramming."""

    def __init__(self, matrix, i: Optional[int] = None, j: Optional[int] = None):
        self.matrix = matrix
        self.i = i
        self.j = j

    @property
    def acc(self) -> Optional[Tuple[int, int]]:
        return None if self.i is None else (self.i, self.j)


# ===========================================================================
# Layout directives, applied per-diagram
# ===========================================================================
# sPyTial rejects a selector that names a type/relation with no atoms, so we
# can't hang one static decorator stack on the class — a CSR diagram has no
# ``row[]`` array, a plain layout has no access edges, an empty row has nothing
# to ``scan``. Instead we build the graph once, see which types and relations it
# actually contains, and attach only the matching rules to that one object.
_GROUPS = {  # atom type -> box label
    "Ptr": "indptr[]", "MajIdx": "indices[]",
    "RowIx": "row[]", "ColIx": "col[]", "Val": "data[]",
}
_RIGHT = {"nextPtr", "nextIdx", "nextVal", "nextRow", "nextCol"}  # array order
_BELOW = {"pair", "slice", "tripRC", "tripCV"}                    # stack partners
_EDGE_COLORS = {  # access-path overlay, by lookup step
    "bound": "#d97706",   # amber: read the slice bounds
    "scan":  "#9ca3af",   # grey:  entries the scan skips
    "hit":   "#16a34a",   # green: the entry that matches
}


def _decorated(obj: "SparseLayout") -> "SparseLayout":
    """Attach exactly the layout rules this matrix's graph can satisfy."""
    atoms, rels = _build_graph(obj.matrix, obj.acc, lambda _m: "m")
    types = {a.type for a in atoms}
    names = {r.name for r in rels}

    for typ, label in _GROUPS.items():
        if typ in types:
            spytial.annotate_group(obj, selector=typ, name=label)
    for name in names & _RIGHT:
        spytial.annotate_orientation(obj, selector=name, directions=["right"])
    for name in names & _BELOW:
        spytial.annotate_orientation(obj, selector=name, directions=["below"])
    for name, color in _EDGE_COLORS.items():
        if name in names:
            spytial.annotate_edgeColor(obj, field=name, value=color)
    if "Query" in types:
        spytial.annotate_atomColor(obj, selector="Query", value="#fde68a")
    return obj


# ===========================================================================
# The relationalizer
# ===========================================================================
@relationalizer(priority=100)
class SparseLayoutRelationalizer(RelationalizerBase):
    """Turn a sparse matrix's storage arrays into atoms + relations.

    The generic relationalizer can't help here: it walks attributes with
    ``inspect.getmembers`` and a numpy array exposes endlessly many array-valued
    properties (``.T``, ``.real``, …), so it recurses until it blows the stack.
    A sparse matrix needs a relationalizer that knows what its arrays *mean*.
    """

    def can_handle(self, obj: Any) -> bool:
        return isinstance(obj, SparseLayout) or sp.issparse(obj)

    def relationalize(self, obj, walker) -> Tuple[List[Atom], List[Relation]]:
        if isinstance(obj, SparseLayout):
            return _build_graph(obj.matrix, obj.acc, walker._get_id)
        return _build_graph(obj, None, walker._get_id)


# ===========================================================================
# Graph construction (one source of truth, used for rendering *and* decoration)
# ===========================================================================
def _build_graph(matrix, acc, get_id: Callable[[Any], str]
                 ) -> Tuple[List[Atom], List[Relation]]:
    if matrix.format == "coo":
        return _coo_graph(matrix, acc, get_id)
    if matrix.format not in ("csr", "csc"):
        matrix = matrix.tocsr()
    return _compressed_graph(matrix, acc, get_id)


def _compressed_graph(matrix, acc, get_id):
    """CSR / CSC: ``indptr[]`` slices the parallel ``indices[]`` / ``data[]``."""
    fmt = matrix.format
    A = matrix.sorted_indices()              # sorted copy; never mutates caller
    indptr, indices, data = A.indptr, A.indices, A.data
    m, n = A.shape
    nnz = A.nnz
    n_major = m if fmt == "csr" else n       # indptr ranges over rows / cols

    mid = get_id(matrix)
    atoms = [Atom(mid, "CSX", f"{fmt}  {m}×{n} · nnz={nnz}")]
    rels: List[Relation] = []

    ptr = [f"{mid}::p{r}" for r in range(n_major + 1)]
    for r in range(n_major + 1):
        atoms.append(Atom(ptr[r], "Ptr", f"{indptr[r]}"))
        if r:
            rels.append(Relation("nextPtr", [ptr[r - 1], ptr[r]]))
    rels.append(Relation("indptr", [mid, ptr[0]]))

    idx = [f"{mid}::i{k}" for k in range(nnz)]
    val = [f"{mid}::v{k}" for k in range(nnz)]
    for k in range(nnz):
        atoms.append(Atom(idx[k], "MajIdx", f"{indices[k]}"))
        atoms.append(Atom(val[k], "Val", _fmt(data[k])))
        rels.append(Relation("pair", [idx[k], val[k]]))
        if k:
            rels.append(Relation("nextIdx", [idx[k - 1], idx[k]]))
            rels.append(Relation("nextVal", [val[k - 1], val[k]]))
    if nnz:
        rels.append(Relation("indices", [mid, idx[0]]))
        rels.append(Relation("data", [mid, val[0]]))

    for r in range(n_major):
        if indptr[r] < indptr[r + 1]:        # row/col r has >= 1 stored entry
            rels.append(Relation("slice", [ptr[r], idx[indptr[r]]]))

    if acc is not None:
        i, j = acc
        major, target = (i, j) if fmt == "csr" else (j, i)
        start, end = int(indptr[major]), int(indptr[major + 1])
        hit_k = next((k for k in range(start, end) if indices[k] == target), None)

        q = f"{mid}::q"
        atoms.append(Atom(q, "Query",
                          f"A[{i},{j}] = {'0' if hit_k is None else f'data[{hit_k}]'}"))
        rels.append(Relation("bound", [q, ptr[major]]))
        rels.append(Relation("bound", [q, ptr[major + 1]]))
        for k in range(start, end):
            name = "hit" if k == hit_k else "scan"
            src = ptr[major] if k == start else idx[k - 1]
            rels.append(Relation(name, [src, idx[k]]))
        if hit_k is not None:
            rels.append(Relation("hit", [idx[hit_k], val[hit_k]]))

    return atoms, rels


def _coo_graph(matrix, acc, get_id):
    """COO: the uncompressed parallel ``row[]`` / ``col[]`` / ``data[]`` triplets."""
    A = matrix
    row, col, data = A.row, A.col, A.data
    m, n = A.shape
    nnz = A.nnz

    mid = get_id(matrix)
    atoms = [Atom(mid, "CSX", f"coo  {m}×{n} · nnz={nnz}")]
    rels: List[Relation] = []

    r_ids = [f"{mid}::r{k}" for k in range(nnz)]
    c_ids = [f"{mid}::c{k}" for k in range(nnz)]
    v_ids = [f"{mid}::v{k}" for k in range(nnz)]
    for k in range(nnz):
        atoms.append(Atom(r_ids[k], "RowIx", f"{row[k]}"))
        atoms.append(Atom(c_ids[k], "ColIx", f"{col[k]}"))
        atoms.append(Atom(v_ids[k], "Val", _fmt(data[k])))
        rels.append(Relation("tripRC", [r_ids[k], c_ids[k]]))
        rels.append(Relation("tripCV", [c_ids[k], v_ids[k]]))
        if k:
            rels.append(Relation("nextRow", [r_ids[k - 1], r_ids[k]]))
            rels.append(Relation("nextCol", [c_ids[k - 1], c_ids[k]]))
            rels.append(Relation("nextVal", [v_ids[k - 1], v_ids[k]]))
    if nnz:
        rels.append(Relation("row", [mid, r_ids[0]]))
        rels.append(Relation("col", [mid, c_ids[0]]))
        rels.append(Relation("data", [mid, v_ids[0]]))

    if acc is not None:
        i, j = acc
        # COO has no index — an access scans every triplet for (i, j).
        hit_k = next((k for k in range(nnz) if row[k] == i and col[k] == j), None)
        q = f"{mid}::q"
        atoms.append(Atom(q, "Query",
                          f"A[{i},{j}] = {'0' if hit_k is None else f'data[{hit_k}]'}"))
        for k in range(nnz):
            name = "hit" if k == hit_k else "scan"
            rels.append(Relation(name, [q if k == 0 else r_ids[k - 1], r_ids[k]]))
        if hit_k is not None:
            rels.append(Relation("hit", [r_ids[hit_k], c_ids[hit_k]]))
            rels.append(Relation("hit", [c_ids[hit_k], v_ids[hit_k]]))

    return atoms, rels


def _fmt(x) -> str:
    """Compact label for a numeric value (drop a trailing .0)."""
    f = float(x)
    return str(int(f)) if f.is_integer() else f"{f:g}"

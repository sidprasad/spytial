# Deep, theory-agnostic Z3 model relationalizer for SpyTial/CnD.
# - Creates atoms for Model, Symbols, Sorts, and recursively for Values
# - Emits generic relations:
#     contains, hasSort, argSort, resSort,
#     interp (constant value),
#     graphOf/arg_i/res (finite function graphs),
#     ctor/field_i (ADTs),
#     map/mapsTo/default (Arrays)
# - Optionally synthesizes unary function edges: f(x) = y  ==>  f(x, y)

import z3
from typing import Tuple, List, Optional
# Adjust these imports to your project layout
from spytial import relationalizer, RelationalizerBase, Atom, Relation

def _is_string_sort(s: z3.SortRef) -> bool:
    # Portable: compare to the canonical StringSort(); also allow Seq[Char] fallback
    try:
        return s == z3.StringSort()
    except Exception:
        return s.kind() == z3.Z3_SEQ_SORT

def _is_builtin_num_sort(s: z3.SortRef) -> bool:
    return s == z3.IntSort() or s == z3.RealSort()

def _sort_id(s: z3.SortRef) -> str:
    if s.kind() == z3.Z3_ARRAY_SORT:
        return f"sort:Array[{s.domain()}→{s.range()}]"
    if s.kind() == z3.Z3_BV_SORT:
        return f"sort:BitVec{s.size()}"
    return f"sort:{s}"

@relationalizer(priority=50)
class DeepZ3Relationalizer(RelationalizerBase):
    """
    Deep relationalizer for z3.ModelRef.
    Set `synthesize_unary_edges=True` to additionally emit simple binary edges
    for unary function graphs (e.g., row/col/val).
    """

    def __init__(self, synthesize_unary_edges: bool = True):
        self.synthesize_unary_edges = synthesize_unary_edges

    # ---------- base API ----------
    def can_handle(self, obj) -> bool:
        return isinstance(obj, z3.ModelRef)

    def relationalize(self, model: z3.ModelRef, walk) -> Tuple[Atom, List[Relation]]:
        mid = walk._get_id(model)
        model_atom = Atom(id=mid, type="Z3Model", label="Z3Model")
        rels: List[Relation] = []

        # --- helpers that capture state via closure ---
        def ensure_atom(atom_id: str, typ: str, label: str):
            if not any(a["id"] == atom_id for a in walk._atoms):
                walk._atoms.append(Atom(id=atom_id, type=typ, label=label).to_dict())

        def ensure_sort_atom(s: z3.SortRef) -> str:
            sid = _sort_id(s)
            ensure_atom(sid, "Sort", sid.split("sort:")[1])
            return sid

        def emit_literal(v: z3.AstRef) -> Optional[str]:
            s = v.sort()
            # Bool
            if s == z3.BoolSort():
                lab = "true" if z3.is_true(v) else "false"
                vid = f"bool:{lab}"
                ensure_atom(vid, "LitBool", lab)
                return vid
            # Int
            if s == z3.IntSort():
                lab = str(v.as_long())
                vid = f"int:{lab}"
                ensure_atom(vid, "LitInt", lab)
                return vid
            # Real
            if s == z3.RealSort():
                lab = v.as_decimal(20) if hasattr(v, "as_decimal") else str(v)
                vid = f"real:{lab}"
                ensure_atom(vid, "LitReal", lab)
                return vid
            # BitVec numeral
            if s.kind() == z3.Z3_BV_SORT and isinstance(v, z3.BitVecNumRef):
                lab = f"{v.as_long()}_bv{s.size()}"
                vid = f"bv:{lab}"
                ensure_atom(vid, f"BitVec{s.size()}", lab)
                return vid
            # String / Seq
            if _is_string_sort(s):
                lab = v.as_string() if hasattr(v, "as_string") else str(v)
                vid = f"str:{lab}"
                ensure_atom(vid, "LitStr", lab)
                return vid
            return None

        def emit_value(v: z3.AstRef) -> str:
            """Return atom id for any value; recursively materialize structure."""
            # literals first
            lit = emit_literal(v)
            if lit is not None:
                return lit

            s = v.sort()

            # ADT node (constructor app)
            if s.kind() == z3.Z3_DATATYPE_SORT and z3.is_app(v):
                ctor = v.decl().name()
                vid = f"adt:{ctor}:{z3.ast_to_string(v)}"
                if not any(a["id"] == vid for a in walk._atoms):
                    ensure_atom(vid, "ADTNode", ctor)
                    ctor_atom = f"ctor:{ctor}"
                    ensure_atom(ctor_atom, "Ctor", ctor)
                    rels.append(Relation("ctor", vid, ctor_atom))
                    for i in range(v.num_args()):
                        child_id = emit_value(v.arg(i))
                        rels.append(Relation(f"field_{i}", vid, child_id))
                return vid

            # Array value: materialize store chain + default
            if s.kind() == z3.Z3_ARRAY_SORT:
                aid = f"array:{z3.ast_to_string(v)}"
                if not any(a["id"] == aid for a in walk._atoms):
                    ensure_atom(aid, "Array", "Array")
                    cur = v
                    stores = []
                    default = None
                    while z3.is_app_of(cur, z3.Z3_OP_STORE):
                        a, i, val = cur.children()
                        stores.append((i, val))
                        cur = a
                    if z3.is_app_of(cur, z3.Z3_OP_CONST_ARRAY):
                        default = cur.children()[0]
                    stores.reverse()
                    for i, val in stores:
                        iid = emit_value(i)
                        vid2 = emit_value(val)
                        rels.append(Relation("map", aid, iid))
                        rels.append(Relation("mapsTo", iid, vid2))
                    if default is not None:
                        did = emit_value(default)
                        rels.append(Relation("default", aid, did))
                return aid

            # Uninterpreted domain element (e.g., u!val0)
            if s.kind() == z3.Z3_UNINTERPRETED_SORT:
                lab = str(v)
                vid = f"uelem:{s.name()}:{lab}"
                ensure_atom(vid, s.name(), lab)
                return vid

            # fallback: delegate (lets your PrimitiveRelationalizer catch misc cases)
            return walk(v)

        # Track unary apps so we can synthesize binary edges: f(x) = y  ==>  f(x, y)
        unary_apps: List[Tuple[str, str, str]] = []  # (func_name, arg_id, res_id)

        # Iterate model decls (symbols)
        for d in model.decls():
            name = d.name()
            sym_id = f"decl:{name}"
            ensure_atom(sym_id, "Symbol", name)
            rels.append(Relation("contains", mid, sym_id))

            # Sort info
            if d.arity() == 0:
                rels.append(Relation("hasSort", sym_id, ensure_sort_atom(d.range())))
            else:
                for i in range(d.arity()):
                    rels.append(Relation("argSort", sym_id, ensure_sort_atom(d.domain(i))))
                rels.append(Relation("resSort", sym_id, ensure_sort_atom(d.range())))

            interp = model.get_interp(d)
            if interp is None:
                continue

            # Constants → interpretation edge
            if d.arity() == 0:
                val_id = emit_value(interp)
                rels.append(Relation("interp", sym_id, val_id))
                continue

            # Functions → finite graph via application nodes
            try:
                entries = list(interp.as_list())
                app_idx = 0
                for entry in entries:
                    if hasattr(entry, "num_args"):
                        args = [entry.arg(i) for i in range(d.arity())]
                        res = interp.entry_value(entry)
                    else:
                        args, res = entry  # ((a1,...,an), val)
                    app_id = f"app:{name}:{app_idx}"
                    app_idx += 1
                    ensure_atom(app_id, "App", name)
                    rels.append(Relation("graphOf", app_id, sym_id))
                    arg_ids = []
                    for i, a in enumerate(args):
                        aid = emit_value(a)
                        arg_ids.append(aid)
                        rels.append(Relation(f"arg_{i}", app_id, aid))
                    rid = emit_value(res)
                    rels.append(Relation("res", app_id, rid))
                    if self.synthesize_unary_edges and len(arg_ids) == 1:
                        unary_apps.append((name, arg_ids[0], rid))

                # else value
                ev = interp.else_value()
                if ev is not None:
                    app_id = f"app:{name}:else"
                    ensure_atom(app_id, "App", f"{name}:else")
                    rels.append(Relation("graphOf", app_id, sym_id))
                    rid = emit_value(ev)
                    rels.append(Relation("res", app_id, rid))
            except Exception:
                # Robustness over perfection: skip weird cases quietly.
                pass

        # Synthesize unary function edges as plain binary relations
        for fname, arg_id, res_id in unary_apps:
            rels.append(Relation(fname, arg_id, res_id))

        return model_atom, rels

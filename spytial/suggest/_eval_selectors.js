// Headless SGQ selector-evaluation shim for spytial.suggest (tier-2 validation).
//
// Reads {datum, selectors:[...]} as JSON on stdin, evaluates each selector over
// the datum with the windowless spytial-core evaluator (the `./evaluator` entry,
// spytial-core>=2.9.2), and writes {ok, vocabulary, results} JSON to stdout. A
// malformed or nonsense selector never aborts the run -- its outcome is captured
// in its own result entry.
//
// The evaluator module is chosen by the Python side (see _eval.py):
//   * SPYTIAL_EVALUATOR_MODULE -- an absolute path to the vendored, self-contained
//     evaluator shipped in the wheel (the default; no npm install needed), or
//   * the bare "spytial-core/evaluator" specifier resolved via NODE_PATH, when the
//     user points SPYTIAL_CORE_NODE_PATH at their own spytial-core install.
const evaluatorModule = process.env.SPYTIAL_EVALUATOR_MODULE || "spytial-core/evaluator";
const mod = require(evaluatorModule);
const { JSONDataInstance, SGraphQueryEvaluator } = mod;

// The static analyzer is a cheap companion to evaluation: it folds a selector to
// unsat / tautology / empty / ill-typed / unknown and, crucially, carries a
// human-readable `reason` (e.g. "provably the empty set", an arity mismatch). It is
// present only in evaluator builds that re-export it (the spytial-core ./evaluator
// analyze/synth surface); older installs won't have it, so this stays optional and the
// shim behaves exactly as before when it's absent.
const analyzeForgeExpression =
  typeof mod.analyzeForgeExpression === "function" ? mod.analyzeForgeExpression : null;

function readStdin() {
  return new Promise((resolve, reject) => {
    let buf = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (d) => (buf += d));
    process.stdin.on("end", () => resolve(buf));
    process.stdin.on("error", reject);
  });
}

function evalOne(ev, sel) {
  try {
    const r = ev.evaluate(sel);
    const out = { selector: sel, isError: r.isError(), empty: r.noResult(), arity: r.maxArity() };
    if (r.isError()) out.error = r.prettyPrint();
    else if (r.isSingleton()) out.value = r.singleResult();
    else out.pretty = r.prettyPrint();
    return out;
  } catch (e) {
    // Evaluator threw mid-traversal (distinct from a structured error result).
    return { selector: sel, threw: String((e && e.message) || e) };
  }
}

// Static verdict for one selector. The data instance doubles as the schema (its
// type lattice + relation column types drive the arity / type-disjointness checks),
// so a datum is all the analyzer needs. Returns undefined when the analyzer isn't
// available or has nothing to say, so callers only see a `static` field when it's real.
function analyzeOne(sel, di) {
  if (!analyzeForgeExpression) return undefined;
  try {
    const a = analyzeForgeExpression(sel, di);
    if (!a || !a.status) return undefined;
    const out = { status: a.status };
    if (a.reason) out.reason = a.reason;
    return out;
  } catch (e) {
    return undefined; // analysis is best-effort; never let it sink a selector
  }
}

(async () => {
  try {
    const { datum, selectors } = JSON.parse(await readStdin());
    const di = new JSONDataInstance(datum);
    const ev = new SGraphQueryEvaluator();
    ev.initialize({ sourceData: di });

    // The closed vocabulary a model may reference -- types and relation names,
    // straight off the datum. Mirrors what tier-2 grounds the model in.
    const vocabulary = {
      types: di.getTypes().map((t) => ({ id: t.id, atoms: t.atoms.length })),
      relations: di.getRelations().map((r) => ({ name: r.name, arity: r.types.length, tuples: r.tuples.length })),
    };
    const results = (selectors || []).map((sel) => {
      const out = evalOne(ev, sel);
      const st = analyzeOne(sel, di);
      if (st) out.static = st;
      return out;
    });
    process.stdout.write(JSON.stringify({ ok: true, vocabulary, results }));
  } catch (e) {
    process.stdout.write(JSON.stringify({ ok: false, error: String((e && e.message) || e) }));
    process.exitCode = 1;
  }
})();

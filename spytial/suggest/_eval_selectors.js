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
const { JSONDataInstance, SGraphQueryEvaluator } = require(evaluatorModule);

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
    const results = (selectors || []).map((sel) => evalOne(ev, sel));
    process.stdout.write(JSON.stringify({ ok: true, vocabulary, results }));
  } catch (e) {
    process.stdout.write(JSON.stringify({ ok: false, error: String((e && e.message) || e) }));
    process.exitCode = 1;
  }
})();

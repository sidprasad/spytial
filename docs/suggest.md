# Develop diagramming rules with suggest

Start with the [interactive notebook demo](https://github.com/sidprasad/spytial/blob/main/demos/06-suggest-session.ipynb).
`suggest` uses an LLM, Hypothesis, and Spytial's solver together. You work with
two diagrams at a time, with an upvote, downvote, or unsure vote for each.

```python
from spytial.suggest import suggest

session = suggest(
    TreeNode,
    rules=["Put children below their parents", "Align children"],
)
session.show()  # Or display `session` in a local Jupyter notebook.
```

`rules` is optional. The default proposer is `Codex()`, using your configured,
authenticated Codex CLI. Supply `proposer=ClaudeCode()`, another provider callable,
or a model-id string to use a different model. Model failures are reported;
they do not silently switch to a simpler workflow.

If VS Code's notebook kernel cannot find `codex`, the provider also checks common
local installation paths. You can explicitly select it with
`proposer=Codex(bin="/absolute/path/to/codex")` or the `SPYTIAL_CODEX` environment
variable. The notebook interface appears immediately; model proposals and formal
checks run in the background. A short status line shows progress and any failure.
In scripts, call `session.wait()` before inspecting candidates or rules. Methods
such as `next()`, `vote()`, `revise()`, and `finish()` wait for startup themselves;
startup failures raise there as well as appearing in the notebook.

## The combined loop

1. The LLM proposes a few **complete programs**. Additional rules it suggests
   are labeled separately from your requests.
2. Hypothesis generates data and checks complete programs for conflicts.
3. The session searches for data on which the programs can be distinguished.
   Suggest constructs candidate contrast programs and checks them with core's
   existing `spytial-check` conformance API. Both diagrams use the **same data**;
   at least one satisfies one program while violating the other. Core interprets
   and solves the constraints; suggest chooses what to compare.
4. Each diagram has three controls: **▲ upvote**, **▼ downvote**, **? unsure**.
   Each vote is saved immediately. Once both diagrams are rated, the next pair
   appears. Mixed judgments, such as upvote and unsure, stay separate.
5. Later, `session.revise("Keep whole subtrees together")` sends your correction
   and earlier judgments to the proposer. New programs go through the same checks.
   The embedded interface follows the same session; no restart is needed.

An answer is saved with the datum, complete programs, witness program, and the
actual layout you judged, including dragging. Drag to explore first; voting checks
that arrangement against **every candidate** using core's conformance solver.

| Judgment | Candidate permits the arrangement | Candidate excludes it |
| --- | --- | --- |
| Upvote | Positive vote | Negative vote |
| Downvote | Negative vote | No vote |
| Unsure | No vote | No vote |

Each candidate is a complete program. A **survivor** has fewer than
`elimination_threshold` negative votes. A **supported survivor** also has at least
`min_positive_votes` positive votes. The defaults are 2 and 1, respectively.
Individual rules do not receive scores.

The LLM is asked for 2–4 programs. `max_candidates=4` limits each proposal batch,
including one repair attempt. Invalid and duplicate proposals are discarded.
Later revisions can add another batch.

Eliminated candidates remain in history but contribute no rules to the living
spec. Reclassifying an old example recomputes all scores and can restore a
candidate. Repeated classifications of the same datum and qualitative arrangement
count once; the latest classification wins. Changing that classification to
unsure removes its effect on the scores.

## Apply with multiple survivors

The session does not require a single remaining candidate. It selects programs
using the following rules:

| Remaining candidates | Program constructed | Live application |
| --- | --- | --- |
| No survivors | None | Rejected |
| Survivors exist; none have sufficient positive support | All surviving programs combined, for inspection and confirmation examples | Rejected |
| One or more supported survivors | Only the supported surviving programs combined | Requires the checks below |

**Combine** means include all rules from the selected programs and remove exact
duplicates. All included rules apply together. The permitted layouts are the
intersection of the layouts permitted by those programs. Surviving candidates
below the positive threshold remain available for comparison, but contribute no
rules when supported survivors exist.

Before `session.apply()`, `session.spec.snapshot()`, `session.finish()`, or a
diagram call using the living spec can succeed, the combined program must:

1. Be checkable by core and feasible on every retained datum. A bounded search
   over generated data must find no additional conflict.
2. Permit every currently upvoted arrangement.
3. Exclude every currently downvoted arrangement.
4. Have at least `min_positive_votes` distinct, currently upvoted examples that
   satisfy the complete combination.

The negative-vote threshold controls candidate elimination. It does not relax
these application checks. A rejected arrangement can block application before
any candidate reaches the elimination threshold. The bounded data check does
not prove feasibility for every possible datum.

For example, candidate A puts a child **below** its parent. Candidate B puts it
**left** of its parent. With no votes, the inspection draft requires **below and
left**, but application is unavailable. An upvote for a below-right arrangement
supports A and counts against B. With the default thresholds, both survive, but
only A contributes to the applicable program.

If an above-left arrangement is then upvoted, both candidates have positive
support. Their combination requires below and left and excludes both approved
arrangements. Application is therefore rejected. In a separate session, approving
a below-left confirmation example can support both candidates and their
combination. It remains subject to all other retained judgments.

When positive support is missing, the loop can show confirmation examples even
with one survivor. A single survivor or exhausted search does not establish a
supported result. If core cannot check a synthetic comparison or combination,
the session reports it as unsupported; this produces no negative evidence.

## What the formal checks establish

The current membership adapter observes the order and alignment of visible node
centres, ignoring absolute distances, font metrics and canvas translation. Centres
within half a layout-coordinate pixel are grouped into an alignment class. Those
observations become ordinary Spytial constraints; core checks their joint
feasibility with each candidate. This supports suggest's orientation, alignment
and cyclic proposals; grouping and changing presentation are not supported.

`examples=` adds fixed cases **alongside generated data**. Use `strategy=` for a
Hypothesis strategy that respects your class's invariants; the default derives
one from its type. `max_examples=20` bounds each search invocation, including
candidate checks, contrast searches, and checking the combined result before use.
Exhaustion means “no further contrast found,” never equivalence or a finished design.
Data generation ignores existing diagram annotations, including an unavailable
living spec bound to the class. A replacement session can therefore start without
removing the earlier binding. It does not replace that binding until `apply()`.

## Replace components explicitly

The proposal and search components are independent:

- `proposer=` accepts a callable `(prompt, *, schema) -> dict`. Its response has
  `rules` and `programs`; each program has a readable `summary` and an `operations`
  list. The supplied schema describes the supported operations. Every proposal
  passes the same selector and whole-program checks.
- `search=` accepts an `ExampleSearch`: `initial(cls, *, max_examples)` supplies
  an optional seed, and `find(cls, predicate, *, max_examples)` searches for a
  value satisfying the predicate. Return `None` when nothing is found; raise
  generation errors. Both candidate checking and contrast search use this backend.
- `FixedExamples()` explicitly disables generated search; supply `examples=`.
- `FixedProposals(programs)` replays saved proposals without an LLM. Natural-language
  revision is disabled for this proposer. This is useful for controlled ablations.

```python
from spytial.suggest import FixedExamples, FixedProposals

# `saved_programs` uses the same summary/operations format as proposer output.
session = suggest(
    TreeNode,
    examples=[root],
    proposer=FixedProposals(saved_programs),
    search=FixedExamples(),
)
```

`strategy=` is shorthand for configuring the default `HypothesisSearch`; do not
combine it with `search=`. Neither backend needs to implement layout semantics:
those remain in spytial-core. The comparison strategy lives in
`spytial.suggest._compare` and uses the released checker already shared with
integration tests. There is no custom core build or new core comparison API.

Every comparison result is specific to its datum. Programs that agree on a leaf
may differ on a branching tree, which is why Hypothesis searches over data too.
Even on one datum, finding no contrast is not an equivalence proof: this search
tries particular constraint negations and can miss a possible distinction.

## Use and close a session

Drag the diagrams to explore, then rate them. **History** reopens the saved
arrangements and lets you correct classifications. Historical arrangements are
held fixed so a correction refers to the same example. **I'm done** saves a
checkpoint and pauses. It neither selects a candidate nor applies a spec. It is
available with zero, one, or several survivors, including unresolved results.
**Resume** continues with the same data and evidence. If no candidates remain,
correct earlier classifications or call `revise()` to request new candidates.

Once the session has a supported result, apply its **living spec**:

```python
import spytial

spec = session.apply()               # Same object as session.spec.
spytial.diagram(root)                # Uses the current rules for TreeNode.

session.resume()
session.revise("Keep subtrees together")
# Continue judging in the session. Once the result is supported again:
spytial.diagram(root)                # Picks up the updated rules automatically.
```

Applying connects the spec to the target class; existing and future instances
use its current rules on each `diagram()` call. The spec object keeps its identity
as votes, corrections, and new proposals change the program. Applying repeatedly
does not accumulate old rules, and ordinary class/object annotations remain intact.
Existing diagrams stay as they were; the next call uses the updated spec.

To use the spec for one diagram without changing the class:

```python
spec = session.spec
spytial.diagram(root, spec=spec)
snapshot = spec.snapshot()           # Independent, supported SpecDraft.
spytial.diagram(root, spec=snapshot)  # Keeps that version's rules.
spec.unapply()                       # Remove only this spec's class binding.
```

An explicit `spec=` replaces collected annotations for that call and accepts a
living spec, a `SpecDraft`, or a registry dictionary. `spec.status` and
`spec.result` expose the current support/conflict state. Application and use run
the same bounded generated-data check as `finish()`, cached until the living
result changes. They do not pause the exploration session.

If later evidence leaves no supported, consistent result, the same spec object
becomes unavailable and drawing raises `SpecUnavailableError`. It never silently
keeps eliminated rules or substitutes an unconstrained diagram. Further feedback
can make it usable again. `snapshot()` and `finish()` provide fixed copies when
that is wanted; `session.draft` exposes a separate editable copy for inspection.

```python
session.done()                       # Save this round, even if unresolved.
session.resume()                     # Continue exploring.
draft = session.finish()             # Export only a supported, consistent result.

session.save("tree-spec.json")       # Includes candidates, data, layouts and votes.
from spytial.suggest import SuggestSession
restored = SuggestSession.load(TreeNode, "tree-spec.json")
restored.resume()                    # No new LLM proposals needed to load.
restored.apply()                     # Explicitly bind the restored living spec.
```

Loading does not change class bindings. Applying the restored spec replaces the
previous living binding for that class. Closing a session stops its server.
An already supported living spec remains usable for drawing.

`session.draft` is available when the combination is checkable and feasible on
retained data. The copy can lack positive support or conflict with classifications.
Calling that copy's `apply()` or passing it as `diagram(..., spec=draft)` bypasses
the session's support and classification checks. It is a fixed `SpecDraft` and
does not follow later session changes. Use `session.apply()` or `session.spec`
for the checked, living result.

`finish()` checks support and conflicts, checkpoints the round, and raises if the
result is not ready. `session.spec.snapshot()` makes the same supported fixed
copy without pausing.
`session.checkpoints` preserves earlier results; `session.history` preserves
judged examples. `session.reclassify(question_id, side, "unsure")` corrects a
classification programmatically and reopens the session.

Without a browser, `next()` returns a question. Definite votes require the actual
positions: `vote(0, "upvote", layout_state={"positions": [...]})`. Each position
contains `id`, `x`, and `y` for a visible node. `judge("both", layout_states=[...,
...])` validates both layouts before saving either judgment. It can replace a
partial pair; the session updates scores and advances only after both judgments
are saved. If either layout is invalid, the question and saved evidence remain
unchanged. Missing, invalid, or incomplete positions cannot produce elimination
evidence. Unsure can be recorded without positions.

Run `python -m demos.suggest_session` for the browser demo. Keep the Python
process running while using it. Requires Node and the `suggest-search` extra,
plus the configured model provider. The local server serves the packaged renderer;
`SPYTIAL_BROWSER_BUNDLE` can select another build for development. `close()` stops
the local server; sessions support `with` blocks.

## Test the session contract

Mechanism tests use `FixedProposals` and known data and arrangements. They call
the released core checker; they require Node but no model credentials or external
network.
Expected votes and application results are specified independently of the
session's implementation.

| Behavior | Tests |
| --- | --- |
| All nine pairs of upvote, downvote, and unsure; candidate scores, elimination, and result availability | `test/test_suggest_session.py` |
| Evidence counted once; correction and replay; zero survivors; shared support; save and load | `test/test_suggest_living.py` |
| Several survivors; supported rules selected; combination applied or refused; configurable positive threshold; next diagram uses the same updated handle | `test/test_suggest_apply.py` |
| Generated data distinguishes programs and exposes conflicts missed by supplied examples | `test/test_suggest_session.py`, `test/test_suggest_apply.py` |
| Arrangement membership and datum-specific contrast witnesses | `test/test_suggest_evidence.py`, `test/test_suggest_compare.py` |
| Actual dragging, independent controls, history restoration, notebook startup, and rendered output after revision | `test/test_suggest_session_browser.py`, `test/test_suggest_apply.py` |

Run the mechanism checks from the repository root:

```bash
python -m pip install -e '.[dev]'
python -m pytest test/test_suggest_session.py test/test_suggest_living.py \
  test/test_suggest_apply.py test/test_suggest_evidence.py test/test_suggest_compare.py
```

Hypothesis integration tests use explicit strategies with known distinguishing
or conflicting cases. Exhausting a search must leave the result unresolved when
positive evidence is missing. Model proposal quality requires a separate
evaluation; these tests establish the behavior of the interaction mechanism.

Run the browser checks with the packaged renderer:

```bash
python -m pip install -e '.[dev,e2e]'
python -m playwright install chromium
SPYTIAL_BROWSER_TESTS=1 python -m pytest \
  test/test_suggest_session_browser.py test/test_suggest_apply.py
```

CI runs both sets. The browser checks include a real `diagram()` call after a
revision and verify that an earlier exported diagram remains unchanged.

## Migration from draft-only suggest

`suggest(...)` now returns a `SuggestSession`. Existing one-shot draft code
should import `suggest_draft` instead. Its `enrich=` and `ask=` behavior is
preserved. Sessions use `proposer=` and `rules=`; `interactive=True` is no longer
needed or accepted.

## Generate an editable draft

Spytial annotations are the decorators that shape a diagram, such as
`@orientation` and `@hideAtom`. The hard part is starting them from a blank
page. A blank page asks for two decisions at once: what the diagram should look
like, and which selectors and directives express that. A missing rule is often
noticed only after it is broken. Diagonal children suggest the rule "put every
child directly below its parent." A visible parent pointer suggests the rule
"hide that implementation detail."

`suggest_draft` replaces the blank page with a concrete, editable draft, a
`SpecDraft`. A draft that is almost right is easier to fix than a blank page is
to fill. Even a wrong suggestion points at one specific thing to change. So a
suggested default need not be correct to be useful. If it is correct, apply it.
If it is wrong, read its selectors and correct one part.

By default, `suggest_draft` runs locally and is deterministic. Models and Hypothesis
witness search are optional. They load only when they are requested.

## How it works

`suggest_draft` inspects a class or object and returns a `SpecDraft`: a set of
proposed annotations, each with a rationale and a source.

The default path is deterministic. It matches common field shapes to directives,
with no model and no network. These built-in rules are covered under
[Deterministic heuristics](#deterministic-heuristics).

`enrich=` adds a model. The model can pick a layout shape from a fixed
vocabulary, or author a selector, including one translated from a plain-language
`ask=`. A model can be wrong, so anything it authors is checked: the selector
runs against the values in `instance=`, `examples=`, or `strategy=`, and shall
denote real atoms or edges before it joins the draft.

Nothing is applied automatically. The draft is there to inspect, edit, and
apply.

## Quick start

The following is an ordinary Python tree:

```python
from dataclasses import dataclass
from typing import Optional

import spytial
from spytial.suggest import suggest_draft


@dataclass
class TreeNode:
    value: int
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None


root = TreeNode(8, TreeNode(3), TreeNode(10))
draft = suggest_draft(root)
print(draft.to_source())
```

The deterministic analyzer suggests a standard tree layout:

```python
@spytial.orientation(
    selector='left - (univ -> NoneType)',
    directions=['below', 'left'],
)
@spytial.orientation(
    selector='right - (univ -> NoneType)',
    directions=['below', 'right'],
)
@spytial.attribute(field='value')
@spytial.hideAtom(selector='NoneType')
@spytial.flag(name='hideDisconnected')
```

`to_source()` writes each decorator on one line and adds a comment. The example
above is expanded for readability. Paste and edit this source, or apply the
draft to the class directly:

```python
draft.apply()
spytial.diagram(root)
```

If the layout is close but not correct, state the correction:

```python
from spytial.suggest import ClaudeCode

draft = suggest_draft(
    root,
    ask="put every child directly below its parent",
    enrich=ClaudeCode(),
)
```

Spytial accepts the request. It selects `left + right` and uses `below`. The
earlier below-left and below-right rules move to `draft.alternatives`. Spytial
does not discard them.

Either import style can be used; both explicitly select draft construction:

```python
import spytial

draft = spytial.suggest.suggest_draft(root)
```

```python
from spytial.suggest import suggest_draft

draft = suggest_draft(root)
```

## What each parameter does

The full interface is:

```python
suggest_draft(
    target,
    *,
    instance=None,
    examples=None,
    strategy=None,
    enrich=None,
    ask=None,
    registry=None,
)
```

Each input provides a different kind of information. `examples=` and `strategy=`
are not the same thing.

| Parameter | Meaning | Use it when |
| --- | --- | --- |
| `target` | Required. A class, or an object. An object means the class and one concrete value. | Always provide this. |
| `instance` | One concrete value for a class target. It shows runtime structure that annotations and `__init__` do not. Spytial also uses it as the default witness for selector checks. | A representative object is already available. |
| `examples` | Fixed, specific cases. A model-written selector shall pass on every example that Spytial can build. | Awkward or important cases need to be preserved. |
| `strategy` | A Hypothesis strategy for a family of values. Spytial runs a bounded search for one representative witness. The value `"auto"` uses `hypothesis.strategies.from_type(target)`. | Valid values require generation, or one hand-picked value would mislead. |
| `enrich` | The model provider. It is a model name, a callable, or a built-in such as `ClaudeCode()` or `Codex()`. There is no default model. | Field names or domain conventions carry intent that types do not show. |
| `ask` | A plain-language statement of the required layout. `enrich=` translates it. It overrides any overlapping geometric suggestion. | The correction is easier to describe than to write as a selector. |
| `registry` | A different registry of deterministic rules. | The project has its own field conventions or layout policy. |

### Choose the input

Static analysis of a type needs no value, model, or optional dependency:

```python
draft = suggest_draft(TreeNode)
```

Pass an object, or a type with `instance=`, when runtime values show structure
that static inspection cannot find:

```python
draft = suggest_draft(root)
draft = suggest_draft(TreeNode, instance=root)  # equivalent input
```

Use `examples=` for fixed cases. Every model-written selector shall pass all of
them:

```python
draft = suggest_draft(
    TreeNode,
    examples=[empty_tree, balanced_tree, zig_zag_tree],
    enrich=model,
)
```

Use `strategy=` for a family of valid values. Spytial adds one generated witness
to the fixed set:

```python
draft = suggest_draft(
    RedBlackNode,
    examples=[empty_tree, deletion_corner_case],
    strategy=valid_red_black_trees(),
    enrich=model,
)
```

For a request on a class alone, Spytial uses `strategy="auto"`:

```python
draft = suggest_draft(
    TreeNode,
    ask="put every child below its parent",
    enrich=ClaudeCode(),
)
```

Hypothesis builds a strategy from `TreeNode`. For a recursive class, Spytial
searches in three steps. First, it looks for a value that fills every public
recursive field. Next, it looks for any non-leaf value. Last, it looks for any
value that it can build. Supply a custom strategy when the type has invariants
that Hypothesis cannot infer.

Install witness search separately:

```console
pip install "spytial_diagramming[suggest-search]"
```

The plain `suggest_draft(TreeNode)` path does not import Hypothesis.

## Working with `SpecDraft`

`suggest_draft()` returns a draft. It does not change the target class. The main
collections show both the suggestion and the reason for it:

| Member | Contents |
| --- | --- |
| `draft.suggestions` | The current `Suggestion` objects. This includes the disabled low-confidence rows. |
| `draft.enabled()` | The suggestions that are enabled by default. |
| `draft.alternatives` | Suggestions that lost a conflict, and geometry that was replaced. Spytial keeps them so they can be inspected or restored. |
| `draft.notes` | Missing input, skipped enrichment, validation results, and other diagnostics. |

Each `Suggestion` records its `directive`, `kwargs`, `confidence`, `rationale`,
and `source_field`. It also records whether it is enabled, and whether it came
from a deterministic rule or a model.

The draft can be rendered or applied in four ways:

| Call | Result |
| --- | --- |
| `draft.to_source()` | A pasteable stack of `@spytial.*` decorators. |
| `draft.to_registry()` | A `{"constraints": [...], "directives": [...]}` registry dictionary. |
| `draft.apply()` | Decorates the target class in place and returns it. |
| `draft` in Jupyter | A panel that shows the directives, rationales, alternatives, and notes. |

These methods use the enabled suggestions by default. Pass `enabled_only=False`
to include the disabled ones. `to_source(with_comments=False)` leaves out the
generated rationales.

Review the draft before calling `apply()`. `apply()` installs decorators on the
class. This changes every later diagram of its instances.

## Deterministic heuristics

Without a model, `suggest_draft` reads the field types, the field names, the
`__init__` assignments, and any instance values, then maps common structures to
directives. Three examples:

| Field shape | Suggested treatment |
| --- | --- |
| `left` and `right` of the same node type | Orient below-left and below-right. |
| A scalar such as `value`, `key`, or `name` | Fold it into the node with `attribute`. |
| A `parent` back-pointer duplicated by child edges | Hide it. |

Each rule is a function registered with `@heuristic`. Register a rule to add a
project convention or a domain field name:

```python
from spytial.suggest import Suggestion, heuristic


@heuristic(scope="field", priority=100)
def color_by_status(field, cls_info):
    if field.name == "status" and field.enum_members:
        return [
            Suggestion(
                directive="atomStyle",
                kwargs={
                    "selector": (
                        f"{{ x : {cls_info.cls.__name__} | "
                        f'@:(x.status) = "active" }}'
                    ),
                    "borderStyle": {"color": "seagreen"},
                },
                confidence="high",
                rationale="active status → green",
                source_field="status",
            )
        ]
    return []
```

A field-scope heuristic receives `(FieldInfo, ClassInfo)`. A class-scope
heuristic receives `ClassInfo` and can find multi-field patterns. On the same
field, the higher priority wins, and the losing suggestion becomes an
alternative.

Pass `suggest_draft(cls, registry=my_registry)` for a separate rule set. Use
`DEFAULT_REGISTRY.copy()` to extend the built-in rules without changing the
global registry.

## Model providers

`enrich=` always names a provider. There is no default model. The default path
makes no model call.

### Claude Code

`ClaudeCode` uses the installed and authenticated `claude` CLI. It needs no
Spytial model extra and no API key:

```python
from spytial.suggest import ClaudeCode, suggest_draft

draft = suggest_draft(Ticket, enrich=ClaudeCode())
draft = suggest_draft(Ticket, enrich=ClaudeCode(model="opus"))
```

If `ANTHROPIC_API_KEY` is set, the CLI can use metered API billing instead of a
Claude subscription. Check the current authentication behavior of the CLI before
choosing a provider.

### Codex

`Codex` uses the installed and authenticated `codex` CLI. It uses the native
JSON-schema output of that CLI:

```python
from spytial.suggest import Codex, suggest_draft

draft = suggest_draft(Ticket, enrich=Codex())
```

### A model identifier through `llm`

The `llm` library by Simon Willison resolves a string name. It supports hosted
providers and local models through plugins:

```console
pip install "spytial_diagramming[suggest-llm]"
llm install llm-anthropic
llm keys set anthropic
```

```python
draft = suggest_draft(Ticket, enrich="claude-sonnet-4-6")
draft = suggest_draft(Ticket, enrich="llama3.2")  # for example, through Ollama
```

### A custom provider

A provider is any callable with the signature `(prompt, *, schema) -> dict`.
Spytial provides helpers for text-only models:

```python
from spytial.suggest.providers import extract_json, instruct_json


def my_provider(prompt, *, schema):
    text = call_some_model(instruct_json(prompt, schema))
    return extract_json(text)


draft = suggest_draft(Ticket, enrich=my_provider)
```

The shape layer sends the class, field, and type names. When values are present,
the selector layer also sends the relation names, arities, and atom counts. The
field values stay on the local machine. Spytial uses them only to evaluate
selectors. With a local provider, no data leaves the machine.

<!--
## Engineering considerations

### Give inference only as much freedom as can be checked

Suggestion has three layers:

1. The deterministic layer finds common program structures. It writes selector
   forms that Spytial maintains.
2. In the shape layer, a model may choose `orientation`, `cyclic`, `group`, or
   no shape, with arguments from a fixed vocabulary. Spytial writes the
   selector.
3. In the selector layer, a model may write a selector, or translate an `ask=`,
   provided concrete witnesses are present. Each candidate shall run before it
   enters the draft.

The rule is the same at each layer. More freedom to generate requires a stronger
check. A static rule needs no check. A chosen shape cannot become an invalid
selector. A model-written selector shall run and pass first.

A valid shape becomes the active geometry for the fields it covers. The
deterministic geometry that it replaces becomes an alternative. If enrichment
fails, the deterministic draft still works. `draft.notes` explains what Spytial
skipped.

A model-written selector from automatic enrichment stays disabled until it is
reviewed. An explicit `ask=` is different. Spytial enables it on acceptance,
because it was requested.

### Check denotation, not only syntax

A model-written selector shall meet all of the following conditions:

1. use a supported directive and arguments from the vocabulary;
2. parse correctly, return a non-empty result, and have the exact arity of the
   directive on every validation example that Spytial can build; and
3. pass the same authoring checks as a handwritten decorator.

An orientation selector shall denote pairs. `hideAtom` shall denote atoms. This
arity check is important. An invented bareword can parse as an arity-zero
literal. It does not fail as a syntax error.

An explicit request receives one repair attempt. The repair uses the concrete
validation diagnostics. If Spytial can accept no part of the request, `suggest_draft`
raises `spytial.suggest.AskError`. A request with several parts can accept the
valid parts. Spytial records the rest in `draft.notes`.

### Keep alternatives, and fail loudly on an explicit ask

When an explicit ask replaces overlapping geometry, the earlier suggestions move
to `draft.alternatives`. Spytial does not destroy them. To find an overlap,
Spytial evaluates the intersection of the selectors on the available witnesses.
It does not compare selector strings.

Optional enrichment can fail. If it fails, the deterministic draft does not
change. An explicit `ask=` shall install at least one validated directive, or
raise an error. This difference prevents a requested correction from
disappearing without notice.

### A witness is not a proof

`examples=` checks the specific cases that are supplied. `strategy=` adds one
generated witness. Neither one proves that a selector works for every value.

This matters for empty structures. On a leaf, a child selector returns no pairs.
This does not disprove the rule "put every child below its parent." On a leaf,
the rule simply has no children to place. For this reason, auto-generation
prefers a filled recursive witness that exercises the selector.

Evaluation can show that a selector denotes real atoms or edges in the
witnesses. It cannot show that `below` matches the user's intent. The user makes
the final specification.

### Keep the default path cheap and local

Static suggestion needs no model, network, Hypothesis, or headless evaluator.
Provider resolution, witness search, and selector evaluation load only when the
matching argument asks for them.

Selector authoring and `ask=` require a `node` runtime on `PATH`, or a binary
named by `SPYTIAL_NODE`. Spytial uses it to run the vendored headless evaluator.
-->

## Limits

Program structure is input for a layout. It is not the layout. `suggest_draft`
cannot recover a tree that exists only as index arithmetic in an array-backed
heap. A model can read a real field in the wrong
way. A selector can pass every supplied example and still fail on the next one.

These limits are the reason the result is a `SpecDraft`. The rationales and the
provenance are visible. The alternatives stay available. Model-written selectors
run before Spytial accepts them. An explicit ask fails loudly. The user decides
what becomes the final layout.

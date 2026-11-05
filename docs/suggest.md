# Build a visualization one requirement at a time

Start with the [interactive notebook](https://github.com/sidprasad/spytial/blob/main/demos/06-suggest-session.ipynb).

```python
from spytial.suggest import suggest

session = suggest(TreeNode, examples=[root], strategy=trees)
display(session)  # In a local Jupyter notebook; session.show() opens a browser.
```

Startup prepares data and shows an initial diagram. It makes no model request.
Enter **Parents above children** in the embedded prompt and click **Explore**.
Adding, judging, finishing, and revising requirements all happen in this view.
The Python methods below provide the same controls for scripts.

The LLM proposes interpretations of that requirement. Hypothesis searches for data
that distinguishes them. Spytial constructs two draggable diagrams of the same
datum. Rate each with **upvote**, **downvote**, or **unsure**, judging the requested
requirement. Every previously accepted requirement applies to both diagrams.

## Finish a requirement round

**I'm done** ends the active round. Programmatically:

```python
checkpoint = session.done()
session.active_requirement.status
```

A **survivor** has fewer than `elimination_threshold=2` negative votes. A
**supported survivor** also has at least `min_positive_votes=1` positive vote.
These thresholds are configurable. The round combines **all supported survivors**
by including every rule from their interpretations and removing exact duplicates.
Unreviewed and eliminated candidates contribute no rules.

The combination is accepted only when:

- It permits every current upvote for this requirement and excludes every current
  downvote for this requirement.
- At least `min_positive_votes` distinct upvoted arrangements support the whole
  combination. Separate support for its parts is insufficient.
- It is feasible with the other accepted requirements on retained data, and bounded
  generated-data search finds no further conflict.

For example, supported interpretations requiring **below** and **right** contribute
**below and right**. An earlier upvote for a below-left arrangement prevents this
combination from being accepted. The session keeps the requirement unfinished so the
person can correct history or revise its interpretations.

A completed vote pair automatically accepts a sole surviving interpretation when
these checks pass. One survivor without positive evidence remains unfinished.
Several survivors can be accepted together through **I'm done**. Exhausting a
search never establishes equivalence and never automatically accepts a requirement.

`done()` checkpoints and pauses even when no candidates remain or the combination
is unresolved. It does not bind a spec to the class, close the controls, or write a
file. `requirement.accept()` performs the same combination checks explicitly.

## Add another requirement

After acceptance, the view opens a prompt for the next requirement. Enter **Align
siblings horizontally** and click **Explore**. You can also use **Add requirement**
at any point. The accepted prompts remain visible with a ✓; click one to revisit it.

The corresponding Python call is:

```python
horizontal = session.add_requirement("Align siblings horizontally")
# Drag and judge in the existing view, then click I'm done.
```

The accepted parent-child requirement remains applied throughout this round.
Conceptually, comparisons use `accepted background + interpretation A` and
`accepted background + interpretation B`. The proposals describe only the new
requirement. One prompted requirement may compile into several Spytial operations.

An unfinished new requirement contributes no rules. The living spec continues to use
previously accepted requirements. The requirement buttons above the diagrams let you
return to an earlier requirement, continue judging it, or revise its wording.

## Keep judgments as evidence about a requirement

Each saved judgment includes the requirement's identity and wording revision, the
datum, the actual dragged positions, the programs shown, and the accepted
background at that time.

An upvote while judging **Parents above children** does not approve every incidental
feature of the picture. Later adding **Align siblings** may exclude that old
arrangement without contradicting the parent-child judgment. Candidate scoring
checks each requirement's own rules, with the fixed presentation; it does not include
other requirements' positional constraints.

| Classification | Interpretation permits the arrangement | Interpretation excludes it |
| --- | --- | --- |
| Upvote | +1 positive | +1 negative |
| Downvote | +1 negative | No change |
| Unsure | No change | No change |

Votes update scores immediately. After both diagrams are rated, the next pair is
prepared, or a sole supported survivor is accepted. Repeated classifications of
the same requirement, datum, and qualitative arrangement count once; the latest
classification wins. The same arrangement can supply independent evidence for
another requirement. Corrections can restore eliminated candidates. Use
`session.add_examples([another_root])` to retain more data without dropping evidence.

**History** reopens saved arrangements and permits corrections. Their positions
stay fixed so a correction concerns the same example. Programmatically:

```python
vertical = session.requirements[0]
entry = vertical.history[0]
session.reclassify(entry["id"], 0, "unsure")
```

A correction recomputes only the relevant evidence. Accepted candidates that lose
support or are eliminated are removed from that requirement's definition. If the
remaining combination disagrees with its judgments, the requirement's acceptance is
withdrawn. Other accepted requirements remain active.

## Revise an earlier requirement

Click its prompt in the view, edit the wording, and choose **Revise**. Choose
**Continue** to resume its existing candidates. In Python:

```python
vertical = session.requirements[0]
vertical.revise("Keep left children below and left of their parent")
# Judge in the same embedded view; vertical.done() ends this round.
```

Revision replaces that requirement's candidate set, archives its old wording and
candidates, and replays its entire classification history against the new
interpretations. Its old definition is withdrawn while it is edited. The other
accepted requirements stay applied to the living spec and the comparison diagrams.
A new wording does not erase a conflicting judgment; correct it in History when
your intent changes.

`vertical.resume()` returns to its existing candidates without making a model
request. `session.resume()` continues the active requirement. `session.requirements`
contains handles for every requirement, including unfinished ones.

## Apply the living spec

```python
import spytial

spec = session.apply()       # Same stable object as session.spec.
print(spec)                 # Rules annotated with their prompts and interpretations.
spytial.diagram(root)        # Uses accepted requirements for TreeNode.

# After accepting another requirement or revising one:
spytial.diagram(root)        # Reads the updated rules on this call.
```

`print(spec)` resolves the current rules each time. Each rule's comment names its
requirement, wording revision, and accepted interpretation. If several accepted
interpretations or prompts contribute the same rule, all sources are preserved.
Presentation rules inferred from Python data are marked separately.

`spec.provenance` returns a list of `{rule, origin, sources}` records. Each source
contains `requirement_id`, `prompt`, `revision`, `candidate_id`, and `interpretation`.
It also contains `prompt_fragments`: exact excerpts supplied for that rule. The
model supplies these per operation, and the session checks that they occur in the
prompt. A provider that omits excerpts attributes the operation to the whole prompt.
Only currently accepted candidates contribute sources. Revision, corrected votes,
and save/load update or preserve this mapping along with the living spec.

`spec.to_source()` returns the annotated source; `spec.to_source(with_comments=False)`
omits comments. `spec.to_registry()` returns the registry dictionary. A snapshot's
source comments remain fixed with its rules.

Each accepted requirement's definition is conjoined with every other accepted
requirement. Existing diagrams retain their earlier layout. Ordinary handwritten
annotations and inheritance controls remain intact.

To avoid a class binding:

```python
spytial.diagram(root, spec=session.spec)
```

An explicit `spec=` replaces collected annotations for that call. No accepted
requirements, or an infeasible accepted combination, makes live use raise
`SpecUnavailableError`. It does not draw an unconstrained fallback. An unresolved
new requirement leaves earlier accepted definitions usable. Editing the only accepted
requirement temporarily makes the living spec unavailable until a definition is
accepted again.

`spec.snapshot()` returns a fixed, supported `SpecDraft`; later feedback does not
change it. `finish()` checkpoints the active round and returns a fixed copy of the
accepted spec. `spec.unapply()` removes its class binding.

## Save, close, and reopen

```python
session.save("tree-session.json")
session.close()
spytial.diagram(root, spec=spec)  # A supported spec still works.

from spytial.suggest import SuggestSession
session = SuggestSession.load(TreeNode, "tree-session.json", strategy=trees)
session.resume()
display(session)
spec = session.apply()           # Explicitly connect the restored session.
```

`close()` stops the local controls. A closed session cannot resume; load a saved
session to continue. Loading preserves requirements, wording revisions, accepted
candidate sets, datums, positions, partial votes, corrections, and checkpoints. It
makes no model request and changes no class binding. Applying the restored handle
replaces the earlier living binding. Save format **3** requires requirement-scoped
judgments; earlier save formats are rejected explicitly.

## Configuration and formal checks

The default model provider is `Codex()`, using an authenticated local CLI. Select
another with `proposer=ClaudeCode()`, a model-id string, or a callable
`(prompt, *, schema) -> dict`. A response contains `programs`, each with a readable
`summary` and an `operations` list. The schema permits orientation, alignment,
and cyclic operations with `hold: always` or `hold: never`, plus a `prompt_fragment`
quoting the relevant wording. Attribution metadata is kept out of the core spec.
The LLM is asked for
2–4 interpretations; `max_candidates=4` caps each round, including one repair call.
Provider failures leave earlier requirements and judgments available for retry.

The default search is `HypothesisSearch(strategy or "auto")`. Supplied examples
supplement generated data. Each candidate/contrast search is limited to
`max_examples=20` predicate checks, including shrinking. It stops starting checks
after five seconds; an in-progress core request has a separate hard 20-second
timeout. A checked witness is retained if shrinking runs out of budget. These are
per-search limits; a round can run several searches. To configure them:

```python
from spytial.suggest import HypothesisSearch

session = suggest(TreeNode, examples=[root],
                  search=HypothesisSearch(trees, max_seconds=5), max_examples=10)
```

Generation inspects data without resolving existing diagram annotations or an
unavailable older living binding. Install `spytial_diagramming[suggest-search]`
for Hypothesis and have Node available for core checks. Set `SPYTIAL_CODEX` or
`Codex(bin="/absolute/path/to/codex")` if the notebook kernel cannot find the CLI.

Each session starts one Node worker lazily and reuses the released checker and
selector evaluator. Identical selectors and program checks use bounded caches.
`close()` stops the worker as well as the controls. A timeout or worker failure
raises an error and never counts as negative evidence. Later requests can start a
fresh worker. The released checker, its version checks, and its semantics are
unchanged.

The view reports model drafting, checking, and comparison phases while a request
is running. `session.timings` reports seconds for `model`, `checking`, and
`comparison`, reset when a requirement is proposed or revised. Later comparison
searches accumulate in the comparison total. `session.search.last_run` reports
the last Hypothesis search's check count, duration, budget cutoff, and witness status.

`FixedExamples()` disables generated search; supply examples explicitly.
`FixedProposals(programs)` substitutes deterministic model responses. An
`ExampleSearch` implements `initial(cls, *, max_examples)` and
`find(cls, predicate, *, max_examples)`; both return a value or `None` and propagate
generation errors. These components can be replaced independently.

Core owns selector interpretation, negation, layout feasibility, and rendering.
Python owns proposal, search, classification, and acceptance policy. Membership
checks qualitative node-centre order and alignment with tolerance 0.5 layout units.
Invalid positions or checker errors never become rejection evidence. Grouping,
spacing, and font metrics are outside this classification mechanism.

Contrast search retains the accepted background and uses checked rule negations
to find an arrangement accepted by one interpretation and excluded by another.
It is incomplete, even for one datum. A multi-operation requirement is not negated
merely by negating every rule. Bounded search is evidence, not an equivalence or
universal feasibility proof. Modal comparison remains separate (#174).

## Test the interaction contract

```bash
python -m pytest test/test_suggest_session.py test/test_suggest_living.py \
  test/test_suggest_apply.py test/test_suggest_evidence.py test/test_suggest_compare.py

SPYTIAL_BROWSER_TESTS=1 python -m pytest \
  test/test_suggest_session_browser.py test/test_suggest_apply.py
```

Tests use deterministic proposals, known arrangements, real Hypothesis strategies,
and the released core checker. They cover all nine vote pairs, shared support for
multiple survivors, requirement-scoped evidence, additive contexts, replacement and
replay, atomic batch judgments, persistence, live application, and dragging in the
embedded controls. Browser tests require Playwright and Chromium. CI runs both.

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

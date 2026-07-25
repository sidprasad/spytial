# Suggesting Spytial Annotations

Spytial annotations are the decorators that shape a diagram, such as
`@orientation` and `@hideAtom`. The hard part is starting them from a blank
page. A blank page asks for two decisions at once: what the diagram should look
like, and which selectors and directives express that. A missing rule is often
noticed only after it is broken. Diagonal children suggest the rule "put every
child directly below its parent." A visible parent pointer suggests the rule
"hide that implementation detail."

`spytial.suggest` replaces the blank page with a concrete, editable draft, a
`SpecDraft`. A draft that is almost right is easier to fix than a blank page is
to fill. Even a wrong suggestion points at one specific thing to change. So a
suggested default need not be correct to be useful. If it is correct, apply it.
If it is wrong, read its selectors and correct one part.

By default, `suggest` runs locally and is deterministic. Models and Hypothesis
witness search are optional. They load only when they are requested.

## How it works

`suggest` inspects a class or object and returns a `SpecDraft`: a set of
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
from spytial.suggest import suggest


@dataclass
class TreeNode:
    value: int
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None


root = TreeNode(8, TreeNode(3), TreeNode(10))
draft = suggest(root)
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

draft = suggest(
    root,
    ask="put every child directly below its parent",
    enrich=ClaudeCode(),
)
```

Spytial accepts the request. It selects `left + right` and uses `below`. The
earlier below-left and below-right rules move to `draft.alternatives`. Spytial
does not discard them.

Either import style can be used. The `suggest` subpackage is lazy and callable:

```python
import spytial

draft = spytial.suggest(root)
```

```python
from spytial.suggest import suggest

draft = suggest(root)
```

## What each parameter does

The full interface is:

```python
suggest(
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
draft = suggest(TreeNode)
```

Pass an object, or a type with `instance=`, when runtime values show structure
that static inspection cannot find:

```python
draft = suggest(root)
draft = suggest(TreeNode, instance=root)  # equivalent input
```

Use `examples=` for fixed cases. Every model-written selector shall pass all of
them:

```python
draft = suggest(
    TreeNode,
    examples=[empty_tree, balanced_tree, zig_zag_tree],
    enrich=model,
)
```

Use `strategy=` for a family of valid values. Spytial adds one generated witness
to the fixed set:

```python
draft = suggest(
    RedBlackNode,
    examples=[empty_tree, deletion_corner_case],
    strategy=valid_red_black_trees(),
    enrich=model,
)
```

For a request on a class alone, Spytial uses `strategy="auto"`:

```python
draft = suggest(
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

The plain `suggest(TreeNode)` path does not import Hypothesis.

## Working with `SpecDraft`

`suggest()` returns a draft. It does not change the target class. The main
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

Without a model, `suggest` reads the field types, the field names, the
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

Pass `suggest(cls, registry=my_registry)` for a separate rule set. Use
`DEFAULT_REGISTRY.copy()` to extend the built-in rules without changing the
global registry.

## Model providers

`enrich=` always names a provider. There is no default model. The default path
makes no model call.

### Claude Code

`ClaudeCode` uses the installed and authenticated `claude` CLI. It needs no
Spytial model extra and no API key:

```python
from spytial.suggest import ClaudeCode, suggest

draft = suggest(Ticket, enrich=ClaudeCode())
draft = suggest(Ticket, enrich=ClaudeCode(model="opus"))
```

If `ANTHROPIC_API_KEY` is set, the CLI can use metered API billing instead of a
Claude subscription. Check the current authentication behavior of the CLI before
choosing a provider.

### Codex

`Codex` uses the installed and authenticated `codex` CLI. It uses the native
JSON-schema output of that CLI:

```python
from spytial.suggest import Codex, suggest

draft = suggest(Ticket, enrich=Codex())
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
draft = suggest(Ticket, enrich="claude-sonnet-4-6")
draft = suggest(Ticket, enrich="llama3.2")  # for example, through Ollama
```

### A custom provider

A provider is any callable with the signature `(prompt, *, schema) -> dict`.
Spytial provides helpers for text-only models:

```python
from spytial.suggest.providers import extract_json, instruct_json


def my_provider(prompt, *, schema):
    text = call_some_model(instruct_json(prompt, schema))
    return extract_json(text)


draft = suggest(Ticket, enrich=my_provider)
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
validation diagnostics. If Spytial can accept no part of the request, `suggest`
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

Program structure is input for a layout. It is not the layout. `suggest`
cannot recover a tree that exists only as index arithmetic in an array-backed
heap. A model can read a real field in the wrong
way. A selector can pass every supplied example and still fail on the next one.

These limits are the reason the result is a `SpecDraft`. The rationales and the
provenance are visible. The alternatives stay available. Model-written selectors
run before Spytial accepts them. An explicit ask fails loudly. The user decides
what becomes the final layout.

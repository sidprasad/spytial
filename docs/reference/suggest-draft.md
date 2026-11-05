# Drafting annotations

`suggest_draft()` inspects a class or object and proposes editable annotations.
By default it uses local rules without an LLM or Hypothesis. Use
[interactive suggest](../suggest.md) to develop rules by judging diagrams.

## Inspect and apply

Given an existing object `root`:

```python
from spytial.suggest import suggest_draft

draft = suggest_draft(root)
print(draft.to_source())
```

Inspect the draft before applying it:

```python
draft.apply()  # Install its enabled annotations on the object's class.
```

| Member | Use |
| --- | --- |
| `draft.suggestions` | Inspect suggestions, confidence, rationale, and enabled state. |
| `draft.alternatives` | Inspect suggestions displaced by another choice. |
| `draft.notes` | Read diagnostics. |
| `draft.to_source()` | Export decorators; `with_comments=False` omits rationales. |
| `draft.to_registry()` | Export constraints and directives as a dictionary. |

Export and application use enabled suggestions by default. Pass
`enabled_only=False` to include disabled suggestions. A draft is fixed: applying
it does not create a living spec or an interactive session.

## Request a model-generated draft

Choose a provider explicitly with `enrich=`. Add `ask=` for a specific request:

```python
from spytial.suggest import Codex

draft = suggest_draft(
    root,
    enrich=Codex(),
    ask="Put every child below its parent",
)
print(draft.to_source())
```

`enrich` also accepts `ClaudeCode()`, a model-id string, or a callable
`(prompt, *, schema) -> dict`. CLI providers must be installed and authenticated.
Model-id strings require the `suggest-llm` extra and a configured `llm` provider.
Selector validation needs Node.js.

Pass `examples=[...]` to check model-authored selectors on additional objects.
`strategy=` adds a generated example; it requires the `suggest-search` extra.
Checks on examples do not establish correctness for every possible input.
An unsuccessful enrichment leaves notes on the draft. An explicit `ask=` raises
`AskError` if its request cannot be translated and validated.

## Customize the local rules

Built-in rules recognize common fields such as `left`, `right`, and `value`.
Pass `registry=` to use your own rules. `DEFAULT_REGISTRY.copy()` provides a
starting point; register field or class rules with its `heuristic()` decorator.

See the API reference for [all draft options](api.md#spytial.suggest.suggest_draft)
and [heuristic registration](api.md#spytial.suggest.HeuristicRegistry).

# Suggesting specs

`spytial.suggest` reads a class and proposes a starting set of layout
directives — a lightweight scaffold you then edit, not a finished spec. By
default it is pure static analysis: no LLM, no network, no extra dependencies
(an optional model-backed enrichment layer is described [below](#optional-llm-enrichment)).
The whole point is to get you past the blank page.

It lives in its own subpackage and is **not** imported by `spytial` itself, so
you opt in:

```python
from spytial.suggest import suggest

draft = suggest(TreeNode)
print(draft.to_source())
```

```text
@spytial.orientation(selector='left', directions=['below', 'left'])   # left child of the same type → tree edge below-left
@spytial.orientation(selector='right', directions=['below', 'right'])  # right child of the same type → tree edge below-right
@spytial.attribute(field='value')                                      # value is scalar data → fold into the node
```

Paste those above your class and adjust. Every suggestion carries the reasoning
that produced it, so the scaffold doubles as a tour of the directive language.

## What you get back

`suggest()` returns a `SpecDraft` you can render four ways:

| Call | Result |
|------|--------|
| `draft.to_source()` | the paste-able `@spytial.*` decorator stack (a string) |
| `draft.to_registry()` | the `{"constraints": [...], "directives": [...]}` dict |
| `draft.apply()` | decorates the class live and returns it |
| `draft` (in Jupyter) | a rich panel of proposed directives with the reasoning |

By default these show only the high-confidence suggestions. Pass
`enabled_only=False` to include the speculative ones too.

## How it decides

The analyzer reads two cheap facts per field — its **type** and its **name** —
and maps them to directives:

| Field shape | Suggestion |
|-------------|-----------|
| `left` + `right` of the same type | `orientation` below-left / below-right |
| a single self-referential field | `orientation` below |
| a list/dict of the same type (`children`) | `orientation` below |
| `next` (+ `prev`) of the same type | `orientation` right (reverse link hidden) |
| `parent` / back-pointer | `hideField` if child edges exist, else `orientation` above |
| a scalar (`value`, `key`, `name`, …) | `attribute` — folded into the node |
| an `Enum`-typed field | one `atomColor` per member (off by default) |
| children that can be `None` | `hideAtom(selector='NoneType')` |

Two choices worth knowing:

- **Edge selectors are `None`-aware.** A nullable edge — a `left` that can be
  empty — is emitted as `left - (univ -> NoneType)`: the `left` relation with its
  `None` targets removed, so the orientation never tries to place the `NoneType`
  atoms that `hideAtom('NoneType')` removes. Subtracting only the `None` targets
  (rather than intersecting with a named node type,
  `left & (TreeNode -> TreeNode)`) keeps edges to *subtype* nodes that an
  exact-type match would wrongly drop. A non-nullable edge uses the simpler bare
  relation name (`selector='left'`).
- **`parent` is context-aware.** When a class also has child fields, `parent`
  just duplicates those edges, so it is hidden by default — with the "place
  above" orientation kept as a toggled-off alternative on
  `draft.alternatives`. When `parent` is the only link, "above" wins.

## Reading plain classes

Dataclasses and classes with annotations are read statically. For a plain class
whose fields can't be typed from the source alone (children default to `None`,
say), pass an example object so the analyzer can sample the real shape:

```python
root = TreeNode(1, TreeNode(2), TreeNode(3))
draft = suggest(TreeNode, instance=root)   # or just suggest(root)
```

Sampling walks the whole object graph, so a `parent` back-link on a child is
enough to recognize `parent` as structural across the class.

## Extending with your own heuristics

The built-in rules are just functions registered with `@heuristic`. Add your
own the same way — domain field names, project conventions, a house color
palette:

```python
from spytial.suggest import heuristic, Suggestion

@heuristic(scope='field', priority=100)   # >= 100 beats the built-ins
def color_by_status(field, cls_info):
    if field.name == 'status' and field.enum_members:
        return [Suggestion(
            directive='atomColor',
            kwargs={'selector': f'{{ x : {cls_info.cls.__name__} | @:(x.status) = active }}',
                    'value': 'seagreen'},
            confidence='high',
            rationale='active status → green',
            source_field='status',
        )]
    return []
```

- `scope='field'` heuristics run per field with signature `(FieldInfo, ClassInfo)`;
  `scope='class'` heuristics run once with `(ClassInfo)` and are how multi-field
  patterns (binary tree, linked list) are detected.
- Higher `priority` wins a same-field conflict; the loser becomes an alternative.
- Pass `suggest(cls, registry=my_registry)` to run an isolated rule set, or use
  `DEFAULT_REGISTRY.copy()` to start from the built-ins and add to them.

## Optional: LLM enrichment

The deterministic rules key off a fixed name vocabulary — `left`/`right`,
`next`/`prev`, `parent`/`children` — and fall back to a flat `below` for any
self-reference they don't recognize. The optional enrichment layer asks a model
to suggest the *spatial shape* of those fields instead, behind the
`[suggest-llm]` extra:

```bash
pip install "spytial_diagramming[suggest-llm]"
llm install llm-anthropic        # or llm-gemini, llm-openai, llm-ollama, …
llm keys set anthropic           # llm owns key management; spytial doesn't
```

```python
draft = suggest(Ticket, enrich="claude-sonnet-4-6")   # a named llm model
draft = suggest(Ticket, enrich="llama3.2")            # a local model via llm-ollama
```

You always say **what** to enrich with; there is no ambient default. A string is a
model id resolved through [`llm`](https://llm.datasette.io/) (Simon Willison's), so
you pick the model (Claude, GPT, Gemini, a local model via Ollama) and `llm` owns
the keys.

A **provider is just a callable** `(prompt, *, schema) -> dict`. So you can enrich
from a **subscription** instead of a metered key — the built-in `ClaudeCode` and
`Codex` providers run the respective CLI on your existing plan:

```python
from spytial.suggest import ClaudeCode, Codex

draft = suggest(Ticket, enrich=ClaudeCode(model="sonnet"))   # your Claude Max/Pro sub
draft = suggest(Ticket, enrich=Codex())                      # your ChatGPT plan (codex)
```

Or write your own in a few lines — anything callable with that signature works,
including a bare function (use `instruct_json` / `extract_json` for a text-only
backend):

```python
from spytial.suggest.providers import instruct_json, extract_json

def my_provider(prompt, *, schema):
    text = call_some_model(instruct_json(prompt, schema))
    return extract_json(text)

draft = suggest(Ticket, enrich=my_provider)
```

It suggests **shape**: an `orientation` direction per structural field, `cyclic`
for ring-like links, and `group` for collections. So a field named `escalation`
— which the rules can only lay out `below` — gets a model-proposed `above`,
because the model reads the name. The key line: **the model picks the shape, not
the selector.** It chooses a direction from a fixed vocabulary; spytial builds the
selector from the field, reusing the same render-verified forms the deterministic
rules emit. That's what keeps it schema-level and safe:

- **Type-level first.** It reasons over the class's fields, so `enrich=` needs no
  instance.
- **You pick.** Enriched rows are tagged `source="llm"` (a `model` chip in the
  notebook panel) and stay **off by default** — candidates beside the
  deterministic ones, never applied behind your back.
- **It can't break `suggest()`.** An unresolvable `enrich=` spec (no `llm`
  installed, an unknown model id, a non-provider value) or a malformed response
  each degrade to the static draft with a note in `draft.notes` — never an
  exception. Choices that name an unknown field or an out-of-vocabulary direction
  are dropped.

When you pass example instances (`suggest(obj, enrich=...)` or
`suggest(Cls, examples=[a, b, ...], enrich=...)`), a second tier lets the model
**author selector expressions** for relational cases the shape tier can't reach —
each admitted only if it evaluates cleanly, at the right arity, on *every* example.
A selector can only be validated by running it over data (the engine has no
schema-only mode), which is why that tier needs the examples and the shape tier
above does not. It runs headlessly on a vendored spytial-core evaluator, so it
needs only a `node` runtime.

## Limits

`suggest` infers structure from fields and references. It cannot recover
structure that lives in *computation* — an array-backed heap whose tree is
implied by index arithmetic, for example — and it will say so in `draft.notes`
rather than invent edges. The deterministic core aims to get the structure right
and the rest close enough to edit; the [enrichment tier](#optional-llm-enrichment)
above helps with the spatial shape of unfamiliar fields.

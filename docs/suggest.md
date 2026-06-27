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

The deterministic core gets the *structure* right but punts on taste — enum
colors come from an arbitrary built-in palette. The optional enrichment layer
fills those in semantically, behind the `[suggest-llm]` extra:

```bash
pip install "spytial_diagramming[suggest-llm]"
llm install llm-anthropic        # or llm-gemini, llm-openai, llm-ollama, …
llm keys set anthropic           # llm owns key management; spytial doesn't
```

```python
draft = suggest(RBNode, enrich=True)              # uses your default llm model
draft = suggest(RBNode, enrich=True, enrich_model="claude-sonnet-4-6")
```

It depends on [`llm`](https://llm.datasette.io/) (Simon Willison's) rather than a
single provider SDK, so you choose the model — Claude, GPT, Gemini, a local model
via Ollama — and `llm` handles the keys.

The design is deliberately conservative, in one sentence: **the model never
writes a selector.** Spytial selectors are Alloy/Forge relational expressions; a
model gets them subtly wrong and there is no in-Python validator to catch it (the
engine runs in the browser). So enrichment only substitutes *values* into the
selectors the deterministic rules already generated and render-verified — today,
one color per enum member. Consequences:

- **Type-level first.** Enum members are read statically, so `enrich=True` needs
  no instance.
- **You pick.** Enriched rows are tagged `source="llm"` (a `model` chip in the
  notebook panel) and stay **off by default** — they are candidates, never
  applied behind your back.
- **It can't break `suggest()`.** No `llm` installed, no model configured, or a
  malformed response each degrade to the static draft with a note in
  `draft.notes` — never an exception.

Unfamiliar domain naming and freeform structural selectors (the heap) are *not*
done here — that needs the datum schema, an instance, and render-verification,
and is left for a later, hard-gated tier.

## Limits

`suggest` infers structure from fields and references. It cannot recover
structure that lives in *computation* — an array-backed heap whose tree is
implied by index arithmetic, for example — and it will say so in `draft.notes`
rather than invent edges. Unfamiliar domain naming is still left to you (or the
enrichment tier above); the deterministic core aims to get the structure right
and the rest close enough to edit.

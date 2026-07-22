# Suggesting specs

`spytial.suggest` reads a class and proposes a starting set of layout
directives — a lightweight scaffold you then edit, not a finished spec. By
default it is pure static analysis: no LLM, no network, no extra dependencies
(an optional model-backed enrichment layer is described [below](#optional-llm-enrichment)).
The whole point is to get you past the blank page.

It lives in its own subpackage and is **not** imported by `spytial` itself —
nothing loads until you reach for it. Both spellings work:

```python
import spytial

draft = spytial.suggest(TreeNode)      # the subpackage is callable
print(draft.to_source())
```

```python
from spytial.suggest import suggest    # or import the function

draft = suggest(TreeNode)
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
| an `Enum`-typed field | one `atomStyle` per member (off by default) |
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
            directive='atomStyle',
            kwargs={'selector': f'{{ x : {cls_info.cls.__name__} | @:(x.status) = active }}',
                    'borderStyle': {'color': 'seagreen'}},
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
self-reference they don't recognize. The optional enrichment layer asks a model to
suggest the *spatial shape* of those fields instead.

You pass **`enrich=`** to say *what* to enrich with — there is no ambient default.
It's either a model-id **string** (routed through the [`llm`](https://llm.datasette.io/)
library) or a **provider**: any callable `(prompt, *, schema) -> dict`. Pick the
backend that matches how you pay for models:

### Use your Claude Max / Pro subscription (no API key)

Requires only the `claude` CLI (Claude Code) installed and signed in to your plan —
the same login you already use. `ClaudeCode` shells out to it, so you need **no
`[suggest-llm]` extra and no API key**:

```python
from spytial.suggest import suggest, ClaudeCode

draft = suggest(Ticket, enrich=ClaudeCode())               # model="sonnet" by default
draft = suggest(Ticket, enrich=ClaudeCode(model="opus"))   # opus for best quality
```

> **Stay on your subscription:** if `ANTHROPIC_API_KEY` is set in your environment,
> the `claude` CLI uses *that* (metered API billing) instead of your Max plan. Unset
> it to bill against the subscription. `model=` accepts anything `claude --model`
> takes (`sonnet`, `opus`, `haiku`, or a full model id).

### Use your ChatGPT plan (Codex)

Same idea with the `codex` CLI (included in ChatGPT Plus/Pro), which has *native*
JSON-schema output:

```python
from spytial.suggest import suggest, Codex

draft = suggest(Ticket, enrich=Codex())          # needs the `codex` CLI, signed in
```

### Use an API key, or a fully-local model (via `llm`)

A **string** is a model id resolved through `llm` (Simon Willison's), which owns key
management — spytial never sees a key. This covers metered APIs *and* local models:

```bash
pip install "spytial_diagramming[suggest-llm]"
llm install llm-anthropic        # or llm-openai, llm-gemini, llm-ollama, …
llm keys set anthropic           # only for hosted APIs; Ollama needs no key
```

```python
draft = suggest(Ticket, enrich="claude-sonnet-4-6")   # a metered API model
draft = suggest(Ticket, enrich="llama3.2")            # local via Ollama — nothing leaves your machine
```

### Bring your own

A provider is just a callable, so a few lines wire up any backend. `instruct_json` /
`extract_json` handle the JSON round-trip for a text-only model:

```python
from spytial.suggest.providers import instruct_json, extract_json

def my_provider(prompt, *, schema):
    text = call_some_model(instruct_json(prompt, schema))
    return extract_json(text)

draft = suggest(Ticket, enrich=my_provider)
```

*What leaves your machine:* only schema-level **names** — class/field/type/relation
names and counts, never your field *values* (those are used locally to validate
selectors). With a local model (`enrich="llama3.2"`) nothing leaves at all. The
`ClaudeCode`/`Codex` subscription providers are for individual, local use — for a
hosted or multi-user service use an API-key model instead.

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

## Ask for a directive in your own words

The enrichment tiers propose on their own initiative. `ask=` is the other
direction: **you** state what you want, in prose, and the model's only job is to
translate it —

```python
import spytial
from spytial.suggest import ClaudeCode

draft = spytial.suggest(
    tree,
    ask="all binary tree children should be below their parents",
    enrich=ClaudeCode(),          # ask uses the same provider slot
)
draft.to_source()
# @spytial.orientation(selector='left + right', directions=['below'])  # ask: children hang below their parent
```

A translation reaches the draft only after the full gauntlet:

1. **Kind + vocabulary** — the directive is one ask can author (`orientation`,
   `cyclic`, `align`, `inferredEdge`, `hideAtom`, `atomStyle`), and its enum
   kwargs are in the canonical sets.
2. **Evaluation** — the selector parses, is non-empty, and has the directive's
   exact arity on **every** example instance, via the headless evaluator. A
   failing round is fed back to the model once, with the per-candidate
   diagnostics, for a repair attempt.
3. **The authoring gate** — the kwargs run the same validation the `@spytial.*`
   decorators run, so an admitted row can't fail later in `apply()`.

Because you asked, the ask is **the key thing in the draft** — authoritative on
the ground it covers. Admitted rows come in **enabled by default** (a
translation that lands on a row the rules already proposed just switches that
row on), and an admitted `orientation`/`cyclic`/`align` row **demotes every
enabled geometric row that overlaps it** — rule-proposed and model-proposed
alike — to `draft.alternatives`, kept and one toggle away. Overlap isn't guessed
from selector syntax: `(ask_sel) & (rival_sel)` is itself a selector, and a
non-empty intersection on any example means both constraints claim the same
edges. So asking for *"children below parents"* on a binary tree replaces the
rules' `below-left`/`below-right` pair with your plain `below`, instead of
stacking a third constraint on the same edges. Styling and hiding rows don't
fight the layout solver, so they are left alone.

One ask is not necessarily one directive. A compound sentence — *"children
below their parents, and color the leaves green"* — translates to several
candidates (up to three), each admitted independently. What validates lands;
a failed part is what the repair round retries; and anything still unvalidated
after that is recorded in `draft.notes`, so no half of a request vanishes
without a trace.

Every failure, by contrast, is **loud**.
No provider, no example instance to validate against, no `node` runtime, or a
sentence of which *nothing* survives translation (`"make it pretty"`) raises
`spytial.suggest.AskError` carrying the model's own reason or the per-candidate
diagnostics — never a silently ignored request.

## Limits

`suggest` infers structure from fields and references. It cannot recover
structure that lives in *computation* — an array-backed heap whose tree is
implied by index arithmetic, for example — and it will say so in `draft.notes`
rather than invent edges. The deterministic core aims to get the structure right
and the rest close enough to edit; the [enrichment tier](#optional-llm-enrichment)
above helps with the spatial shape of unfamiliar fields.

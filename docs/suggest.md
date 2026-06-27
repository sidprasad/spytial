# Suggesting specs

`spytial.suggest` reads a class and proposes a starting set of layout
directives — a lightweight scaffold you then edit, not a finished spec. It is
pure static analysis: no LLM, no network, no extra dependencies. The whole point
is to get you past the blank page.

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
  empty — is emitted as `left & (TreeNode -> TreeNode)`, the surgical idiom from
  the [Selectors](selectors.md) guide. Restricting both ends to the node type
  keeps only the node→node pairs, excluding the `(leaf, None)` tuples the bare
  `left` relation would include — so the orientation never tries to place the
  `NoneType` atoms that `hideAtom('NoneType')` removes. A non-nullable edge uses
  the simpler bare relation name (`selector='left'`). (A type-agnostic
  `left - (univ -> NoneType)` would also work and tolerate subtype targets, but
  `univ` is outside the documented selector grammar, so the type-restricted form
  is the safe default.)
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

## Limits

`suggest` infers structure from fields and references. It cannot recover
structure that lives in *computation* — an array-backed heap whose tree is
implied by index arithmetic, for example — and it will say so in `draft.notes`
rather than invent edges. Semantic color palettes and unfamiliar domain naming
are deliberately left to you (or a future enrichment layer); the deterministic
core aims to get the structure right and the rest close enough to edit.

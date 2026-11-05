# Build a living spec with suggest

Describe a requirement, judge diagrams, and apply the accepted rules. Add or revise
requirements in the same session as your visualization develops.

## Open a session

Install `spytial_diagramming[suggest-search]`. The default setup also needs Node.js
and an installed, authenticated `codex` CLI.

In a local Jupyter notebook:

```python
from dataclasses import dataclass
from typing import Optional
from IPython.display import display
from spytial.suggest import suggest

@dataclass
class TreeNode:
    value: int
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None

root = TreeNode(1, TreeNode(2), TreeNode(3))
session = suggest(TreeNode, examples=[root])
display(session)
```

The controls open inside the notebook. The first diagram has no inferred rules:
the numbers and `None` appear as nodes. The LLM runs when you request a requirement.
Use `session.show()` for a browser tab.

Hypothesis derives a generator from the class by default. Pass `strategy=trees`
to supply your own. The [demo notebook](https://github.com/sidprasad/spytial/blob/main/demos/06-suggest-session.ipynb)
includes a bounded tree generator and the complete workflow.

## Describe and judge

1. Enter **Parents above children** and click **Explore**. The LLM proposes up to
   four interpretations; Spytial checks them on supplied and generated data.
2. Explore the two diagrams. They show the same datum, keep all previously
   accepted requirements, and remain draggable. Hypothesis searches for data that
   helps distinguish the interpretations.
3. Rate each diagram **upvote**, **downvote**, or **unsure** for the current
   requirement. The vote records the positions you have dragged it to.
4. Continue judging, or click **I'm done** to end this round.

Each vote is checked against every candidate interpretation:

| Vote | Candidate allows this arrangement | Candidate excludes it |
| --- | --- | --- |
| Upvote | Gains positive evidence | Gains negative evidence |
| Downvote | Gains negative evidence | No change |
| Unsure | No change | No change |

By default, two negative votes eliminate a candidate. One positive vote makes a
surviving candidate eligible for acceptance. Repeated votes on the same datum and
relative arrangement count once per requirement; the latest vote wins.

**I'm done** combines all eligible candidates: every included rule must apply.
The combination must agree with the requirement's recorded votes, have positive
evidence for the whole combination, and work with the other accepted requirements
on checked data. For example, “children below” and “children to the right” together
require children below **and** to the right. An upvoted below-left arrangement
prevents that combination from being accepted.

When only one candidate survives, it is accepted automatically after both diagrams
are rated if it has positive evidence and passes these checks. If no candidate
remains, or the combination fails the checks, the round stays unfinished. Earlier
accepted requirements remain usable. Finding no further comparison does not by
itself accept a requirement.

## Apply and inspect the spec

After a requirement is accepted:

```python
import spytial

spec = session.apply()
print(spec)
spytial.diagram(root)
```

`spec` is the same living object as `session.spec`. Later diagram calls use its
current accepted rules. Diagrams already open keep their earlier output.

`print(spec)` shows the rules with their originating prompts, relevant prompt
fragments, and accepted interpretations. `spec.provenance` provides the same
mapping as structured records. Use `spec.to_source(with_comments=False)` for
plain decorators, or `spec.snapshot()` for a fixed copy.

To use the spec for just one call, use `spytial.diagram(root, spec=session.spec)`
without `apply()`. To remove a class binding, call `spec.unapply()`.
Applying or using a spec with no accepted requirements, or with conflicting
accepted rules, raises `SpecUnavailableError`.

## Add, revisit, or revise

After acceptance, the view opens the next prompt. Enter **Align siblings
horizontally** and judge it with the accepted parent-child rule still applied.
Accepted prompts remain visible with a ✓. Unfinished requirements add no rules
to the living spec.

Click an earlier prompt to **Continue** judging it, or edit its wording and choose
**Revise**. Revision replaces that requirement's candidates and withdraws its old
rules while you edit. Other accepted requirements stay applied.

Judgments remain attached to their requirement and are checked against its new
candidates. Use **History** to correct a previous vote when your intent changes.
A correction can restore an eliminated candidate or remove an accepted rule.

After accepting changes, `print(spec)` and the next `spytial.diagram(root)` call
use the updated rules without another `apply()`.

## Save, close, and continue later

**I'm done** ends a round; it does not save a file or close the session.

```python
session.save("tree-session.json")
session.close()
```

`close()` stops the controls and local worker. An accepted spec remains usable.
To continue a closed session, load the saved file:

```python
from spytial.suggest import SuggestSession

session = SuggestSession.load(TreeNode, "tree-session.json")
display(session)
spec = session.apply()  # Reconnect the restored spec after it has accepted rules.
```

Loading preserves the original presentation, requirements, revisions, examples, arrangements, and votes.
It makes no LLM request and does not bind the restored spec automatically. Supply
any custom `strategy=`, `search=`, or `proposer=` again when loading.

## Options

Pass these to `suggest(...)`:

| Option | Default | Purpose |
| --- | --- | --- |
| `proposer` | `Codex()` | Use `ClaudeCode()`, a model-id string, or a callable provider. |
| `strategy` | Derived from the class | Supply a Hypothesis generator for your data. |
| `registry` | `None` | Pass `DEFAULT_REGISTRY` from `spytial.suggest` to infer fixed rules such as hiding `None` and displaying values inside nodes. |
| `max_candidates` | `4` | Cap candidate interpretations per round. |
| `elimination_threshold` | `2` | Negative votes needed to eliminate a candidate. |
| `min_positive_votes` | `1` | Positive votes needed to support a candidate or combination. |
| `max_examples` | `20` | Limit predicate checks per generated search, including shrinking. |

For a time budget, pass `search=HypothesisSearch(trees, max_seconds=5)` instead of
`strategy=trees`. The default budget is five seconds per search; an in-progress
core check can finish later. A round may run several searches. These checks do
not prove that the spec works for all possible data.

`FixedExamples()` uses only supplied examples. `FixedProposals(programs)` replaces
the LLM with supplied candidates. Import these helpers from `spytial.suggest`.
If a notebook cannot find Codex, set `proposer=Codex(bin="/absolute/path/to/codex")`.
Model-id strings require the `suggest-llm` extra and a configured `llm` provider.

For full signatures, see the [API reference](reference/api.md#spytial.suggest).
For a one-shot editable draft, see [Drafting annotations](reference/suggest-draft.md).

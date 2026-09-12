---
name: add-spytial-python
description: Integrate sPyTial into Python programs with a high-quality authoring workflow. Use when users ask to add, tune, or debug spytial diagram/evaluator usage, selector-driven constraints and directives, CLRS-style data-structure layouts, sequence diagrams, or custom relationalizers in Python codebases and notebooks.
---

# Add sPyTial (Python)

Use this skill to produce a polished, low-friction authoring experience for Python users adopting sPyTial.

## Workflow

1. Establish target and constraints.
- Identify structure shape, desired rendering mode (`inline`, `browser`, `file`), and whether the user needs single snapshot or sequence playback.
- If shape matches standard structures, load [CLRS Patterns](references/clrs-patterns.md) and choose the closest template first.

2. Land a minimal working integration before styling.
- Add a tiny baseline with `spytial.evaluate(obj)` and `spytial.diagram(obj)`.
- Keep first patch runnable with one clear entrypoint.
- If starting from scratch, scaffold with:
  `python scripts/scaffold_spytial_starter.py --shape <linked-list|tree|graph|matrix> --out <path>`

3. Add operations incrementally.
- Add one operation at a time (`orientation`, `align`, `group`, `attribute`, `inferredEdge`, `hideField`, `hideAtom`, `edgeColor`).
- Validate selectors against actual serialized data.
- Load [Selector Cheatsheet](references/selector-cheatsheet.md) for expression syntax and debugging patterns.

4. Use custom relationalizers only when needed.
- Prefer built-in relationalizers first.
- If semantics are still wrong, implement `RelationalizerBase` with `@relationalizer(priority=100+)`.
- Validate serialization with `evaluate()` before tuning layout.
- Load [Relationalizer Workflow](references/relationalizer-workflow.md).

5. Finish with verifiable handoff.
- Show run command and expected output artifact.
- If working in this repo, run scoped verification in `spytial-py` (`pytest` or targeted tests).
- Summarize changed files, chosen pattern, selector assumptions, and next tuning options.

## Quality Bar

- Deliver runnable code, not pseudocode.
- Preserve a fast feedback loop: `evaluate()` then `diagram()`.
- Prefer CLRS-derived patterns for common data structures.
- Explain non-obvious selectors inline with short comments.
- State assumptions explicitly when the data model is ambiguous.

## References

- [Authoring Workflow](references/authoring-workflow.md)
- [CLRS Patterns](references/clrs-patterns.md)
- [Selector Cheatsheet](references/selector-cheatsheet.md)
- [Relationalizer Workflow](references/relationalizer-workflow.md)

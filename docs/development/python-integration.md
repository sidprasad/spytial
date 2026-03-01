# Python Integration

This package bridges ordinary Python objects to the Spytial data model that `spytial-core` consumes.

## High-level flow

The main runtime flow is:

1. Python objects are walked by `CnDDataInstanceBuilder`.
2. Built-in or custom relationalizers emit `Atom` and `Relation` records.
3. Annotations from decorators, object-level metadata, or `typing.Annotated` are collected.
4. The data instance and annotation spec are passed to the HTML templates that embed `spytial-core`.

## Annotation system

`spytial/annotations.py` provides three ways to attach operations:

- class decorators such as `@spytial.orientation(...)`
- object-level helpers such as `spytial.annotate_group(obj, ...)`
- `typing.Annotated` or `spytial.AnnotatedType(...)` metadata for plain containers and reusable type aliases

During serialization, annotations are merged from class inheritance, instance-level metadata, and any `as_type=` override passed into `diagram()` or `evaluate()`.

## Relationalization

`spytial/provider_system.py` coordinates the walk across the object graph. It chooses a `RelationalizerBase` implementation for each value and assembles the final payload:

- `atoms`
- `relations`
- `types`

The built-ins cover the common Python cases already:

- primitives
- `dict`
- `list`
- `tuple`
- `set`
- dataclasses
- generic Python objects as a fallback

This is why many examples in `spytial-clrs` can stay simple and focus mostly on operations rather than custom serialization.

## Rendering entry points

The public API is intentionally small:

- `spytial.diagram(...)`
- `spytial.evaluate(...)`
- `spytial.dataclass_builder(...)`

These functions generate HTML around the serialized payload and choose an output mode such as inline notebook display, browser output, or file output.

## Where changes usually belong

- change annotation semantics: probably `spytial-core`, then this repo if Python adaptation is needed
- change Python serialization or object handling: this repo
- change example or tutorial coverage: `spytial-clrs`

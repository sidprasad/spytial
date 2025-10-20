# Python Integration Details

This document summarizes how sPyTial uses Python features to bridge spatial annotations with the CnD atom/relation data model.

## Annotation lifecycle

*Decorator factories* defined in `spytial.annotations` create per-constraint callables that can target either classes or individual objects. The unified decorator detects whether the target is a type or an instance, initializes or locates the appropriate registry, validates keyword arguments against the allowed schema, and stores the resulting payload in a structured `constraints`/`directives` map (`__spytial_registry__` for classes or `__spytial_object_annotations__`/a global fallback for objects).【F:spytial/annotations.py†L204-L341】

During serialization, `collect_decorators` walks the instance’s method resolution order (MRO), merging each class registry that is eligible for inheritance and layering in any per-instance annotations from both direct attributes and the fallback registry.【F:spytial/annotations.py†L450-L499】 The collected directives can then be emitted as YAML via `serialize_to_yaml_string`, allowing CnD to consume the constraints as part of a visualization spec.【F:spytial/annotations.py†L502-L508】

## Relationalization pipeline

`CnDDataInstanceBuilder` orchestrates conversion of arbitrary Python values into the atom/relation graph that CnD expects. As it traverses an object graph it records encountered objects, captures their annotations, and selects an appropriate `RelationalizerBase` implementation from the `RelationalizerRegistry` to describe each value.【F:spytial/provider_system.py†L84-L259】 Every relationalizer returns `Atom` and `Relation` dataclasses, which the builder normalizes, augments with type hierarchies, and merges into the aggregated instance payload (`{"atoms": ..., "relations": ..., "types": ...}`).【F:spytial/provider_system.py†L262-L355】【F:spytial/domain_relationalizers/base.py†L13-L78】 ID management ensures stable references for primitives, object instances, and annotated objects so relations remain consistent across the walk.【F:spytial/provider_system.py†L185-L224】 The builder also deduplicates atoms and attaches inherited type information so CnD receives canonical tuples for each relation.【F:spytial/provider_system.py†L135-L180】【F:spytial/provider_system.py†L270-L355】

## Enabling Python features

This integration relies on dynamic capabilities that are idiomatic to Python:

- **Runtime attribute injection.** Decorators and annotation helpers attach registries and identifiers directly onto classes or instances, and fall back to module-level dictionaries when objects do not expose `__dict__`. This leverages Python’s ability to add attributes post-definition, even for decorator-generated metadata.【F:spytial/annotations.py†L204-L341】
- **Reflection and inspection.** The builder uses `inspect.currentframe()` to locate the caller’s namespace so relationalizers can recover variable names for labeling, and to derive MRO-based type hierarchies for atoms.【F:spytial/provider_system.py†L107-L176】【F:spytial/domain_relationalizers/base.py†L55-L91】
- **Duck typing with registries.** Relationalizers self-register through a decorator, and the registry queries each candidate’s `can_handle` method at runtime to determine how to serialize a value. This plug-in mechanism depends on Python’s flexible class system and dynamic imports.【F:spytial/provider_system.py†L15-L63】

Together these features let sPyTial observe, annotate, and serialize live Python objects without code generation, enabling a smooth bridge between idiomatic Python data structures and CnD’s declarative spatial model.

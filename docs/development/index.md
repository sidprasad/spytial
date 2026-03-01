# Develop sPyTial

`spytial-py` is the Python-facing integration for the Spytial ecosystem. It owns Python serialization, annotations, notebook and browser output, and the user-facing API for Python developers.

## Ownership boundaries

When you change this repo, keep the dependency boundaries straight:

- `spytial-core` owns layout semantics, directives, and the browser-facing engine
- `spytial-py` owns Python object handling, annotations, rendering entry points, and Python docs
- `spytial-clrs` is the examples companion, not the source of core semantics

If a requested behavior feels fundamental to Spytial rather than specific to Python, it likely belongs in `spytial-core` first.

## Main code areas

- `spytial/annotations.py`: decorators, object annotations, and `typing.Annotated` support
- `spytial/provider_system.py`: the object-to-atoms-and-relations pipeline
- `spytial/domain_relationalizers/`: built-in relationalizers for Python value types
- `spytial/visualizer.py` and `spytial/evaluator.py`: HTML output entry points
- `spytial/dataclass_builder.py`: interactive dataclass builder UI
- `test/`: regression coverage for annotations and relationalization
- `docs/`: MkDocs source for this site

## Development paths

- Read [Python Integration](python-integration.md) for the runtime model.
- Read [Workflow](workflow.md) for local setup and verification.
- Read [Docs and GitHub Pages](docs-site.md) for the docs publishing flow.

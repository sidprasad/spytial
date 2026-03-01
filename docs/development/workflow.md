# Workflow

## Local setup

```bash
git clone https://github.com/sidprasad/cnd-py.git
cd cnd-py
python -m pip install -e ".[dev]"
```

If you are also working on the docs locally:

```bash
python -m pip install -e ".[docs]"
```

## Core verification

Use the smallest useful verification for the change:

```bash
python -m pytest
```

For packaging smoke checks, the repo also includes:

```bash
python scripts/quick_publish_check.py
python scripts/pre_publish_check.py
```

## Cross-repo workflow

This workspace is an ecosystem, not a single monorepo package. For Python-facing work:

- start in `spytial-py` when the change is about Python object export, Python API ergonomics, notebook or browser output, or docs
- start in `spytial-core` when the change is about layout semantics or reusable directives
- use `spytial-clrs` as a downstream example corpus when you want richer smoke tests or tutorial material

## Practical contributor loop

1. make the smallest change in the owning repo
2. run `python -m pytest`
3. if docs changed, run `mkdocs build --strict`
4. if the change affects examples or rendering expectations, spot-check a relevant `spytial-clrs` notebook

# Getting Started

[![PyPI version](https://img.shields.io/pypi/v/spytial-diagramming.svg)](https://pypi.org/project/spytial-diagramming/)
[![Python versions](https://img.shields.io/pypi/pyversions/spytial-diagramming.svg)](https://pypi.org/project/spytial-diagramming/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/sidprasad/spytial/blob/main/LICENSE)
[![CI](https://github.com/sidprasad/spytial/actions/workflows/ci.yml/badge.svg)](https://github.com/sidprasad/spytial/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue.svg)](https://sidprasad.github.io/spytial/)

## Install

```bash
pip install spytial-diagramming
```

- **PyPI:** [pypi.org/project/spytial-diagramming](https://pypi.org/project/spytial-diagramming/)
- **Source:** [github.com/sidprasad/spytial](https://github.com/sidprasad/spytial)
- **Supported Python:** 3.8 – 3.12

## Optional extras

Most users do not need these. Install them only if you hit one of the listed cases.

```bash
pip install "spytial-diagramming[widget]"     # anywidget-based Jupyter widget mode
pip install "spytial-diagramming[headless]"   # Selenium-driven headless rendering for benchmarking
pip install "spytial-diagramming[dev]"        # pytest, flake8, black (contributors)
pip install "spytial-diagramming[docs]"       # mkdocs + plugins (contributors)
```

- `[headless]` also requires a Chrome / Chromedriver installation on `PATH`. See [Diagramming → Headless benchmarking](usage/diagramming.md#headless-benchmarking).

## Environment

`sPyTial` works in three places without configuration:

| Where you run it | Default output |
| --- | --- |
| Jupyter / IPython notebook | Inline HTML |
| Script / REPL | Opens a new browser tab |
| Anywhere, on demand | Writes an HTML file |

Rendering itself is done in the browser by [`spytial-core`](how-it-works.md), which is loaded from a CDN the first time you render. There is nothing extra to install; the bundle is cached by the browser after first load. See [How It Works](how-it-works.md) for the pipeline and for offline / pinning guidance.

## First diagram

```python
import spytial

example = {
    "id": "root",
    "children": [
        {"id": "left"},
        {"id": "right"},
    ],
}

spytial.diagram(example)
```

## Inspect before you diagram

If you want to confirm how an object is being serialized, use the evaluator first:

```python
import spytial

spytial.evaluate(example)
```

This is useful when you are debugging a custom class, an annotation, or a relationalizer.

## Display methods

`sPyTial` chooses a display method based on environment. You can override it explicitly:

```python
spytial.diagram(example, method="browser")   # open a new tab
spytial.diagram(example, method="file")      # write an HTML file
spytial.diagram(example, method="inline")    # force inline output
```

## When to use each tool

| Tool | Best for | Output |
| --- | --- | --- |
| `diagram()` | Visualizing object structure | HTML diagram (inline or browser) |
| `evaluate()` | Inspecting serialized data | HTML evaluator view |
| `dataclass_builder()` | Constructing dataclass instances | Interactive builder |

## Next steps

- Read [Diagramming](usage/diagramming.md) for the main rendering workflow.
- Read [Operations](operations.md) to control layout and drawing.
- Read [How It Works](how-it-works.md) to understand the Python → browser pipeline.
- Browse [CLRS Notebook Examples](examples/spytial-clrs.md) for worked examples on classic data structures (heaps, trees, graphs, hash tables, disjoint-set forests, and more).

# Publishing SpYTial to PyPI

This document explains how to publish SpYTial to the Python Package Index (PyPI) so users can install it with `pip install spytial`.

## Prerequisites

1. Install publishing tools:
   ```bash
   pip install build twine
   ```

2. Create accounts on:
   - [PyPI](https://pypi.org/) for production
   - [Test PyPI](https://test.pypi.org/) for testing

## Building the Package

1. Clean any previous builds:
   ```bash
   rm -rf build/ dist/ *.egg-info/
   ```

2. Build the package:
   ```bash
   python -m build
   ```
   
   This creates:
   - `dist/spytial-0.1.0.tar.gz` (source distribution)
   - `dist/spytial-0.1.0-py3-none-any.whl` (wheel)

## Testing Before Publishing

1. Test install locally:
   ```bash
   pip install dist/spytial-0.1.0-py3-none-any.whl
   python -c "import spytial; print('Success!')"
   ```

2. Upload to Test PyPI first:
   ```bash
   twine upload --repository testpypi dist/*
   ```

3. Install from Test PyPI:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ spytial
   ```

## Publishing to PyPI

Once tested, publish to the real PyPI:

```bash
twine upload dist/*
```

## After Publishing

Users can then install SpYTial with:

```bash
pip install spytial
```

## Version Management

To release a new version:

1. Update version in `setup.py` and `pyproject.toml`
2. Create a git tag: `git tag v0.1.1`
3. Build and publish following the steps above

## Package Contents

The published package includes:
- Core SpYTial modules
- HTML templates for visualization
- Documentation (README, LICENSE)
- Example notebooks in demos/
- Dependencies: jinja2, pyyaml, ipython
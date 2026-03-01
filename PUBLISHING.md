# Minimal publish steps

1. Ensure metadata
   - Confirm distribution name in pyproject.toml: `[project].name = "spytial-diagramming"`
   - `setup.py` is a thin shim; package metadata lives in `pyproject.toml`.
   - Bump the version in `spytial/_version.py`.

2. Clean previous builds
```bash
rm -rf dist/ build/ *.egg-info/
```

3. Build distributions
```bash
python -m pip install --upgrade build
python -m build --no-isolation
ls -la dist/
```

4. (Optional quick test) Run unit tests and import check
```bash
python -m pytest test/ -q
python -c "import spytial; print('import ok')"
```

5. Upload to Test PyPI first
```bash
# set token interactively or via env:
# export TWINE_USERNAME="__token__"
# export TWINE_PASSWORD="pypi-<TEST_API_TOKEN>"

python -m pip install --upgrade twine
python -m twine upload --repository testpypi dist/*
# verify install:
pip install --index-url https://test.pypi.org/simple/ spytial-diagramming
python -c "import spytial; print('test install ok')"
```

6. Publish to PyPI (when ready)
```bash
# export TWINE_USERNAME="__token__"
# export TWINE_PASSWORD="pypi-<PROD_API_TOKEN>"
python -m twine upload dist/*
```

7. Common troubleshooting
   - If you get `403 Forbidden` for a package name, one of your artifacts uses a name you don't own. Inspect `dist/` and upload only the intended files:
```bash
ls dist/
python -m twine upload dist/spytial_diagramming-*.*
```
   - Ensure `pyproject.toml` still points to `spytial._version.__version__` and that `spytial/_version.py` has the intended release version.
   - Use TestPyPI to verify before publishing to production.

That’s it — the minimal end-to-end flow: update metadata, clean, build, test on TestPyPI, then upload to PyPI.

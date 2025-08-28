# Publishing sPyTial to PyPI

> **📚 For complete publishing instructions, see [docs/PUBLISHING.md](docs/PUBLISHING.md)**

This document explains how to publish sPyTial to the Python Package Index (PyPI) so users can install it with `pip install spytial`.

## Quick Start

### Automated Publishing (Recommended)
```bash
# 1. Run validation
python scripts/quick_publish_check.py

# 2. Commit and tag
git add . && git commit -m "Prepare for release v0.1.0"
git tag v0.1.0 && git push origin main --tags

# 3. Create GitHub release (triggers auto-publish)
# Go to GitHub → Releases → Create new release
```

### Manual Publishing
```bash
python -m build
twine upload dist/*
```

## Automated Publishing (Recommended)

### GitHub Workflows

The repository includes automated GitHub workflows for CI/CD:

1. **`.github/workflows/ci.yml`** - Continuous Integration
   - Runs on every push and pull request
   - Tests multiple Python versions (3.8-3.12)
   - Code quality checks (black, flake8)
   - Full test suite
   - Build validation

2. **`.github/workflows/publish.yml`** - Automated Publishing
   - Triggers on GitHub releases or manual dispatch
   - Runs comprehensive pre-publish validation
   - Publishes to PyPI or Test PyPI
   - Includes all validation scenarios from copilot instructions

### Publishing Process

1. **Run local pre-publish checks:**
   ```bash
   python scripts/pre_publish_check.py
   ```

2. **Commit and tag a release:**
   ```bash
   git add .
   git commit -m "Prepare for release v0.1.0"
   git tag v0.1.0
   git push origin main --tags
   ```

3. **Create a GitHub release:**
   - Go to GitHub → Releases → Create new release
   - Choose the tag you created
   - Add release notes
   - Publish the release

4. **Automated publishing will trigger** and handle:
   - All validation checks
   - Package building
   - Publishing to PyPI
   - Release summary generation

### Manual Testing

To test on Test PyPI first:
1. Go to GitHub Actions
2. Select "Publish to PyPI" workflow
3. Click "Run workflow"
4. Check "Publish to Test PyPI instead of PyPI"
5. Run workflow

## Manual Publishing (Fallback)

1. Install publishing tools:
   ```bash
   pip install build twine
   ```

2. Create accounts on:
   - [PyPI](https://pypi.org/) for production
   - [Test PyPI](https://test.pypi.org/) for testing

## Manual Publishing (Fallback)

### Prerequisites

1. Install publishing tools:
   ```bash
   pip install build twine
   ```

2. Create accounts on:
   - [PyPI](https://pypi.org/) for production
   - [Test PyPI](https://test.pypi.org/) for testing

### Manual Build and Publish

1. **Run comprehensive validation:**
   ```bash
   python scripts/pre_publish_check.py
   ```

2. **Clean any previous builds:**
   ```bash
   rm -rf build/ dist/ *.egg-info/
   ```

3. **Build the package:**
   ```bash
   python -m build
   ```

4. **Test on Test PyPI first:**
   ```bash
   twine upload --repository testpypi dist/*
   pip install --index-url https://test.pypi.org/simple/ spytial
   ```

5. **Publish to PyPI:**
   ```bash
   twine upload dist/*
   ```

## Setup for Automated Publishing

### Required GitHub Secrets

For automated publishing to work, add these secrets to your GitHub repository:

1. **`PYPI_API_TOKEN`** - Your PyPI API token
   - Go to PyPI → Account Settings → API Tokens
   - Create token with "Entire account" scope
   - Add to GitHub → Settings → Secrets and Variables → Actions

2. **`TEST_PYPI_API_TOKEN`** - Your Test PyPI API token
   - Go to Test PyPI → Account Settings → API Tokens  
   - Create token with "Entire account" scope
   - Add to GitHub secrets

### Repository Environments (Optional but Recommended)

Create GitHub environments for additional security:

1. Go to GitHub → Settings → Environments
2. Create `pypi` environment
3. Create `test-pypi` environment  
4. Add protection rules and required reviewers

## Validation Checks

The automated workflows run comprehensive validation including:

- ✅ **Code Quality**: Black formatting, Flake8 linting
- ✅ **Test Suite**: Full pytest test execution
- ✅ **Basic Visualization**: Core diagram generation
- ✅ **Class Annotations**: Decorator functionality  
- ✅ **Object Annotations**: Runtime annotation system
- ✅ **Provider System**: Data serialization pipeline
- ✅ **Package Building**: Source and wheel distribution
- ✅ **Installation Testing**: Install from built package

All checks from the copilot instructions are automated!

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
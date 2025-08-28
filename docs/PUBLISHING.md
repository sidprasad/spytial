# 🚀 sPyTial Publishing Guide

This guide provides complete instructions for publishing sPyTial to PyPI, with both automated and manual options.

## 📋 Quick Reference

### Status Check
```bash
# Run quick validation
python scripts/quick_publish_check.py

# Run comprehensive validation (includes all tests)
python scripts/pre_publish_check.py
```

### Automated Publishing (Recommended)
```bash
# 1. Commit and tag
git add .
git commit -m "Prepare for release v0.1.0"
git tag v0.1.0
git push origin main --tags

# 2. Create GitHub release (triggers auto-publish)
# Go to GitHub → Releases → Create new release
```

### Manual Publishing
```bash
# Build and publish
python -m build
twine upload dist/*
```

---

## 🤖 Automated Publishing Setup

### Prerequisites

1. **GitHub Secrets Required:**
   - `PYPI_API_TOKEN` - Your PyPI API token ([Get one here](https://pypi.org/manage/account/))
   - `TEST_PYPI_API_TOKEN` - Your Test PyPI API token ([Get one here](https://test.pypi.org/manage/account/))

2. **How to Add Secrets:**
   - Go to GitHub → Repository → Settings → Secrets and Variables → Actions
   - Click "New repository secret"
   - Add both tokens

### Workflows Available

#### 1. Continuous Integration (`.github/workflows/ci.yml`)
**Triggers:** Push to main/develop, Pull Requests

**What it does:**
- ✅ Tests on Python 3.8-3.12
- ✅ Code quality checks (black, flake8)
- ✅ Full test suite
- ✅ Build validation
- ✅ Installation testing

#### 2. Automated Publishing (`.github/workflows/publish.yml`)
**Triggers:** GitHub Releases, Manual dispatch

**What it does:**
- ✅ All CI checks plus comprehensive validation
- ✅ Core functionality tests (from copilot instructions)
- ✅ Package building and validation
- ✅ Automatic publishing to PyPI or Test PyPI
- ✅ Release summary generation

### Publishing Process

#### Option A: Release-Triggered Publishing
1. **Prepare release:**
   ```bash
   git add .
   git commit -m "Prepare for release v0.1.0"
   git tag v0.1.0
   git push origin main --tags
   ```

2. **Create GitHub release:**
   - Go to GitHub → Releases → "Create a new release"
   - Select your tag (v0.1.0)
   - Add release notes
   - Click "Publish release"
   - **Publishing automatically starts!**

#### Option B: Manual Workflow Trigger
1. **Go to GitHub Actions**
2. **Select "Publish to PyPI" workflow**
3. **Click "Run workflow"**
4. **Choose options:**
   - ☐ Publish to Test PyPI (for testing)
   - ☑ Publish to PyPI (for production)

---

## 🛠 Manual Publishing

### Prerequisites
```bash
pip install build twine
```

### Step-by-Step Process

1. **Validate everything is ready:**
   ```bash
   python scripts/quick_publish_check.py
   ```

2. **Clean previous builds:**
   ```bash
   rm -rf build/ dist/ *.egg-info/
   ```

3. **Build the package:**
   ```bash
   python -m build
   ```

4. **Test on Test PyPI first (recommended):**
   ```bash
   twine upload --repository testpypi dist/*
   
   # Test install from Test PyPI
   pip install --index-url https://test.pypi.org/simple/ spytial
   python -c "import spytial; print('Test install successful!')"
   ```

5. **Publish to real PyPI:**
   ```bash
   twine upload dist/*
   ```

---

## 🔍 Validation Details

### Quick Check (`scripts/quick_publish_check.py`)
- ✅ Package installation
- ✅ Code formatting
- ✅ Package building
- ✅ Distribution validation
- ✅ Core functionality test

### Comprehensive Check (`scripts/pre_publish_check.py`)
- ✅ All quick checks
- ✅ Full test suite
- ✅ All validation scenarios from copilot instructions:
  - Basic visualization test
  - Class-level annotations
  - Object-level annotations
  - Provider system validation

---

## 📦 Package Information

**Package Name:** `spytial`  
**Current Version:** `0.1.0`  
**Repository:** `https://github.com/sidprasad/spytial`

### Installation (After Publishing)
```bash
pip install spytial
```

### Dependencies
- `jinja2>=3.0.0`
- `pyyaml>=6.0`
- `ipython>=8.0.0`

---

## 🐛 Troubleshooting

### Common Issues

1. **Version files (=23.0.0, etc.):**
   - These are from broken pip install commands
   - They're now in `.gitignore`
   - Remove with: `rm -f "=*.*.*"`

2. **Test failures:**
   - Some advanced features may have failing tests
   - Core functionality still works
   - Use `quick_publish_check.py` for essential validation

3. **Authentication errors:**
   - Ensure API tokens are correctly set in GitHub secrets
   - Tokens need "Entire account" scope for publishing

4. **Build failures:**
   - Check `pyproject.toml` and `setup.py` are consistent
   - Ensure all required files are in `MANIFEST.in`

### Getting Help
- Check GitHub Actions logs for detailed error messages
- Test locally with `python scripts/quick_publish_check.py`
- Validate distribution with `twine check dist/*`

---

## 🎯 Version Management

### Releasing New Versions

1. **Update version numbers in:**
   - `setup.py` (line with `version=`)
   - `pyproject.toml` (line with `version =`)

2. **Create and push tag:**
   ```bash
   git tag v0.1.1
   git push origin main --tags
   ```

3. **Create GitHub release or publish manually**

### Version Numbering
- Use semantic versioning: `MAJOR.MINOR.PATCH`
- `0.1.0` → `0.1.1` (patch: bug fixes)
- `0.1.1` → `0.2.0` (minor: new features)
- `0.2.0` → `1.0.0` (major: breaking changes)

---

## ✨ After Publishing

Users can install sPyTial with:
```bash
pip install spytial
```

And use it immediately:
```python
import spytial

# Visualize any Python object
data = {"name": "example", "values": [1, 2, 3]}
spytial.diagram(data)
```

🎉 **Happy Publishing!**

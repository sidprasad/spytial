# sPyTial Development Guide

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sidprasad/spytial.git
   cd spytial
   ```

2. **Install in development mode:**
   ```bash
   pip install -e .
   pip install pytest>=7.0.0 flake8>=6.0.0 black>=23.0.0
   ```

3. **Run tests:**
   ```bash
   python -m pytest test/ -v
   ```

## Code Quality

### Formatting
```bash
# Check formatting
python -m black spytial/ --check

# Apply formatting
python -m black spytial/
```

### Linting
```bash
python -m flake8 spytial/ --count --statistics
```

## Common Development Issues

### Erroneous Version Files
If you see files like `=23.0.0`, `=6.0.0`, `=7.0.0` in your directory:

**What they are:** These files are created when pip install commands are malformed, causing version specifiers to be interpreted as filenames instead of package requirements.

**How to fix:**
```bash
# Remove them
rm -f "=*.*.*"

# They're already in .gitignore so won't be tracked
```

**Prevention:** Always use proper pip install syntax:
```bash
# ✅ Correct
pip install "package>=1.0.0"

# ❌ Incorrect (creates =1.0.0 file)
pip install package>=1.0.0
```

## Publishing

See [docs/PUBLISHING.md](docs/PUBLISHING.md) for complete publishing instructions.

### Quick validation:
```bash
python scripts/quick_publish_check.py
```

## Git Workflow

### Branches
- `main` - Production releases
- `publishing` - Publishing workflow setup
- `develop` - Development integration

### Releases
```bash
git tag v0.1.0
git push origin main --tags
# Create GitHub release to trigger automated publishing
```

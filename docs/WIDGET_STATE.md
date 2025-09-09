# sPyTial Dataclass Widget - Repository State

## 📁 Current File Structure (Cleaned)

### Core Widget Files
- **`dataclass_widget.py`** - Main widget implementation with bundled local dependencies ✅
- **`input_template.html`** - HTML template with bundled JS/CSS (no CDN dependencies) ✅

### Legacy/Reference Files  
- **`input_template_cdn.html`** - Old template using external CDNs (kept for reference)

### Static Assets
- **`static/js/`** - Bundled JavaScript libraries (D3.js, CnD Core, React integration)
- **`static/css/`** - Bundled CSS files
- **`scripts/refresh_dependencies.py`** - Script to update bundled dependencies

## 🎯 What to Use

### For Production Use:
```python
import spytial

# This uses the bundled local dependencies (no CDN issues)
widget = spytial.dataclass_widget(MyDataclass)
```

### For Development:
- **Edit**: `spytial/dataclass_widget.py` (main implementation)
- **Edit**: `spytial/input_template.html` (HTML template with bundled deps)
- **Refresh deps**: `python scripts/refresh_dependencies.py`

## 🔄 Dependency Management

The widget now uses **bundled local dependencies** instead of external CDNs:

### Current Bundled Libraries:
- **D3.js v4** (~221 KB) - Data visualization
- **CnD Core** (~6.3 MB) - Graph engine  
- **CnD React Integration** (~4.1 MB) - UI components
- **CSS** (~22 KB) - Styling

### To Update Dependencies:
```bash
python scripts/refresh_dependencies.py
```

This will download the latest versions from CDNs and bundle them locally.

## ✅ Current State Benefits

1. **No CDN reliability issues** - Everything bundled locally
2. **Direct JavaScript-to-Python communication** - No iframe complexity  
3. **Full CnD visualization capabilities** - Sophisticated graph interface
4. **Reliable value access** - `widget.value` property works consistently
5. **JSON export functionality** - Built-in export capabilities
6. **Backward compatibility** - `update_from_json()` method preserved

## 🚀 Usage Example

```python
from dataclasses import dataclass
import spytial

@dataclass
class Person:
    name: str = ""
    age: int = 0
    hobbies: list = None

# Create widget with bundled dependencies (reliable)
widget = spytial.dataclass_widget(Person)

# Use the sophisticated CnD graph interface in Jupyter
# Click "💾 Save Value" to save data to widget

# Access the built dataclass instance
person = widget.value  # Returns Person instance

# Programmatic updates also work
widget.update_from_json({"name": "Alice", "age": 30})
```

## 🧹 Cleanup Completed

### Removed:
- ❌ `dataclass_widget_clean.py` (duplicate/outdated)  
- ❌ `input_template_local.html` (renamed to main template)

### Renamed:
- ✅ `input_template.html` ← `input_template_local.html` (now the main template)
- ✅ `input_template_cdn.html` ← `input_template.html` (old CDN version, kept for reference)

### Current Status: 
🎉 **Repository is clean and production-ready!**

# Export Functionality Fix Summary

## Issue Identified
The dataclass builder widget's Export button wasn't working due to a namespace issue in JavaScript → Python communication.

## Root Cause
When the CnD interface's Export button was clicked, it sent a `postMessage` to trigger Python code execution via `window.Jupyter.notebook.kernel.execute()`. However, the executed Python code couldn't access the widget registry because:

1. The registry `_spytial_widgets` existed in the module namespace
2. But `kernel.execute()` runs in a different namespace (globals) 
3. The import `from spytial.dataclass_widget_cnd import _spytial_widgets` failed in this context

## Evidence
```python
# This test revealed the issue:
if '_spytial_widgets' in globals():
    print("✓ Registry accessible from globals()")
else:
    print("✗ Registry NOT in globals() - This is the problem!")
    # ^ This was the actual output
```

## Solution
Modified the message handler in `spytial/dataclass_widget_cnd.py` to access the registry via `sys.modules` instead of direct import:

**Before (broken):**
```python
from spytial.dataclass_widget_cnd import _spytial_widgets, _json_to_dataclass
```

**After (fixed):**
```python
import sys
if 'spytial.dataclass_widget_cnd' in sys.modules:
    widget_module = sys.modules['spytial.dataclass_widget_cnd']
    _spytial_widgets = widget_module._spytial_widgets
    _json_to_dataclass = widget_module._json_to_dataclass
else:
    from spytial.dataclass_widget_cnd import _spytial_widgets, _json_to_dataclass
```

## Testing Results
- ✅ Registry now accessible via `sys.modules` approach
- ✅ Export simulation test successful
- ✅ Widget value updates correctly when Export is clicked
- ✅ All widgets created after the fix work properly

## Files Modified
- `spytial/dataclass_widget_cnd.py` - Fixed message handler code
- `demos/06-dataclass-cnd-builder.ipynb` - Added comprehensive tests

## Validation
The fix has been validated with:
1. Registry accessibility test
2. Complete export flow simulation  
3. New widget creation and testing
4. End-to-end user interaction test

## Usage
All new widgets created with `spytial.dataclass_builder()` now have working Export functionality. Widgets created before the fix may still have the old message handler - create a new widget to get the fix.
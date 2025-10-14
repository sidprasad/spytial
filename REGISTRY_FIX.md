# Widget Registry Fix - Final Summary

## Problem Identified

The widget value was staying `None` after clicking "Export JSON" because of a **namespace issue**:

### Old Approach (Broken)
```python
# In __init__:
globals()['_spytial_widgets'][self._widget_id] = self

# In JavaScript handler:
if '_spytial_widgets' in globals() and widget_id in _spytial_widgets:
    widget = _spytial_widgets[widget_id]
```

**Issue**: `globals()` in the widget's `__init__` refers to the **module's globals**, but when Jupyter's kernel executes code via `kernel.execute()`, it runs in the **notebook's global namespace**, which is different!

### New Approach (Fixed)
```python
# Module-level registry
_spytial_widgets = {}

# In __init__:
_spytial_widgets[self._widget_id] = self

# In JavaScript handler:
from spytial.dataclass_widget_cnd import _spytial_widgets
widget = _spytial_widgets[widget_id]
```

**Solution**: Use a **module-level variable** that can be imported directly, ensuring it's accessible from any execution context.

## Changes Made

### File: `spytial/dataclass_widget_cnd.py`

1. **Added module-level registry** (line ~120):
   ```python
   _spytial_widgets = {}
   ```

2. **Updated widget registration** (in `__init__`):
   ```python
   _spytial_widgets[self._widget_id] = self
   ```

3. **Updated JavaScript handler** (in `_setup_widget`):
   ```python
   from spytial.dataclass_widget_cnd import _spytial_widgets, _json_to_dataclass
   widget = _spytial_widgets[widget_id]
   ```

4. **Added CnD format converter** (`_cnd_to_flat_dict`):
   - Handles CnD relational format (`atoms`, `relations`)
   - Extracts field values from atoms/relations
   - Converts to flat dict for dataclass construction

5. **Enhanced `_json_to_dataclass`**:
   - Detects CnD format vs flat dict
   - Automatically converts CnD format before processing
   - Supports both input styles

## Testing Results

### ✅ Verified Working

```bash
$ python test_script.py
✓ Widget created
✓ Registry accessible
✓ Widget in registry
✓ Retrieved widget matches
✓ Exec simulation works
✓ Widget value updates correctly
✅ Module-level registry works!
```

### ✅ Format Conversion

```python
# Flat dict (original)
{'name': 'Alice', 'age': 30} → Person(name='Alice', age=30)

# CnD relational format (from structured-input-graph)
{
  'atoms': [...],
  'relations': [...]
} → Person(name='Alice', age=30)
```

## Testing in Jupyter

### Notebook: `demos/06-dataclass-cnd-builder.ipynb`

The notebook now includes debugging cells:

1. **Cell after widget creation**: Check registry status
2. **Manual test cell**: Simulate export without JavaScript
3. **Value check cell**: Verify `widget.value` updates

### Steps to Test

1. **Run cells 1-6**: Create widget and display it
2. **Open browser console** (F12)
3. **Click "Export JSON"** button in widget
4. **Watch for console logs**:
   ```
   Export button clicked!
   Got data: {atoms: [...], relations: [...]}
   Sending message: {type: 'spytial-export', ...}
   ```
5. **Check notebook output**:
   ```
   📥 Received data (length: 234 chars)
   📊 Data structure keys: ['atoms', 'relations', 'types']
   ✅ Built: Person(name='...', age=...)
   ```
6. **Run value check cell**: `widget.value` should contain the Person instance

### Debugging Checklist

- [ ] Widget displays in notebook
- [ ] CnD interface loads (see graph visualization)
- [ ] Can edit field values in interface
- [ ] Export button visible in toolbar
- [ ] Click export shows console logs
- [ ] Notebook output shows "📥 Received data"
- [ ] Notebook output shows "✅ Built: Person(...)"
- [ ] `widget.value` returns Person instance (not None)

### If Still Not Working

Run the manual test cell to isolate the issue:
- If manual test works → JavaScript communication problem
- If manual test fails → Python conversion problem

Check browser console for:
- `postMessage` being sent
- Jupyter kernel available
- No JavaScript errors

Check notebook for:
- Import errors
- Module not found errors
- Traceback from kernel execution

## Architecture Flow

```
User clicks "Export JSON"
    ↓
JavaScript: exportDataToFile()
    ↓
JavaScript: graphElement.getDataInstance()
    ↓
Returns: {atoms: [...], relations: [...]}
    ↓
JavaScript: window.parent.postMessage({...})
    ↓
Parent window receives message
    ↓
JavaScript: window.Jupyter.notebook.kernel.execute(code)
    ↓
Python kernel executes:
    from spytial.dataclass_widget_cnd import _spytial_widgets
    widget = _spytial_widgets[widget_id]
    data = json.loads(...)
    widget._current_value = _json_to_dataclass(data, ...)
    ↓
_json_to_dataclass detects CnD format
    ↓
_cnd_to_flat_dict extracts field values
    ↓
Creates dataclass instance
    ↓
Updates widget._current_value
    ↓
User accesses widget.value
```

## Files Modified

1. `spytial/dataclass_widget_cnd.py` - Registry and conversion fixes
2. `spytial/input_template.html` - Enhanced debugging logs
3. `demos/06-dataclass-cnd-builder.ipynb` - Added debugging cells

## Next Steps

1. **Test in Jupyter** - Run the notebook and interact with widget
2. **Verify export** - Click button and check console/output
3. **Check value** - Ensure `widget.value` is not None
4. **Report results** - Any errors or success confirmation

## Expected Behavior

### Success Indicators ✅

- Widget displays with CnD interface
- Can edit field values visually
- Export button works without errors
- Console shows data being sent
- Notebook prints "✅ Built: Person(...)"
- `widget.value` returns actual Person instance

### Still Broken? ❌

- Widget value stays None
- No console logs when clicking export
- JavaScript errors in console
- Python traceback in notebook
- "Widget not found in registry" error

If still broken, check:
1. Browser console for JS errors
2. Notebook output for Python errors
3. Run manual test cell to isolate issue
4. Verify iframe can communicate with parent window

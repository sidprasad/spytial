# Dataclass Builder Widget - CnD-core Integration

## Summary of Changes

### Files Changed
1. **Created: `spytial/dataclass_widget_cnd.py`** - New CnD-core based widget
2. **Modified: `spytial/__init__.py`** - Import the new widget
3. **Deleted: `spytial/dataclass_widget_new.py`** - Old HTML form version
4. **Deleted: `spytial/dataclass_widget.py`** - Original broken file-based version

### What We Built

A **visual dataclass builder** that uses CnD-core's `structured-input-graph` component:

- ✅ No file I/O (uses postMessage communication)
- ✅ No timeouts (direct kernel execution)
- ✅ Includes spatial annotations from decorators
- ✅ Real-time `widget.value` updates
- ✅ Visual, interactive construction interface

## Architecture

```
Python Side                    JavaScript Side (iframe)
-----------                    ------------------------
dataclass_builder(Person)  →  Generate CnD spec from decorators
         ↓                          ↓
Create empty instance     →  Convert to CnD data format
         ↓                          ↓
Embed in iframe           →  Load structured-input-graph
         ↓                          ↓
Register in global dict   →  User edits visually
         ↓                          ↓
Wait for export           ←  Click "Export JSON" button
         ↓                          ↓
Receive postMessage       ←  Send data via postMessage
         ↓
Execute Python code via kernel
         ↓
Convert JSON → dataclass
         ↓
Update widget._current_value
         ↓
User accesses widget.value
```

## How to Test

### 1. Basic Functionality (Already Verified ✅)
```bash
python test_widget_instantiation.py
```

This confirms:
- Widget can be instantiated
- Helper functions work
- Data conversion works

### 2. Interactive Testing (NEEDS MANUAL TEST)

Run in Jupyter:
```bash
jupyter notebook demos/test-widget-interaction.ipynb
```

Then:
1. Create widget: `widget = spytial.dataclass_builder(Person)`
2. Display it: `widget`
3. **Interact with CnD interface** - edit nodes, add connections
4. Click **"Export JSON"** button
5. Check: `widget.value` should contain your Person instance

### What to Look For

#### ✅ Success Indicators:
- CnD visual interface loads in the widget
- You can see dataclass fields as editable nodes
- Export button exists in toolbar
- Clicking export prints "✅ Built: Person(...)"
- `widget.value` contains the dataclass instance

#### ❌ Failure Indicators:
- Blank iframe (CnD not loading)
- JavaScript errors in console
- "Jupyter kernel not available" error
- `widget.value` stays None after export
- postMessage not reaching Python

## Communication Flow Details

### JavaScript → Python (Export)

When user clicks "Export JSON":

```javascript
// In input_template.html
window.parent.postMessage({
    type: 'spytial-export',
    widgetId: 'spytial_12345',
    data: { name: 'Alice', age: 30 },
    dataclassName: 'Person'
}, '*');
```

### Python Receives Message

Message handler in `dataclass_widget_cnd.py`:

```python
# Executed via kernel.execute()
widget = _spytial_widgets['spytial_12345']
data = json.loads('{"name": "Alice", "age": 30}')
widget._current_value = _json_to_dataclass(data, Person)
print(f"✅ Built: {widget._current_value}")
```

### User Accesses Result

```python
person = widget.value  # Returns widget._current_value
```

## Known Issues & Limitations

### Current Limitations:
1. **Nested dataclasses** - Not fully supported yet
2. **Complex types** - List[T], Dict[K,V] need work
3. **Validation** - No field-level validation yet

### Dependencies:
- `ipywidgets` - Required for Jupyter widgets
- `pyyaml` - For CnD spec generation
- CnD-core CDN - Loaded from `cdn.jsdelivr.net`

## Testing Checklist

- [x] Widget instantiation works
- [x] Helper functions work (empty instance, spec generation, JSON conversion)
- [x] Import paths correct
- [x] No import errors
- [ ] **CnD interface loads in Jupyter** (NEEDS MANUAL TEST)
- [ ] **Export button functional** (NEEDS MANUAL TEST)
- [ ] **JavaScript → Python communication works** (NEEDS MANUAL TEST)
- [ ] **widget.value updates correctly** (NEEDS MANUAL TEST)

## Next Steps

1. **Run `demos/test-widget-interaction.ipynb` in Jupyter**
2. **Check browser console** for any JavaScript errors
3. **Verify postMessage** is being sent and received
4. **Test with spatial annotations** (orientation, group, etc.)
5. **Test visualization workflow**: build → export → diagram

## Troubleshooting Guide

### Issue: Widget shows blank iframe
- Check internet connection (CnD loads from CDN)
- Check browser console for loading errors
- Verify input_template.html exists

### Issue: Export does nothing
- Open browser console (F12)
- Look for "Jupyter kernel not available"
- Check if postMessage is being logged
- Verify widget is in global registry

### Issue: widget.value is None
- Make sure you clicked Export button
- Check for errors in notebook output
- Verify widget._widget_id matches in registry
- Try running the debugging cell in test notebook

## Files Reference

- `spytial/dataclass_widget_cnd.py` - Main implementation
- `spytial/input_template.html` - CnD interface template
- `spytial/__init__.py` - Exports dataclass_builder
- `demos/test-widget-interaction.ipynb` - Quick test notebook
- `demos/06-dataclass-cnd-builder.ipynb` - Full demo
- `test_widget_instantiation.py` - Unit test script

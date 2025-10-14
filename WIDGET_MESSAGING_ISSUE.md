# Widget Messaging Issue Summary

## Problem
The dataclass builder widget shows "Data sent to widget!" when Export is clicked, but the Python side doesn't receive the data. The `widget.value` remains `None`.

## Root Cause
The `postMessage` communication from the iframe to the parent window isn't reaching the Python message handler. This is because:

1. **Message is sent**: The iframe correctly calls `window.parent.postMessage(message, '*')`
2. **Handler exists**: The message handler with `window.addEventListener('message', ...)` is present
3. **But not caught**: The handler never fires, OR `window.Jupyter.notebook.kernel.execute()` fails silently

## Evidence
- User sees: "Success - Data sent to widget!" (JavaScript side works)
- User does NOT see: "📥 Received data..." (Python side doesn't execute)
- `widget.value` remains `None`

## Why This Happens in Jupyter
- In regular Jupyter Notebook, iframe→parent `postMessage` may be blocked
- `window.Jupyter.notebook.kernel.execute()` may not work from iframe context
- Jupyter's security model restricts cross-frame communication

## Solutions to Try

### Solution 1: Use IPyWidgets Comm System (Recommended)
Instead of `postMessage`, use Jupyter's built-in comm system which is designed for widget communication.

### Solution 2: Direct DOM Access
Have the iframe write to a hidden element that Python polls.

### Solution 3: File-based Communication
Fall back to the file download approach (already works as backup).

### Solution 4: Custom JavaScript Extension
Create a Jupyter nbextension that acts as a bridge.

## Current Workaround
Users can manually update the widget with test data:
```python
from spytial.dataclass_widget_cnd import _json_to_dataclass
tree_widget._current_value = _json_to_dataclass({'value': 10}, TreeNode)
```

## Next Steps
1. Test if `window.Jupyter` is available in iframe context
2. Try using IPyWidgets comm system instead of postMessage
3. Add more debugging to see where the message flow breaks

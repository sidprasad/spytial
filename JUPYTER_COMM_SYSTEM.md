# Jupyter Communication System

## Overview

The dataclass builder widget now uses a three-tier communication system to export data from the CnD interface back to Python:

## Communication Methods (In Order of Priority)

### 1. postMessage (Primary - Works in Jupyter)
**Location**: Parent window message listener
**How it works**:
- Iframe posts message to `window.parent` with widget data
- Parent window has event listener registered when widget is created
- Listener extracts data and calls `IPython.notebook.kernel.execute()` to run Python code
- Python code updates widget's `_current_value` in the registry

**Advantages**:
- Works across iframe boundaries
- No file I/O needed
- Instant updates
- Browser security allows postMessage between parent and iframe

**Code Flow**:
```
[CnD Interface in iframe]
  ↓ window.parent.postMessage({type: 'spytial-export', data: ...})
[Parent Window Listener] 
  ↓ IPython.notebook.kernel.execute(python_code)
[Python Kernel]
  ↓ Updates _spytial_widgets[widget_id]._current_value
[User accesses widget.value]
  ↓ Returns updated value
```

### 2. Jupyter Comm (Secondary - Native Jupyter)
**Location**: Jupyter kernel comm system  
**How it works**:
- Widget creates a Jupyter `Comm` object with target name = widget_id
- JavaScript tries to access `window.parent.Jupyter.notebook.kernel.comm_manager`
- If successful, creates matching comm and sends messages

**Status**: 
- ⚠️ Currently blocked by iframe security restrictions
- Jupyter object not accessible from inside iframe in VS Code/JupyterLab
- Kept as fallback for future Jupyter versions or different environments

### 3. File System Access API (Tertiary - Standalone)
**Location**: Browser Save Dialog
**How it works**:
- Uses modern `showSaveFilePicker()` API
- Opens native file save dialog
- User navigates to temp directory and saves
- Python polls directory and auto-loads file

**Advantages**:
- User can choose exact save location
- Works outside Jupyter notebooks
- No iframe restrictions

**Limitations**:
- Requires user interaction (choose location)
- Only available in Chromium browsers (Chrome, Edge)
- Doesn't work inside iframes

### 4. Traditional Download (Fallback - Universal)
**Location**: Downloads folder
**How it works**:
- Creates blob URL and triggers download
- File saves to browser's Downloads folder
- User manually moves file to widget's temp directory
- Python detects and loads file

**Advantages**:
- Works in all browsers
- Works in all environments
- No special APIs needed

**Limitations**:
- Requires manual file movement
- Most steps for user
- File I/O overhead

## Implementation Details

### Python Side (`dataclass_widget_cnd.py`)

```python
class DataclassBuilderWidget:
    def __init__(self, dataclass_type):
        # Register in global registry
        _spytial_widgets[self._widget_id] = self
        
        # Setup Jupyter comm (may not work in iframe)
        self._setup_comm()
        
        # Inject postMessage listener into parent window
        message_handler = """
        <script>
        window.addEventListener('message', function(event) {
            if (event.data.type === 'spytial-export') {
                // Execute Python via Jupyter kernel
                IPython.notebook.kernel.execute(python_code);
            }
        });
        </script>
        """
```

### JavaScript Side (`input_template.html`)

```javascript
async function exportDataToFile() {
    const data = graphElement.getDataInstance();
    
    // Try 1: postMessage to parent (works in Jupyter iframes)
    window.parent.postMessage({
        type: 'spytial-export',
        widgetId: '{{ widget_id }}',
        data: data
    }, '*');
    
    // Try 2: Jupyter comm (if accessible)
    if (jupyterComm) {
        jupyterComm.send({type: 'export_data', data: data});
        return;
    }
    
    // Try 3: File System Access API (Chrome/Edge standalone)
    if ('showSaveFilePicker' in window) {
        const fileHandle = await showSaveFilePicker({...});
        // Save file directly
        return;
    }
    
    // Try 4: Traditional download (all browsers)
    const blob = new Blob([JSON.stringify(data)]);
    downloadFile(blob, filename);
}
```

## Debugging

### Check if postMessage works:
1. Create widget
2. Look for: `✓ Message listener registered for widget: spytial_XXXXX`
3. Click Export
4. Look for: `📥 Received data via postMessage`
5. Check: `widget.value` should return dataclass instance

### Check Jupyter kernel execution:
- Open browser console (F12)
- Look for: `Executing via IPython.notebook.kernel`
- Check Python output for: `📥 Received data via postMessage`

### If postMessage fails:
- Falls back to Jupyter comm (usually also blocked)
- Falls back to File System Access API (user dialog)
- Falls back to download (manual file movement)

## Browser Compatibility

| Method | Chrome | Firefox | Safari | Edge | Jupyter | VS Code |
|--------|--------|---------|--------|------|---------|---------|
| postMessage | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Jupyter Comm | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| File System API | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Download | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

✅ = Fully supported
⚠️ = Limited (iframe restrictions)
❌ = Not supported

## Why This Approach?

1. **postMessage works in iframes**: Unlike Jupyter comm, postMessage is explicitly designed for cross-frame communication

2. **Jupyter kernel execution**: We can execute Python code from JavaScript using `IPython.notebook.kernel.execute()`, which is available in the parent window

3. **Global registry**: Widgets are stored in module-level `_spytial_widgets` dict, accessible from any execution context

4. **Multiple fallbacks**: If postMessage fails, we have 3 other methods to ensure it works somewhere

## Testing

```python
# Create widget
widget = spytial.dataclass_builder(TreeNode)

# Check if listener is registered (browser console)
# Should see: "✓ Message listener registered"

# Click Export button
# Should see: "📥 Received data via postMessage"

# Access value
result = widget.value
print(result)  # Should show TreeNode instance
```

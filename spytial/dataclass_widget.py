"""
sPyTial Dataclass Input Widget

A Jupyter widget that displays build_input interface in an iframe with 
real-time value tracking via postMessage communication.
"""

import json
import os
import tempfile
import threading
import time
from dataclasses import fields, is_dataclass
from typing import Any, Dict, Optional, Type, get_type_hints

try:
    from ipywidgets import HTML, VBox, Button, Output, DOMWidget
    from traitlets import Unicode, observe, Dict as TraitDict
    IPYWIDGETS_AVAILABLE = True
except ImportError:
    IPYWIDGETS_AVAILABLE = False

from .dataclassbuilder import json_to_dataclass
    
# Only define widget classes if ipywidgets is available
if IPYWIDGETS_AVAILABLE:
    from ipywidgets import HTML, Button, VBox, HBox, Text, Output
    
    class DataclassInputWidget:
        """
        A Jupyter widget that displays build_input interface in an iframe
        with continuous value observation.
        """
        
        def __init__(self, dataclass_type: Type):
            """
            Initialize the dataclass input widget.
            
            Args:
                dataclass_type: The dataclass type to build instances for
            """
            if not is_dataclass(dataclass_type):
                raise ValueError(f"{dataclass_type} is not a dataclass.")
                
            self.dataclass_type = dataclass_type
            self._current_value = None
            self._html_file = None
            self._export_dir = None
            self._observer_thread = None
            self._stop_observer = False
            
            self._setup_widget()
        
        def _setup_widget(self):
            """Setup the widget with iframe and file watching."""
            
            # Create temporary directory for data export
            self._export_dir = tempfile.mkdtemp(prefix='spytial_widget_')
            
            # Generate HTML content using build_input
            try:
                from .dataclassbuilder import build_input
                
                # Get HTML content directly (not file)
                html_content = build_input(
                    self.dataclass_type,
                    method='inline',
                    auto_open=False,
                    export_dir=self._export_dir
                )
                
                # Create iframe with embedded HTML content and message handler
                # Use data URL to embed HTML directly
                import base64
                html_b64 = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
                
                iframe_html = f"""
                <iframe 
                    src="data:text/html;base64,{html_b64}" 
                    width="100%" 
                    height="600px" 
                    frameborder="0"
                    id="spytial-iframe"
                    style="border: 1px solid #ddd; border-radius: 4px;">
                    <p>Your browser does not support iframes.</p>
                </iframe>
                <script>
                // Global variable to store widget reference
                window.spytialWidget_{id(self)} = null;
                
                window.addEventListener('message', function(event) {{
                    if (event.data && event.data.type === 'spytial-export') {{
                        // Save data to export directory
                        const data = event.data.data;
                        const filename = event.data.filename;
                        const exportDir = event.data.exportDir;
                        
                        // Execute Python code to save file
                        if (window.Jupyter && window.Jupyter.notebook && window.Jupyter.notebook.kernel) {{
                            const code = `
import json
import os
from spytial.dataclassbuilder import json_to_dataclass

# Save export file  
data = ${{JSON.stringify(event.data.data)}}
export_dir = "${{event.data.exportDir}}"
filename = "${{event.data.filename}}"
filepath = os.path.join(export_dir, filename)
os.makedirs(export_dir, exist_ok=True)
with open(filepath, 'w') as f:
    json.dump(data, f, indent=2)

# Also update widget value directly
try:
    widget = spytial_widget_{id(self)}
    if widget:
        widget._current_value = json_to_dataclass(data, widget.dataclass_type)
        with widget.status_output:
            widget.status_output.clear_output()
            print(f"Updated: {{widget._current_value}}")
except:
    pass
`;
                            window.Jupyter.notebook.kernel.execute(code);
                        }}
                    }}
                }});
                
                // Store widget reference globally
                window.spytialWidget_{id(self)} = window.spytialWidget_{id(self)} || {{}};
                </script>
                """
                
                # Create the widget components
                self.iframe_widget = HTML(value=iframe_html)
                self.status_output = Output()
                
                # Create layout
                self.widget = VBox([
                    HTML(f"<h3>{self.dataclass_type.__name__} Builder</h3>"),
                    self.iframe_widget,
                    self.status_output
                ])
                
                # Start file observer thread
                self._start_file_observer()
                
                # Register this widget globally for JavaScript access
                import sys
                globals()[f'spytial_widget_{id(self)}'] = self
                
                with self.status_output:
                    print("Widget ready - export data to see it here")
                
            except Exception as e:
                # Fallback to error message
                error_html = f"<p><strong>Error creating widget:</strong> {e}</p>"
                self.widget = VBox([HTML(value=error_html)])
        
        def _start_file_observer(self):
            """Start a background thread to watch for exported JSON files."""
            self._stop_observer = False
            self._observer_thread = threading.Thread(target=self._observe_export_files, daemon=True)
            self._observer_thread.start()
        
        def _observe_export_files(self):
            """Background thread that watches for new JSON files and updates value."""
            last_mtime = 0
            
            while not self._stop_observer:
                try:
                    # Look for JSON files in export directory
                    json_files = [f for f in os.listdir(self._export_dir) if f.endswith('.json')]
                    
                    if json_files:
                        # Get the most recent JSON file
                        latest_file = max(
                            [os.path.join(self._export_dir, f) for f in json_files],
                            key=os.path.getmtime
                        )
                        
                        current_mtime = os.path.getmtime(latest_file)
                        
                        # If file is newer, update value
                        if current_mtime > last_mtime:
                            last_mtime = current_mtime
                            self._update_value_from_file(latest_file)
                    
                    time.sleep(1)  # Check every second
                    
                except Exception as e:
                    # Continue watching even if there's an error
                    time.sleep(2)
        
        def _update_value_from_file(self, file_path):
            """Update the current value from a JSON file."""
            try:
                with open(file_path, 'r') as f:
                    json_data = json.load(f)
                    
                # Convert to dataclass
                new_value = json_to_dataclass(json_data, self.dataclass_type)
                
                # Update current value
                old_value = self._current_value
                self._current_value = new_value
                
                # Update status display
                with self.status_output:
                    self.status_output.clear_output()
                    print(f"Updated: {new_value}")
                    
            except Exception as e:
                with self.status_output:
                    print(f"Error: {e}")
        
        @property 
        def value(self):
            """Get the current built dataclass instance."""
            return self._current_value
        
        def _repr_mimebundle_(self, **kwargs):
            """Display the widget in Jupyter."""
            return self.widget._repr_mimebundle_(**kwargs)
        
        def __del__(self):
            """Clean up resources."""
            self._stop_observer = True
            if self._observer_thread and self._observer_thread.is_alive():
                self._observer_thread.join(timeout=1)
            
            # Clean up temporary files
            try:
                if self._html_file and os.path.exists(self._html_file):
                    os.unlink(self._html_file)
                if self._export_dir and os.path.exists(self._export_dir):
                    import shutil
                    shutil.rmtree(self._export_dir, ignore_errors=True)
            except:
                pass
            
else:
    # Create placeholder class when ipywidgets is not available
    class DataclassInputWidget:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "ipywidgets is required for DataclassInputWidget. "
                "Install with: pip install ipywidgets"
            )





def create_dataclass_widget(dataclass_type: Type) -> Any:
    """
    Create a dataclass input widget.
    
    Args:
        dataclass_type: The dataclass type to create a widget for
        
    Returns:
        A widget instance for building dataclass instances
    """
    if not IPYWIDGETS_AVAILABLE:
        raise ImportError(
            "ipywidgets is required for widgets. Install with: pip install ipywidgets"
        )
    
    return DataclassInputWidget(dataclass_type)


# Convenience function for notebook use  
def dataclass_widget(dataclass_type: Type) -> Any:
    """
    Create and display a dataclass input widget in a Jupyter notebook.
    
    This creates a widget that displays the build_input interface in an iframe
    with continuous value observation. The widget automatically updates its
    'value' property when you export data from the interface.
    
    Args:
        dataclass_type: The dataclass type to create input interface for
        
    Returns:
        Widget instance with real-time value tracking
        
    Example:
        @dataclass
        class Person:
            name: str = ""
            age: int = 0
            
        widget = spytial.dataclass_widget(Person)
        # Use the interface to build and export data
        # widget.value automatically updates with the latest dataclass instance
        person = widget.value  # Get the current built instance
    """
    return create_dataclass_widget(dataclass_type)

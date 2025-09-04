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
            
            # Create temporary directory for HTML file and data export
            self._export_dir = tempfile.mkdtemp(prefix='spytial_widget_')
            
            # Generate HTML file using build_input
            try:
                from .dataclassbuilder import build_input
                
                # Create HTML file instead of inline content
                html_path = build_input(
                    self.dataclass_type,
                    method='file',
                    auto_open=False,
                    export_dir=self._export_dir
                )
                
                self._html_file = os.path.abspath(html_path)
                
                # Create iframe to display the HTML file
                iframe_html = f"""
                <iframe 
                    src="file://{self._html_file}" 
                    width="100%" 
                    height="600px" 
                    frameborder="0"
                    style="border: 1px solid #ddd; border-radius: 4px;">
                    <p>Your browser does not support iframes. 
                    <a href="file://{self._html_file}" target="_blank">Open in new window</a></p>
                </iframe>
                """
                
                # Create the widget components
                self.iframe_widget = HTML(value=iframe_html)
                self.status_output = Output()
                
                # Create layout
                self.widget = VBox([
                    HTML(f"<h3>{self.dataclass_type.__name__} Builder</h3>"),
                    HTML("<p>Build your data in the interface below. The value will update automatically.</p>"),
                    self.iframe_widget,
                    HTML("<hr><b>Current Status:</b>"),
                    self.status_output
                ])
                
                # Start file observer thread
                self._start_file_observer()
                
                with self.status_output:
                    print(f"✅ Widget ready! Export directory: {self._export_dir}")
                    print("💡 Data will be captured automatically when you export from the interface.")
                
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
                    print(f"🔄 Value updated from: {os.path.basename(file_path)}")
                    print(f"📊 Current value: {new_value}")
                    print(f"🕒 Updated at: {time.strftime('%H:%M:%S')}")
                    
            except Exception as e:
                with self.status_output:
                    print(f"❌ Error updating value: {e}")
        
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

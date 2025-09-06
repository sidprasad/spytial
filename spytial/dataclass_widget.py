"""
sPyTial Dataclass Input Widget

A Jupyter widget that displays build_input interface in an iframe with 
direct postMessage communication - no file I/O needed.
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
        with direct postMessage communication.
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
            self._widget_id = id(self)
            
            self._setup_widget()
        
        def _setup_widget(self):
            """Setup the widget with iframe and direct communication."""
            
            # Generate HTML content using build_input
            try:
                from .dataclassbuilder import build_input
                
                # Get HTML content with widget_id template variable
                html_content = build_input(
                    self.dataclass_type,
                    method='inline',
                    auto_open=False,
                    export_dir='/tmp',  # Not used but required
                    widget_id=str(self._widget_id)  # Pass widget ID to template
                )
                
                # Create iframe with embedded HTML content
                import base64
                html_b64 = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
                
                # Create message handler script
                message_handler = f"""
                <script>
                window.addEventListener('message', function(event) {{
                    try {{
                        if (event.data && event.data.type === 'spytial-export' && event.data.widgetId === '{self._widget_id}') {{
                            console.log('Received export data:', event.data);
                            
                            // Execute Python to update widget value directly
                            var code = `
# Update widget value directly
try:
    import json
    from spytial.dataclassbuilder import json_to_dataclass
    
    # Get widget from global registry
    widget_id = '{self._widget_id}'
    if '_spytial_widgets' in globals() and widget_id in _spytial_widgets:
        widget = _spytial_widgets[widget_id]
        data = ${{JSON.stringify(event.data.data)}}
        widget._current_value = json_to_dataclass(data, widget.dataclass_type)
        
        # Update status
        with widget.status_output:
            widget.status_output.clear_output()
            print(f"✅ Exported: {{widget._current_value}}")
    else:
        print(f"Widget {{widget_id}} not found in registry")
            
except Exception as e:
    print(f"Error updating widget: {{e}}")
    import traceback
    traceback.print_exc()
`;
                            
                            if (window.Jupyter && window.Jupyter.notebook && window.Jupyter.notebook.kernel) {{
                                window.Jupyter.notebook.kernel.execute(code);
                            }} else {{
                                console.error('Jupyter kernel not available');
                            }}
                        }}
                    }} catch (error) {{
                        console.error('Message handler error:', error);
                    }}
                }});
                </script>
                """
                
                iframe_html = f"""
                {message_handler}
                <iframe 
                    src="data:text/html;base64,{html_b64}" 
                    width="100%" 
                    height="600px" 
                    frameborder="0"
                    id="spytial-iframe-{self._widget_id}"
                    style="border: 1px solid #ddd; border-radius: 4px;">
                    <p>Your browser does not support iframes.</p>
                </iframe>
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
                
                # Register this widget globally for access from JavaScript
                if '_spytial_widgets' not in globals():
                    globals()['_spytial_widgets'] = {}
                globals()['_spytial_widgets'][str(self._widget_id)] = self
                
                with self.status_output:
                    print("Widget ready - build and export your data!")
                
            except Exception as e:
                # Fallback to error message
                error_html = f"<p><strong>Error creating widget:</strong> {e}</p>"
                self.widget = VBox([HTML(value=error_html)])
        
        def update_value_directly(self, data):
            """Update widget value directly from JavaScript."""
            try:
                self._current_value = json_to_dataclass(data, self.dataclass_type)
                with self.status_output:
                    self.status_output.clear_output()
                    print(f"✅ Updated: {self._current_value}")
            except Exception as e:
                with self.status_output:
                    self.status_output.clear_output()
                    print(f"❌ Error: {e}")
        
        @property 
        def value(self):
            """Get the current built dataclass instance."""
            return self._current_value
        
        def _repr_mimebundle_(self, **kwargs):
            """Display the widget in Jupyter."""
            return self.widget._repr_mimebundle_(**kwargs)
        
        def __del__(self):
            """Clean up resources."""
            # Remove from global registry
            if '_spytial_widgets' in globals() and str(self._widget_id) in globals()['_spytial_widgets']:
                del globals()['_spytial_widgets'][str(self._widget_id)]
            
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

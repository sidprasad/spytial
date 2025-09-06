"""
sPyTial Dataclass Input Widget

A unified widget that combines dataclass building and interactive input interface.
Provides real-time communication between iframe and Jupyter via postMessage.
"""

import json
import os
import tempfile
import threading
import time
import uuid
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
        A unified Jupyter widget that displays build_input interface in an iframe
        with real-time bidirectional communication for seamless dataclass building.

        This widget combines the functionality of dataclass building and interactive
        input interface into one streamlined component.
        """

        def __init__(self, dataclass_type: Type):
            """
            Initialize the unified dataclass input widget.

            Args:
                dataclass_type: The dataclass type to build instances for
            """
            if not is_dataclass(dataclass_type):
                raise ValueError(f"{dataclass_type} is not a dataclass.")

            self.dataclass_type = dataclass_type
            self._current_value = None
            self._widget_id = str(uuid.uuid4())  # Use UUID for unique identification
            self._response_data = None
            self._waiting_for_response = False

            self._setup_widget()

        def _setup_widget(self):
            """Setup the widget with iframe and bidirectional communication system."""

            # Generate HTML content using build_input
            try:
                from .dataclassbuilder import build_input

                # Get HTML content with widget_id template variable
                html_content = build_input(
                    self.dataclass_type,
                    method="inline",
                    auto_open=False,
                    export_dir="/tmp",  # Not used but required
                    widget_id=self._widget_id,  # Pass widget ID to template
                )

                # Create iframe with embedded HTML content
                import base64

                html_b64 = base64.b64encode(html_content.encode("utf-8")).decode(
                    "utf-8"
                )

                # Create bidirectional message handler script
                # This handles both automatic updates and on-demand value requests
                message_handler = f"""
                <script>
                window.addEventListener('message', function(event) {{
                    try {{
                        // Handle export data from iframe (automatic updates)
                        if (event.data && event.data.type === 'spytial-export' && event.data.widgetId === '{self._widget_id}') {{
                            console.log('Received export data:', event.data);
                            
                            // Execute Python to update widget value directly
                            var code = `
# Update widget value from iframe export
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
            print(f"✅ Auto-updated: {{widget._current_value}}")
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
                        
                        // Handle value request response from iframe
                        else if (event.data && event.data.type === 'spytial-value-response' && event.data.widgetId === '{self._widget_id}') {{
                            console.log('Received value response:', event.data);
                            
                            // Execute Python to set response data
                            var code = `
# Handle value request response
try:
    import json
    from spytial.dataclassbuilder import json_to_dataclass
    
    # Get widget from global registry
    widget_id = '{self._widget_id}'
    if '_spytial_widgets' in globals() and widget_id in _spytial_widgets:
        widget = _spytial_widgets[widget_id]
        data = ${{JSON.stringify(event.data.data)}}
        
        # Set response data and clear waiting flag
        widget._response_data = json_to_dataclass(data, widget.dataclass_type)
        widget._waiting_for_response = False
    else:
        print(f"Widget {{widget_id}} not found in registry")
            
except Exception as e:
    print(f"Error handling value response: {{e}}")
    widget._waiting_for_response = False
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
                
                // Function to request current value from iframe
                window.requestSpytialValue_{self._widget_id.replace('-', '_')} = function() {{
                    var iframe = document.getElementById('spytial-iframe-{self._widget_id}');
                    if (iframe && iframe.contentWindow) {{
                        console.log('Requesting current value from iframe');
                        iframe.contentWindow.postMessage({{
                            type: 'spytial-get-value',
                            widgetId: '{self._widget_id}'
                        }}, '*');
                    }} else {{
                        console.error('Iframe not found or not accessible');
                    }}
                }};
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
                self.widget = VBox(
                    [
                        HTML(f"<h3>{self.dataclass_type.__name__} Builder</h3>"),
                        self.iframe_widget,
                        self.status_output,
                    ]
                )

                # Register this widget globally for access from JavaScript
                if "_spytial_widgets" not in globals():
                    globals()["_spytial_widgets"] = {}
                globals()["_spytial_widgets"][self._widget_id] = self

                with self.status_output:
                    print("Widget ready - build your data in the interface above!")
                    print(
                        "💡 Access widget.value anytime to get the current dataclass instance"
                    )

            except Exception as e:
                # Fallback to error message
                error_html = f"<p><strong>Error creating widget:</strong> {e}</p>"
                self.widget = VBox([HTML(value=error_html)])

        def _request_current_value(self) -> Optional[Any]:
            """
            Request current value from the iframe via postMessage communication.

            This method:
            1. Sends a message to the iframe requesting current data
            2. Waits for the iframe to respond with current form state
            3. Converts the response to a dataclass instance
            4. Returns the instance

            Returns:
                Current dataclass instance from the iframe, or None if communication fails
            """
            try:
                # Clear any previous response
                self._response_data = None
                self._waiting_for_response = True

                # Execute JavaScript to request value from iframe
                from IPython.display import Javascript, display

                js_code = (
                    f"window.requestSpytialValue_{self._widget_id.replace('-', '_')}();"
                )
                display(Javascript(js_code))

                # Wait for response with timeout
                timeout = 5.0  # 5 second timeout
                start_time = time.time()

                while (
                    self._waiting_for_response and (time.time() - start_time) < timeout
                ):
                    time.sleep(0.1)  # Check every 100ms

                if self._waiting_for_response:
                    # Timeout occurred
                    self._waiting_for_response = False
                    with self.status_output:
                        print("⚠️  Timeout requesting current value from interface")
                    return self._current_value  # Return last known value

                # Response received
                return self._response_data

            except Exception as e:
                self._waiting_for_response = False
                with self.status_output:
                    print(f"❌ Error requesting current value: {e}")
                return self._current_value  # Return last known value

        @property
        def value(self):
            """
            Get the current built dataclass instance from the interface.

            This property dynamically requests the current state from the iframe
            and converts it to a dataclass instance. The communication works as follows:

            1. Python sends postMessage to iframe requesting current form data
            2. Iframe responds with current form state as JSON
            3. Python receives response and converts to dataclass instance
            4. Returns the built dataclass instance

            Returns:
                Current dataclass instance reflecting the interface state
            """
            return self._request_current_value()

        def _repr_mimebundle_(self, **kwargs):
            """Display the widget in Jupyter."""
            return self.widget._repr_mimebundle_(**kwargs)

        def __del__(self):
            """Clean up resources."""
            # Remove from global registry
            if (
                "_spytial_widgets" in globals()
                and self._widget_id in globals()["_spytial_widgets"]
            ):
                del globals()["_spytial_widgets"][self._widget_id]

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
    Create a unified dataclass input widget that combines building and interaction.

    This function creates a streamlined widget that merges the functionality of
    dataclass building and interactive input interface into one component.

    Args:
        dataclass_type: The dataclass type to create a widget for

    Returns:
        A unified widget instance for building dataclass instances
    """
    if not IPYWIDGETS_AVAILABLE:
        raise ImportError(
            "ipywidgets is required for widgets. Install with: pip install ipywidgets"
        )

    return DataclassInputWidget(dataclass_type)


# Primary API functions that both return the same unified widget
def dataclass_widget(dataclass_type: Type) -> Any:
    """
    Create and display a unified dataclass input widget in a Jupyter notebook.

    This creates a streamlined widget that displays the build_input interface
    with real-time bidirectional communication. The widget automatically
    provides access to current form data via the 'value' property.

    Args:
        dataclass_type: The dataclass type to create input interface for

    Returns:
        Unified widget instance with real-time value access

    Example:
        @dataclass
        class Person:
            name: str = ""
            age: int = 0

        widget = spytial.dataclass_widget(Person)
        # Use the interface to build data
        # widget.value dynamically returns current dataclass instance
        person = widget.value  # Get the current built instance
    """
    return create_dataclass_widget(dataclass_type)


def dataclass_builder(dataclass_type: Type) -> Any:
    """
    Create a unified dataclass builder widget in a Jupyter notebook.

    This is an alias for dataclass_widget() that provides the same unified
    widget functionality. Both functions return the same streamlined widget
    that combines building and interaction capabilities.

    Args:
        dataclass_type: The dataclass type to create builder interface for

    Returns:
        Unified widget instance with real-time value access

    Example:
        @dataclass
        class Person:
            name: str = ""
            age: int = 0

        builder = spytial.dataclass_builder(Person)
        # Use the interface to build data
        # builder.value dynamically returns current dataclass instance
        person = builder.value  # Get the current built instance
    """
    return create_dataclass_widget(dataclass_type)

"""
sPyTial Unified Dataclass Widget

A unified system that combines dataclass building and interactive input interface.
Provides real-time communication between iframe and Jupyter via postMessage.
"""

import json
import os
import tempfile
import threading
import time
import uuid
import yaml
import webbrowser
from dataclasses import fields, is_dataclass
from typing import Any, Dict, Optional, Type, get_type_hints, Union

try:
    from ipywidgets import HTML, VBox, Button, Output, DOMWidget
    from traitlets import Unicode, observe, Dict as TraitDict
    IPYWIDGETS_AVAILABLE = True
except ImportError:
    IPYWIDGETS_AVAILABLE = False

from .annotations import collect_decorators
from .provider_system import CnDDataInstanceBuilder


# Core dataclass processing functions (moved from dataclassbuilder.py)

def json_to_dataclass(json_data: Union[str, Dict], dataclass_type: Type) -> Any:
    """
    Convert JSON data back to a dataclass instance.

    Args:
        json_data: JSON string or dictionary containing the data
        dataclass_type: The target dataclass type to create

    Returns:
        An instance of the dataclass populated with the JSON data
    """
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data

    if not is_dataclass(dataclass_type):
        raise ValueError(f"{dataclass_type} is not a dataclass.")

    # Get field information
    field_info = {f.name: f for f in fields(dataclass_type)}
    type_hints = get_type_hints(dataclass_type)

    # Build kwargs for dataclass constructor
    kwargs = {}

    for field_name, field_def in field_info.items():
        if field_name in data:
            field_value = data[field_name]
            field_type = type_hints.get(field_name, field_def.type)

            # Handle nested dataclasses
            if is_dataclass(field_type) and isinstance(field_value, dict):
                kwargs[field_name] = json_to_dataclass(field_value, field_type)
            # Handle lists of dataclasses
            elif (
                hasattr(field_type, "__origin__")
                and field_type.__origin__ is list
                and len(field_type.__args__) > 0
                and is_dataclass(field_type.__args__[0])
            ):
                nested_type = field_type.__args__[0]
                kwargs[field_name] = [
                    (
                        json_to_dataclass(item, nested_type)
                        if isinstance(item, dict)
                        else item
                    )
                    for item in field_value
                ]
            else:
                kwargs[field_name] = field_value

    return dataclass_type(**kwargs)


def load_from_json_file(json_file_path: str, dataclass_type: Type) -> Any:
    """
    Load a dataclass instance from a JSON file exported from the input builder.

    Args:
        json_file_path: Path to the JSON file containing exported data
        dataclass_type: The target dataclass type to create

    Returns:
        An instance of the dataclass populated with the file data
    """
    with open(json_file_path, "r") as f:
        json_data = json.load(f)

    return json_to_dataclass(json_data, dataclass_type)


def create_export_watcher(output_dir: str = None) -> str:
    """
    Create a directory for watching exported JSON files.

    Args:
        output_dir: Optional directory path. If None, creates a temp directory.

    Returns:
        Path to the export directory
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="spytial_exports_")
    else:
        os.makedirs(output_dir, exist_ok=True)

    return output_dir


def collect_dataclass_annotations(cls: Type) -> Dict[str, Any]:
    """
    Recursively collect spatial annotations from a dataclass and its sub-classes.
    Returns a dict representing the CnD spec structure for the dataclass schema.
    """
    if not is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass.")

    # Create a dummy instance to collect decorators
    try:
        # Try to create instance with default values
        instance = cls()
    except TypeError:
        # If default constructor fails, try to create with None values
        # for required fields
        field_defaults = {}
        for field in fields(cls):
            if field.default is not field.default_factory:
                field_defaults[field.name] = field.default
            elif field.default_factory is not field.default_factory:
                field_defaults[field.name] = field.default_factory()
            else:
                # Use None or appropriate default based on type
                field_defaults[field.name] = None
        instance = cls(**field_defaults)

    # Collect decorators from the class/instance
    annotations = collect_decorators(instance)

    # Build spec structure
    spec = {
        "dataclass_name": cls.__name__,
        "constraints": annotations["constraints"],
        "directives": annotations["directives"],
        "fields": {},
        "nested_classes": {},
    }

    # Analyze fields for nested dataclasses
    type_hints = get_type_hints(cls)
    for field in fields(cls):
        field_info = {
            "name": field.name,
            "type": str(field.type),
            "required": field.default is field.default_factory
            and field.default_factory is field.default_factory,
        }

        # Check if field type is a dataclass
        field_type = type_hints.get(field.name, field.type)
        if is_dataclass(field_type):
            nested_spec = collect_dataclass_annotations(field_type)
            spec["nested_classes"][field.name] = nested_spec
            field_info["is_dataclass"] = True
        else:
            field_info["is_dataclass"] = False

        spec["fields"][field.name] = field_info

    return spec


def generate_cnd_spec(cls: Type) -> str:
    """
    Generate a CnD spec in YAML format from the collected annotations of a dataclass.
    """
    annotations = collect_dataclass_annotations(cls)
    # Convert to YAML format suitable for CnD
    return yaml.dump(annotations, default_flow_style=False)


def create_empty_instance(cls: Type) -> Any:
    """
    Create an empty/default instance of a dataclass for initial data.
    """
    try:
        # Try to create instance with default values
        return cls()
    except TypeError:
        # If default constructor fails, create with None/default values
        field_defaults = {}
        for field in fields(cls):
            if field.default is not field.default_factory:
                field_defaults[field.name] = field.default
            elif field.default_factory is not field.default_factory:
                field_defaults[field.name] = field.default_factory()
            else:
                # Use appropriate default based on type annotation
                field_type = field.type
                if field_type == str:
                    field_defaults[field.name] = ""
                elif field_type == int:
                    field_defaults[field.name] = 0
                elif field_type == float:
                    field_defaults[field.name] = 0.0
                elif field_type == bool:
                    field_defaults[field.name] = False
                elif field_type == list:
                    field_defaults[field.name] = []
                elif field_type == dict:
                    field_defaults[field.name] = {}
                else:
                    field_defaults[field.name] = None
        return cls(**field_defaults)


def build_input(
    cls: Type,
    method: str = "file",
    auto_open: bool = True,
    width: Optional[int] = None,
    height: Optional[int] = None,
    title: Optional[str] = None,
    export_dir: Optional[str] = None,
    widget_id: Optional[str] = None,
) -> str:
    """
    Build an interactive input interface for a dataclass with spatial annotations.

    Args:
        cls: The dataclass type to build an input interface for
        method: 'file' to save HTML file, 'inline' to return HTML string
        auto_open: Whether to automatically open the HTML file in browser
        width: Optional width for the visualization
        height: Optional height for the visualization
        title: Optional title for the HTML page
        export_dir: Optional directory for JSON exports. If None, uses temp directory.
        widget_id: Optional widget identifier for communication

    Returns:
        Path to generated HTML file (if method='file') or HTML string
        (if method='inline')
    """
    if method not in ["file", "inline"]:
        raise ValueError("Method must be 'file' or 'inline'.")

    if not is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass. Use @dataclass decorator.")

    # Setup export directory
    if export_dir is None:
        export_dir = create_export_watcher()

    # Generate CnD spec from dataclass annotations
    cnd_spec = generate_cnd_spec(cls)

    # Create initial empty instance for the input interface
    initial_instance = create_empty_instance(cls)

    # Convert to CnD data instance format
    builder = CnDDataInstanceBuilder()
    initial_data = builder.build_instance(initial_instance)

    # Load the input template
    template_path = os.path.join(os.path.dirname(__file__), "input_template.html")
    with open(template_path, "r") as f:
        template = f.read()

    # Prepare template variables
    page_title = title or f"Input Builder for {cls.__name__}"

    # Replace template placeholders
    html_content = template.replace(
        '{{ title | default("sPyTial Visualization") }}', page_title
    )
    html_content = html_content.replace("{{ cnd_spec | safe }}", cnd_spec)
    html_content = html_content.replace(
        "{{ python_data | safe }}", json.dumps(initial_data)
    )
    # Add export directory information
    html_content = html_content.replace("{{ export_dir | safe }}", export_dir)
    html_content = html_content.replace("{{ dataclass_name | safe }}", cls.__name__)
    html_content = html_content.replace("{{ widget_id | default(\"\") }}", widget_id or "")

    if method == "file":
        # Generate output filename in the specified export directory if provided
        if export_dir and os.path.exists(export_dir):
            output_path = os.path.join(export_dir, f"input_builder_{cls.__name__.lower()}.html")
        else:
            output_path = f"input_builder_{cls.__name__.lower()}.html"

        # Write HTML file
        with open(output_path, "w") as f:
            f.write(html_content)

        # Auto-open in browser if requested
        if auto_open:
            webbrowser.open(f"file://{os.path.abspath(output_path)}")

        # Print instructions for retrieving data
        print(f"\n📁 Export directory: {export_dir}")
        print(f"📄 Input builder: {output_path}")
        print("\n💡 To retrieve your built dataclass:")
        print(
            f"   exported_data = spytial.load_from_json_file("
            f"'path/to/exported.json', {cls.__name__})"
        )
        print(f"   # Or monitor the export directory: {export_dir}")

        return output_path
    else:
        # Return HTML content directly
        return html_content


# Widget classes (only define if ipywidgets is available)
if IPYWIDGETS_AVAILABLE:
    from ipywidgets import HTML, Button, VBox, HBox, Text, Output

    class DataclassInputWidget:
        """
        A unified Jupyter widget that displays build_input interface in an iframe
        with simplified bidirectional communication for seamless dataclass building.

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

            self._setup_widget()

        def _setup_widget(self):
            """Setup the widget with iframe and simplified communication system."""

            # Generate HTML content using build_input
            try:
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

                # Create simplified communication handler
                # This only handles automatic data updates from the iframe
                message_handler = f"""
                <script>
                window.addEventListener('message', function(event) {{
                    try {{
                        // Handle export data from iframe (automatic updates)
                        if (event.data && event.data.type === 'spytial-export' && event.data.widgetId === '{self._widget_id}') {{
                            console.log('Received export data from iframe:', event.data);
                            
                            // Store data for access via .value property
                            window._spytial_widget_data_{self._widget_id.replace('-', '_')} = event.data.data;
                            
                            // Show update status 
                            var statusArea = document.getElementById('spytial-status-{self._widget_id}');
                            if (statusArea) {{
                                statusArea.innerHTML = '<div style="color: green; font-size: 12px; margin-top: 5px;">✅ Data updated automatically</div>';
                            }}
                        }}
                    }} catch (error) {{
                        console.error('Message handler error:', error);
                    }}
                }});
                
                // Initialize data storage
                window._spytial_widget_data_{self._widget_id.replace('-', '_')} = null;
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
                <div id="spytial-status-{self._widget_id}"></div>
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

                with self.status_output:
                    print("Widget ready - build your data in the interface above!")
                    print("💡 Use widget.value to get the current dataclass instance")

            except Exception as e:
                # Fallback to error message
                error_html = f"<p><strong>Error creating widget:</strong> {e}</p>"
                self.widget = VBox([HTML(value=error_html)])

        def update_from_json(self, json_data) -> bool:
            """
            Update the widget's internal value from JSON data.
            
            This method provides backward compatibility for tests and direct updates.
            
            Args:
                json_data: JSON string or dict containing the data
                
            Returns:
                True if update was successful, False otherwise
            """
            try:
                # Convert JSON data to dataclass instance
                instance = json_to_dataclass(json_data, self.dataclass_type)
                self._current_value = instance
                
                with self.status_output:
                    print(f"✅ Updated from JSON: {instance}")
                
                return True
            except Exception as e:
                with self.status_output:
                    print(f"❌ Error updating from JSON: {e}")
                return False

        @property
        def value(self):
            """
            Get the current built dataclass instance from the interface.

            This property accesses the data that was automatically sent from the iframe
            via postMessage when the user interacts with the form. The communication flow:

            1. User interacts with form in iframe
            2. Iframe automatically sends data via postMessage 
            3. JavaScript stores the data in window object
            4. Python accesses the stored data and converts to dataclass instance

            If no data has been received from the iframe, returns the last value
            set via update_from_json() or None.

            Returns:
                Current dataclass instance reflecting the interface state, or None if no data
            """
            try:
                # Execute JavaScript to get current data from window storage
                from IPython.display import Javascript, display
                from IPython import get_ipython

                # Get the current data from JavaScript
                js_code = f"""
                var data = window._spytial_widget_data_{self._widget_id.replace('-', '_')};
                if (data) {{
                    // Store in IPython for Python to access
                    IPython.notebook.kernel.execute("_spytial_temp_data = " + JSON.stringify(data));
                }} else {{
                    IPython.notebook.kernel.execute("_spytial_temp_data = None");
                }}
                """
                
                # Execute the JavaScript
                display(Javascript(js_code))
                
                # Give time for the JavaScript to execute
                time.sleep(0.1)
                
                # Get the data from the global namespace
                ipython = get_ipython()
                if ipython and hasattr(ipython.user_ns, '_spytial_temp_data'):
                    temp_data = ipython.user_ns.get('_spytial_temp_data')
                    if temp_data is not None:
                        # Convert JSON data to dataclass instance
                        return json_to_dataclass(temp_data, self.dataclass_type)
                
                # Fallback to stored value from update_from_json
                return self._current_value

            except Exception as e:
                with self.status_output:
                    print(f"❌ Error accessing current value: {e}")
                return self._current_value

        def _repr_mimebundle_(self, **kwargs):
            """Display the widget in Jupyter."""
            return self.widget._repr_mimebundle_(**kwargs)

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
    with simplified bidirectional communication. The widget automatically
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
        # widget.value returns current dataclass instance
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
        # builder.value returns current dataclass instance
        person = builder.value  # Get the current built instance
    """
    return create_dataclass_widget(dataclass_type)


# Legacy compatibility functions (moved from dataclassbuilder.py)

class DataclassDerelationalizer:
    """
    De-relationalizer that converts CnD relational data back to dataclass instances.
    This handles the reverse of the relationalization process.
    """
    
    def __init__(self, dataclass_type: Type):
        self.dataclass_type = dataclass_type
        self.field_info = {f.name: f for f in fields(dataclass_type)}
        self.type_hints = get_type_hints(dataclass_type)
    
    def derelationalize(self, relational_data: Dict) -> Any:
        """
        Convert relational/CnD data back to a dataclass instance.
        
        Args:
            relational_data: The relational data structure from CnD
            
        Returns:
            A dataclass instance built from the relational data
        """
        # If it's already in simple JSON format, use json_to_dataclass
        if self._is_simple_json(relational_data):
            return json_to_dataclass(relational_data, self.dataclass_type)
        
        # Otherwise, process CnD relational format
        return self._process_cnd_data(relational_data)
    
    def _is_simple_json(self, data: Dict) -> bool:
        """Check if data is in simple JSON format vs CnD relational format."""
        # Simple heuristic: if all keys match dataclass fields, it's simple JSON
        if not isinstance(data, dict):
            return False
        return all(key in self.field_info for key in data.keys())
    
    def _process_cnd_data(self, cnd_data: Dict) -> Any:
        """Process CnD relational data format."""
        # This would need to be implemented based on CnD's actual output format
        # For now, try to extract data from CnD structure
        
        if 'atoms' in cnd_data and 'relations' in cnd_data:
            # Handle CnD atoms/relations format
            return self._extract_from_atoms_relations(cnd_data)
        else:
            # Fallback to simple JSON processing
            return json_to_dataclass(cnd_data, self.dataclass_type)
    
    def _extract_from_atoms_relations(self, cnd_data: Dict) -> Any:
        """Extract dataclass instance from CnD atoms/relations structure."""
        # Implementation would depend on CnD's exact output format
        # For now, use a simplified approach
        atoms = cnd_data.get('atoms', [])
        relations = cnd_data.get('relations', [])
        
        # Try to reconstruct the original data structure
        reconstructed = {}
        
        # Extract field values from atoms
        for atom in atoms:
            if isinstance(atom, dict):
                label = atom.get('label', '')
                if label in self.field_info:
                    reconstructed[label] = atom.get('value', '')
        
        return json_to_dataclass(reconstructed, self.dataclass_type)


class InteractiveInputBuilder:
    """
    Enhanced input builder that can capture data dynamically from the web interface.
    """
    
    def __init__(self, dataclass_type: Type, export_dir: Optional[str] = None):
        self.dataclass_type = dataclass_type
        self.export_dir = export_dir or tempfile.mkdtemp(prefix="spytial_interactive_")
        self.derelationalizer = DataclassDerelationalizer(dataclass_type)
        self.captured_data = None
        self.waiting_for_input = False
        
    def build_and_wait(self, timeout: float = 300.0, **kwargs) -> Optional[Any]:
        """
        Build input interface and wait for user to export data, then return dataclass instance.
        
        Args:
            timeout: Maximum time to wait for user input (seconds)
            **kwargs: Additional arguments for build_input
            
        Returns:
            Dataclass instance created from user input, or None if timeout
        """
        # Ensure export_dir is set in kwargs
        kwargs['export_dir'] = self.export_dir
        kwargs.setdefault('auto_open', True)
        kwargs.setdefault('method', 'file')
        
        print(f"🎯 Building interactive input for {self.dataclass_type.__name__}")
        print(f"📁 Watching for exports in: {self.export_dir}")
        
        # Build the input interface
        html_file = build_input(self.dataclass_type, **kwargs)
        
        print(f"🌐 Input interface: {html_file}")
        print(f"⏱️  Waiting up to {timeout} seconds for you to build and export data...")
        print("💡 Build your data in the web interface, then click 'Export JSON'")
        
        # Start watching for exported files
        return self._wait_for_export(timeout)
    
    def _wait_for_export(self, timeout: float) -> Optional[Any]:
        """Wait for user to export data and return the dataclass instance."""
        start_time = time.time()
        os.makedirs(self.export_dir, exist_ok=True)
        
        while time.time() - start_time < timeout:
            # Check for new JSON files in export directory
            try:
                json_files = [f for f in os.listdir(self.export_dir) if f.endswith('.json')]
                
                if json_files:
                    # Use the most recent file
                    latest_file = max(json_files, key=lambda f: os.path.getctime(
                        os.path.join(self.export_dir, f)))
                    file_path = os.path.join(self.export_dir, latest_file)
                    
                    print(f"📥 Found export: {latest_file}")
                    
                    # Load and convert the data
                    with open(file_path, 'r') as f:
                        exported_data = json.load(f)
                    
                    # Convert to dataclass instance
                    instance = self.derelationalizer.derelationalize(exported_data)
                    
                    print(f"✅ Successfully created {self.dataclass_type.__name__} instance!")
                    print(f"🎉 Result: {instance}")
                    
                    return instance
                    
            except Exception as e:
                print(f"⚠️  Error checking exports: {e}")
            
            time.sleep(1.0)  # Check every second
        
        print(f"⏰ Timeout reached ({timeout}s). No data was exported.")
        return None


def build_interactive(dataclass_type: Type, timeout: float = 300.0, **kwargs) -> Optional[Any]:
    """
    Build an interactive input interface and wait for user to create data.
    
    This is the main function that provides seamless roundtrip functionality:
    1. Opens web interface for building data
    2. Waits for user to export data  
    3. Automatically converts exported JSON back to dataclass instance
    4. Returns the built dataclass instance directly
    
    Args:
        dataclass_type: The dataclass type to build
        timeout: Maximum time to wait for user input (default 5 minutes)
        **kwargs: Additional arguments for the input builder
        
    Returns:
        Dataclass instance built by the user, or None if timeout
        
    Example:
        @dataclass
        class Person:
            name: str = ""
            age: int = 0
            
        # This will open a web interface and return the built Person instance
        person = spytial.build_interactive(Person)
        if person:
            print(f"Built person: {person.name}, age {person.age}")
    """
    builder = InteractiveInputBuilder(dataclass_type)
    return builder.build_and_wait(timeout=timeout, **kwargs)


# Convenience function that works similar to spytial.diagram()
def input_builder(dataclass_type: Type, **kwargs) -> str:
    """
    Convenience function to build input interface for a dataclass.
    This mirrors the spytial.diagram() API but for input building.

    Args:
        dataclass_type: The dataclass type to create input interface for
        **kwargs: Additional arguments passed to build_input()

    Returns:
        Path to generated HTML file or HTML string
    """
    return build_input(dataclass_type, **kwargs)
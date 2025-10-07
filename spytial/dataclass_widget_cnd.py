"""
sPyTial Dataclass Builder Widget with CnD-core Integration

A Jupyter widget for building dataclass instances interactively using CnD-core's
visual structured-input-graph component. Provides real-time visual construction
with direct JavaScript-Python communication (no file I/O, no timeouts).
"""

import json
import os
import base64
import yaml
from dataclasses import dataclass, fields, is_dataclass, MISSING
from typing import Type, Any, Optional, Dict

try:
    from ipywidgets import HTML, VBox, Output
    IPYWIDGETS_AVAILABLE = True
except ImportError:
    IPYWIDGETS_AVAILABLE = False

from .provider_system import CnDDataInstanceBuilder
from .annotations import collect_decorators


def _create_empty_instance(dataclass_type: Type) -> Any:
    """Create an empty/default instance of a dataclass for initial data."""
    try:
        return dataclass_type()
    except TypeError:
        field_defaults = {}
        for field in fields(dataclass_type):
            if field.default is not MISSING:
                field_defaults[field.name] = field.default
            elif field.default_factory is not MISSING:
                field_defaults[field.name] = field.default_factory()
            else:
                # Type-appropriate defaults
                field_type = str(field.type)
                if 'str' in field_type:
                    field_defaults[field.name] = ""
                elif 'int' in field_type:
                    field_defaults[field.name] = 0
                elif 'float' in field_type:
                    field_defaults[field.name] = 0.0
                elif 'bool' in field_type:
                    field_defaults[field.name] = False
                elif 'list' in field_type.lower() or 'List' in field_type:
                    field_defaults[field.name] = []
                elif 'dict' in field_type.lower() or 'Dict' in field_type:
                    field_defaults[field.name] = {}
                else:
                    field_defaults[field.name] = None
        return dataclass_type(**field_defaults)


def _generate_cnd_spec(dataclass_type: Type) -> str:
    """Generate CnD spec in YAML format from dataclass annotations."""
    if not is_dataclass(dataclass_type):
        raise ValueError(f"{dataclass_type} is not a dataclass")
    
    # Create instance to collect decorators
    instance = _create_empty_instance(dataclass_type)
    
    # Collect CnD annotations
    annotations = collect_decorators(instance)
    
    # Build spec structure
    spec = {
        "dataclass_name": dataclass_type.__name__,
        "constraints": annotations.get("constraints", []),
        "directives": annotations.get("directives", [])
    }
    
    return yaml.dump(spec, default_flow_style=False)


def _json_to_dataclass(data: Dict, dataclass_type: Type) -> Any:
    """
    Convert JSON data to a dataclass instance with basic type coercion.
    
    Args:
        data: Dictionary containing field values
        dataclass_type: Target dataclass type
        
    Returns:
        Instance of the dataclass
    """
    if not is_dataclass(dataclass_type):
        raise ValueError(f"{dataclass_type} is not a dataclass")
    
    kwargs = {}
    for field in fields(dataclass_type):
        if field.name in data:
            value = data[field.name]
            field_type = field.type
            
            # Basic type coercion
            if field_type == int or str(field_type) == "<class 'int'>":
                kwargs[field.name] = int(value) if value != '' else 0
            elif field_type == float or str(field_type) == "<class 'float'>":
                kwargs[field.name] = float(value) if value != '' else 0.0
            elif field_type == bool or str(field_type) == "<class 'bool'>":
                kwargs[field.name] = bool(value) if isinstance(value, bool) else value == 'true'
            elif field_type == str or str(field_type) == "<class 'str'>":
                kwargs[field.name] = str(value)
            else:
                kwargs[field.name] = value
        elif field.default is not MISSING:
            kwargs[field.name] = field.default
        elif field.default_factory is not MISSING:
            kwargs[field.name] = field.default_factory()
    
    return dataclass_type(**kwargs)


if IPYWIDGETS_AVAILABLE:
    class DataclassBuilderWidget:
        """
        A widget that uses CnD-core's structured-input-graph for visual dataclass construction.
        """
        
        def __init__(self, dataclass_type: Type):
            if not is_dataclass(dataclass_type):
                raise ValueError(f"{dataclass_type} is not a dataclass")
            
            self.dataclass_type = dataclass_type
            self._current_value = None
            self._widget_id = f"spytial_{id(self)}"
            
            # Register widget globally for JavaScript access
            if '_spytial_widgets' not in globals():
                globals()['_spytial_widgets'] = {}
            globals()['_spytial_widgets'][self._widget_id] = self
            
            self._setup_widget()
        
        def _setup_widget(self):
            """Setup the CnD-core based widget."""
            # Generate CnD spec from dataclass annotations
            cnd_spec = _generate_cnd_spec(self.dataclass_type)
            
            # Create initial empty instance
            initial_instance = _create_empty_instance(self.dataclass_type)
            
            # Convert to CnD data instance format
            builder = CnDDataInstanceBuilder()
            initial_data = builder.build_instance(initial_instance)
            
            # Load HTML template
            template_path = os.path.join(os.path.dirname(__file__), "input_template.html")
            with open(template_path, "r") as f:
                template_html = f.read()
            
            # Replace template placeholders
            html_content = template_html.replace(
                '{{ title | default("sPyTial Visualization") }}',
                f"{self.dataclass_type.__name__} Builder"
            )
            html_content = html_content.replace(
                "{{ cnd_spec | safe }}", cnd_spec
            )
            html_content = html_content.replace(
                "{{ python_data | safe }}", json.dumps(initial_data)
            )
            html_content = html_content.replace(
                "{{ export_dir | safe }}", ""
            )
            html_content = html_content.replace(
                "{{ dataclass_name | safe }}", self.dataclass_type.__name__
            )
            html_content = html_content.replace(
                '{{ widget_id | default("") }}', self._widget_id
            )
            
            # Encode HTML for iframe
            html_b64 = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
            
            # Create message handler script
            message_handler = f"""
            <script>
            window.addEventListener('message', function(event) {{
                try {{
                    if (event.data && event.data.type === 'spytial-export' && 
                        event.data.widgetId === '{self._widget_id}') {{
                        console.log('Received export data:', event.data);
                        
                        // Execute Python to update widget value
                        var code = `
try:
    import json
    
    # Get widget from global registry
    widget_id = '{self._widget_id}'
    if '_spytial_widgets' in globals() and widget_id in _spytial_widgets:
        widget = _spytial_widgets[widget_id]
        data = json.loads('''` + JSON.stringify(event.data.data) + `''')
        
        # Convert to dataclass instance
        from spytial.dataclass_widget_cnd import _json_to_dataclass
        widget._current_value = _json_to_dataclass(data, widget.dataclass_type)
        
        print(f"✅ Built: {{widget._current_value}}")
    else:
        print(f"Widget {{widget_id}} not found")
except Exception as e:
    print(f"Error: {{e}}")
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
                id="{self._widget_id}"
                style="border: 1px solid #ddd; border-radius: 4px;">
            </iframe>
            """
            
            # Create widget components
            self.iframe_widget = HTML(value=iframe_html)
            self.status_output = Output()
            
            self.widget = VBox([
                HTML(f"<h3>{self.dataclass_type.__name__} Builder (CnD-core)</h3>"),
                HTML("<p>Build your data visually, then click 'Export JSON' to capture it.</p>"),
                self.iframe_widget,
                self.status_output
            ])
            
            with self.status_output:
                print(f"✨ Widget ready! Build your {self.dataclass_type.__name__} and export to capture.")
        
        @property
        def value(self):
            """Get the current built dataclass instance."""
            return self._current_value
        
        def _repr_mimebundle_(self, **kwargs):
            """Display in Jupyter."""
            return self.widget._repr_mimebundle_(**kwargs)
        
        def __del__(self):
            """Cleanup."""
            if '_spytial_widgets' in globals() and self._widget_id in globals()['_spytial_widgets']:
                del globals()['_spytial_widgets'][self._widget_id]

else:
    class DataclassBuilderWidget:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "ipywidgets is required. Install with: pip install ipywidgets"
            )


def dataclass_builder(dataclass_type: Type):
    """
    Create a CnD-core based visual builder widget for a dataclass.
    
    Args:
        dataclass_type: The dataclass type to build instances for
        
    Returns:
        Widget instance with visual construction interface
        
    Example:
        @dataclass
        class Person:
            name: str = ""
            age: int = 0
            
        widget = spytial.dataclass_builder(Person)
        # Build visually in the widget, then:
        person = widget.value  # Get the built instance
    """
    return DataclassBuilderWidget(dataclass_type)

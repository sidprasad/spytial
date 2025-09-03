import os
import json
import yaml
import webbrowser
from dataclasses import fields, is_dataclass
from typing import Any, Dict, List
from .annotations import get_annotations  # Assuming this exists in annotations.py to retrieve spatial annotations
from .provider_system import CnDDataInstanceBuilder  # For building initial data instances if needed

def collect_annotations(cls: Any) -> Dict[str, Any]:
    """
    Recursively collect spatial annotations from a dataclass and its sub-classes.
    Returns a dict representing the CnD spec structure.
    """
    spec = {}
    if not is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass.")
    
    # Collect annotations for the current class
    spec[cls.__name__] = get_annotations(cls)  # Custom function to extract decorators like @orientation, @group
    
    # Recurse into fields that are dataclasses
    for field in fields(cls):
        if is_dataclass(field.type):
            spec.update(collect_annotations(field.type))
    
    return spec

def generate_cnd_spec(cls: Any) -> str:
    """
    Generate a CnD spec in YAML format from the collected annotations.
    """
    annotations = collect_annotations(cls)
    # Convert to YAML (simplified; extend based on CnD format)
    return yaml.dump(annotations, default_flow_style=False)

def build_input(cls: Any, method: str = 'file', auto_open: bool = True, width: int = None, height: int = None) -> str:
    """
    Build an input interface for the given dataclass.
    - Collects annotations into a CnD spec.
    - Generates HTML using the input template.
    - Opens the HTML file if auto_open is True.
    Returns the path to the generated HTML file.
    """
    if method not in ['file', 'inline']:
        raise ValueError("Method must be 'file' or 'inline'.")
    
    # Generate CnD spec
    cnd_spec = generate_cnd_spec(cls)
    
    # Prepare initial data (empty instance for input)
    builder = CnDDataInstanceBuilder()
    initial_data = builder.build_instance(cls())  # Assumes cls() creates an empty instance
    
    # Load and populate the input template
    template_path = os.path.join(os.path.dirname(__file__), 'input_template.html')
    with open(template_path, 'r') as f:
        template = f.read()
    
    # Replace placeholders (similar to Jinja2 but simplified)
    html_content = template.replace('{{ title | default("sPyTial Visualization") }}', f"Input for {cls.__name__}")
    html_content = html_content.replace('{{ cnd_spec | safe }}', cnd_spec)
    html_content = html_content.replace('{{ python_data | safe }}', json.dumps(initial_data))
    
    if method == 'file':
        output_path = f"input_{cls.__name__.lower()}.html"
        with open(output_path, 'w') as f:
            f.write(html_content)
        if auto_open:
            webbrowser.open(f"file://{os.path.abspath(output_path)}")
        return output_path
    else:
        # For 'inline', return the HTML string (not opening)
        return html_content

# Example usage (for testing):
# from your_dataclass_module import YourDataclass
# build_input(YourDataclass, method='file', auto_open=True)
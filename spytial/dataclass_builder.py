"""
sPyTial Dataclass Builder with CnD-core Integration

A simple function for building dataclass instances interactively using CnD-core's
visual structured-input-graph component. Generates Python constructor code that
you can copy and paste.
"""

import json
import os
import base64
import yaml
from dataclasses import dataclass, fields, is_dataclass, MISSING
from typing import Type, Any, Optional, Dict

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
        #"dataclass_name": dataclass_type.__name__,
        "constraints": annotations.get("constraints", []),
        "directives": annotations.get("directives", [])
    }
    
    return yaml.dump(spec, default_flow_style=False)


def _json_to_dataclass(data: Dict, dataclass_type: Type) -> Any:
    """
    Convert JSON data to a dataclass instance with basic type coercion.
    
    Args:
        data: Dictionary containing field values (can be flat dict or CnD format)
        dataclass_type: Target dataclass type
        
    Returns:
        Instance of the dataclass
    """
    if not is_dataclass(dataclass_type):
        raise ValueError(f"{dataclass_type} is not a dataclass")
    
    # If data is in CnD format (has atoms/relations), extract the field values
    if isinstance(data, dict) and 'atoms' in data and 'relations' in data:
        # Convert CnD relational format to flat dict
        data = _cnd_to_flat_dict(data, dataclass_type)
    
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


def _cnd_to_flat_dict(cnd_data: Dict, dataclass_type: Type) -> Dict:
    """
    Convert CnD relational format back to a flat dictionary.
    
    CnD format has:
    - atoms: list of {id, label, type, ...}
    - relations: list of {id, source, target, label, ...}
    
    We need to extract field values from atoms and relations.
    """
    result = {}
    
    # Get dataclass field names
    field_names = {f.name for f in fields(dataclass_type)}
    
    # Extract from atoms - look for atoms with labels matching field names
    if 'atoms' in cnd_data:
        for atom in cnd_data['atoms']:
            if isinstance(atom, dict):
                label = atom.get('label', '')
                # Check if label contains a field name (format might be "field:value" or just field name)
                for field_name in field_names:
                    if field_name in label or label == field_name:
                        # Try to get value from atom
                        if 'value' in atom:
                            result[field_name] = atom['value']
                        # Or from label itself if it has the format "field:value"
                        elif ':' in label:
                            parts = label.split(':', 1)
                            if parts[0] == field_name:
                                result[field_name] = parts[1]
    
    # Extract from relations - look for field-value pairs
    if 'relations' in cnd_data:
        for relation in cnd_data['relations']:
            if isinstance(relation, dict):
                label = relation.get('label', '')
                # Check if this is a field relation
                for field_name in field_names:
                    if label == field_name or field_name in label:
                        # Get target atom value
                        target_id = relation.get('target')
                        if target_id and 'atoms' in cnd_data:
                            for atom in cnd_data['atoms']:
                                if atom.get('id') == target_id:
                                    if 'value' in atom:
                                        result[field_name] = atom['value']
                                    elif 'label' in atom:
                                        result[field_name] = atom['label']
    
    return result


def dataclass_builder(dataclass_type: Type, method: str = 'browser', auto_open: bool = True):
    """
    Create a visual builder interface for a dataclass using CnD-core.
    
    Opens an HTML interface where you can build instances visually.
    Click "Export" to get Python constructor code to copy/paste.
    
    Args:
        dataclass_type: The dataclass type to build instances for
        method: 'browser' to open in browser, 'file' to save HTML file, 'inline' for notebook
        auto_open: Whether to automatically open the result (for 'browser' and 'file' methods)
        
    Returns:
        str: Path to the generated HTML file (for 'file' method)
        
    Example:
        @dataclass
        class TreeNode:
            value: int = 0
            left: Optional['TreeNode'] = None
            right: Optional['TreeNode'] = None
            
        # Open builder in browser
        spytial.dataclass_builder(TreeNode)
        
        # Build your tree visually, click Export, copy the Python code
        # Then paste: result = TreeNode(value=42, left=TreeNode(value=21, ...))
    """
    if not is_dataclass(dataclass_type):
        raise ValueError(f"{dataclass_type} is not a dataclass")
    
    # Generate CnD spec from dataclass annotations
    cnd_spec = _generate_cnd_spec(dataclass_type)
    
    # Create initial empty instance
    initial_instance = _create_empty_instance(dataclass_type)
    
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
        f"{dataclass_type.__name__} Builder"
    )
    html_content = html_content.replace(
        "{{ cnd_spec | safe }}", cnd_spec
    )
    html_content = html_content.replace(
        "{{ python_data | safe }}", json.dumps(initial_data)
    )
    html_content = html_content.replace(
        "{{ dataclass_name | safe }}", dataclass_type.__name__
    )
    html_content = html_content.replace(
        '{{ widget_id | default("") }}', f"builder_{id(dataclass_type)}"
    )
    
    # Handle different output methods
    if method == 'file':
        # Save to file
        output_file = "dataclass_builder.html"
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        if auto_open:
            import webbrowser
            webbrowser.open(f'file://{os.path.abspath(output_file)}')
        
        return output_file
    
    elif method == 'browser':
        # Save to temp file and open in browser
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_path = f.name
        
        if auto_open:
            import webbrowser
            webbrowser.open(f'file://{temp_path}')
        
        return temp_path
    
    elif method == 'inline':
        # For Jupyter notebooks - return an HTML widget
        try:
            from IPython.display import HTML as IPythonHTML
            return IPythonHTML(html_content)
        except ImportError:
            print("IPython not available. Use method='browser' or 'file' instead.")
            return None
    
    else:
        raise ValueError(f"Unknown method: {method}. Use 'browser', 'file', or 'inline'.")

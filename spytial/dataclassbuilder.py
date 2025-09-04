import os
import json
import yaml
import webbrowser
from dataclasses import fields, is_dataclass
from typing import Any, Dict, Optional, Type, get_type_hints
from .annotations import collect_decorators
from .provider_system import CnDDataInstanceBuilder


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

    Returns:
        Path to generated HTML file (if method='file') or HTML string
        (if method='inline')
    """
    if method not in ["file", "inline"]:
        raise ValueError("Method must be 'file' or 'inline'.")

    if not is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass. Use @dataclass decorator.")

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

    if method == "file":
        # Generate output filename
        output_path = f"input_builder_{cls.__name__.lower()}.html"

        # Write HTML file
        with open(output_path, "w") as f:
            f.write(html_content)

        # Auto-open in browser if requested
        if auto_open:
            webbrowser.open(f"file://{os.path.abspath(output_path)}")

        return output_path
    else:
        # Return HTML content directly
        return html_content


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

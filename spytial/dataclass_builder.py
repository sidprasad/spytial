"""
sPyTial Dataclass Builder with spytial-core Integration

A simple function for building dataclass instances interactively using spytial-core's
visual structured-input-graph component. Generates Python constructor code that
you can copy and paste.
"""

import json
import os
import yaml
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from IPython.display import HTML as IPythonHTML

from .provider_system import CnDDataInstanceBuilder
from .annotations import collect_decorators
from .core_assets import get_template_asset_context

try:
    from jinja2 import Environment, FileSystemLoader

    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


def _generate_cnd_spec(instance: Any) -> str:
    """Generate Spytial-Core spec in YAML format from dataclass instance annotations."""
    if not is_dataclass(instance):
        raise ValueError(f"{instance} is not a dataclass instance")

    # Collect Spytial-Core annotations directly from the instance
    annotations = collect_decorators(instance)

    # Build spec structure
    spec = {
        "constraints": annotations.get("constraints", []),
        "directives": annotations.get("directives", []),
    }

    return yaml.dump(spec, default_flow_style=False)


def dataclass_builder(
    instance: Any, method: str = "inline", auto_open: bool = True
) -> Optional[Union[str, "IPythonHTML"]]:
    """
    Create a visual builder interface for a dataclass instance using spytial-core.

    Opens an HTML interface where you can build/modify instances visually.
    Click "Export" to get Python constructor code to copy/paste.

    Args:
        instance: A dataclass instance to start with (can be empty or pre-populated)
        method: 'browser' to open in browser, 'file' to save HTML file, 'inline' for notebook
        auto_open: Whether to automatically open the result (for 'browser' and 'file' methods)

    Returns:
        str: Path to the generated HTML file (for 'file' and 'browser' methods)
        IPython.HTML: HTML widget for inline display ('inline' method)

    Example:
        @dataclass
        class TreeNode:
            value: int = 0
            left: Optional['TreeNode'] = None
            right: Optional['TreeNode'] = None

        # Start with empty instance
        spytial.dataclass_builder(TreeNode())

        # Or start with pre-populated data
        initial_tree = TreeNode(value=42, left=TreeNode(value=21))
        spytial.dataclass_builder(initial_tree)

        # Build your tree visually, click Export, copy the Python code
        # Then paste: result = TreeNode(value=42, left=TreeNode(value=21, ...))
    """
    if not is_dataclass(instance):
        raise ValueError(
            f"{instance} is not a dataclass instance. Pass an instance like: dataclass_builder(MyClass())"
        )

    # Get the dataclass type from the instance
    dataclass_type = type(instance)

    # Generate Spytial-Core spec from the instance's annotations
    cnd_spec = _generate_cnd_spec(instance)

    # Convert to Spytial-Core data instance format (using the provided instance)
    builder = CnDDataInstanceBuilder()
    initial_data = builder.build_instance(instance)

    html_content = _generate_dataclass_builder_html(
        initial_data=initial_data,
        cnd_spec=cnd_spec,
        dataclass_name=dataclass_type.__name__,
    )

    # Handle different output methods
    if method == "file":
        # Save to file
        output_file = "dataclass_builder.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        if auto_open:
            import webbrowser

            webbrowser.open(f"file://{os.path.abspath(output_file)}")

        return output_file

    elif method == "browser":
        # Save to temp file and open in browser
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(html_content)
            temp_path = f.name

        if auto_open:
            import webbrowser

            webbrowser.open(f"file://{temp_path}")

        return temp_path

    elif method == "inline":
        # For Jupyter notebooks - return an HTML widget
        try:
            from IPython.display import HTML as IPythonHTML

            return IPythonHTML(html_content)
        except ImportError:
            print("IPython not available. Use method='browser' or 'file' instead.")
            return None

    else:
        raise ValueError(
            f"Unknown method: {method}. Use 'browser', 'file', or 'inline'."
        )


def _generate_dataclass_builder_html(initial_data, cnd_spec, dataclass_name):
    """Generate HTML for the interactive dataclass builder."""

    if not HAS_JINJA2:
        raise ImportError(
            "Jinja2 is required for HTML generation. Install with: pip install jinja2"
        )

    current_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(current_dir))

    try:
        template = env.get_template("input_template.html")
    except Exception as e:
        raise FileNotFoundError(f"input_template.html not found in {current_dir}: {e}")

    return template.render(
        python_data=json.dumps(initial_data),
        cnd_spec=cnd_spec,
        dataclass_name=dataclass_name,
        title=f"{dataclass_name} Builder",
        **get_template_asset_context(),
    )

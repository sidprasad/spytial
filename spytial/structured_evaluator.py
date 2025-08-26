"""
sPyTial Structured Input Evaluator Module

This module provides an enhanced evaluator interface for structured input,
allowing users to interactively build data structures with templates and holes.
"""

import json
import tempfile
import webbrowser
from pathlib import Path
import os

try:
    from IPython.display import display, HTML

    HAS_IPYTHON = True
except ImportError:
    HAS_IPYTHON = False

try:
    from jinja2 import Environment, FileSystemLoader

    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


def structured_input(
    initial_data=None,
    method="inline",
    auto_open=True,
    width=None,
    height=None,
    cnd_version=None,
):
    """
    Launch a structured input interface for building data interactively.

    Args:
        initial_data: Optional initial data to start with
        method: Display method - "inline" (Jupyter), "browser" (new tab), or "file" (save to file)
        auto_open: Whether to automatically open browser (for "browser" method)
        width: Width of the interface container in pixels (default: auto-detected)
        height: Height of the interface container in pixels (default: auto-detected)
        cnd_version: Version of the cnd-core library to use

    Returns:
        str: Path to the generated HTML file (if method="file" or "browser")
    """
    # Auto-detect sizing if not provided
    if width is None or height is None:
        width, height = 1200, 800  # Larger default for structured input interface

    # Prepare initial data
    if initial_data is None:
        initial_data = {"message": "Welcome to structured input!"}

    # Serialize the initial data using the provider system
    from .provider_system import CnDDataInstanceBuilder

    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(initial_data)

    # Generate the HTML content
    html_content = _generate_structured_input_html(
        data_instance, width, height, cnd_version
    )

    if method == "inline":
        # Display inline in Jupyter notebook using iframe
        if HAS_IPYTHON:
            try:
                import base64

                # Encode HTML as base64 for iframe
                encoded_html = base64.b64encode(html_content.encode("utf-8")).decode(
                    "utf-8"
                )

                # Create iframe HTML
                iframe_html = f"""
                <div style="border: 2px solid #007acc; border-radius: 8px; overflow: hidden;">
                    <iframe 
                        src="data:text/html;base64,{encoded_html}" 
                        width="100%" 
                        height="{height}px" 
                        frameborder="0"
                        style="display: block;">
                    </iframe>
                </div>
                """

                display(HTML(iframe_html))
                return

            except Exception as e:
                print(f"Iframe display failed: {e}")
                # Fall back to browser if iframe fails
                return structured_input(
                    initial_data,
                    method="browser",
                    auto_open=auto_open,
                    width=width,
                    height=height,
                )

        # Fall back to browser if not in Jupyter
        return structured_input(
            initial_data,
            method="browser",
            auto_open=auto_open,
            width=width,
            height=height,
        )

    elif method == "browser":
        # Open in browser
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(html_content)
            temp_path = f.name

        if auto_open:
            webbrowser.open(f"file://{temp_path}")

        return temp_path

    elif method == "file":
        # Save to file
        output_path = Path("structured_input.html")
        with open(output_path, "w") as f:
            f.write(html_content)

        print(f"Structured input interface saved to: {output_path.absolute()}")
        return str(output_path.absolute())

    else:
        raise ValueError(f"Unknown display method: {method}")


def _generate_structured_input_html(
    data_instance, width=1200, height=800, cnd_version="1.1.9"
):
    """
    Generate HTML content for the structured input interface using Jinja2 templating.

    Args:
        data_instance: The serialized data instance
        width: Width of the interface container in pixels
        height: Height of the interface container in pixels
        cnd_version: Version of the cnd-core library to use

    Returns:
        str: The generated HTML content
    """
    if not HAS_JINJA2:
        raise ImportError(
            "Jinja2 is required for HTML generation. Install with: pip install jinja2"
        )

    # Set up Jinja2 environment
    current_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(current_dir))

    try:
        template = env.get_template("structured_evaluator_template.html")
    except Exception as e:
        raise FileNotFoundError(
            f"structured_evaluator_template.html not found in {current_dir}: {e}"
        )

    # Render the template with our data
    html_content = template.render(
        python_data=json.dumps(data_instance),  # Properly serialize to JSON
        width=width,  # Container width
        height=height,  # Container height
        cnd_version=cnd_version,  # Cope and Drag version
    )

    return html_content

"""
sPyTial Evaluator Module

This module provides functions to evaluate expressions using the sPyTial evaluator.
"""

import json
import tempfile
import webbrowser
from pathlib import Path
import os
from typing import Any, Optional

from .utils import is_notebook, default_method

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


def evaluate(
    obj: Any,
    method: Optional[str] = None,
    auto_open: bool = True,
    width: Optional[int] = None,
    height: Optional[int] = None,
    as_type: Optional[Any] = None,
) -> Optional[str]:
    """
    Evaluate a Python object using the sPyTial evaluator.

    Args:
        obj: Any Python object to evaluate.
        method: Display method - "inline" (Jupyter), "browser" (new tab), or "file" (save to file).
                If None (default), automatically selects "inline" in notebooks or "browser" otherwise.
        auto_open: Whether to automatically open the browser (for "browser" method).
        width: Width of the evaluation container in pixels (default: auto-detected).
        height: Height of the evaluation container in pixels (default: auto-detected).
        as_type: Optional annotated type to treat the object as. Annotations from this type
                 will be applied in addition to any introspected from the object itself.

    Returns:
        str: Path to the generated HTML file (if method="file" or "browser").
    """
    # Handle AnnotatedType - extract the underlying Annotated type
    from .utils import AnnotatedType

    if isinstance(as_type, AnnotatedType):
        as_type = as_type._annotated

    # Auto-detect method based on environment if not specified
    if method is None:
        method = default_method()

    # Auto-detect sizing if not provided
    if width is None or height is None:
        width, height = 600, 200

    # Serialize the object using the provider system
    from .provider_system import CnDDataInstanceBuilder

    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(obj, as_type=as_type)

    # Generate the HTML content
    html_content = _generate_evaluator_html(data_instance, width, height)

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
                return evaluate(
                    obj,
                    method="browser",
                    auto_open=auto_open,
                    width=width,
                    height=height,
                )

        # Fall back to browser if not in Jupyter
        return evaluate(
            obj, method="browser", auto_open=auto_open, width=width, height=height
        )

    elif method == "browser":
        # Open in browser
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html_content)
            temp_path = f.name

        if auto_open:
            webbrowser.open(f"file://{temp_path}")

        return temp_path

    elif method == "file":
        # Save to file
        output_path = Path("cnd_evaluator.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"Evaluator saved to: {output_path.absolute()}")
        return str(output_path.absolute())

    else:
        raise ValueError(f"Unknown display method: {method}")


def _generate_evaluator_html(data_instance, width=800, height=600):
    """
    Generate HTML content for the evaluator using Jinja2 templating.

    Args:
        data_instance: The serialized data instance to evaluate.
        width: Width of the evaluation container in pixels.
        height: Height of the evaluation container in pixels.

    Returns:
        str: The generated HTML content.
    """
    if not HAS_JINJA2:
        raise ImportError(
            "Jinja2 is required for HTML generation. Install with: pip install jinja2"
        )

    # Set up Jinja2 environment
    current_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(current_dir))

    try:
        template = env.get_template("evaluator_template.html")
    except Exception as e:
        raise FileNotFoundError(
            f"evaluator_template.html not found in {current_dir}: {e}"
        )

    # Render the template with our data
    html_content = template.render(
        python_data=json.dumps(data_instance),  # Properly serialize to JSON
        width=width,  # Container width
        height=height,  # Container height
    )

    return html_content

"""
sPyTial Visualization Display Module

This module provides functions to display Python objects using the sPyTial visualizer.
"""

import json
import tempfile
import webbrowser
from pathlib import Path
import os
from typing import Any, Dict, Optional, Union

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


def diagram(
    obj: Any,
    method: Optional[str] = None,
    auto_open: bool = True,
    width: Optional[int] = None,
    height: Optional[int] = None,
    title: Optional[str] = None,
    perf_path: Optional[Union[str, Path]] = None,
    perf_iterations: Optional[int] = None,
    headless: bool = False,
    timeout: Optional[float] = None,
    as_type: Optional[Any] = None,
) -> Optional[Union[str, Dict[str, Any]]]:
    """
    Display a Python object in the sPyTial visualizer.

    Args:
        obj: Any Python object to visualize.
        method: Display method - "inline" (Jupyter), "browser" (new tab), "file" (save to file), or "headless" (headless browser for testing)
                If None (default), automatically selects "inline" in notebooks or "browser" otherwise.
        auto_open: Whether to automatically open browser (for "browser" method)
        width: Width of the visualization container in pixels (default: auto-detected)
        height: Height of the visualization container in pixels (default: auto-detected)
        title: Title for the browser tab/page (default: "sPyTial Visualization")
        perf_path: Optional path to save performance metrics JSON file.
                   If None, metrics are not saved (unless perf_iterations is set).
        perf_iterations: Optional number of times to render for performance benchmarking.
                        If provided, the visualization will be rendered N times and metrics
                        will be aggregated. Works with method="browser", "file", or "headless".
        headless: Run in headless Chrome for testing/benchmarking (requires selenium and chromedriver).
                  If True, method is automatically set to "headless".
        timeout: Timeout in seconds for headless mode. If None, automatically calculated based on
                 perf_iterations (default: max(120, perf_iterations * 5)). For large/complex
                 visualizations, set this higher (e.g., timeout=600 for 10 minutes).
        as_type: Optional annotated type to treat the object as. Annotations from this type
                 will be applied in addition to any introspected from the object itself.
                 Use AnnotatedType() or typing.Annotated to define types with spytial annotations.

    Examples:
        # Define an annotated type
        Graph = AnnotatedType(Dict[int, List[int]], InferredEdge(...), Orientation(...))

        # Display a dict as a Graph
        g = {0: [1], 1: [2]}
        diagram(g, as_type=Graph)

    Returns:
        str: Path to the generated HTML file (if method="file", "browser", or "headless")
        dict: Performance metrics (if method="headless" and perf_iterations > 0)
    """
    # Handle AnnotatedType - extract the underlying Annotated type
    from .utils import AnnotatedType

    if isinstance(as_type, AnnotatedType):
        as_type = as_type._annotated

    # Override method if headless flag is set
    if headless:
        method = "headless"

    # Auto-detect method based on environment if not specified
    if method is None:
        method = default_method()

    # Auto-detect sizing if not provided
    if width is None or height is None:
        detected_width, detected_height = _detect_optimal_size(obj, method)
        width = width or detected_width
        height = height or detected_height
    from .provider_system import CnDDataInstanceBuilder
    from .annotations import (
        serialize_to_yaml_string,
        extract_spytial_annotations,
    )

    # Serialize the object using the provider system (which now also collects decorators)
    if headless and title:
        print(f"Building data instance for: {title}", flush=True)
    builder = CnDDataInstanceBuilder()

    # Pass as_type to the builder so it can extract annotations
    data_instance = builder.build_instance(obj, as_type=as_type)

    # Get all decorators collected during the build process (from all sub-objects)
    decorators = builder.get_collected_decorators()

    # Serialize the collected decorators into a YAML string
    spytial_spec = serialize_to_yaml_string(decorators)

    if headless and title:
        print(f"Generating HTML for: {title}", flush=True)
    # Generate the HTML content
    html_content = _generate_visualizer_html(
        data_instance,
        spytial_spec,
        width,
        height,
        title,
        perf_path,
        perf_iterations,
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
                return diagram(
                    obj,
                    method="browser",
                    auto_open=auto_open,
                    width=width,
                    height=height,
                )

        # Fall back to browser if not in Jupyter
        return diagram(
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
        output_path = Path("spytial_visualization.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"Visualization saved to: {output_path.absolute()}")
        return str(output_path.absolute())

    elif method == "headless":
        # Run in headless browser for testing/benchmarking
        return _run_headless(html_content, perf_path, perf_iterations, timeout, title)

    else:
        raise ValueError(f"Unknown display method: {method}")


def _detect_optimal_size(obj, method):
    """
    Detect optimal sizing based on object complexity and display method.

    Args:
        obj: The object being visualized
        method: The display method ("inline", "browser", "file")

    Returns:
        tuple: (width, height) in pixels
    """
    # Default base sizes
    base_width = 800
    base_height = 600

    # For inline (Jupyter) method, use more conservative sizing
    if method == "inline":
        # Try to detect if we're in a Jupyter environment for better sizing
        try:
            if HAS_IPYTHON:
                from IPython import get_ipython

                ipython = get_ipython()
                if ipython is not None:
                    # We're in Jupyter - use a size that fits well in notebook cells
                    # Most Jupyter cells work well with slightly smaller default sizes
                    base_width = 750
                    base_height = 500
        except:
            # Fall back to conservative sizing for inline display
            base_width = 750
            base_height = 500

    # Analyze object complexity to adjust sizing
    try:
        # Simple heuristic: count attributes and nested objects
        complexity_score = _estimate_object_complexity(obj)

        # Adjust size based on complexity
        if complexity_score > 50:  # High complexity
            width_multiplier = 1.3
            height_multiplier = 1.2
        elif complexity_score > 20:  # Medium complexity
            width_multiplier = 1.1
            height_multiplier = 1.1
        else:  # Low complexity
            width_multiplier = 0.9
            height_multiplier = 0.9

        width = int(base_width * width_multiplier)
        height = int(base_height * height_multiplier)

        # Ensure minimum and maximum bounds
        width = max(400, min(width, 1600))
        height = max(300, min(height, 1200))

    except:
        # Fall back to base sizes if complexity analysis fails
        width = base_width
        height = base_height

    return width, height


def _estimate_object_complexity(obj):
    """
    Estimate the complexity of an object for sizing purposes.

    Args:
        obj: The object to analyze

    Returns:
        int: Complexity score (higher = more complex)
    """
    try:
        complexity = 0

        # Count attributes
        if hasattr(obj, "__dict__"):
            complexity += len(obj.__dict__)

        # Count list/tuple elements
        if isinstance(obj, (list, tuple)):
            complexity += len(obj)
            # Add nested complexity for first few items
            for i, item in enumerate(obj[:5]):
                if hasattr(item, "__dict__"):
                    complexity += len(item.__dict__) * 0.5

        # Count dict keys
        if isinstance(obj, dict):
            complexity += len(obj)
            # Add nested complexity for values
            for value in list(obj.values())[:5]:
                if hasattr(value, "__dict__"):
                    complexity += len(value.__dict__) * 0.5

        return int(complexity)
    except:
        return 10  # Default medium complexity


def _generate_visualizer_html(
    data_instance,
    spytial_spec,
    width=800,
    height=600,
    title=None,
    perf_path=None,
    perf_iterations=None,
):
    """Generate HTML content using Jinja2 templating."""

    if not HAS_JINJA2:
        raise ImportError(
            "Jinja2 is required for HTML generation. Install with: pip install jinja2"
        )

    # Set up Jinja2 environment
    current_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(current_dir))

    # And error handling in react components COULD go here, depending on What we want to include?
    # Like, mount stuff if needed?
    ## Error viz, Spytial-Core Builder, etc.

    try:
        template = env.get_template("visualizer_template.html")
    except Exception as e:
        raise FileNotFoundError(
            f"visualizer_template.html not found in {current_dir}: {e}"
        )

    # Render the template with our data
    html_content = template.render(
        python_data=json.dumps(data_instance),  # Properly serialize to JSON
        cnd_spec=spytial_spec,  # Embed the sPyTial specification
        title=title,  # Page title for browser tab
        width=width,  # Container width
        height=height,  # Container height
        perf_path=perf_path
        or "",  # Performance metrics endpoint path (empty string if None)
        perf_iterations=perf_iterations
        or 0,  # Number of iterations for benchmarking (0 = disabled)
    )

    return html_content


def _run_headless(
    html_content, perf_path=None, perf_iterations=None, timeout=None, title=None
):
    """
    Run visualization in headless Chrome for testing/benchmarking.

    Args:
        html_content: The HTML content to render
        perf_path: Path to save performance metrics
        perf_iterations: Number of iterations to run
        timeout: Custom timeout in seconds. If None, calculated as max(120, perf_iterations * 5)
        title: Title of the visualization (for display in progress messages)

    Returns:
        dict: Performance metrics if perf_iterations > 0, otherwise path to temp file
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        raise ImportError(
            "Headless mode requires selenium. Install with: pip install selenium webdriver-manager"
        )

    try:
        from webdriver_manager.chrome import ChromeDriverManager

        use_webdriver_manager = True
    except ImportError:
        use_webdriver_manager = False

    # Create temporary HTML file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_content)
        temp_path = f.name

    # Configure Chrome options for headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Use new headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # Increase memory for performance testing and enable explicit GC
    chrome_options.add_argument("--js-flags=--max-old-space-size=4096 --expose-gc")

    # Calculate the timeout to use for HTTP client
    http_timeout = timeout if timeout else 300

    driver = None
    try:
        # Initialize Chrome driver with custom HTTP timeout
        if use_webdriver_manager:
            # Automatically download and manage chromedriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Try to use system chromedriver
            driver = webdriver.Chrome(options=chrome_options)

        # Set the RemoteConnection timeout (this is the 120s timeout we're hitting)
        driver.command_executor._client_config.timeout = http_timeout

        # Set longer page load timeout for complex visualizations
        # Use the custom timeout if provided, otherwise use 300s default
        page_load_timeout = http_timeout
        driver.set_page_load_timeout(page_load_timeout)
        driver.set_script_timeout(page_load_timeout)

        if title:
            print(
                f"Loading page for {title} (timeout: {page_load_timeout}s)...",
                flush=True,
            )

        # Load the HTML file
        try:
            driver.get(f"file://{temp_path}")
        except Exception as load_error:
            if (
                "tab crashed" in str(load_error).lower()
                or "crash" in str(load_error).lower()
            ):
                print(
                    f"✗ Chrome tab crashed - visualization too large/complex",
                    flush=True,
                )
                print(
                    f"  Consider: reducing perf_iterations, simplifying data, or using method='browser'",
                    flush=True,
                )
            raise

        # Wait for the page to load and rendering to complete
        # For performance testing, wait for the download to trigger
        if perf_iterations and perf_iterations > 0:
            # Calculate timeout - use custom timeout if provided, otherwise auto-calculate
            if timeout is None:
                # Use 5 seconds per iteration as base, with minimum of 120 seconds
                # Complex visualizations can take much longer than simple ones
                wait_time = max(120, perf_iterations * 5)
            else:
                wait_time = timeout

            # Display title if provided
            title_str = f" - {title}" if title else ""
            print(
                f"Running {perf_iterations} iterations{title_str} (timeout: {wait_time}s)...",
                flush=True,
            )
            if timeout is not None:
                print(f"  Using custom timeout of {timeout}s", flush=True)

            # Monitor progress with periodic polling
            import time

            start_time = time.time()
            last_count = 0
            completed = False

            # Poll for progress updates
            try:
                poll_count = 0
                while time.time() - start_time < wait_time:
                    poll_count += 1
                    try:
                        metrics = driver.execute_script(
                            "return window.performanceMetrics;"
                        )
                        if metrics and "iterations" in metrics:
                            current_count = metrics["iterations"]
                            if current_count > last_count:
                                elapsed = time.time() - start_time
                                print(
                                    f"  Progress: {current_count}/{perf_iterations} iterations ({elapsed:.1f}s elapsed)",
                                    flush=True,
                                )
                                last_count = current_count

                            # Check if benchmark is complete (completed flag set after metrics saved)
                            if metrics.get("completed", False):
                                completed = True
                                break
                        else:
                            # Debug: print when we can't get metrics
                            if poll_count % 6 == 0:  # Every minute (6 * 10s)
                                elapsed = time.time() - start_time
                                print(
                                    f"  Waiting for metrics... ({elapsed:.1f}s elapsed, poll #{poll_count})",
                                    flush=True,
                                )
                    except Exception as poll_error:
                        if poll_count % 6 == 0:
                            print(f"  Poll error: {poll_error}", flush=True)

                    # Sleep before next poll
                    time.sleep(10)  # Poll every 10 seconds

                if not completed:
                    elapsed = time.time() - start_time
                    print(
                        f"Warning: Timeout after {elapsed:.1f}s - completed {last_count}/{perf_iterations} iterations"
                    )

            except Exception as e:
                elapsed = time.time() - start_time
                print(f"Warning: Error after {elapsed:.1f}s waiting for metrics: {e}")
                import traceback

                traceback.print_exc()

            # Try to get performance metrics from the page
            try:
                metrics = driver.execute_script("return window.performanceMetrics;")
                if metrics:
                    print(
                        f"✓ Headless benchmark completed: {perf_iterations} iterations"
                    )
                    print(
                        f"  Generate Layout: {metrics.get('generateLayout', {}).get('avg', 0):.2f}ms avg"
                    )
                    print(
                        f"  Render Layout: {metrics.get('renderLayout', {}).get('avg', 0):.2f}ms avg"
                    )
                    print(
                        f"  Total Time: {metrics.get('totalTime', {}).get('avg', 0):.2f}ms avg"
                    )

                    # Save metrics to file if path provided
                    if perf_path:
                        import json

                        with open(perf_path, "w", encoding="utf-8") as f:
                            json.dump(metrics, f, indent=2)
                        print(f"  Metrics saved to: {perf_path}")

                    return metrics
            except Exception as e:
                print(f"Warning: Could not retrieve performance metrics: {e}")
                import traceback

                traceback.print_exc()
        else:
            # For non-performance runs, just wait for basic rendering
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "graph-container"))
            )
            print(f"✓ Headless render completed")

        return temp_path

    except Exception as e:
        print(f"Error running headless browser: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        if driver:
            driver.quit()
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except:
            pass

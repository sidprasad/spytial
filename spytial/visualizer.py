"""
sPyTial Visualization Display Module

This module provides functions to display Python objects using the sPyTial visualizer.
"""

import json
import tempfile
import webbrowser
from pathlib import Path
import os
from typing import Any, Callable, Dict, Optional, Sequence, Union

from .utils import default_method
from .core_assets import get_template_asset_context

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


SEQUENCE_POLICY_NAMES = {
    "ignore_history",
    "stability",
    "change_emphasis",
    "random_positioning",
}


def _normalize_as_type(as_type: Optional[Any]) -> Optional[Any]:
    """Extract the underlying Annotated type when passed an AnnotatedType wrapper."""
    from .utils import AnnotatedType

    if isinstance(as_type, AnnotatedType):
        return as_type._annotated
    return as_type


def _merge_decorator_registries(*registries: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple decorator registries while preserving stable order."""
    from .annotations import _deduplicate_entries

    merged = {"constraints": [], "directives": []}
    for registry in registries:
        merged["constraints"].extend(registry.get("constraints", []))
        merged["directives"].extend(registry.get("directives", []))

    merged["constraints"] = _deduplicate_entries(merged["constraints"])
    merged["directives"] = _deduplicate_entries(merged["directives"])
    return merged


def _deliver_html_content(
    html_content: str,
    method: str,
    auto_open: bool,
    height: int,
    output_filename: str,
) -> Optional[str]:
    """Display or persist already-rendered visualization HTML."""
    if method == "inline":
        if HAS_IPYTHON:
            try:
                import html as html_mod

                escaped = html_mod.escape(html_content, quote=True)

                iframe_html = f"""
                <div style="border: 2px solid #007acc; border-radius: 8px; overflow: hidden;">
                    <iframe
                        srcdoc="{escaped}"
                        width="100%"
                        height="{height + 50}px"
                        frameborder="0"
                        style="display: block;">
                    </iframe>
                </div>
                """

                display(HTML(iframe_html))
                return None
            except Exception as e:
                print(f"Inline display failed: {e}")

        return _deliver_html_content(
            html_content,
            method="browser",
            auto_open=auto_open,
            height=height,
            output_filename=output_filename,
        )

    if method == "browser":
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html_content)
            temp_path = f.name

        if auto_open:
            webbrowser.open(f"file://{temp_path}")

        return temp_path

    if method == "file":
        output_path = Path(output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"Visualization saved to: {output_path.absolute()}")
        return str(output_path.absolute())

    raise ValueError(f"Unknown display method: {method}")


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
    as_type = _normalize_as_type(as_type)

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
    from .annotations import serialize_to_yaml_string

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

    if method == "headless":
        # Run in headless browser for testing/benchmarking
        return _run_headless(html_content, perf_path, perf_iterations, timeout, title)

    return _deliver_html_content(
        html_content,
        method=method,
        auto_open=auto_open,
        height=height,
        output_filename="spytial_visualization.html",
    )


class SequenceRecorder:
    """Context manager for recording a sequence of object snapshots for visualization.

    Uses a single shared builder across all :meth:`record` calls so that atom IDs
    remain stable across frames.  This handles two common patterns:

    - **In-place mutation** — the same Python objects are modified between frames.
      Because ``id(obj)`` never changes, the persistent ID table keeps IDs stable
      automatically with no extra configuration.

    - **Snapshot / deepcopy** — a fresh copy of the data structure is created each
      step (e.g. functional algorithms, undo-history).  Pass an ``identity``
      callable that returns a stable string key for each object; atoms will then
      receive an ``identity:<key>`` ID that stays constant across frames.

    Example — in-place mutation::

        with spytial.sequence() as seq:
            seq.record(root)
            insert(root, 42)
            seq.record(root)
            insert(root, 7)
            seq.record(root)
        seq.diagram()

    Example — deepcopy snapshots with identity::

        with spytial.sequence(identity=lambda n: str(n.id)) as seq:
            for snap in snapshots:
                seq.record(snap)
        seq.diagram(method="file")
    """

    def __init__(
        self,
        identity: Optional[Callable[[Any], Optional[str]]] = None,
        sequence_policy: str = "stability",
        method: Optional[str] = None,
        auto_open: bool = True,
        width: Optional[int] = None,
        height: Optional[int] = None,
        title: Optional[str] = None,
        as_type: Optional[Any] = None,
    ):
        from .provider_system import CnDDataInstanceBuilder

        if sequence_policy not in SEQUENCE_POLICY_NAMES:
            allowed = ", ".join(sorted(SEQUENCE_POLICY_NAMES))
            raise ValueError(
                f"Unknown sequence_policy: {sequence_policy!r}. Expected one of: {allowed}"
            )

        self._identity = identity
        self._sequence_policy = sequence_policy
        self._method = method
        self._auto_open = auto_open
        self._width = width
        self._height = height
        self._title = title
        self._as_type = _normalize_as_type(as_type)

        # A single shared builder preserves _persistent_object_ids across frames,
        # giving stable atom IDs for in-place-mutated objects.
        self._builder = CnDDataInstanceBuilder(
            preserve_object_ids=True,
            identity_resolver=identity,
        )
        self._data_instances = []
        self._merged_decorators = {"constraints": [], "directives": []}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False  # never suppress exceptions

    def record(self, obj: Any) -> None:
        """Capture a snapshot of *obj* as the next frame in the sequence."""
        instance = self._builder.build_instance(obj, as_type=self._as_type)
        self._data_instances.append(instance)
        self._merged_decorators = _merge_decorator_registries(
            self._merged_decorators,
            self._builder.get_collected_decorators(),
        )

    def diagram(
        self,
        method: Optional[str] = None,
        auto_open: Optional[bool] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        title: Optional[str] = None,
        sequence_policy: Optional[str] = None,
    ) -> Optional[str]:
        """Render all recorded frames as an interactive sequence visualization.

        Parameters override the values supplied to :func:`sequence` / the
        constructor; omit them to use the constructor defaults.
        """
        if not self._data_instances:
            raise ValueError(
                "No frames recorded. Call .record() at least once before .diagram()."
            )

        _method = method if method is not None else self._method
        _auto_open = auto_open if auto_open is not None else self._auto_open
        _width = width if width is not None else self._width
        _height = height if height is not None else self._height
        _title = title if title is not None else self._title

        if sequence_policy is not None and sequence_policy not in SEQUENCE_POLICY_NAMES:
            allowed = ", ".join(sorted(SEQUENCE_POLICY_NAMES))
            raise ValueError(
                f"Unknown sequence_policy: {sequence_policy!r}. Expected one of: {allowed}"
            )
        _policy = sequence_policy if sequence_policy is not None else self._sequence_policy

        if _method is None:
            _method = default_method()

        if _width is None or _height is None:
            _width = _width or 1200
            _height = _height or 800

        from .annotations import serialize_to_yaml_string

        spytial_spec = serialize_to_yaml_string(self._merged_decorators)
        html_content = _generate_sequence_visualizer_html(
            data_instances=self._data_instances,
            spytial_spec=spytial_spec,
            sequence_policy=_policy,
            width=_width,
            height=_height,
            title=_title,
        )

        return _deliver_html_content(
            html_content,
            method=_method,
            auto_open=_auto_open,
            height=_height,
            output_filename="spytial_sequence_visualization.html",
        )


def sequence(
    identity: Optional[Callable[[Any], Optional[str]]] = None,
    sequence_policy: str = "stability",
    method: Optional[str] = None,
    auto_open: bool = True,
    width: Optional[int] = None,
    height: Optional[int] = None,
    title: Optional[str] = None,
    as_type: Optional[Any] = None,
) -> "SequenceRecorder":
    """Create a :class:`SequenceRecorder` for capturing algorithm steps or temporal snapshots.

    The recorder uses a **shared** builder so atom IDs are stable across every
    :meth:`~SequenceRecorder.record` call within the same session.

    Args:
        identity: Optional callable ``(obj) -> str | None``.  When provided, any
            object for which it returns a non-``None`` string will receive an atom
            ID of ``identity:<returned-string>``.  Use this for deepcopy / snapshot
            workflows where Python's ``id()`` changes each frame but each node has a
            stable semantic key (e.g. a node's ``.id`` field).
        sequence_policy: Continuity policy for the frontend renderer.  One of
            ``"stability"`` (default), ``"ignore_history"``, ``"change_emphasis"``,
            or ``"random_positioning"``.
        method: Display method — ``"inline"`` (Jupyter), ``"browser"``, or ``"file"``.
            Defaults to auto-detection.
        auto_open: Whether to open the browser automatically (``"browser"`` method).
        width: Width of the visualization in pixels.
        height: Height of the visualization in pixels.
        title: Browser tab / page title.
        as_type: Optional annotated type applied to every recorded object.

    Returns:
        A :class:`SequenceRecorder` instance, usable as a context manager.

    Example::

        with spytial.sequence() as seq:
            seq.record(data)
            step(data)
            seq.record(data)
        seq.diagram()
    """
    return SequenceRecorder(
        identity=identity,
        sequence_policy=sequence_policy,
        method=method,
        auto_open=auto_open,
        width=width,
        height=height,
        title=title,
        as_type=as_type,
    )


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
        **get_template_asset_context(),
    )

    return html_content


def _generate_sequence_visualizer_html(
    data_instances,
    spytial_spec,
    sequence_policy,
    width=800,
    height=600,
    title=None,
):
    """Generate HTML content for a sequence visualizer using Jinja2 templating."""
    if not HAS_JINJA2:
        raise ImportError(
            "Jinja2 is required for HTML generation. Install with: pip install jinja2"
        )

    current_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(current_dir))

    try:
        template = env.get_template("sequence_visualizer_template.html")
    except Exception as e:
        raise FileNotFoundError(
            f"sequence_visualizer_template.html not found in {current_dir}: {e}"
        )

    html_content = template.render(
        sequence_data=json.dumps(data_instances),
        cnd_spec=spytial_spec,
        sequence_policy=sequence_policy,
        title=title,
        width=width,
        height=height,
        **get_template_asset_context(),
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
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
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

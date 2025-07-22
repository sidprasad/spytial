"""
sPyTial Visualization Display Module

This module provides functions to display Python objects using the sPyTial visualizer.
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


def quick_diagram(obj):
    """
    Quick display function for Jupyter notebooks.
    Alias for diagram(obj, method="inline").
    """
    return diagram(obj, method="inline")


def diagram(obj, method="inline", auto_open=True, width=None, height=None):
    """
    Display a Python object in the sPyTial visualizer.
    
    Args:
        obj: Any Python object to visualize
        method: Display method - "inline" (Jupyter), "browser" (new tab), or "file" (save to file)
        auto_open: Whether to automatically open browser (for "browser" method)
        width: Width of the visualization container in pixels (default: auto-detected)
        height: Height of the visualization container in pixels (default: auto-detected)
    
    Returns:
        str: Path to the generated HTML file (if method="file" or "browser")
    """
    # Auto-detect sizing if not provided
    if width is None or height is None:
        detected_width, detected_height = _detect_optimal_size(obj, method)
        width = width or detected_width
        height = height or detected_height
    from .provider_system import CnDDataInstanceBuilder
    from .annotations import collect_decorators, serialize_to_yaml_string  # Updated to use collect_decorators
    
    # Collect decorators from the object's class
    decorators = collect_decorators(obj)
    
    # Serialize the collected decorators into a YAML string
    spytial_spec = serialize_to_yaml_string(decorators)
    
    # Serialize the object using the provider system
    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(obj)
    
    # Generate the HTML content
    html_content = _generate_visualizer_html(data_instance, spytial_spec, width, height)
    
    if method == "inline":
        # Display inline in Jupyter notebook using iframe
        if HAS_IPYTHON:
            try:
                import base64
                
                # Encode HTML as base64 for iframe
                encoded_html = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
                
                # Create iframe HTML
                iframe_html = f'''
                <div style="border: 2px solid #007acc; border-radius: 8px; overflow: hidden;">
                    <iframe 
                        src="data:text/html;base64,{encoded_html}" 
                        width="100%" 
                        height="{height}px" 
                        frameborder="0"
                        style="display: block;">
                    </iframe>
                </div>
                '''
                
                display(HTML(iframe_html))
                return
                
            except Exception as e:
                print(f"Iframe display failed: {e}")
                # Fall back to browser if iframe fails
                return diagram(obj, method="browser", auto_open=auto_open, 
                             width=width, height=height)
        
        # Fall back to browser if not in Jupyter
        return diagram(obj, method="browser", auto_open=auto_open, 
                      width=width, height=height)
    
    elif method == "browser":
        # Open in browser
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_path = f.name
        
        if auto_open:
            webbrowser.open(f'file://{temp_path}')
        
        return temp_path
    
    elif method == "file":
        # Save to file
        output_path = Path("cnd_visualization.html")
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        print(f"Visualization saved to: {output_path.absolute()}")
        return str(output_path.absolute())
    
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
        if hasattr(obj, '__dict__'):
            complexity += len(obj.__dict__)
        
        # Count list/tuple elements
        if isinstance(obj, (list, tuple)):
            complexity += len(obj)
            # Add nested complexity for first few items
            for i, item in enumerate(obj[:5]):
                if hasattr(item, '__dict__'):
                    complexity += len(item.__dict__) * 0.5
        
        # Count dict keys
        if isinstance(obj, dict):
            complexity += len(obj)
            # Add nested complexity for values
            for value in list(obj.values())[:5]:
                if hasattr(value, '__dict__'):
                    complexity += len(value.__dict__) * 0.5
        
        return int(complexity)
    except:
        return 10  # Default medium complexity


def _generate_visualizer_html(data_instance, spytial_spec, width=800, height=600):
    """Generate HTML content using Jinja2 templating."""
    
    if not HAS_JINJA2:
        raise ImportError("Jinja2 is required for HTML generation. Install with: pip install jinja2")
    
    # Set up Jinja2 environment
    current_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(current_dir))

    # And error handling in react components COULD go here, depending on What we want to include?
    # Like, mount stuff if needed?
    ## Error viz, CnD Builder, etc.

    
    try:
        template = env.get_template('visualizer_template.html')
    except Exception as e:
        raise FileNotFoundError(f"visualizer_template.html not found in {current_dir}: {e}")
    
    # Render the template with our data
    html_content = template.render(
        python_data=json.dumps(data_instance),  # Properly serialize to JSON
        cnd_spec=spytial_spec,                   # Embed the sPyTial specification
        width=width,                             # Container width
        height=height                            # Container height
    )
    
    return html_content


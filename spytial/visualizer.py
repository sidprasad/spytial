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


def quick_diagram(obj, width=800, height=600):
    """
    Quick display function for Jupyter notebooks.
    Alias for diagram(obj, method="inline", width=width, height=height).
    
    Args:
        obj: Any Python object to visualize
        width: Width of the visualization container in pixels (default: 800)
        height: Height of the visualization container in pixels (default: 600)
    """
    return diagram(obj, method="inline", width=width, height=height)


def diagram(obj, method="inline", auto_open=True, width=800, height=600):
    """
    Display a Python object in the sPyTial visualizer.
    
    Args:
        obj: Any Python object to visualize
        method: Display method - "inline" (Jupyter), "browser" (new tab), or "file" (save to file)
        auto_open: Whether to automatically open browser (for "browser" method)
        width: Width of the visualization container in pixels (default: 800)
        height: Height of the visualization container in pixels (default: 600)
    
    Returns:
        str: Path to the generated HTML file (if method="file" or "browser")
    """
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
                        height="{height + 50}px" 
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


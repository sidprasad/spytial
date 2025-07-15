"""
CnD Visualization Display Module

This module provides functions to display Python objects using the CnD visualizer.
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


def quick_show(obj):
    """
    Quick display function for Jupyter notebooks.
    Alias for show(obj, method="inline").
    """
    return show(obj, method="inline")


def show(obj, method="inline", auto_open=True):
    """
    Display a Python object in the CnD visualizer.
    
    Args:
        obj: Any Python object to visualize
        method: Display method - "inline" (Jupyter), "browser" (new tab), or "file" (save to file)
        auto_open: Whether to automatically open browser (for "browser" method)
    
    Returns:
        str: Path to the generated HTML file (if method="file" or "browser")
    """
    from .provider_system import CnDDataInstanceBuilder
    from .annotations import serialize_to_yaml_string  # Import the function to generate cnd_spec
    
    # Dynamically generate the CnD specification
    cnd_spec = serialize_to_yaml_string()
    
    # Serialize the object using the provider system
    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(obj)
    
    # Generate the HTML content

    html_content = _generate_visualizer_html(data_instance, cnd_spec)
    
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
                        height="650px" 
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
                return show(obj, method="browser", auto_open=auto_open)
        
        # Fall back to browser if not in Jupyter
        return show(obj, method="browser", auto_open=auto_open)
    
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


def _generate_visualizer_html(data_instance, cnd_spec):
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
        cnd_spec=cnd_spec                       # Embed the CnD specification
    )
    
    return html_content


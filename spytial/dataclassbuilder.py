import os
import json
import yaml
import webbrowser
import tempfile
import threading
import time
from dataclasses import fields, is_dataclass
from typing import Any, Dict, Optional, Type, get_type_hints, Union
from .annotations import collect_decorators
from .provider_system import CnDDataInstanceBuilder


class DataclassDerelationalizer:
    """
    De-relationalizer that converts CnD relational data back to dataclass instances.
    This handles the reverse of the relationalization process.
    """
    
    def __init__(self, dataclass_type: Type):
        self.dataclass_type = dataclass_type
        self.field_info = {f.name: f for f in fields(dataclass_type)}
        self.type_hints = get_type_hints(dataclass_type)
    
    def derelationalize(self, relational_data: Dict) -> Any:
        """
        Convert relational/CnD data back to a dataclass instance.
        
        Args:
            relational_data: The relational data structure from CnD
            
        Returns:
            A dataclass instance built from the relational data
        """
        # If it's already in simple JSON format, use json_to_dataclass
        if self._is_simple_json(relational_data):
            return json_to_dataclass(relational_data, self.dataclass_type)
        
        # Otherwise, process CnD relational format
        return self._process_cnd_data(relational_data)
    
    def _is_simple_json(self, data: Dict) -> bool:
        """Check if data is in simple JSON format vs CnD relational format."""
        # Simple heuristic: if all keys match dataclass fields, it's simple JSON
        if not isinstance(data, dict):
            return False
        return all(key in self.field_info for key in data.keys())
    
    def _process_cnd_data(self, cnd_data: Dict) -> Any:
        """Process CnD relational data format."""
        # This would need to be implemented based on CnD's actual output format
        # For now, try to extract data from CnD structure
        
        if 'atoms' in cnd_data and 'relations' in cnd_data:
            # Handle CnD atoms/relations format
            return self._extract_from_atoms_relations(cnd_data)
        else:
            # Fallback to simple JSON processing
            return json_to_dataclass(cnd_data, self.dataclass_type)
    
    def _extract_from_atoms_relations(self, cnd_data: Dict) -> Any:
        """Extract dataclass instance from CnD atoms/relations structure."""
        # Implementation would depend on CnD's exact output format
        # For now, use a simplified approach
        atoms = cnd_data.get('atoms', [])
        relations = cnd_data.get('relations', [])
        
        # Try to reconstruct the original data structure
        reconstructed = {}
        
        # Extract field values from atoms
        for atom in atoms:
            if isinstance(atom, dict):
                label = atom.get('label', '')
                if label in self.field_info:
                    reconstructed[label] = atom.get('value', '')
        
        return json_to_dataclass(reconstructed, self.dataclass_type)


class InteractiveInputBuilder:
    """
    Enhanced input builder that can capture data dynamically from the web interface.
    """
    
    def __init__(self, dataclass_type: Type, export_dir: Optional[str] = None):
        self.dataclass_type = dataclass_type
        self.export_dir = export_dir or tempfile.mkdtemp(prefix="spytial_interactive_")
        self.derelationalizer = DataclassDerelationalizer(dataclass_type)
        self.captured_data = None
        self.waiting_for_input = False
        
    def build_and_wait(self, timeout: float = 300.0, **kwargs) -> Optional[Any]:
        """
        Build input interface and wait for user to export data, then return dataclass instance.
        
        Args:
            timeout: Maximum time to wait for user input (seconds)
            **kwargs: Additional arguments for build_input
            
        Returns:
            Dataclass instance created from user input, or None if timeout
        """
        # Ensure export_dir is set in kwargs
        kwargs['export_dir'] = self.export_dir
        kwargs.setdefault('auto_open', True)
        kwargs.setdefault('method', 'file')
        
        print(f"🎯 Building interactive input for {self.dataclass_type.__name__}")
        print(f"📁 Watching for exports in: {self.export_dir}")
        
        # Build the input interface
        html_file = build_input(self.dataclass_type, **kwargs)
        
        print(f"🌐 Input interface: {html_file}")
        print(f"⏱️  Waiting up to {timeout} seconds for you to build and export data...")
        print("💡 Build your data in the web interface, then click 'Export JSON'")
        
        # Start watching for exported files
        return self._wait_for_export(timeout)
    
    def _wait_for_export(self, timeout: float) -> Optional[Any]:
        """Wait for user to export data and return the dataclass instance."""
        start_time = time.time()
        os.makedirs(self.export_dir, exist_ok=True)
        
        while time.time() - start_time < timeout:
            # Check for new JSON files in export directory
            try:
                json_files = [f for f in os.listdir(self.export_dir) if f.endswith('.json')]
                
                if json_files:
                    # Use the most recent file
                    latest_file = max(json_files, key=lambda f: os.path.getctime(
                        os.path.join(self.export_dir, f)))
                    file_path = os.path.join(self.export_dir, latest_file)
                    
                    print(f"📥 Found export: {latest_file}")
                    
                    # Load and convert the data
                    with open(file_path, 'r') as f:
                        exported_data = json.load(f)
                    
                    # Convert to dataclass instance
                    instance = self.derelationalizer.derelationalize(exported_data)
                    
                    print(f"✅ Successfully created {self.dataclass_type.__name__} instance!")
                    print(f"🎉 Result: {instance}")
                    
                    return instance
                    
            except Exception as e:
                print(f"⚠️  Error checking exports: {e}")
            
            time.sleep(1.0)  # Check every second
        
        print(f"⏰ Timeout reached ({timeout}s). No data was exported.")
        return None


def build_interactive(dataclass_type: Type, timeout: float = 300.0, **kwargs) -> Optional[Any]:
    """
    Build an interactive input interface and wait for user to create data.
    
    This is the main function that provides seamless roundtrip functionality:
    1. Opens web interface for building data
    2. Waits for user to export data  
    3. Automatically converts exported JSON back to dataclass instance
    4. Returns the built dataclass instance directly
    
    Args:
        dataclass_type: The dataclass type to build
        timeout: Maximum time to wait for user input (default 5 minutes)
        **kwargs: Additional arguments for the input builder
        
    Returns:
        Dataclass instance built by the user, or None if timeout
        
    Example:
        @dataclass
        class Person:
            name: str = ""
            age: int = 0
            
        # This will open a web interface and return the built Person instance
        person = spytial.build_interactive(Person)
        if person:
            print(f"Built person: {person.name}, age {person.age}")
    """
    builder = InteractiveInputBuilder(dataclass_type)
    return builder.build_and_wait(timeout=timeout, **kwargs)


def json_to_dataclass(json_data: Union[str, Dict], dataclass_type: Type) -> Any:
    """
    Convert JSON data back to a dataclass instance.

    Args:
        json_data: JSON string or dictionary containing the data
        dataclass_type: The target dataclass type to create

    Returns:
        An instance of the dataclass populated with the JSON data
    """
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data

    if not is_dataclass(dataclass_type):
        raise ValueError(f"{dataclass_type} is not a dataclass.")

    # Get field information
    field_info = {f.name: f for f in fields(dataclass_type)}
    type_hints = get_type_hints(dataclass_type)

    # Build kwargs for dataclass constructor
    kwargs = {}

    for field_name, field_def in field_info.items():
        if field_name in data:
            field_value = data[field_name]
            field_type = type_hints.get(field_name, field_def.type)

            # Handle nested dataclasses
            if is_dataclass(field_type) and isinstance(field_value, dict):
                kwargs[field_name] = json_to_dataclass(field_value, field_type)
            # Handle lists of dataclasses
            elif (
                hasattr(field_type, "__origin__")
                and field_type.__origin__ is list
                and len(field_type.__args__) > 0
                and is_dataclass(field_type.__args__[0])
            ):
                nested_type = field_type.__args__[0]
                kwargs[field_name] = [
                    (
                        json_to_dataclass(item, nested_type)
                        if isinstance(item, dict)
                        else item
                    )
                    for item in field_value
                ]
            else:
                kwargs[field_name] = field_value

    return dataclass_type(**kwargs)


def load_from_json_file(json_file_path: str, dataclass_type: Type) -> Any:
    """
    Load a dataclass instance from a JSON file exported from the input builder.

    Args:
        json_file_path: Path to the JSON file containing exported data
        dataclass_type: The target dataclass type to create

    Returns:
        An instance of the dataclass populated with the file data
    """
    with open(json_file_path, "r") as f:
        json_data = json.load(f)

    return json_to_dataclass(json_data, dataclass_type)


def create_export_watcher(output_dir: str = None) -> str:
    """
    Create a directory for watching exported JSON files.

    Args:
        output_dir: Optional directory path. If None, creates a temp directory.

    Returns:
        Path to the export directory
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="spytial_exports_")
    else:
        os.makedirs(output_dir, exist_ok=True)

    return output_dir


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
    export_dir: Optional[str] = None,
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
        export_dir: Optional directory for JSON exports. If None, uses temp directory.

    Returns:
        Path to generated HTML file (if method='file') or HTML string
        (if method='inline')
    """
    if method not in ["file", "inline"]:
        raise ValueError("Method must be 'file' or 'inline'.")

    if not is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass. Use @dataclass decorator.")

    # Setup export directory
    if export_dir is None:
        export_dir = create_export_watcher()

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
    # Add export directory information
    html_content = html_content.replace("{{ export_dir | safe }}", export_dir)
    html_content = html_content.replace("{{ dataclass_name | safe }}", cls.__name__)

    if method == "file":
        # Generate output filename in the specified export directory if provided
        if export_dir and os.path.exists(export_dir):
            output_path = os.path.join(export_dir, f"input_builder_{cls.__name__.lower()}.html")
        else:
            output_path = f"input_builder_{cls.__name__.lower()}.html"

        # Write HTML file
        with open(output_path, "w") as f:
            f.write(html_content)

        # Auto-open in browser if requested
        if auto_open:
            webbrowser.open(f"file://{os.path.abspath(output_path)}")

        # Print instructions for retrieving data
        print(f"\n📁 Export directory: {export_dir}")
        print(f"📄 Input builder: {output_path}")
        print("\n💡 To retrieve your built dataclass:")
        print(
            f"   exported_data = spytial.load_from_json_file("
            f"'path/to/exported.json', {cls.__name__})"
        )
        print(f"   # Or monitor the export directory: {export_dir}")

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

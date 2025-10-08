"""
Demo: Simple Dataclass Builder Widget

Shows how to use the new, simplified dataclass builder widget.
This demo can be run in a Jupyter notebook or JupyterLab.
"""

from dataclasses import dataclass
import spytial

# Define a dataclass with spatial annotations
@dataclass
@spytial.orientation(selector='name', directions=['above'])
class Person:
    name: str = ""
    age: int = 0
    email: str = ""
    active: bool = True

# In a Jupyter notebook, you would do:
# person_widget = spytial.dataclass_builder(Person)
# person_widget  # Display the widget

# Access the current value at any time:
# current_person = person_widget.value
# print(current_person)

# The widget updates automatically as you type
# No need to click "export" or wait for file I/O

print("To use this demo:")
print("1. Open this file in a Jupyter notebook")
print("2. Run: person_widget = spytial.dataclass_builder(Person)")
print("3. Display: person_widget")
print("4. Fill in the form")
print("5. Access the value: person_widget.value")
print()
print("Example:")
print("  person_widget = spytial.dataclass_builder(Person)")
print("  # ... fill in the form ...")
print("  current_person = person_widget.value")
print("  print(current_person)  # Person(name='Alice', age=30, email='alice@example.com', active=True)")

# More complex example with nested dataclasses
@dataclass
class Address:
    street: str = ""
    city: str = ""
    zipcode: str = ""

@dataclass
class Employee:
    name: str = ""
    employee_id: int = 0
    salary: float = 0.0
    # Note: nested dataclasses would need additional handling
    # address: Address = None  # Not yet supported

# Demo with employee
print("\n\nEmployee Builder:")
print("  employee_widget = spytial.dataclass_builder(Employee)")
print("  employee_widget")
print("  current_employee = employee_widget.value")

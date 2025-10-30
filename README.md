# sPyTial: Lightweight Diagrams for Structured Python Data

```
pip install spytial-diagramming
```


Sometimes you just want to see your data.

You’re working with a tree, a graph, a recursive object -- maybe an AST, a neural network, or a symbolic term. You don’t need an interactive dashboard or a production-grade visualization system. You just need a diagram, something that lays it out clearly so you can understand what’s going on.

That’s what `sPyTial` is for. It’s designed for developers, educators, and researchers who work with structured data and need to make that structure visible — to themselves or to others — with minimal effort. 

## Why Spatial Representation Matters

There’s strong evidence — from cognitive science, human-computer interaction, and decades of programming tool design — that **spatial representations help people understand structure**. When elements are placed meaningfully in space — grouped, aligned, oriented — we can spot patterns, detect errors, and reason more effectively. This idea shows up in research from Barbara Tversky, Larkin & Simon, and in the design of tools like Alloy and Scratch. 

`sPyTial` gives you that kind of spatial layout **by default**. When you visualize a Python object, the diagram reflects how the parts are connected, not just how they're stored. You get:
- A **box-and-arrow diagram** that shows the shape of your data
- A layout that follows cognitive and structural conventions
- A tool that knows when something doesn't make sense

## Quick Start

```python
import spytial

# Visualize any Python object
data = {
    'name': 'root',
    'children': [
        {'value': 1},
        {'value': 2},
        {'value': 3}
    ]
}

# Opens in browser
spytial.diagram(data)

# Or save to file
spytial.diagram(data, method='file')
```

## Headless Mode for Testing & Automation

sPyTial supports headless browser mode for automated testing, CI/CD pipelines, and performance benchmarking without GUI overhead:

```python
import spytial

# Basic headless rendering
result = spytial.diagram(data, headless=True)

# Performance benchmarking in headless mode
metrics = spytial.diagram(
    data,
    headless=True,
    perf_iterations=10,
    perf_path='metrics.json'
)

print(f"Average render time: {metrics['totalTime']['avg']:.2f}ms")

# For large/complex visualizations, specify a custom timeout
# Default timeout is max(120, perf_iterations * 5) seconds
metrics = spytial.diagram(
    large_data,
    headless=True,
    perf_iterations=30,
    timeout=600  # 10 minutes for complex visualization
)
```

**Requirements for headless mode:**
```bash
pip install spytial_diagramming[headless]
# chromedriver is automatically managed via webdriver-manager
```

Headless mode uses Selenium with Chrome to render visualizations programmatically, making it ideal for:
- Automated testing in CI/CD pipelines
- Performance regression testing
- Batch processing of visualizations
- Server-side rendering without display

**Timeout Guidance:**
- Small visualizations (< 20 atoms): Default timeout is sufficient
- Medium visualizations (20-100 atoms): Consider `timeout=300` (5 min) for 30+ iterations
- Large visualizations (100+ atoms): Use `timeout=600` (10 min) or higher



## License
This project is licensed under the MIT License. See the LICENSE file for details.



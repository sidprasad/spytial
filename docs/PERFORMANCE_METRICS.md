# Performance Metrics and Benchmarking

sPyTial includes built-in performance tracking and benchmarking capabilities to help you analyze visualization performance.

## Basic Usage

### Single Render with Metrics

```python
import spytial

data = {'name': 'Test', 'values': [1, 2, 3]}
result = spytial.diagram(data, method='file', auto_open=True)
```

Performance metrics are automatically tracked and available in the browser console:
- Access via `window.spytialPerformance.getMetrics()`
- Includes: parse spec time, layout generation time, render time, total time

### Performance Benchmarking

Run multiple iterations to collect statistical metrics:

```python
import spytial

data = {'complex': 'data', 'structure': [1, 2, 3, 4, 5]}

# Run 10 iterations and collect metrics
result = spytial.diagram(
    data,
    method='file',
    auto_open=True,
    perf_iterations=10
)
```

This will:
1. Render the visualization 10 times
2. Collect metrics for each iteration
3. Calculate min, max, average, and median for each metric
4. Automatically trigger a download of the aggregated results

### Custom Download Path/Name

Specify a custom filename for the performance metrics:

```python
import spytial

result = spytial.diagram(
    data,
    method='file',
    perf_path='benchmarks/my-test/results.json',
    perf_iterations=5
)
```

**Important Notes:**
- The browser will download the file to your default Downloads folder
- The `perf_path` parameter sets the **filename** (not the actual filesystem path)
- This avoids CORS issues with local file:// URLs
- The browser may add a parent directory name to organize downloads

## Performance Metrics Structure

The downloaded JSON file contains:

```json
{
  "parseSpec": {
    "min": 1.2,
    "max": 2.5,
    "avg": 1.8,
    "median": 1.7
  },
  "generateLayout": {
    "min": 45.3,
    "max": 52.1,
    "avg": 48.2,
    "median": 47.9
  },
  "renderLayout": {
    "min": 12.4,
    "max": 15.8,
    "avg": 13.9,
    "median": 13.7
  },
  "totalTime": {
    "min": 58.9,
    "max": 70.4,
    "avg": 63.9,
    "median": 63.3
  },
  "timestamp": "2025-10-23T10:30:45.123Z",
  "iterations": 5,
  "dataSize": {
    "atomCount": 42,
    "relationCount": 38,
    "typeCount": 5
  }
}
```

## Browser Console Utilities

When a visualization is loaded, performance utilities are available:

```javascript
// Get current metrics
window.spytialPerformance.getMetrics()

// Get historical metrics from localStorage
window.spytialPerformance.getHistory()

// Download current metrics as JSON
window.spytialPerformance.downloadMetrics()

// Export all history as CSV
window.spytialPerformance.exportAsCSV()

// Clear stored history
window.spytialPerformance.clearHistory()
```

## Example: Comparing Data Structures

```python
import spytial

# Test different data structures
test_cases = [
    ('small_list', [1, 2, 3, 4, 5]),
    ('nested_dict', {'a': {'b': {'c': {'d': 'value'}}}},
    ('large_tree', create_tree(depth=5, branching=3))
]

for name, data in test_cases:
    spytial.diagram(
        data,
        method='file',
        auto_open=False,
        perf_path=f'benchmarks/{name}.json',
        perf_iterations=10
    )
```

## Troubleshooting

### "CORS policy" Error
**Fixed in current version.** The old implementation tried to use `fetch()` with `file://` URLs, which browsers block. The new version uses blob URLs and browser download APIs, which work without CORS issues.

### Download Location
The browser controls where files are downloaded. You cannot programmatically set the exact filesystem path from a web page for security reasons. The `perf_path` parameter sets the suggested filename.

### Large Benchmarks
For very large datasets or many iterations, the browser may become unresponsive. Consider:
- Reducing `perf_iterations` (5-10 is usually sufficient)
- Running benchmarks with `auto_open=False` to avoid browser overhead
- Using smaller representative datasets

## Performance Optimization Tips

Based on metrics, you can identify bottlenecks:

- **High parseSpec time**: CnD specification is complex, consider simplifying constraints
- **High generateLayout time**: Data structure is large or constraints are expensive to solve
- **High renderLayout time**: Many visual elements, consider simplifying styling or reducing data

## See Also

- [Spatial Annotations](pythonspecific.md) - Learn about spatial constraint decorators
- [Development Guide](DEVELOPMENT.md) - Development workflow and testing

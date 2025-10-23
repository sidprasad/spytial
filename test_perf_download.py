#!/usr/bin/env python3
"""
Test script to verify performance metrics download with custom path works correctly.
This tests the fix for CORS issue when downloading performance metrics.
"""

import spytial
import os
import tempfile

def test_perf_path_download():
    """Test that perf_path parameter triggers download with correct filename"""
    
    print("Testing performance metrics download with custom path...")
    
    # Create a simple test data structure
    data = {
        'name': 'Test',
        'values': [1, 2, 3, 4, 5],
        'nested': {
            'a': 'hello',
            'b': 'world'
        }
    }
    
    # Create temporary directory for output
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = os.path.join(tmpdir, 'test_viz.html')
        perf_file = 'perf/test/metrics.json'
        
        # Generate visualization with perf_path
        result = spytial.diagram(
            data,
            method='file',
            auto_open=False,
            perf_path=perf_file,
            perf_iterations=5  # Run 5 iterations for benchmarking
        )
        
        print(f"✓ Generated visualization: {result}")
        
        # Verify the HTML was created
        assert os.path.exists(result), f"Output file not created: {result}"
        print(f"✓ HTML file exists: {result}")
        
        # Read and verify perf_path is embedded correctly
        with open(result, 'r') as f:
            content = f.read()
            assert 'perfPath' in content, "perfPath variable not found in HTML"
            assert perf_file in content, f"perf_path value '{perf_file}' not embedded in HTML"
            assert 'saveMetricsToServer' in content, "saveMetricsToServer function not found"
            assert 'URL.createObjectURL(blob)' in content, "Blob download approach not found"
            # Verify the old fetch approach is gone
            assert 'fetch(perfPath' not in content, "Old fetch approach still present!"
            print(f"✓ perfPath correctly embedded: {perf_file}")
            print(f"✓ Download approach uses blob URLs (no CORS issues)")
        
        print("\n✅ All tests passed!")
        print(f"\nTo test manually:")
        print(f"  1. Open {result} in a browser")
        print(f"  2. Wait for the benchmark to complete (5 iterations)")
        print(f"  3. Check your Downloads folder for '{perf_file}'")
        print(f"  4. The file should download automatically without CORS errors")

if __name__ == '__main__':
    test_perf_path_download()

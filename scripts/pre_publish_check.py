#!/usr/bin/env python3
"""
Pre-publish validation script for sPyTial.

Runs all the checks mentioned in the copilot instructions to ensure
the package is ready for publishing.
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

def run_command(cmd, description):
    """Run a command and report success/failure."""
    print(f"🔍 {description}...")
    try:
        # Ensure we run from the project root directory
        project_root = Path(__file__).parent.parent
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=project_root)
        if result.returncode != 0:
            print(f"❌ {description} FAILED")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False
        else:
            print(f"✅ {description} PASSED")
            return True
    except Exception as e:
        print(f"❌ {description} ERROR: {e}")
        return False

def validate_imports_and_functionality():
    """Test import and basic functionality."""
    print("🔍 Testing imports and basic functionality...")
    
    # Ensure we can import from the project directory
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    try:
        # Test basic import
        import spytial
        print("✅ Import successful")
        
        # Basic visualization test
        data = {
            'name': 'John', 'age': 30, 'hobbies': ['reading', 'cycling'],
            'address': {'street': '123 Main St', 'city': 'Boston'}
        }
        result = spytial.diagram(data, method='file', auto_open=False)
        print(f"✅ Generated: {result}")
        
        # Validate file was created and contains valid content
        if os.path.exists(result):
            with open(result, 'r') as f:
                content = f.read()
                if 'html' in content.lower() and len(content) > 1000:
                    print("✅ Basic visualization works")
                else:
                    print("❌ Generated HTML content is invalid")
                    return False
        else:
            print("❌ Visualization file was not created")
            return False
        
        # Test class decorators
        @spytial.group(field='children', groupOn=0, addToGroup=1)
        @spytial.orientation(selector='value', directions=['above'])
        class Node:
            def __init__(self, value, children=None):
                self.value = value
                self.children = children or []
        
        node = Node('root', [Node('child1'), Node('child2')])
        result = spytial.diagram(node, method='file', auto_open=False)
        print("✅ Class annotations work")
        
        # Test object annotations
        my_list = [1, 2, 3, 4, 5]
        spytial.annotate_orientation(my_list, selector='items', directions=['horizontal'])
        result = spytial.diagram(my_list, method='file', auto_open=False)
        print("✅ Object annotations work")
        
        # Test provider system
        builder = spytial.CnDDataInstanceBuilder()
        data = {'test': 'data', 'nested': {'values': [1, 2, 3]}}
        instance = builder.build_instance(data)
        if isinstance(instance, dict):
            print("✅ Provider system works")
        else:
            print("❌ Provider system failed")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all pre-publish checks."""
    print("🚀 sPyTial Pre-Publish Validation")
    print("=" * 50)
    
    checks = []
    
    # Install package in development mode
    checks.append(run_command(
        "python -m pip install -e .",
        "Installing package in development mode"
    ))
    
    # Install development dependencies
    checks.append(run_command(
        "python -m pip install pytest>=7.0.0 flake8>=6.0.0 black>=23.0.0",
        "Installing development dependencies"
    ))
    
    # Code formatting check
    checks.append(run_command(
        "python -m black spytial/ --check",
        "Code formatting check"
    ))
    
    # Linting
    checks.append(run_command(
        "python -m flake8 spytial/ --count --statistics --max-line-length=88 --extend-ignore=E203,W503",
        "Code linting"
    ))
    
    # Run tests
    checks.append(run_command(
        "python -m pytest test/ -v",
        "Running test suite"
    ))
    
    # Functionality validation
    checks.append(validate_imports_and_functionality())
    
    # Build package
    checks.append(run_command(
        "python -m pip install build",
        "Installing build tools"
    ))
    
    # Clean previous builds
    checks.append(run_command(
        "rm -rf build/ dist/ *.egg-info/",
        "Cleaning previous builds"
    ))
    
    # Build
    checks.append(run_command(
        "python -m build --no-isolation",
        "Building package"
    ))
    
    # Check distribution
    checks.append(run_command(
        "python -m pip install twine && twine check dist/*",
        "Checking distribution"
    ))
    
    # Test install from built package
    project_root = Path(__file__).parent.parent
    with tempfile.TemporaryDirectory() as tmpdir:
        checks.append(run_command(
            f"cd {tmpdir} && python -m pip install {project_root}/dist/*.whl && python -c 'import spytial; print(\"✅ Package install test passed\")'",
            "Testing install from built package"
        ))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    passed = sum(checks)
    total = len(checks)
    
    if passed == total:
        print(f"🎉 ALL CHECKS PASSED! ({passed}/{total})")
        print("\n✅ sPyTial is ready for publishing!")
        print("\nNext steps:")
        print("1. Commit your changes: git add . && git commit -m 'Prepare for release'")
        print("2. Create a release tag: git tag v0.1.0 && git push origin v0.1.0")
        print("3. Create a GitHub release to trigger automated publishing")
        print("   OR manually publish: twine upload dist/*")
        return 0
    else:
        print(f"❌ {total - passed} CHECKS FAILED! ({passed}/{total})")
        print("\n🔧 Please fix the failing checks before publishing.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Script to refresh bundled JavaScript/CSS dependencies for sPyTial widgets.

This script downloads the latest versions of external dependencies and bundles
them locally to avoid CDN reliability issues.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a shell command with error handling."""
    print(f"📥 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"   stdout: {e.stdout}")
        print(f"   stderr: {e.stderr}")
        return False


def main():
    """Main function to refresh dependencies."""
    print("🔄 Refreshing sPyTial bundled dependencies...")
    print("=" * 60)
    
    # Get the project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    spytial_dir = project_root / "spytial"
    static_dir = spytial_dir / "static"
    
    # Create static directories
    js_dir = static_dir / "js"
    css_dir = static_dir / "css"
    
    print(f"📁 Project root: {project_root}")
    print(f"📁 Static directory: {static_dir}")
    
    # Create directories if they don't exist
    js_dir.mkdir(parents=True, exist_ok=True)
    css_dir.mkdir(parents=True, exist_ok=True)
    
    # Define dependencies to download
    dependencies = [
        {
            "url": "https://d3js.org/d3.v4.min.js",
            "filename": "d3.v4.min.js",
            "directory": js_dir,
            "description": "D3.js v4 library"
        },
        {
            "url": "https://cdn.jsdelivr.net/npm/cnd-core@1.2.1/dist/browser/cnd-core-complete.global.js",
            "filename": "cnd-core-complete.global.js", 
            "directory": js_dir,
            "description": "CnD Core library"
        },
        {
            "url": "https://cdn.jsdelivr.net/npm/cnd-core@1.2.1/dist/components/react-component-integration.global.js",
            "filename": "react-component-integration.global.js",
            "directory": js_dir,
            "description": "CnD React integration library"
        },
        {
            "url": "https://cdn.jsdelivr.net/npm/cnd-core@1.2.1/dist/components/react-component-integration.css",
            "filename": "react-component-integration.css",
            "directory": css_dir,
            "description": "CnD React integration CSS"
        }
    ]
    
    # Download each dependency
    all_success = True
    for dep in dependencies:
        output_path = dep["directory"] / dep["filename"]
        cmd = f'curl -o "{output_path}" "{dep["url"]}"'
        
        if not run_command(cmd, f"Downloading {dep['description']}"):
            all_success = False
            continue
            
        # Verify the download
        if output_path.exists() and output_path.stat().st_size > 0:
            size_kb = output_path.stat().st_size / 1024
            print(f"   📦 {dep['filename']}: {size_kb:.1f} KB")
        else:
            print(f"   ❌ {dep['filename']}: Download failed or empty file")
            all_success = False
    
    print("=" * 60)
    if all_success:
        print("✅ All dependencies refreshed successfully!")
        print("\n📋 Summary:")
        print(f"   JS files: {len(list(js_dir.glob('*.js')))} files")
        print(f"   CSS files: {len(list(css_dir.glob('*.css')))} files")
        
        # Calculate total size
        total_size = sum(f.stat().st_size for f in js_dir.glob('*') if f.is_file())
        total_size += sum(f.stat().st_size for f in css_dir.glob('*') if f.is_file())
        total_mb = total_size / (1024 * 1024)
        print(f"   Total size: {total_mb:.1f} MB")
        
        print("\n💡 Usage:")
        print("   Dependencies are now bundled locally in spytial/static/")
        print("   The dataclass_widget will use these instead of CDNs")
        
    else:
        print("❌ Some dependencies failed to download")
        print("   Check your internet connection and try again")
        sys.exit(1)


if __name__ == "__main__":
    main()

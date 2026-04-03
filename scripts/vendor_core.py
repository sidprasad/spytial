#!/usr/bin/env python3
"""Download spytial-core assets from npm and vendor them into the package.

Usage:
    python scripts/vendor_core.py          # uses version from core_assets.py
    python scripts/vendor_core.py 2.3.0    # override version

This fetches the npm tarball for spytial-core, extracts the browser and
component bundles, and places them in spytial/vendor/. Run this whenever
you bump the spytial-core version.
"""

import io
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

VENDOR_DIR = Path(__file__).resolve().parent.parent / "spytial" / "vendor"

FILES_TO_EXTRACT = [
    "dist/browser/spytial-core-complete.global.js",
    "dist/components/react-component-integration.global.js",
    "dist/components/react-component-integration.css",
]


def get_default_version() -> str:
    """Read the default version from core_assets.py."""
    core_assets = Path(__file__).resolve().parent.parent / "spytial" / "core_assets.py"
    ns: dict = {}
    exec(core_assets.read_text(), ns)
    return ns["SPYTIAL_CORE_NPM_VERSION"]


def download_and_extract(version: str) -> None:
    url = f"https://registry.npmjs.org/spytial-core/-/spytial-core-{version}.tgz"
    print(f"Downloading spytial-core@{version} from npm...")
    resp = urllib.request.urlopen(url)
    data = resp.read()
    print(f"  Downloaded {len(data):,} bytes")

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member_path in FILES_TO_EXTRACT:
            full_path = f"package/{member_path}"
            member = tar.getmember(full_path)
            f = tar.extractfile(member)
            if f is None:
                print(f"  WARN: {member_path} not found in tarball")
                continue
            dest = VENDOR_DIR / Path(member_path).name
            dest.write_bytes(f.read())
            print(f"  Extracted {dest.name} ({dest.stat().st_size:,} bytes)")

    # Write a version marker so we know what's vendored
    (VENDOR_DIR / "VERSION").write_text(version + "\n")
    print(f"Done. Vendored spytial-core@{version} into {VENDOR_DIR}")


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else get_default_version()
    download_and_extract(version)

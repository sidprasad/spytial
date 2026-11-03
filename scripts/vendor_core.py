#!/usr/bin/env python3
"""Vendor one complete spytial-core release, including the browser assets.

Default: latest npm release. --version selects an exact release; --tarball
uses an already downloaded npm package offline. Re-running the same version
repairs missing/stale artifacts. Validation and generation finish before any
checkout files are changed. --check only verifies the existing vendor lock.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

import generate_spec_tables
import vendor_lock

ROOT = Path(__file__).resolve().parent.parent


def prepare(tarball, root=ROOT, version=None):
    """Read only allowlisted regular files; never extract arbitrary archive paths."""
    with tarfile.open(tarball, "r:gz") as archive:

        def read(name):
            try:
                member = archive.getmember("package/" + name)
            except KeyError as exc:
                raise ValueError(f"npm package is missing {name}") from exc
            if not member.isfile():
                raise ValueError(f"npm artifact is not a regular file: {name}")
            data = archive.extractfile(member).read()
            if not data:
                raise ValueError(f"npm artifact is empty: {name}")
            return data

        package = json.loads(read("package.json"))
        release = package.get("version", "")
        if package.get("name") != "spytial-core" or not re.fullmatch(
            r"\d+\.\d+\.\d+(?:-[\w.-]+)?", release
        ):
            raise ValueError("Expected a versioned spytial-core npm package")
        if version and version != release:
            raise ValueError(f"Requested {version}, but archive contains {release}")
        updates = {
            destination: read(source)
            for source, (destination, _) in vendor_lock.ARTIFACTS.items()
        }

    manifest = json.loads(updates["spytial/_vendor/spytial-language.json"])
    schema = json.loads(updates["spytial/_vendor/spytial-spec.schema.json"])
    if (
        manifest.get("spytialCoreVersion") != release
        or schema.get("x-spytial-core-version") != release
    ):
        raise ValueError(
            "npm package metadata, language manifest, and schema versions disagree"
        )
    # This refuses unknown language features before the installed pin or any
    # bundle is changed, so a failed update leaves a usable checkout.
    updates["spytial/_spec_tables.py"] = generate_spec_tables.render(manifest).encode(
        "utf-8"
    )
    pin_path = root / "spytial/core_assets.py"
    old = vendor_lock.pinned_version(root)
    updates["spytial/core_assets.py"] = (
        pin_path.read_text()
        .replace(
            f'SPYTIAL_CORE_VERSION = "{old}"', f'SPYTIAL_CORE_VERSION = "{release}"'
        )
        .encode("utf-8")
    )
    for filename in (
        "test/test_data_instance_format.py",
        "spytial/suggest/_vendor/README.md",
    ):
        text = (root / filename).read_text()
        text = text.replace(f"spytial-core v{old}", f"spytial-core v{release}")
        text = text.replace(f"spytial-core {old}", f"spytial-core {release}")
        text = text.replace(f"VERSION={old}", f"VERSION={release}")
        updates[filename] = text.encode("utf-8")
    updates["spytial/_vendor/VENDORED.json"] = (
        json.dumps(vendor_lock.capture(release, contents=updates), indent=2) + "\n"
    ).encode("utf-8")
    return release, updates


def install(updates, root=ROOT):
    """Restore previous bytes if a write fails; all validation precedes writes."""
    backups = {
        name: (root / name).read_bytes() if (root / name).exists() else None
        for name in updates
    }
    written = []
    try:
        for name, data in updates.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            written.append(name)
            target.write_bytes(data)
    except Exception:
        for name in reversed(written):
            if backups[name] is None:
                (root / name).unlink(missing_ok=True)
            else:
                (root / name).write_bytes(backups[name])
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--version", help="exact npm version (default: latest)")
    source.add_argument("--tarball", type=Path, help="offline npm pack .tgz")
    source.add_argument(
        "--check",
        action="store_true",
        help="verify installed artifacts without downloading",
    )
    args = parser.parse_args()
    if args.check:
        errors = vendor_lock.verify()
        if errors:
            parser.exit(1, "\n".join(errors) + "\n")
        print(f"Verified vendored spytial-core {vendor_lock.pinned_version()}.")
        return
    try:
        with tempfile.TemporaryDirectory(prefix="spytial-core-") as temporary:
            if args.tarball:
                tarball = args.tarball.resolve()
            else:
                if args.version and not re.fullmatch(
                    r"\d+\.\d+\.\d+(?:-[\w.-]+)?", args.version
                ):
                    raise ValueError("--version must be an exact release such as 6.6.0")
                # npm verifies registry integrity and fetches exactly one package.
                result = subprocess.run(
                    [
                        "npm",
                        "pack",
                        f"spytial-core@{args.version or 'latest'}",
                        "--ignore-scripts",
                        "--json",
                        "--pack-destination",
                        temporary,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                metadata = json.loads(result.stdout)
                tarball = Path(temporary) / Path(metadata[0]["filename"]).name
            release, updates = prepare(tarball, version=args.version)
            install(updates)
        print(
            f"Vendored spytial-core {release}: {len(vendor_lock.ARTIFACTS)} artifacts, pin, lock, and generated tables."
        )
        print(
            "Next: review the diff and run pytest. Review/regenerate the API baseline after changing the release."
        )
    except (
        OSError,
        ValueError,
        tarfile.TarError,
        generate_spec_tables.ManifestDrift,
        subprocess.CalledProcessError,
    ) as exc:
        detail = (
            exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        )
        parser.exit(1, f"Vendoring failed: {detail}\n")


if __name__ == "__main__":
    main()

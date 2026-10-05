"""Updates are complete, repeatable, and leave no partial release on failure."""

import io
import json
from pathlib import Path
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vendor_core
import vendor_lock

sys.path.pop(0)


@pytest.fixture
def checkout(tmp_path):
    for name in (
        "spytial/core_assets.py",
        "test/test_data_instance_format.py",
        "spytial/suggest/_vendor/README.md",
    ):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    return tmp_path


def archive(tmp_path, version="6.6.0", missing=None, drift=False):
    payloads = {
        source: (ROOT / target).read_bytes()
        for source, (target, _) in vendor_lock.ARTIFACTS.items()
    }
    for name, key in (
        ("package.json", "version"),
        ("docs/spytial-language.json", "spytialCoreVersion"),
        ("docs/spytial-spec.schema.json", "x-spytial-core-version"),
    ):
        value = json.loads(payloads[name])
        value[key] = version
        if drift and name == "docs/spytial-language.json":
            value["unexpectedNewSection"] = {}
        payloads[name] = json.dumps(value).encode()
    path = tmp_path / "release.tgz"
    with tarfile.open(path, "w:gz") as tar:
        for name, data in payloads.items():
            if name == missing:
                continue
            entry = tarfile.TarInfo("package/" + name)
            entry.size = len(data)
            tar.addfile(entry, io.BytesIO(data))
    return path


def snapshot(root):
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and p.suffix != ".tgz"
    }


def test_update_moves_all_artifacts_and_pin_together(checkout):
    release, updates = vendor_core.prepare(archive(checkout, "6.6.1"), checkout)
    vendor_core.install(updates, checkout)
    assert release == vendor_lock.pinned_version(checkout) == "6.6.1"
    assert vendor_lock.verify(checkout) == []
    assert "6.6.1" in (checkout / "spytial/_spec_tables.py").read_text()
    assert set(vendor_lock.VENDORED_FILES) <= set(updates)


def test_same_version_repairs_missing_and_stale_files(checkout):
    tarball = archive(checkout)
    _, updates = vendor_core.prepare(tarball, checkout)
    vendor_core.install(updates, checkout)
    expected = snapshot(checkout)
    (checkout / "spytial/_vendor/browser/react-component-integration.css").unlink()
    (checkout / "spytial/_vendor/browser/spytial-core-complete.global.js").write_text(
        "stale"
    )
    assert vendor_lock.verify(checkout)
    _, updates = vendor_core.prepare(tarball, checkout)
    vendor_core.install(updates, checkout)
    assert snapshot(checkout) == expected
    vendor_core.install(vendor_core.prepare(tarball, checkout)[1], checkout)
    assert snapshot(checkout) == expected


def test_missing_artifact_does_not_move_pin_or_existing_files(checkout):
    before = snapshot(checkout)
    with pytest.raises(ValueError, match="missing"):
        vendor_core.prepare(
            archive(
                checkout,
                "6.6.1",
                missing="dist/components/react-component-integration.css",
            ),
            checkout,
        )
    assert snapshot(checkout) == before


def test_requested_version_must_match_archive(checkout):
    with pytest.raises(ValueError, match="Requested"):
        vendor_core.prepare(archive(checkout), checkout, version="6.6.1")


def test_unknown_language_does_not_partially_update(checkout):
    before = snapshot(checkout)
    with pytest.raises(vendor_core.generate_spec_tables.ManifestDrift):
        vendor_core.prepare(archive(checkout, "6.6.1", drift=True), checkout)
    assert snapshot(checkout) == before


def test_lock_rejects_an_omitted_browser_asset(checkout):
    vendor_core.install(vendor_core.prepare(archive(checkout), checkout)[1], checkout)
    path = checkout / "spytial/_vendor/VENDORED.json"
    lock = json.loads(path.read_text())
    del lock["files"]["spytial/_vendor/browser/react-component-integration.css"]
    path.write_text(json.dumps(lock))
    assert vendor_lock.verify(checkout)


@pytest.mark.parametrize("name,field", vendor_lock.VERSION_METADATA.items())
def test_regenerated_lock_rejects_mismatched_release_metadata(checkout, name, field):
    vendor_core.install(vendor_core.prepare(archive(checkout), checkout)[1], checkout)
    metadata_path = checkout / name
    metadata = json.loads(metadata_path.read_text())
    metadata[field] = "6.6.1"
    metadata_path.write_text(json.dumps(metadata))
    # Rehashing the copied artifacts must not bless a mixed release.
    (checkout / "spytial/_vendor/VENDORED.json").write_text(
        json.dumps(vendor_lock.capture(root=checkout))
    )
    assert vendor_lock.verify(checkout) == [f"{name} comes from a different release"]
    wheel_path = checkout / "mixed-release.whl"
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        for path in (checkout / "spytial").rglob("*"):
            if path.is_file():
                wheel.write(path, path.relative_to(checkout))
    assert vendor_lock.verify_wheel(wheel_path) == [
        f"Wheel artifact comes from a different release: {name}"
    ]


def test_write_failure_restores_previous_release(checkout, monkeypatch):
    vendor_core.install(vendor_core.prepare(archive(checkout), checkout)[1], checkout)
    before = snapshot(checkout)
    _, updates = vendor_core.prepare(archive(checkout, "6.6.1"), checkout)
    original = Path.write_bytes
    failed = False

    def failing_write(path, data):
        nonlocal failed
        if path.name == "core_assets.py" and not failed:
            failed = True
            raise OSError("simulated write failure")
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", failing_write)
    with pytest.raises(OSError, match="simulated"):
        vendor_core.install(updates, checkout)
    assert snapshot(checkout) == before

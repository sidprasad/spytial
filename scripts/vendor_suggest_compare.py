"""Build/copy the experimental comparison bridge from a local core checkout.

Run core's npm run build:conformance first, then:
    python scripts/vendor_suggest_compare.py ../spytial-core
The development provenance is separate from the released-asset vendor lock.
"""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

core = Path(sys.argv[1]).resolve()
source = core / "dist/cli/spytial-compare.js"
destination = Path(__file__).resolve().parents[1] / "spytial/suggest/_vendor"
shutil.copyfile(source, destination / source.name)
metadata = {
    "artifact": source.name,
    "spytialCoreVersion": json.loads((core / "package.json").read_text())["version"],
    "sourceRevision": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=core, text=True
    ).strip(),
    "developmentBuild": True,
    "sourceFiles": {
        name: hashlib.sha256((core / name).read_bytes()).hexdigest()
        for name in ["src/cli/spytial-compare.ts", "src/layout/compare-programs.ts"]
    },
    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
}
(destination / "comparison-build.json").write_text(
    json.dumps(metadata, indent=2) + "\n"
)

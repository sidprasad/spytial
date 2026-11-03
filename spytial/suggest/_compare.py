"""Host adapter for core's whole-program comparison (no layout semantics here)."""

import json
import os
from pathlib import Path
import subprocess

from ._eval import _node_bin


def compare(datum, a, b):
    node = _node_bin()
    bridge = Path(
        os.environ.get(
            "SPYTIAL_COMPARE", Path(__file__).parent / "_vendor" / "spytial-compare.js"
        )
    )
    if not node or not bridge.is_file():
        raise RuntimeError(
            "Interactive suggest needs Node and the spytial-compare bridge. "
            "Set SPYTIAL_NODE / SPYTIAL_COMPARE if needed."
        )
    try:
        result = subprocess.run(
            [node, str(bridge)],
            input=json.dumps({"datum": datum, "a": a, "b": b}),
            capture_output=True,
            text=True,
            timeout=20,
        )
        reply = json.loads(result.stdout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("The layout comparison exceeded its time limit.") from exc
    except (OSError, ValueError) as exc:
        raise RuntimeError("The layout comparison could not run.") from exc
    if not isinstance(reply, dict):
        raise RuntimeError("The layout comparison returned an invalid response.")
    if reply.get("status") == "error":
        raise ValueError(
            reply.get("message", "The proposed program could not be checked.")
        )
    if result.returncode:
        raise RuntimeError("The layout comparison process failed.")
    if reply.get("status") not in {
        "different",
        "no-difference",
        "infeasible",
        "unsupported",
    }:
        raise RuntimeError("The layout comparison returned an unknown status.")
    if reply["status"] == "different" and (
        not isinstance(reply.get("sides"), list)
        or len(reply["sides"]) != 2
        or any(
            not isinstance(side, dict) or not isinstance(side.get("program"), dict)
            for side in reply["sides"]
        )
    ):
        raise RuntimeError("The layout comparison did not return two witnesses.")
    return reply

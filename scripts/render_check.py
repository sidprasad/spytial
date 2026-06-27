#!/usr/bin/env python3
"""Render ``spytial.suggest`` output through headless Chrome to confirm the
generated specs actually lay out — not just that their selectors *parse*.

A selector can be well-formed yet draw the wrong thing (e.g. orienting the
intermediate ``list`` atom instead of the children). The only way to catch that
is to render it. This script applies ``suggest`` to a set of canonical fixtures,
renders each with ``spytial.diagram(method="file")``, loads it in headless
Chrome, and reports any severe console error or an empty render. It saves a
screenshot per fixture so the layout can be eyeballed.

Not run in CI — it needs a real browser and the spytial-core CDN. Run it locally
when adding or changing a structural heuristic::

    pip install -e ".[headless]"          # selenium + a local Chrome/Chromedriver
    python scripts/render_check.py                 # screenshots -> ./_render_check/
    python scripts/render_check.py /tmp/shots       # custom output dir

Exits non-zero if any fixture errors or renders nothing, so it can gate a change.
"""

from __future__ import annotations

import pathlib
import sys
import time

import spytial
from spytial.suggest import suggest


# --------------------------------------------------------------------------- #
# Fixtures — one per structural pattern the heuristics target.
# --------------------------------------------------------------------------- #


def _fixtures():
    class BinTree:
        def __init__(self, value, left=None, right=None):
            self.value, self.left, self.right = value, left, right

    bt = BinTree(10, BinTree(5, BinTree(3), BinTree(7)), BinTree(15, BinTree(12)))

    class NaryTree:
        def __init__(self, value, children=None):
            self.value, self.children = value, children or []

    nary = NaryTree(
        "root",
        [NaryTree("a", [NaryTree("a1"), NaryTree("a2")]), NaryTree("b"), NaryTree("c")],
    )

    class LinkedList:
        def __init__(self, val, nxt=None):
            self.val, self.nxt = val, nxt

    ll = LinkedList(1, LinkedList(2, LinkedList(3)))

    class ArrayStack:
        def __init__(self):
            self.A, self.top = [], -1

    stack = ArrayStack()
    stack.A, stack.top = [10, 20, 30, 40], 3

    return [
        ("binary_tree", BinTree, bt),
        ("nary_tree", NaryTree, nary),
        ("linked_list", LinkedList, ll),
        ("array_stack", ArrayStack, stack),
    ]


# --------------------------------------------------------------------------- #
# Headless render + inspect
# --------------------------------------------------------------------------- #


def _render(html_path: str, shot_path: str, wait: float = 9.0) -> dict:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By

    opts = Options()
    for flag in (
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--window-size=1300,900",
    ):
        opts.add_argument(flag)
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(pathlib.Path(html_path).as_uri())
        time.sleep(wait)  # CDN load + constraint solve
        body = driver.find_element(By.TAG_NAME, "body").text
        logs = driver.get_log("browser")
        errors = [
            log["message"][:200] for log in logs if log["level"] in ("SEVERE", "ERROR")
        ]
        driver.save_screenshot(shot_path)
        return {"rendered": bool(body.strip()), "errors": errors, "shot": shot_path}
    finally:
        driver.quit()


def main(argv) -> int:
    out_dir = pathlib.Path(argv[1] if len(argv) > 1 else "_render_check")
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = True
    for name, cls, instance in _fixtures():
        suggest(cls, instance=instance).apply()
        html = spytial.diagram(instance, method="file")
        shot = str(out_dir / f"{name}.png")
        result = _render(html, shot)
        status = "ok"
        if result["errors"]:
            status, ok = "ERROR", False
        elif not result["rendered"]:
            status, ok = "EMPTY", False
        print(f"  [{status:5}] {name:14} -> {result['shot']}")
        for err in result["errors"][:3]:
            print(f"          {err}")

    print("\nrender-check:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env python3
"""Generate starter sPyTial integration snippets for common data shapes."""

from __future__ import annotations

import argparse
from pathlib import Path
import textwrap


TEMPLATES = {
    "linked-list": textwrap.dedent(
        """\
        import spytial


        @spytial.orientation(selector="next", directions=["directlyRight"])
        @spytial.attribute(field="data")
        class Node:
            def __init__(self, data, nxt=None):
                self.data = data
                self.next = nxt


        head = Node(1, Node(2, Node(3)))

        # Validate serialized structure first.
        spytial.evaluate(head)
        # Then inspect layout.
        spytial.diagram(head)
        """
    ),
    "tree": textwrap.dedent(
        """\
        import spytial


        @spytial.orientation(selector="left & (TreeNode->TreeNode)", directions=["below", "left"])
        @spytial.orientation(selector="right & (TreeNode->TreeNode)", directions=["below", "right"])
        @spytial.attribute(field="key")
        class TreeNode:
            def __init__(self, key, left=None, right=None):
                self.key = key
                self.left = left
                self.right = right


        root = TreeNode(8, TreeNode(3, TreeNode(1), TreeNode(6)), TreeNode(10, None, TreeNode(14)))

        spytial.evaluate(root)
        spytial.diagram(root)
        """
    ),
    "graph": textwrap.dedent(
        """\
        import spytial


        class GNode:
            def __init__(self, key):
                self.key = key
                self.neighbors = []


        a, b, c = GNode("A"), GNode("B"), GNode("C")
        a.neighbors = [b, c]
        b.neighbors = [c]
        c.neighbors = [a]
        nodes = [a, b, c]

        graph = spytial.inferredEdge(
            selector="{x : GNode, y : GNode | y in x.neighbors}",
            name="edge",
        )(nodes)
        graph = spytial.hideAtom(selector="list")(graph)

        spytial.evaluate(graph)
        spytial.diagram(graph)
        """
    ),
    "matrix": textwrap.dedent(
        """\
        import spytial


        class Cell:
            def __init__(self, row, col, value):
                self.row = row
                self.col = col
                self.value = value


        class MatrixWrapper:
            def __init__(self, rows, cols):
                self.cells = [Cell(r, c, r * cols + c) for r in range(rows) for c in range(cols)]


        SAME_ROW = "{a, b : Cell | a.row = b.row and a != b}"
        SAME_COL = "{a, b : Cell | a.col = b.col and a != b}"
        NEXT_ROW = "{a, b : Cell | @num:(a.row) + 1 = @num:(b.row) and a.col = b.col}"
        NEXT_COL = "{a, b : Cell | @num:(a.col) + 1 = @num:(b.col) and a.row = b.row}"


        @spytial.align(selector=SAME_ROW, direction="horizontal")
        @spytial.align(selector=SAME_COL, direction="vertical")
        @spytial.orientation(selector=NEXT_ROW, directions=["below"])
        @spytial.orientation(selector=NEXT_COL, directions=["right"])
        @spytial.attribute(field="value")
        class MatrixView(MatrixWrapper):
            pass


        matrix = MatrixView(3, 4)
        spytial.evaluate(matrix)
        spytial.diagram(matrix)
        """
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate starter sPyTial integration code for a common data shape."
    )
    parser.add_argument(
        "--shape",
        choices=sorted(TEMPLATES.keys()),
        required=True,
        help="Starter template to generate.",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output Python file path.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output file if it already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)

    if out_path.exists() and not args.force:
        print(f"Refusing to overwrite existing file: {out_path}")
        print("Pass --force to overwrite.")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(TEMPLATES[args.shape], encoding="utf-8")
    print(f"Generated {args.shape} starter at {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

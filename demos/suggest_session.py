"""Run `python -m demos.suggest_session` for the combined critique loop.

Requires Node, Hypothesis, and an authenticated Codex CLI. See the notebook
06-suggest-session.ipynb for the same workflow with embedded diagrams.
"""

from dataclasses import dataclass
from typing import Optional

from hypothesis import strategies as st
from spytial.suggest import suggest


@dataclass
class Tree:
    value: int
    left: Optional["Tree"] = None
    right: Optional["Tree"] = None


def trees(depth):
    children = st.none() if depth == 0 else st.one_of(st.none(), trees(depth - 1))
    return st.builds(Tree, value=st.integers(0, 20), left=children, right=children)


if __name__ == "__main__":
    example = Tree(8, Tree(3, Tree(1), Tree(6)), Tree(10, None, Tree(14)))
    with suggest(
        Tree,
        examples=[example],
        strategy=trees(2),
        max_examples=10,
    ) as session:
        session.show()
        input("Add a property in the browser, then drag and judge. Press Enter here to close controls. ")

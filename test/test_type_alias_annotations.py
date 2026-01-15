"""
Test suite for type alias annotations in spytial using typing.Annotated.
"""

import pytest
from typing import Annotated, Dict, List
import spytial


class TestAnnotatedTypeAliases:
    """Tests for the typing.Annotated-based type alias annotation system."""

    def test_basic_orientation_annotation(self):
        """Test basic Orientation annotation with Annotated."""
        IntList = Annotated[
            list[int], spytial.Orientation(selector="items", directions=["horizontal"])
        ]

        annotations = spytial.extract_spytial_annotations(IntList)
        assert annotations is not None
        assert len(annotations["constraints"]) == 1
        assert annotations["constraints"][0]["orientation"]["directions"] == [
            "horizontal"
        ]

    def test_multiple_annotations(self):
        """Test multiple annotations on same type."""
        StyledList = Annotated[
            list[str],
            spytial.Orientation(selector="items", directions=["vertical"]),
            spytial.AtomColor(selector="self", value="blue"),
            spytial.Size(selector="items", height=50, width=100),
        ]

        annotations = spytial.extract_spytial_annotations(StyledList)
        assert len(annotations["constraints"]) == 1  # Orientation
        assert len(annotations["directives"]) == 2  # AtomColor, Size

    def test_all_constraint_classes(self):
        """Test all constraint annotation classes."""
        ann1 = spytial.Orientation(selector="x", directions=["left"])
        assert ann1._annotation_type == "orientation"
        assert ann1._is_constraint is True

        ann2 = spytial.Cyclic(selector="x", direction="clockwise")
        assert ann2._annotation_type == "cyclic"

        ann3 = spytial.Align(selector="x", direction="left")
        assert ann3._annotation_type == "align"

        ann4 = spytial.Group(field="children", groupOn=0, addToGroup=1)
        assert ann4._annotation_type == "group"

    def test_all_directive_classes(self):
        """Test all directive annotation classes."""
        directives = [
            spytial.AtomColor(selector="x", value="red"),
            spytial.Size(selector="x", height=10, width=10),
            spytial.Icon(selector="x", path="icon.svg"),
            spytial.EdgeColor(field="edge", value="blue"),
            spytial.HideField(field="_private"),
            spytial.HideAtom(selector="hidden"),
            spytial.Projection(sig="MySig"),
            spytial.Attribute(field="value"),
            spytial.InferredEdge(name="link", selector="nodes"),
            spytial.Flag(name="debug"),
        ]

        for d in directives:
            assert d._is_constraint is False

    def test_get_base_type(self):
        """Test get_base_type helper function."""
        StyledList = Annotated[
            list[str],
            spytial.AtomColor(selector="self", value="blue"),
        ]

        base = spytial.get_base_type(StyledList)
        assert base == list[str]

        # Non-annotated type returns itself
        plain = list[int]
        assert spytial.get_base_type(plain) == list[int]

    def test_non_annotated_returns_none(self):
        """Test that non-annotated types return None."""
        plain_list = list[int]
        annotations = spytial.extract_spytial_annotations(plain_list)
        assert annotations is None

    def test_annotation_repr(self):
        """Test annotation repr for debugging."""
        ann = spytial.Orientation(selector="items", directions=["horizontal"])
        repr_str = repr(ann)
        assert "Orientation" in repr_str
        assert "items" in repr_str
        assert "horizontal" in repr_str

    def test_complex_nested_types(self):
        """Test annotations on complex nested types."""
        TreeDict = Annotated[
            Dict[str, List[int]],
            spytial.Orientation(selector="values", directions=["below"]),
            spytial.HideField(field="_metadata"),
        ]

        annotations = spytial.extract_spytial_annotations(TreeDict)
        assert annotations is not None
        assert len(annotations["constraints"]) == 1
        assert len(annotations["directives"]) == 1

    def test_to_entry_format(self):
        """Test that to_entry produces correct format."""
        ann = spytial.Orientation(selector="items", directions=["horizontal"])
        entry = ann.to_entry()

        assert entry == {"orientation": {"selector": "items", "directions": ["horizontal"]}}

    def test_flag_to_entry_special_format(self):
        """Test that Flag directive uses scalar format."""
        flag = spytial.Flag(name="debug")
        entry = flag.to_entry()

        # Flag uses scalar format, not dict
        assert entry == {"flag": "debug"}

    def test_optional_parameters(self):
        """Test annotations with optional parameters."""
        # EdgeColor with optional selector
        ec1 = spytial.EdgeColor(field="children", value="red")
        assert "selector" not in ec1.kwargs

        ec2 = spytial.EdgeColor(field="children", value="red", selector="Tree")
        assert ec2.kwargs["selector"] == "Tree"

        # InferredEdge with optional color
        ie1 = spytial.InferredEdge(name="link", selector="nodes")
        assert "color" not in ie1.kwargs

        ie2 = spytial.InferredEdge(name="link", selector="nodes", color="blue")
        assert ie2.kwargs["color"] == "blue"


class TestLegacyTypeAliasRegistry:
    """Tests for backward compatibility with legacy registry-based system."""

    def setup_method(self):
        """Clear legacy registry before each test."""
        spytial.clear_type_alias_annotations()

    def test_legacy_annotate_type_alias(self):
        """Test legacy annotate_type_alias function still works."""
        IntList = list[int]
        spytial.annotate_type_alias(
            IntList, "orientation", selector="items", directions=["horizontal"]
        )
        annotations = spytial.get_type_alias_annotations(IntList)

        assert annotations is not None
        assert len(annotations["constraints"]) == 1

    def test_legacy_clear(self):
        """Test legacy clear function."""
        IntList = list[int]
        spytial.annotate_type_alias(
            IntList, "atomColor", selector="self", value="red"
        )

        spytial.clear_type_alias_annotations(IntList)
        assert spytial.get_type_alias_annotations(IntList) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

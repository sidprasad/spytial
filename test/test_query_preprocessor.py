"""
Test suite for the Query Preprocessor module.

Tests the new @: operator syntax and ensures == operator is properly rejected.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spytial.query_preprocessor import QueryPreprocessor, preprocess_selector, validate_selector


def test_basic_label_operator():
    """Test basic @: operator transformation."""
    print("=== Testing Basic @: Operator ===")
    
    # Test single @: operator
    selector = "{ x : RBTreeNode | @:(x.color) = black }"
    expected = "{ x : RBTreeNode | getLabelForValue(x.color) = black }"
    result = preprocess_selector(selector)
    
    print(f"Input:    {selector}")
    print(f"Expected: {expected}")
    print(f"Result:   {result}")
    
    assert result == expected, f"Expected '{expected}', got '{result}'"
    print("✓ Basic @: operator transformation works")
    print()


def test_multiple_label_operators():
    """Test multiple @: operators in same selector."""
    print("=== Testing Multiple @: Operators ===")
    
    selector = "{ x, y : Node | @:(x.v) = @:(y.v) }"
    expected = "{ x, y : Node | getLabelForValue(x.v) = getLabelForValue(y.v) }"
    result = preprocess_selector(selector)
    
    print(f"Input:    {selector}")
    print(f"Expected: {expected}")
    print(f"Result:   {result}")
    
    assert result == expected, f"Expected '{expected}', got '{result}'"
    print("✓ Multiple @: operators work")
    print()


def test_mixed_operators():
    """Test mixing @: operators with regular expressions."""
    print("=== Testing Mixed Operators ===")
    
    # @: operator mixed with regular field access
    selector = "{ x : RBTreeNode | @:(x.color) = red and x.value = 10 }"
    expected = "{ x : RBTreeNode | getLabelForValue(x.color) = red and x.value = 10 }"
    result = preprocess_selector(selector)
    
    print(f"Input:    {selector}")
    print(f"Expected: {expected}")
    print(f"Result:   {result}")
    
    assert result == expected, f"Expected '{expected}', got '{result}'"
    print("✓ Mixed operators work")
    print()


def test_equals_operator_rejection():
    """Test that == operator is properly rejected."""
    print("=== Testing == Operator Rejection ===")
    
    selectors_with_equals = [
        "{ x : Node | x.value == 5 }",
        "{ x, y : Node | x.id == y.id }",
        "{ x : RBTreeNode | x.color == \"red\" }"
    ]
    
    for selector in selectors_with_equals:
        try:
            result = preprocess_selector(selector)
            assert False, f"Expected ValueError for selector with ==: {selector}"
        except ValueError as e:
            print(f"✓ Correctly rejected: {selector}")
            print(f"  Error: {str(e)}")
        except Exception as e:
            assert False, f"Unexpected error type for {selector}: {type(e).__name__}: {e}"
    
    print("✓ == operator rejection works")
    print()


def test_no_transformation_needed():
    """Test selectors that don't need transformation."""
    print("=== Testing No Transformation Cases ===")
    
    selectors = [
        "{ x : RBTreeNode | x.color = red }",  # Regular comparison
        "{ x : Node | x.left = y }",  # Regular field access
        "items",  # Simple field selector
        "",  # Empty selector
        "{ x : Node | x.value > 5 and x.active = true }",  # Complex without @:
    ]
    
    for selector in selectors:
        result = preprocess_selector(selector)
        print(f"Input:  {selector}")
        print(f"Result: {result}")
        assert result == selector, f"Selector should not be modified: {selector}"
        print("✓ No change (correct)")
        print()


def test_complex_expressions():
    """Test complex expressions with @: operator."""
    print("=== Testing Complex Expressions ===")
    
    # Complex field access in @: operator
    selector = "{ x : Tree | @:(x.node.color.value) = red }"
    expected = "{ x : Tree | getLabelForValue(x.node.color.value) = red }"
    result = preprocess_selector(selector)
    
    print(f"Input:    {selector}")
    print(f"Expected: {expected}")
    print(f"Result:   {result}")
    
    assert result == expected, f"Expected '{expected}', got '{result}'"
    print("✓ Complex expressions work")
    print()


def test_validation():
    """Test selector validation."""
    print("=== Testing Selector Validation ===")
    
    valid_selectors = [
        "{ x : Node | x.value = 5 }",
        "items",
        "",
        "{ x, y : Tree | x.left = y }",
        "{ x : RBTreeNode | @:(x.color) = black }"
    ]
    
    for selector in valid_selectors:
        assert validate_selector(selector), f"Should be valid: {selector}"
        print(f"✓ Valid: {selector}")
    
    print("✓ Selector validation works")
    print()


def run_all_tests():
    """Run all test functions."""
    print("Testing Query Preprocessor")
    print("=" * 50)
    
    test_basic_label_operator()
    test_multiple_label_operators()
    test_mixed_operators()
    test_equals_operator_rejection()
    test_no_transformation_needed()
    test_complex_expressions()
    test_validation()
    
    print("🎉 All query preprocessor tests passed!")


if __name__ == "__main__":
    run_all_tests()
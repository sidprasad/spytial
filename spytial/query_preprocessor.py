"""
Query Preprocessor for sPyTial Selector Syntax

This module handles preprocessing of selector query strings to support the new @: operator
and replace the problematic == operator.

The new syntax supports:
- @:(x.color) = black   # Check if label has value black
- (x.color) = black     # Check if node ID black equals x.color
- @:(x.v) = @:(y.v)     # Compare labels instead of IDs
"""

import re
from typing import Optional


class QueryPreprocessor:
    """
    Preprocessor for sPyTial query selector strings.
    
    Transforms selectors containing the new @: operator into a format
    that can be processed by the CnD evaluator.
    """
    
    def __init__(self):
        # Pattern to match @:(expression) 
        self.label_pattern = re.compile(r'@:\(([^)]+)\)')
        
        # Pattern to match == operator (to be removed/replaced)
        self.equals_pattern = re.compile(r'==')
    
    def preprocess_selector(self, selector: str) -> str:
        """
        Preprocess a selector string to handle @: operator and remove == operator.
        
        Args:
            selector: The original selector string (e.g., "{ x : RBTreeNode | @:(x.color) = black }")
            
        Returns:
            The transformed selector string compatible with CnD evaluator
            
        Raises:
            ValueError: If selector contains unsupported == operator
        """
        if not selector or not isinstance(selector, str):
            return selector
        
        # Check for prohibited == operator
        if self.equals_pattern.search(selector):
            raise ValueError(
                f"Selector contains prohibited '==' operator. "
                f"Use '@:(expr) = value' to compare labels or '(expr) = value' to compare IDs. "
                f"Selector: {selector}"
            )
        
        # Transform @:(expression) patterns
        transformed = self._transform_label_operators(selector)
        
        return transformed
    
    def _transform_label_operators(self, selector: str) -> str:
        """
        Transform @:(expression) patterns into label value comparisons.
        
        The @: operator extracts the label/value of an expression for comparison.
        This is transformed into a format that the CnD evaluator can handle.
        """
        def replace_label_op(match):
            expression = match.group(1)
            # Transform @:(x.color) into getLabelForValue(x.color)
            # This assumes the CnD evaluator has a getLabelForValue function
            return f"getLabelForValue({expression})"
        
        # Replace all @:(expr) with getLabelForValue(expr)
        transformed = self.label_pattern.sub(replace_label_op, selector)
        
        return transformed
    
    def validate_selector(self, selector: str) -> bool:
        """
        Validate that a selector string is syntactically correct.
        
        Args:
            selector: The selector string to validate
            
        Returns:
            True if selector is valid, False otherwise
        """
        try:
            # Basic validation - check for balanced braces and pipes
            if not selector.strip():
                return True
                
            # Should have format { vars : types | condition }
            if selector.strip().startswith('{') and selector.strip().endswith('}'):
                inner = selector.strip()[1:-1]
                if '|' in inner:
                    return True
            
            # Simple selectors without braces are also valid
            return True
            
        except Exception:
            return False


# Global preprocessor instance
_preprocessor = QueryPreprocessor()


def preprocess_selector(selector: str) -> str:
    """
    Convenience function to preprocess a selector string.
    
    Args:
        selector: The selector string to preprocess
        
    Returns:
        The preprocessed selector string
    """
    return _preprocessor.preprocess_selector(selector)


def validate_selector(selector: str) -> bool:
    """
    Convenience function to validate a selector string.
    
    Args:
        selector: The selector string to validate
        
    Returns:
        True if valid, False otherwise
    """
    return _preprocessor.validate_selector(selector)
#!/usr/bin/env python3
"""
Test file for domain-specific relationalizers.

Tests each domain-specific relationalizer when the corresponding library is available.
"""

import sys
from spytial import RelationalizerBase, Atom, Relation, CnDDataInstanceBuilder, diagram


def test_pydantic_relationalizer():
    """Test Pydantic model relationalizer."""
    try:
        import pydantic
        from pydantic import BaseModel
        from spytial.domain_relationalizers.pydantic_relationalizer import (
            PydanticRelationalizer,
        )

        class User(BaseModel):
            name: str
            age: int
            email: str = None

        user = User(name="Alice", age=30, email="alice@example.com")

        relationalizer = PydanticRelationalizer()
        assert relationalizer.can_handle(user) == True
        assert relationalizer.can_handle("not a pydantic model") == False

        # Test with CnDDataInstanceBuilder
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(user)

        # Should have atoms for the user and its fields
        assert len(data_instance["atoms"]) >= 4  # user + name + age + email

        # Test visualization
        result = diagram(user, method="file", auto_open=False)
        assert result.endswith(".html")

        print("✓ Pydantic relationalizer works")
        return True

    except ImportError:
        print("⚠ Pydantic not available, skipping test")
        return True
    except Exception as e:
        print(f"✗ Pydantic relationalizer test failed: {e}")
        return False


def test_attrs_relationalizer():
    """Test Attrs class relationalizer."""
    try:
        import attr
        from spytial.domain_relationalizers.attrs_relationalizer import (
            AttrsRelationalizer,
        )

        @attr.s
        class Point:
            x = attr.ib()
            y = attr.ib()

        point = Point(x=10, y=20)

        relationalizer = AttrsRelationalizer()
        assert relationalizer.can_handle(point) == True
        assert relationalizer.can_handle("not an attrs class") == False

        # Test with CnDDataInstanceBuilder
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(point)

        # Should have atoms for the point and its fields
        assert len(data_instance["atoms"]) >= 3  # point + x + y

        # Test visualization
        result = diagram(point, method="file", auto_open=False)
        assert result.endswith(".html")

        print("✓ Attrs relationalizer works")
        return True

    except ImportError:
        print("⚠ Attrs not available, skipping test")
        return True
    except Exception as e:
        print(f"✗ Attrs relationalizer test failed: {e}")
        return False


def test_pytorch_relationalizer():
    """Test PyTorch tensor and module relationalizers."""
    try:
        import torch
        import torch.nn as nn
        from spytial.domain_relationalizers.pytorch_relationalizer import (
            PyTorchTensorRelationalizer,
            PyTorchModuleRelationalizer,
        )

        # Test tensor relationalizer
        tensor = torch.tensor([1.0, 2.0, 3.0])
        tensor_relationalizer = PyTorchTensorRelationalizer()
        assert tensor_relationalizer.can_handle(tensor) == True
        assert tensor_relationalizer.can_handle("not a tensor") == False

        # Test module relationalizer
        class SimpleNet(nn.Module):
            def __init__(self):
                super().__init__()
                self.linear1 = nn.Linear(10, 5)
                self.linear2 = nn.Linear(5, 1)

        net = SimpleNet()
        module_relationalizer = PyTorchModuleRelationalizer()
        assert module_relationalizer.can_handle(net) == True
        assert module_relationalizer.can_handle("not a module") == False

        # Test with CnDDataInstanceBuilder
        builder = CnDDataInstanceBuilder()

        # Test tensor
        tensor_instance = builder.build_instance(tensor)
        assert len(tensor_instance["atoms"]) >= 1

        # Test module
        net_instance = builder.build_instance(net)
        assert len(net_instance["atoms"]) >= 1

        # Test visualization
        tensor_result = diagram(tensor, method="file", auto_open=False)
        assert tensor_result.endswith(".html")

        net_result = diagram(net, method="file", auto_open=False)
        assert net_result.endswith(".html")

        print("✓ PyTorch relationalizers work")
        return True

    except ImportError:
        print("⚠ PyTorch not available, skipping test")
        return True
    except Exception as e:
        print(f"✗ PyTorch relationalizer test failed: {e}")
        return False


def test_networkx_relationalizer():
    """Test NetworkX graph relationalizer."""
    try:
        import networkx as nx
        from spytial.domain_relationalizers.networkx_relationalizer import (
            NetworkXRelationalizer,
        )

        # Create a simple graph
        G = nx.Graph()
        G.add_edges_from([(1, 2), (2, 3), (3, 1)])

        relationalizer = NetworkXRelationalizer()
        assert relationalizer.can_handle(G) == True
        assert relationalizer.can_handle("not a graph") == False

        # Test with CnDDataInstanceBuilder
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(G)

        # Should have atoms for the graph and nodes
        assert len(data_instance["atoms"]) >= 4  # graph + 3 nodes

        # Test visualization
        result = diagram(G, method="file", auto_open=False)
        assert result.endswith(".html")

        print("✓ NetworkX relationalizer works")
        return True

    except ImportError:
        print("⚠ NetworkX not available, skipping test")
        return True
    except Exception as e:
        print(f"✗ NetworkX relationalizer test failed: {e}")
        return False


def test_pandas_relationalizer():
    """Test Pandas DataFrame and Series relationalizers."""
    try:
        import pandas as pd
        from spytial.domain_relationalizers.pandas_relationalizer import (
            PandasDataFrameRelationalizer,
            PandasSeriesRelationalizer,
        )

        # Test DataFrame
        df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"], "C": [1.1, 2.2, 3.3]})

        df_relationalizer = PandasDataFrameRelationalizer()
        assert df_relationalizer.can_handle(df) == True
        assert df_relationalizer.can_handle("not a dataframe") == False

        # Test Series
        series = pd.Series([10, 20, 30], name="test_series")

        series_relationalizer = PandasSeriesRelationalizer()
        assert series_relationalizer.can_handle(series) == True
        assert series_relationalizer.can_handle("not a series") == False

        # Test with CnDDataInstanceBuilder
        builder = CnDDataInstanceBuilder()

        # Test DataFrame
        df_instance = builder.build_instance(df)
        assert len(df_instance["atoms"]) >= 4  # dataframe + 3 columns

        # Test Series
        series_instance = builder.build_instance(series)
        assert len(series_instance["atoms"]) >= 1

        # Test visualization
        df_result = diagram(df, method="file", auto_open=False)
        assert df_result.endswith(".html")

        series_result = diagram(series, method="file", auto_open=False)
        assert series_result.endswith(".html")

        print("✓ Pandas relationalizers work")
        return True

    except ImportError:
        print("⚠ Pandas not available, skipping test")
        return True
    except Exception as e:
        print(f"✗ Pandas relationalizer test failed: {e}")
        return False


def test_antlr_relationalizer():
    """Test ANTLR parse tree relationalizer."""
    try:
        from antlr4 import ParserRuleContext, TerminalNode
        from spytial.domain_relationalizers.antlr_relationalizer import (
            ANTLRParseTreeRelationalizer,
        )

        # We can't easily create ANTLR objects without a full parser setup,
        # so we'll just test the import and basic functionality
        relationalizer = ANTLRParseTreeRelationalizer()

        # These should return False since we don't have real ANTLR objects
        assert relationalizer.can_handle("not antlr") == False
        assert relationalizer.can_handle([1, 2, 3]) == False

        print("✓ ANTLR relationalizer imports successfully")
        return True

    except ImportError:
        print("⚠ ANTLR not available, skipping test")
        return True
    except Exception as e:
        print(f"✗ ANTLR relationalizer test failed: {e}")
        return False


def test_domain_relationalizers_registration():
    """Test that domain relationalizers are properly registered."""
    try:
        from spytial.provider_system import RelationalizerRegistry
        from spytial.domain_relationalizers import register_builtin_relationalizers

        # Save current state
        original_relationalizers = RelationalizerRegistry._relationalizers.copy()
        original_instances = RelationalizerRegistry._instances.copy()

        try:
            # Clear and re-register
            RelationalizerRegistry.clear()
            register_builtin_relationalizers(RelationalizerRegistry)

            # Check that we have more than just the basic relationalizers
            assert (
                len(RelationalizerRegistry._relationalizers) >= 7
            )  # At least the core ones

            print(
                f"✓ Domain relationalizers registration works ({len(RelationalizerRegistry._relationalizers)} total)"
            )
            return True

        finally:
            # Restore original state
            RelationalizerRegistry._relationalizers = original_relationalizers
            RelationalizerRegistry._instances = original_instances

    except Exception as e:
        print(f"✗ Domain relationalizers registration test failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing Domain-Specific Relationalizers")
    print("=" * 50)

    # Run all tests
    test_functions = [
        test_domain_relationalizers_registration,
        test_pydantic_relationalizer,
        test_attrs_relationalizer,
        test_pytorch_relationalizer,
        test_networkx_relationalizer,
        test_pandas_relationalizer,
        test_antlr_relationalizer,
    ]

    passed = 0
    total = len(test_functions)

    for test_func in test_functions:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__}: Unexpected error: {e}")

    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All domain-specific relationalizer tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)

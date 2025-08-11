"""Relationalizer for Pandas DataFrames and Series."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None


class PandasDataFrameRelationalizer(RelationalizerBase):
    """Handles Pandas DataFrame objects."""

    def can_handle(self, obj: Any) -> bool:
        if not PANDAS_AVAILABLE:
            return False
        return isinstance(obj, pd.DataFrame)

    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)

        rows, cols = obj.shape
        label = f"DataFrame[{rows}×{cols}]"

        atom = Atom(id=obj_id, type="PandasDataFrame", label=label)

        relations = []

        # Add column information
        for col_name in obj.columns:
            col_series = obj[col_name]
            col_id = walker_func(col_series)
            relations.append(
                Relation(name=str(col_name), source_id=obj_id, target_id=col_id)
            )

        # For small DataFrames, we might want to show the index too
        if rows <= 10 and not obj.index.equals(pd.RangeIndex(rows)):
            # Non-default index
            index_id = walker_func(obj.index)
            relations.append(
                Relation(name="index", source_id=obj_id, target_id=index_id)
            )

        return atom, relations


class PandasSeriesRelationalizer(RelationalizerBase):
    """Handles Pandas Series objects."""

    def can_handle(self, obj: Any) -> bool:
        if not PANDAS_AVAILABLE:
            return False
        return isinstance(obj, pd.Series)

    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)

        length = len(obj)
        dtype_str = str(obj.dtype)
        name = obj.name if obj.name else "unnamed"

        label = f"Series[{length}] {name} ({dtype_str})"

        atom = Atom(id=obj_id, type="PandasSeries", label=label)

        relations = []

        # For small series, show some values
        if length <= 10:
            for idx, value in obj.items():
                try:
                    value_id = walker_func(value)
                    relations.append(
                        Relation(name=f"[{idx}]", source_id=obj_id, target_id=value_id)
                    )
                except Exception:
                    # Some values might not be serializable
                    pass
        else:
            # For large series, show head and tail
            try:
                # Show first few values
                for i, (idx, value) in enumerate(obj.head(3).items()):
                    value_id = walker_func(value)
                    relations.append(
                        Relation(name=f"[{idx}]", source_id=obj_id, target_id=value_id)
                    )

                # Add ellipsis indicator if we have more data
                if length > 6:
                    ellipsis_id = walker_func("...")
                    relations.append(
                        Relation(name="...", source_id=obj_id, target_id=ellipsis_id)
                    )

                # Show last few values
                for i, (idx, value) in enumerate(obj.tail(3).items()):
                    value_id = walker_func(value)
                    relations.append(
                        Relation(name=f"[{idx}]", source_id=obj_id, target_id=value_id)
                    )
            except Exception:
                # If we can't access values, just show summary stats
                try:
                    stats = obj.describe()
                    for stat_name, stat_value in stats.items():
                        stat_id = walker_func(stat_value)
                        relations.append(
                            Relation(
                                name=stat_name, source_id=obj_id, target_id=stat_id
                            )
                        )
                except Exception:
                    pass

        return atom, relations


class PandasIndexRelationalizer(RelationalizerBase):
    """Handles Pandas Index objects."""

    def can_handle(self, obj: Any) -> bool:
        if not PANDAS_AVAILABLE:
            return False
        return isinstance(obj, pd.Index)

    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)

        length = len(obj)
        index_type = type(obj).__name__
        name = obj.name if obj.name else "unnamed"

        label = f"{index_type}[{length}] {name}"

        atom = Atom(id=obj_id, type="PandasIndex", label=label)

        relations = []

        # For small indices, show values
        if length <= 10:
            for i, value in enumerate(obj):
                try:
                    value_id = walker_func(value)
                    relations.append(
                        Relation(name=f"[{i}]", source_id=obj_id, target_id=value_id)
                    )
                except Exception:
                    pass
        else:
            # For large indices, show start and end
            try:
                for i in range(min(3, length)):
                    value_id = walker_func(obj[i])
                    relations.append(
                        Relation(name=f"[{i}]", source_id=obj_id, target_id=value_id)
                    )

                if length > 6:
                    ellipsis_id = walker_func("...")
                    relations.append(
                        Relation(name="...", source_id=obj_id, target_id=ellipsis_id)
                    )

                for i in range(max(0, length - 3), length):
                    value_id = walker_func(obj[i])
                    relations.append(
                        Relation(name=f"[{i}]", source_id=obj_id, target_id=value_id)
                    )
            except Exception:
                pass

        return atom, relations

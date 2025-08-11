"""Relationalizer for NetworkX graphs."""

from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation

try:
    import networkx as nx

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None


class NetworkXRelationalizer(RelationalizerBase):
    """Handles NetworkX graph objects."""

    def can_handle(self, obj: Any) -> bool:
        if not NETWORKX_AVAILABLE:
            return False
        return isinstance(obj, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph))

    def relationalize(self, obj: Any, walker_func) -> Tuple[Atom, List[Relation]]:
        obj_id = walker_func._get_id(obj)

        # Determine graph type
        graph_type = type(obj).__name__
        num_nodes = obj.number_of_nodes()
        num_edges = obj.number_of_edges()

        label = f"{graph_type}({num_nodes} nodes, {num_edges} edges)"

        atom = Atom(id=obj_id, type="NetworkXGraph", label=label)

        relations = []

        # For small graphs, show the actual structure
        if num_nodes <= 20:  # Reasonable limit to avoid clutter
            # Create atoms for nodes
            for node in obj.nodes():
                node_id = walker_func(node)
                relations.append(
                    Relation(name="node", source_id=obj_id, target_id=node_id)
                )

            # Create relationships for edges
            for edge in obj.edges():
                if len(edge) >= 2:
                    source_node = edge[0]
                    target_node = edge[1]

                    source_id = walker_func(source_node)
                    target_id = walker_func(target_node)

                    # Create edge relation
                    edge_name = "edge"
                    if isinstance(obj, (nx.DiGraph, nx.MultiDiGraph)):
                        edge_name = "directed_edge"

                    relations.append(
                        Relation(
                            name=edge_name, source_id=source_id, target_id=target_id
                        )
                    )
        else:
            # For large graphs, just show some summary statistics
            try:
                # Add some graph properties as related data
                properties = {}

                if hasattr(obj, "is_connected") and obj.is_connected:
                    properties["connected"] = obj.is_connected()

                if hasattr(obj, "density"):
                    properties["density"] = round(nx.density(obj), 3)

                if hasattr(obj, "is_directed") and not obj.is_directed():
                    try:
                        properties["avg_clustering"] = round(
                            nx.average_clustering(obj), 3
                        )
                    except Exception:
                        pass

                for prop_name, prop_value in properties.items():
                    prop_id = walker_func(prop_value)
                    relations.append(
                        Relation(name=prop_name, source_id=obj_id, target_id=prop_id)
                    )

            except Exception:
                # If we can't compute properties, that's okay
                pass

        return atom, relations

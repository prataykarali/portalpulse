"""Dynamic Topological Dependency & Causal DAG for Arbitrary Portals.

Constructs a NetworkX Directed Acyclic Graph (DAG) dynamically from any
host portal's declared DependencyGraphSpec rather than hardcoding a static topology.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

from portalpulse_sdk.schema import DependencyGraphSpec, UniversalTelemetry


class DynamicTopologyDAG:
    """Dynamic NetworkX DAG constructed per connected portal."""

    def __init__(self, spec: Optional[DependencyGraphSpec] = None) -> None:
        self.spec = spec or DependencyGraphSpec()
        self.graph: nx.DiGraph = nx.DiGraph()
        self._build_graph()

    def _build_graph(self) -> None:
        """Construct the NetworkX DiGraph from the provided spec."""
        self.graph.clear()
        for node in self.spec.nodes:
            self.graph.add_node(node)

        for src, dst in self.spec.edges:
            self.graph.add_edge(src, dst)

        # Compute topological depth from entrypoint
        entrypoint = self.spec.entrypoint_node
        if entrypoint not in self.graph and self.spec.nodes:
            entrypoint = self.spec.nodes[0]

        self.node_depths: Dict[str, int] = {}
        for node in self.spec.nodes:
            if entrypoint in self.graph and nx.has_path(self.graph, entrypoint, node):
                self.node_depths[node] = nx.shortest_path_length(self.graph, entrypoint, node)
            else:
                self.node_depths[node] = 0

    def update_spec(self, spec: DependencyGraphSpec) -> None:
        """Update topology spec and rebuild graph."""
        self.spec = spec
        self._build_graph()

    def trace_root_cause(
        self,
        node_anomaly_scores: Dict[str, float],
        anomaly_threshold: float = 0.50,
    ) -> Tuple[str, List[str], float]:
        """Pinpoint the deepest downstream node exceeding anomaly threshold.

        Returns (root_cause_node, propagation_path_from_root_to_ingress, confidence).
        """
        anomalous_nodes = {
            node: score
            for node, score in node_anomaly_scores.items()
            if score >= anomaly_threshold and node in self.graph
        }

        if not anomalous_nodes:
            return (self.spec.entrypoint_node, [self.spec.entrypoint_node], 0.10)

        # Select the anomalous node with maximum depth in the causal graph
        root_node = max(
            anomalous_nodes.keys(),
            key=lambda n: (self.node_depths.get(n, 0), anomalous_nodes[n]),
        )
        root_score = anomalous_nodes[root_node]

        # Trace causal path from entrypoint to root cause
        entrypoint = self.spec.entrypoint_node
        if nx.has_path(self.graph, entrypoint, root_node):
            path = nx.shortest_path(self.graph, entrypoint, root_node)
        else:
            path = [entrypoint, root_node]

        return (root_node, path, round(root_score, 4))

    def evaluate_node_scores(self, telemetry: UniversalTelemetry) -> Dict[str, float]:
        """Compute estimated anomaly scores across discovered nodes based on universal metrics."""
        scores: Dict[str, float] = {}

        # Heuristic mapping across common node types
        for node in self.spec.nodes:
            lower = node.lower()
            if "db" in lower or "database" in lower or "sql" in lower:
                # DB node anomaly depends on db_latency and connection saturation
                db_lat_norm = min(1.0, telemetry.db_latency_ms / 500.0)
                db_conn_norm = min(1.0, telemetry.db_connections / 100.0)
                scores[node] = round(max(db_lat_norm, db_conn_norm), 4)
            elif "cache" in lower or "redis" in lower:
                # Cache misses / latency
                scores[node] = round(min(1.0, (telemetry.latency_ms / 1000.0) * 0.4), 4)
            elif "gateway" in lower or "ingress" in lower:
                # 5xx errors or arrival surge
                err_norm = min(1.0, telemetry.error_rate / 0.05)
                scores[node] = round(err_norm, 4)
            elif "cdn" in lower or "edge" in lower:
                scores[node] = round(min(1.0, telemetry.requests_per_sec / 10000.0), 4)
            elif "backend" in lower or "pod" in lower or "worker" in lower or "app" in lower:
                # CPU and RAM saturation
                cpu_norm = min(1.0, telemetry.cpu_percent / 100.0)
                ram_norm = min(1.0, telemetry.ram_percent / 100.0)
                scores[node] = round(max(cpu_norm, ram_norm), 4)
            else:
                # Default baseline
                scores[node] = round(min(1.0, telemetry.error_rate * 10.0), 4)

        return scores

    def to_dict(self) -> Dict[str, Any]:
        """Serialize topology for JSON response."""
        return {
            "total_nodes": len(self.spec.nodes),
            "total_edges": len(self.spec.edges),
            "nodes": [
                {
                    "id": node,
                    "depth": self.node_depths.get(node, 0),
                    "is_entrypoint": bool(node == self.spec.entrypoint_node),
                    "is_storage": bool(node in self.spec.storage_nodes),
                }
                for node in self.spec.nodes
            ],
            "edges": [{"source": src, "target": dst} for src, dst in self.spec.edges],
            "entrypoint": self.spec.entrypoint_node,
        }

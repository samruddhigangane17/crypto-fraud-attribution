"""Transaction graph construction and Cytoscape serialization.

Constructs directed NetworkX graphs from NormalizedTransaction or TracePath objects,
preserving flow direction, amounts, assets, timestamps, and transaction identities.
Serializes graphs to the Cytoscape JSON structure expected by frontend/FundFlowGraph.tsx.
"""

from datetime import datetime
from decimal import Decimal
import json
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import networkx as nx

from backend.schemas.path import TracePath
from backend.schemas.transaction import NormalizedTransaction


def truncate_address(address: str) -> str:
    """Format an Ethereum address for UI display, e.g. 0x1234...5678."""
    if not address or len(address) < 12:
        return address
    return f"{address[:6]}...{address[-4:]}"


class FlowGraphBuilder:
    """Builds directed transaction graphs and exports Cytoscape JSON elements."""

    def __init__(
        self,
        root_address: Optional[str] = None,
        address_labels: Optional[Dict[str, str]] = None,
    ):
        """Initialize the graph builder.
        
        Args:
            root_address: The reported/victim wallet address initiating the investigation.
            address_labels: Optional mapping of address -> entity name (e.g. known exchanges).
                            Only addresses present in this mapping are classified as 'exchange'.
        """
        self.root_address = root_address.lower() if root_address else None
        self.address_labels = {k.lower(): v for k, v in (address_labels or {}).items()}
        self.graph = nx.MultiDiGraph()

    def _determine_node_type_and_label(self, address: str) -> Tuple[str, str]:
        """Classify node type and determine human-readable label based strictly on evidence.
        
        Node Types:
        - 'victim': Assigned if the address matches the root/reported address.
        - 'exchange': Assigned ONLY if the address exists in the verified address_labels mapping.
        - 'intermediary': Default safe classification for all other intermediate addresses.
        """
        addr_lower = address.lower()

        if addr_lower in self.address_labels:
            entity_name = self.address_labels[addr_lower]
            return "exchange", entity_name

        if self.root_address and addr_lower == self.root_address:
            return "victim", truncate_address(addr_lower)

        return "intermediary", truncate_address(addr_lower)

    def add_transaction(self, tx: NormalizedTransaction) -> None:
        """Add a transaction as a directed edge in the graph.
        
        Ensures nodes are created with appropriate labels and attributes.
        Uses tx.tx_hash as the edge key in the MultiDiGraph, so parallel transfers
        between the same wallets are preserved without overwriting each other.
        """
        src = tx.from_address.lower()
        dst = tx.to_address.lower()

        # Ensure source node exists
        if src not in self.graph:
            src_type, src_label = self._determine_node_type_and_label(src)
            self.graph.add_node(
                src,
                id=src,
                label=src_label,
                type=src_type,
                address=src,
            )

        # Ensure destination node exists
        if dst not in self.graph:
            dst_type, dst_label = self._determine_node_type_and_label(dst)
            self.graph.add_node(
                dst,
                id=dst,
                label=dst_label,
                type=dst_type,
                address=dst,
            )

        edge_key = tx.tx_hash

        # Avoid duplicate edge insertion for the same transaction hash
        if not self.graph.has_edge(src, dst, key=edge_key):
            self.graph.add_edge(
                src,
                dst,
                key=edge_key,
                tx_hash=tx.tx_hash,
                amount=tx.amount,  # Decimal preserved in graph
                asset=tx.asset_symbol,
                asset_symbol=tx.asset_symbol,
                timestamp=tx.timestamp,
                block_number=tx.block_number,
                contract_address=tx.contract_address,
                chain=tx.chain,
                source=tx.source,
            )

    def add_trace_path(self, path: TracePath) -> None:
        """Add all transactions along a TracePath into the graph."""
        for tx in path.transactions:
            self.add_transaction(tx)

    def add_trace_paths(self, paths: List[TracePath]) -> None:
        """Add all transactions from a collection of TracePath objects."""
        for p in paths:
            self.add_trace_path(p)

    @classmethod
    def build_from_paths(
        cls,
        paths: List[TracePath],
        root_address: Optional[str] = None,
        address_labels: Optional[Dict[str, str]] = None,
    ) -> "FlowGraphBuilder":
        """Convenience factory to construct and populate a FlowGraphBuilder from TracePaths."""
        builder = cls(root_address=root_address, address_labels=address_labels)
        builder.add_trace_paths(paths)
        return builder

    @classmethod
    def build_from_transactions(
        cls,
        transactions: List[NormalizedTransaction],
        root_address: Optional[str] = None,
        address_labels: Optional[Dict[str, str]] = None,
    ) -> "FlowGraphBuilder":
        """Convenience factory to construct and populate a FlowGraphBuilder from a list of transactions."""
        builder = cls(root_address=root_address, address_labels=address_labels)
        for tx in transactions:
            builder.add_transaction(tx)
        return builder

    def to_cytoscape(self, aggregate_parallel_edges: bool = False) -> Dict[str, Any]:
        """Serialize the graph into the exact Cytoscape JSON structure expected by frontend/FundFlowGraph.tsx.
        
        Output format:
        {
            "nodes": [
                {"data": {"id": str, "label": str, "type": "victim" | "intermediary" | "exchange", ...}}
            ],
            "edges": [
                {"data": {"id": str, "source": str, "target": str, "amount": float, "asset": str, ...}}
            ]
        }
        
        Args:
            aggregate_parallel_edges: If True, merges multiple edges between the same two nodes
                                      into a single edge summing their amounts.
                                      If False (default), preserves every distinct transaction edge.
        """
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        # Serialize Nodes
        for node_id, attrs in self.graph.nodes(data=True):
            in_deg = self.graph.in_degree(node_id)
            out_deg = self.graph.out_degree(node_id)
            nodes.append(
                {
                    "data": {
                        "id": node_id,
                        "label": attrs.get("label", truncate_address(node_id)),
                        "type": attrs.get("type", "intermediary"),
                        "address": node_id,
                        "in_degree": in_deg,
                        "out_degree": out_deg,
                    }
                }
            )

        # Sort nodes by id for deterministic output
        nodes.sort(key=lambda n: n["data"]["id"])

        if aggregate_parallel_edges:
            # Aggregate parallel edges between (u, v)
            pair_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
            for u, v, key, data in self.graph.edges(keys=True, data=True):
                pair = (u, v)
                amount_dec = data.get("amount", Decimal("0"))
                asset = data.get("asset", "ETH")
                if pair not in pair_map:
                    pair_map[pair] = {
                        "source": u,
                        "target": v,
                        "total_amount": amount_dec,
                        "asset": asset,
                        "tx_hashes": [data.get("tx_hash", key)],
                    }
                else:
                    pair_map[pair]["total_amount"] += amount_dec
                    pair_map[pair]["tx_hashes"].append(data.get("tx_hash", key))

            for (u, v), agg in pair_map.items():
                edges.append(
                    {
                        "data": {
                            "id": f"e_{u}_{v}",
                            "source": u,
                            "target": v,
                            "amount": float(agg["total_amount"]),
                            "asset": agg["asset"],
                            "tx_count": len(agg["tx_hashes"]),
                            "tx_hashes": agg["tx_hashes"],
                        }
                    }
                )
        else:
            # Default: Preserve every distinct transaction as a separate edge
            for u, v, key, data in self.graph.edges(keys=True, data=True):
                amount_dec = data.get("amount", Decimal("0"))
                amount_float = float(amount_dec)
                ts = data.get("timestamp")
                ts_iso = ts.isoformat() if isinstance(ts, datetime) else str(ts) if ts else None

                edges.append(
                    {
                        "data": {
                            "id": f"e_{u}_{v}_{key}",
                            "source": u,
                            "target": v,
                            "amount": amount_float,
                            "asset": data.get("asset", "ETH"),
                            "asset_symbol": data.get("asset_symbol", data.get("asset", "ETH")),
                            "tx_hash": data.get("tx_hash", key),
                            "timestamp": ts_iso,
                            "block_number": data.get("block_number"),
                            "contract_address": data.get("contract_address"),
                        }
                    }
                )

        # Sort edges by source and target for deterministic output
        edges.sort(key=lambda e: (e["data"]["source"], e["data"]["target"], e["data"]["id"]))

        return {
            "nodes": nodes,
            "edges": edges,
        }


def build_transaction_graph(
    transactions: Union[List[NormalizedTransaction], List[Dict[str, Any]]],
    root_address: Optional[str] = None,
    address_labels: Optional[Dict[str, str]] = None,
) -> nx.MultiDiGraph:
    """Build a directed NetworkX MultiDiGraph from transactions.
    
    Accepts either NormalizedTransaction objects or raw/normalized dicts.
    Preserves multigraph parallel transfers between identical wallets.
    """
    builder = FlowGraphBuilder(root_address=root_address, address_labels=address_labels)
    for item in transactions:
        if isinstance(item, dict):
            if "from_address" in item:
                tx = NormalizedTransaction(**item)
            elif "from" in item:
                from backend.tracing.normalizer import EthereumNormalizer
                tx = EthereumNormalizer.normalize_transaction(item)
            else:
                raise ValueError(f"Unrecognized transaction dictionary format: {item}")
        else:
            tx = item
        builder.add_transaction(tx)
    return builder.graph


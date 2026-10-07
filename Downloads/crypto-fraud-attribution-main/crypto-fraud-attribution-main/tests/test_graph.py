from datetime import datetime, timezone
from decimal import Decimal
import json
import pytest

from backend.schemas.path import TracePath
from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.graph import FlowGraphBuilder, truncate_address
from backend.tracing.tracer import MultiHopTracer


def _sample_tx(from_addr, to_addr, amount, tx_hash, ts="2026-10-01T10:00:00Z"):
    return NormalizedTransaction(
        chain="ethereum",
        tx_hash=tx_hash,
        from_address=from_addr,
        to_address=to_addr,
        amount=Decimal(amount),
        asset_symbol="ETH",
        timestamp=datetime.fromisoformat(ts.replace("Z", "+00:00")),
        source="test",
    )


def test_empty_graph():
    builder = FlowGraphBuilder()
    assert builder.graph.number_of_nodes() == 0
    assert builder.graph.number_of_edges() == 0

    cyto = builder.to_cytoscape()
    assert cyto == {"nodes": [], "edges": []}
    assert json.dumps(cyto) == '{"nodes": [], "edges": []}'


def test_build_from_mock_paths():
    connector = MockConnector()
    tracer = MultiHopTracer(connector=connector, max_hops=5)
    paths = tracer.trace("0xmock_wallet_a")

    labels = {"0xmock_exchange_hot": "MockExchange"}
    builder = FlowGraphBuilder.build_from_paths(
        paths, root_address="0xmock_wallet_a", address_labels=labels
    )

    # In mock data, there are 8 distinct wallets: A, B, C, D, E, F, G, EXCHANGE_HOT
    assert builder.graph.number_of_nodes() == 8
    # 7 distinct transfers: A->B, B->C, C->D, D->EXCHANGE, A->E, E->F, B->G
    assert builder.graph.number_of_edges() == 7

    # Check node types
    nodes_dict = dict(builder.graph.nodes(data=True))
    assert nodes_dict["0xmock_wallet_a"]["type"] == "victim"
    assert nodes_dict["0xmock_exchange_hot"]["type"] == "exchange"
    assert nodes_dict["0xmock_exchange_hot"]["label"] == "MockExchange"
    assert nodes_dict["0xmock_wallet_b"]["type"] == "intermediary"

    # Check edge directions and properties
    assert builder.graph.has_edge("0xmock_wallet_a", "0xmock_wallet_b")
    assert builder.graph.has_edge("0xmock_wallet_d", "0xmock_exchange_hot")
    assert not builder.graph.has_edge("0xmock_exchange_hot", "0xmock_wallet_d")  # Directed!


def test_cytoscape_json_serialization():
    tx = _sample_tx(
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222",
        "10.5",
        "0xhash01",
    )
    builder = FlowGraphBuilder.build_from_transactions(
        [tx], root_address="0x1111111111111111111111111111111111111111"
    )

    cyto = builder.to_cytoscape()

    # Structure check
    assert "nodes" in cyto and "edges" in cyto
    assert len(cyto["nodes"]) == 2
    assert len(cyto["edges"]) == 1

    # Node data contract: id, label, type
    node1 = next(n for n in cyto["nodes"] if n["data"]["id"] == "0x1111111111111111111111111111111111111111")
    assert node1["data"]["type"] == "victim"
    assert "0x1111..." in node1["data"]["label"]

    node2 = next(n for n in cyto["nodes"] if n["data"]["id"] == "0x2222222222222222222222222222222222222222")
    assert node2["data"]["type"] == "intermediary"

    # Edge data contract: source, target, amount, asset
    edge = cyto["edges"][0]["data"]
    assert edge["source"] == "0x1111111111111111111111111111111111111111"
    assert edge["target"] == "0x2222222222222222222222222222222222222222"
    assert edge["amount"] == 10.5
    assert isinstance(edge["amount"], float)
    assert edge["asset"] == "ETH"
    assert edge["tx_hash"] == "0xhash01"
    assert "2026-10-01" in edge["timestamp"]

    # Must be valid JSON string
    serialized = json.dumps(cyto)
    assert isinstance(serialized, str)


def test_duplicate_transactions_idempotent():
    tx = _sample_tx("0xwallet_a", "0xwallet_b", "5.0", "0xduplicate_hash")
    builder = FlowGraphBuilder()
    builder.add_transaction(tx)
    builder.add_transaction(tx)  # Insert duplicate

    assert builder.graph.number_of_nodes() == 2
    assert builder.graph.number_of_edges() == 1


def test_parallel_transactions_preserved():
    # Two distinct transfers between same pair: 5.0 ETH and 3.0 ETH
    tx1 = _sample_tx("0xwallet_a", "0xwallet_b", "5.0", "0xhash_first")
    tx2 = _sample_tx("0xwallet_a", "0xwallet_b", "3.0", "0xhash_second")

    builder = FlowGraphBuilder()
    builder.add_transaction(tx1)
    builder.add_transaction(tx2)

    # MultiDiGraph preserves both edges
    assert builder.graph.number_of_nodes() == 2
    assert builder.graph.number_of_edges() == 2

    # Default serialization preserves both distinct edges
    cyto_default = builder.to_cytoscape(aggregate_parallel_edges=False)
    assert len(cyto_default["edges"]) == 2
    hashes = {e["data"]["tx_hash"] for e in cyto_default["edges"]}
    assert hashes == {"0xhash_first", "0xhash_second"}

    # Aggregated serialization sums them into 1 edge
    cyto_agg = builder.to_cytoscape(aggregate_parallel_edges=True)
    assert len(cyto_agg["edges"]) == 1
    assert cyto_agg["edges"][0]["data"]["amount"] == 8.0
    assert cyto_agg["edges"][0]["data"]["tx_count"] == 2


def test_node_classification_unlabeled_terminal():
    # An address without known label must NOT be classified as exchange
    tx = _sample_tx("0xreported", "0xunlabeled_dest", "2.0", "0xtx1")
    builder = FlowGraphBuilder(root_address="0xreported")
    builder.add_transaction(tx)

    cyto = builder.to_cytoscape()
    dest_node = next(n for n in cyto["nodes"] if n["data"]["id"] == "0xunlabeled_dest")
    assert dest_node["data"]["type"] == "intermediary"


def test_disconnected_paths():
    # Path 1: A -> B
    tx1 = _sample_tx("0xwallet_a", "0xwallet_b", "1.0", "0xtx1")
    # Path 2: X -> Y (no shared nodes)
    tx2 = _sample_tx("0xwallet_x", "0xwallet_y", "2.0", "0xtx2")

    builder = FlowGraphBuilder()
    builder.add_transaction(tx1)
    builder.add_transaction(tx2)

    assert builder.graph.number_of_nodes() == 4
    assert builder.graph.number_of_edges() == 2

    cyto = builder.to_cytoscape()
    assert len(cyto["nodes"]) == 4
    assert len(cyto["edges"]) == 2


def test_truncate_address():
    assert truncate_address("0x1234567890abcdef1234567890abcdef12345678") == "0x1234...5678"
    assert truncate_address("short") == "short"
    assert truncate_address("") == ""


def test_build_transaction_graph_function():
    from backend.tracing.graph import build_transaction_graph
    tx1 = _sample_tx("0xwallet_a", "0xwallet_b", "5.0", "0xtx1")
    tx2 = _sample_tx("0xwallet_b", "0xwallet_c", "4.5", "0xtx2")

    # Pass list of NormalizedTransaction objects
    g = build_transaction_graph([tx1, tx2], root_address="0xwallet_a")
    assert g.number_of_nodes() == 3
    assert g.number_of_edges() == 2
    assert g.has_edge("0xwallet_a", "0xwallet_b")
    assert g.has_edge("0xwallet_b", "0xwallet_c")

    # Pass raw dictionary transactions
    raw_dict_tx = {
        "chain": "ethereum",
        "tx_hash": "0xrawtx3",
        "from_address": "0xwallet_c",
        "to_address": "0xwallet_d",
        "amount": Decimal("4.0"),
        "asset_symbol": "ETH",
        "timestamp": datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
    }
    g_dict = build_transaction_graph([raw_dict_tx])
    assert g_dict.number_of_nodes() == 2
    assert g_dict.number_of_edges() == 1
    assert g_dict.has_edge("0xwallet_c", "0xwallet_d")


def test_graph_edge_attributes_richness():
    tx = NormalizedTransaction(
        chain="ethereum",
        tx_hash="0xrich_edge_tx",
        from_address="0x1111111111111111111111111111111111111111",
        to_address="0x2222222222222222222222222222222222222222",
        amount=Decimal("1500"),
        asset_symbol="USDT",
        timestamp=datetime(2026, 10, 2, 14, 30, tzinfo=timezone.utc),
        block_number=18000500,
        contract_address="0xdac17f958d2ee523a2206206994597c13d831ec7",
        source="etherscan",
    )
    builder = FlowGraphBuilder()
    builder.add_transaction(tx)

    edge_data = builder.graph.get_edge_data(
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222",
        key="0xrich_edge_tx",
    )
    assert edge_data["amount"] == Decimal("1500")
    assert edge_data["asset_symbol"] == "USDT"
    assert edge_data["contract_address"] == "0xdac17f958d2ee523a2206206994597c13d831ec7"
    assert edge_data["block_number"] == 18000500

    cyto = builder.to_cytoscape()
    edge = cyto["edges"][0]["data"]
    assert edge["asset"] == "USDT"
    assert edge["asset_symbol"] == "USDT"
    assert edge["contract_address"] == "0xdac17f958d2ee523a2206206994597c13d831ec7"
    assert edge["amount"] == 1500.0


from datetime import datetime, timezone
from decimal import Decimal
import json
import pytest

from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.analysis import WalletMetrics, WalletRelationshipAnalyzer
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.graph import FlowGraphBuilder
from backend.tracing.tracer import MultiHopTracer
from tests.mock_data import MOCK_TRANSACTIONS


def _tx(from_addr, to_addr, amount, tx_hash, ts="2026-10-01T10:00:00Z"):
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


def test_empty_analysis():
    analyzer = WalletRelationshipAnalyzer([])
    summary = analyzer.get_summary()

    assert summary["total_wallets"] == 0
    assert summary["total_transactions"] == 0
    assert summary["total_transferred_volume"] == 0.0
    assert summary["rapid_pass_through_wallets"] == []

    m = analyzer.analyze_wallet("0xunknown")
    assert m.in_degree == 0
    assert m.out_degree == 0
    assert m.fan_in == 0
    assert m.fan_out == 0
    assert m.total_received == Decimal("0")
    assert m.total_sent == Decimal("0")
    assert m.net_flow == Decimal("0")
    assert not m.is_rapid_pass_through
    assert m.pass_through_duration_seconds is None


def test_fan_in_and_fan_out():
    # S1 -> C, S2 -> C
    # C -> R1, C -> R2, C -> R3
    txs = [
        _tx("0xs1", "0xcenter", "1.0", "0xtx1", "2026-10-01T09:00:00Z"),
        _tx("0xs2", "0xcenter", "2.0", "0xtx2", "2026-10-01T09:30:00Z"),
        _tx("0xcenter", "0xr1", "0.5", "0xtx3", "2026-10-01T10:00:00Z"),
        _tx("0xcenter", "0xr2", "0.5", "0xtx4", "2026-10-01T10:30:00Z"),
        _tx("0xcenter", "0xr3", "0.5", "0xtx5", "2026-10-01T11:00:00Z"),
    ]
    analyzer = WalletRelationshipAnalyzer(txs)
    center = analyzer.analyze_wallet("0xcenter")

    assert center.fan_in == 2
    assert center.senders == {"0xs1", "0xs2"}
    assert center.fan_out == 3
    assert center.recipients == {"0xr1", "0xr2", "0xr3"}
    assert center.in_degree == 2
    assert center.out_degree == 3
    assert center.total_received == Decimal("3.0")
    assert center.total_sent == Decimal("1.5")
    assert center.net_flow == Decimal("1.5")


def test_parallel_transfers_vs_fan_in_out():
    # S1 sends TWO separate transfers to C
    txs = [
        _tx("0xs1", "0xcenter", "1.0", "0xtx1", "2026-10-01T09:00:00Z"),
        _tx("0xs1", "0xcenter", "2.0", "0xtx2", "2026-10-01T09:30:00Z"),
    ]
    analyzer = WalletRelationshipAnalyzer(txs)
    center = analyzer.analyze_wallet("0xcenter")

    # In-degree counts total transactions (2)
    assert center.in_degree == 2
    # Fan-in counts distinct counterparties (1)
    assert center.fan_in == 1

    sender = analyzer.analyze_wallet("0xs1")
    assert sender.out_degree == 2
    assert sender.fan_out == 1


def test_rapid_pass_through_detection():
    # W receives funds at 10:00, forwards funds at 10:45 (45 min = 2700s)
    txs = [
        _tx("0xfunder", "0xwallet_pass", "5.0", "0xtx1", "2026-10-01T10:00:00Z"),
        _tx("0xwallet_pass", "0xdest", "4.8", "0xtx2", "2026-10-01T10:45:00Z"),
    ]
    analyzer = WalletRelationshipAnalyzer(txs)

    # Within 1 hour window (3600s) -> detected
    is_rapid, duration = analyzer.calculate_pass_through("0xwallet_pass", max_window_seconds=3600.0)
    assert is_rapid is True
    assert duration == 2700.0

    # Within 30 minute window (1800s) -> not detected (45 min > 30 min)
    is_rapid_strict, _ = analyzer.calculate_pass_through("0xwallet_pass", max_window_seconds=1800.0)
    assert is_rapid_strict is False


def test_pass_through_non_causal_outgoing_not_credited():
    # Outgoing transfer happened BEFORE incoming transfer
    txs = [
        _tx("0xwallet", "0xother", "2.0", "0xtx_old", "2026-10-01T08:00:00Z"),
        _tx("0xfunder", "0xwallet", "5.0", "0xtx_in", "2026-10-01T10:00:00Z"),
    ]
    analyzer = WalletRelationshipAnalyzer(txs)
    is_rapid, duration = analyzer.calculate_pass_through("0xwallet", max_window_seconds=86400.0)
    assert is_rapid is False
    assert duration is None


def test_volume_statistics_decimal_precision():
    # High-precision Wei-scale Decimal transfers
    txs = [
        _tx("0xa", "0xb", "0.000000000000000001", "0xtx1"),
        _tx("0xa", "0xb", "1.234567890123456789", "0xtx2"),
    ]
    analyzer = WalletRelationshipAnalyzer(txs)
    wallet_b = analyzer.analyze_wallet("0xb")

    expected_sum = Decimal("0.000000000000000001") + Decimal("1.234567890123456789")
    assert wallet_b.total_received == expected_sum
    assert isinstance(wallet_b.total_received, Decimal)


def test_analysis_on_mock_dataset():
    analyzer = WalletRelationshipAnalyzer(MOCK_TRANSACTIONS)
    summary = analyzer.get_summary(max_pass_through_seconds=7200.0)

    # In mock data, 8 unique addresses
    assert summary["total_wallets"] == 8
    assert summary["total_transactions"] == 7

    # Check root wallet A (source)
    wallet_a = analyzer.analyze_wallet("0xmock_wallet_a")
    assert wallet_a.in_degree == 0
    assert wallet_a.out_degree == 2
    assert wallet_a.fan_out == 2
    assert wallet_a.total_sent == Decimal("12.5")
    assert not wallet_a.is_rapid_pass_through

    # Check intermediary B: receives 10.0 from A at 09:00, sends 9.9 to C at 10:00 (1 hour = 3600s)
    wallet_b = analyzer.analyze_wallet("0xmock_wallet_b")
    assert wallet_b.in_degree == 1
    assert wallet_b.out_degree == 2
    assert wallet_b.total_received == Decimal("10.0")
    assert wallet_b.total_sent == Decimal("10.4")
    assert wallet_b.is_rapid_pass_through is True
    assert wallet_b.pass_through_duration_seconds == 3600.0

    # Check terminal exchange
    exchange = analyzer.analyze_wallet("0xmock_exchange_hot")
    assert exchange.in_degree == 1
    assert exchange.out_degree == 0
    assert exchange.total_received == Decimal("9.7")
    assert not exchange.is_rapid_pass_through


def test_from_paths_and_from_graph():
    connector = MockConnector()
    tracer = MultiHopTracer(connector=connector)
    paths = tracer.trace("0xmock_wallet_a")

    # Analyzer from paths
    analyzer_paths = WalletRelationshipAnalyzer.from_paths(paths)
    assert len(analyzer_paths.transactions) == 7

    # Analyzer from graph
    builder = FlowGraphBuilder.build_from_paths(paths)
    analyzer_graph = WalletRelationshipAnalyzer.from_graph(builder)
    assert len(analyzer_graph.transactions) == 7

    # Both analyzers produce identical summary counts
    assert analyzer_paths.get_summary()["total_wallets"] == analyzer_graph.get_summary()["total_wallets"]


def test_json_serialization():
    analyzer = WalletRelationshipAnalyzer(MOCK_TRANSACTIONS)
    summary = analyzer.get_summary()

    # Must serialize cleanly to JSON
    json_str = json.dumps(summary)
    assert isinstance(json_str, str)
    data = json.loads(json_str)
    assert "wallets" in data
    assert "0xmock_wallet_b" in data["wallets"]

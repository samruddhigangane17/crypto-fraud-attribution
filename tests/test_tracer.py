from datetime import datetime, timezone
from decimal import Decimal
import pytest

from backend.schemas.path import TracePath
from backend.schemas.transaction import NormalizedTransaction
from backend.tracing.connectors.mock import MockConnector
from backend.tracing.connectors.base import BaseConnector
from backend.tracing.tracer import MultiHopTracer


def _make_tx(
    from_addr: str,
    to_addr: str,
    amount: str,
    tx_hash: str,
    timestamp: str,
    block_number: int = 1000,
) -> NormalizedTransaction:
    return NormalizedTransaction(
        chain="ethereum",
        tx_hash=tx_hash,
        from_address=from_addr,
        to_address=to_addr,
        amount=Decimal(amount),
        asset_symbol="ETH",
        timestamp=datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
        block_number=block_number,
        source="mock",
    )


def test_tracer_with_mock_data():
    connector = MockConnector()
    tracer = MultiHopTracer(connector=connector, max_hops=5, investigation_id="inv-test-1")
    paths = tracer.trace("0xmock_wallet_a")

    assert len(paths) == 3
    for p in paths:
        assert isinstance(p, TracePath)
        assert p.investigation_id == "inv-test-1"
        assert p.hop_count == len(p.transactions)
        assert p.transactions[0].from_address == "0xmock_wallet_a"

    # Sorted by hop_count desc: longest first
    path_endpoints = [p.end_address for p in paths]
    assert "0xmock_exchange_hot" in path_endpoints
    assert "0xmock_wallet_g" in path_endpoints
    assert "0xmock_wallet_f" in path_endpoints

    # Check the longest 4-hop path: A -> B -> C -> D -> EXCHANGE_HOT
    longest_path = paths[0]
    assert longest_path.hop_count == 4
    assert longest_path.end_address == "0xmock_exchange_hot"
    tx_hashes = [tx.tx_hash for tx in longest_path.transactions]
    assert tx_hashes == ["0xmocktx01", "0xmocktx02", "0xmocktx03", "0xmocktx04"]

    # Verify unique transactions extraction
    unique_txs = MultiHopTracer.extract_unique_transactions(paths)
    assert len(unique_txs) == 7


def test_tracer_max_hops_limit():
    connector = MockConnector()
    tracer = MultiHopTracer(connector=connector, max_hops=2)
    paths = tracer.trace("0xmock_wallet_a")

    # With max_hops=2, all paths must have hop_count <= 2
    for p in paths:
        assert p.hop_count <= 2
    
    # Path 1 (originally 4 hops) now stops at C (hop 2)
    assert any(p.end_address == "0xmock_wallet_c" and p.hop_count == 2 for p in paths)


def test_tracer_temporal_causality():
    # Setup:
    # A -> B at 10:00
    # B -> C at 09:00 (BEFORE A->B arrived: non-causal!)
    # B -> D at 11:00 (AFTER A->B arrived: causal!)
    txs = [
        _make_tx("0xwallet_a", "0xwallet_b", "10.0", "0xtx1", "2026-10-01T10:00:00Z"),
        _make_tx("0xwallet_b", "0xwallet_c", "5.0", "0xtx2", "2026-10-01T09:00:00Z"),
        _make_tx("0xwallet_b", "0xwallet_d", "5.0", "0xtx3", "2026-10-01T11:00:00Z"),
    ]
    connector = MockConnector(transactions=txs)
    tracer = MultiHopTracer(connector=connector, max_hops=5)
    paths = tracer.trace("0xwallet_a")

    assert len(paths) == 1
    assert paths[0].end_address == "0xwallet_d"
    assert [tx.tx_hash for tx in paths[0].transactions] == ["0xtx1", "0xtx3"]


def test_tracer_cycle_prevention():
    # Setup:
    # A -> B -> C -> A (cycle back to root)
    # C -> D (branch to destination)
    txs = [
        _make_tx("0xwallet_a", "0xwallet_b", "10.0", "0xtx1", "2026-10-01T10:00:00Z"),
        _make_tx("0xwallet_b", "0xwallet_c", "9.5", "0xtx2", "2026-10-01T11:00:00Z"),
        _make_tx("0xwallet_c", "0xwallet_a", "1.0", "0xtx_cycle", "2026-10-01T12:00:00Z"),
        _make_tx("0xwallet_c", "0xwallet_d", "8.0", "0xtx3", "2026-10-01T13:00:00Z"),
    ]
    connector = MockConnector(transactions=txs)
    tracer = MultiHopTracer(connector=connector, max_hops=5)
    paths = tracer.trace("0xwallet_a")

    # Cycle to A must be prevented without hanging
    assert tracer.cycles_detected >= 1
    # Path should successfully reach D
    assert len(paths) == 1
    assert paths[0].end_address == "0xwallet_d"
    assert [tx.tx_hash for tx in paths[0].transactions] == ["0xtx1", "0xtx2", "0xtx3"]


def test_tracer_min_amount_threshold():
    connector = MockConnector()
    # Mock data has B -> G with amount 0.5 ETH, others >= 2.4 ETH
    # Setting threshold 1.0 ETH prunes the B -> G branch
    tracer = MultiHopTracer(connector=connector, max_hops=5, min_amount=Decimal("1.0"))
    paths = tracer.trace("0xmock_wallet_a")

    assert len(paths) == 2
    endpoints = [p.end_address for p in paths]
    assert "0xmock_wallet_g" not in endpoints
    assert "0xmock_exchange_hot" in endpoints
    assert "0xmock_wallet_f" in endpoints


def test_tracer_empty_history():
    connector = MockConnector(transactions=[])
    tracer = MultiHopTracer(connector=connector, max_hops=5)
    paths = tracer.trace("0xnonexistent_wallet")

    assert paths == []


def test_tracer_reported_address_no_outgoing():
    # Only incoming transactions to reported address
    txs = [
        _make_tx("0xsender", "0xreported", "5.0", "0xtx1", "2026-10-01T10:00:00Z")
    ]
    connector = MockConnector(transactions=txs)
    tracer = MultiHopTracer(connector=connector)
    paths = tracer.trace("0xreported")

    assert paths == []


def test_tracer_handles_connector_error():
    class FailingConnector(BaseConnector):
        def get_transactions(self, address, start_block=None, end_block=None):
            if address.lower() == "0xwallet_b":
                raise ConnectionError("Simulated provider outage")
            return [
                _make_tx("0xwallet_a", "0xwallet_b", "10.0", "0xtx1", "2026-10-01T10:00:00Z")
            ]

    tracer = MultiHopTracer(connector=FailingConnector())
    paths = tracer.trace("0xwallet_a")

    # Should not crash; records connector error and returns path up to failure point
    assert len(tracer.connector_errors) == 1
    assert "Simulated provider outage" in tracer.connector_errors[0]
    assert len(paths) == 1
    assert paths[0].end_address == "0xwallet_b"


def test_tracer_parameter_validation():
    connector = MockConnector()

    with pytest.raises(ValueError, match="max_hops must be at least 1"):
        MultiHopTracer(connector=connector, max_hops=0)

    with pytest.raises(ValueError, match="not a float"):
        MultiHopTracer(connector=connector, min_amount=0.5)

    with pytest.raises(ValueError, match="cannot be negative"):
        MultiHopTracer(connector=connector, min_amount=Decimal("-1.0"))

    tracer = MultiHopTracer(connector=connector)
    with pytest.raises(ValueError, match="Invalid reported_address"):
        tracer.trace("")


def test_tracer_hop_limits_granularity():
    connector = MockConnector()

    # max_hops = 1: immediate neighbors only (paths with at most 1 edge)
    tracer_1 = MultiHopTracer(connector=connector, max_hops=1)
    paths_1 = tracer_1.trace("0xmock_wallet_a")
    assert len(paths_1) == 2  # paths_count for 0xmock_wallet_a
    assert all(len(p.transactions) == 1 for p in paths_1)  # strictly at most 1 edge
    assert all(p.hop_count == 1 for p in paths_1)
    assert all(p.intermediate_addresses == [] for p in paths_1)  # 1-hop paths have no intermediate addresses
    assert tracer_1.intermediate_addresses == set()  # overall intermediate addresses is empty
    destinations_1 = {p.end_address for p in paths_1}
    assert destinations_1 == {"0xmock_wallet_b", "0xmock_wallet_e"}

    # max_hops = 2: allows longer paths up to 2 edges
    tracer_2 = MultiHopTracer(connector=connector, max_hops=2)
    paths_2 = tracer_2.trace("0xmock_wallet_a")
    assert len(paths_2) == 3
    assert all(len(p.transactions) <= 2 for p in paths_2)
    assert max(len(p.transactions) for p in paths_2) == 2
    assert tracer_2.intermediate_addresses == {"0xmock_wallet_b", "0xmock_wallet_e"}

    # max_hops = 3: allows longer paths up to 3 edges
    tracer_3 = MultiHopTracer(connector=connector, max_hops=3)
    paths_3 = tracer_3.trace("0xmock_wallet_a")
    assert len(paths_3) == 3
    assert all(len(p.transactions) <= 3 for p in paths_3)
    assert max(len(p.transactions) for p in paths_3) == 3
    assert tracer_3.intermediate_addresses == {"0xmock_wallet_b", "0xmock_wallet_c", "0xmock_wallet_e"}

    # max_hops = 5: allows full path exploration up to 4 edges
    tracer_5 = MultiHopTracer(connector=connector, max_hops=5)
    paths_5 = tracer_5.trace("0xmock_wallet_a")
    assert len(paths_5) == 3
    assert max(len(p.transactions) for p in paths_5) == 4
    assert tracer_5.intermediate_addresses == {
        "0xmock_wallet_b",
        "0xmock_wallet_c",
        "0xmock_wallet_d",
        "0xmock_wallet_e",
    }

    # max_hops = 10 (exceeds graph depth of 4)
    tracer_10 = MultiHopTracer(connector=connector, max_hops=10)
    paths_10 = tracer_10.trace("0xmock_wallet_a")
    assert len(paths_10) == 3
    assert max(p.hop_count for p in paths_10) == 4
    assert tracer_10.intermediate_addresses == {
        "0xmock_wallet_b",
        "0xmock_wallet_c",
        "0xmock_wallet_d",
        "0xmock_wallet_e",
    }



def test_tracer_cycles_comprehensive():
    # 1. Direct mutual cycle: A -> B at 10:00, B -> A at 11:00
    # 2. Self transfer: B -> B at 11:30
    # 3. Valid branch: B -> C at 12:00
    txs = [
        _make_tx("0xwallet_a", "0xwallet_b", "10.0", "0xtx1", "2026-10-01T10:00:00Z"),
        _make_tx("0xwallet_b", "0xwallet_a", "1.0", "0xtx_cycle_back", "2026-10-01T11:00:00Z"),
        _make_tx("0xwallet_b", "0xwallet_b", "0.5", "0xtx_self", "2026-10-01T11:30:00Z"),
        _make_tx("0xwallet_b", "0xwallet_c", "8.0", "0xtx_dest", "2026-10-01T12:00:00Z"),
    ]
    connector = MockConnector(transactions=txs)
    tracer = MultiHopTracer(connector=connector, max_hops=5)
    paths = tracer.trace("0xwallet_a")

    # Both cycles (B->A and B->B) should be detected
    assert tracer.cycles_detected >= 2
    # Only valid non-cyclic path to C should be produced
    assert len(paths) == 1
    assert paths[0].end_address == "0xwallet_c"
    assert [tx.tx_hash for tx in paths[0].transactions] == ["0xtx1", "0xtx_dest"]


def test_tracer_repeated_transfers_between_same_wallets():
    # A sends to B twice at different times:
    # tx1: 10:00 (5 ETH)
    # tx2: 12:00 (3 ETH)
    # B sends to C at 13:00 (after both tx1 and tx2)
    # B sends to D at 11:00 (after tx1, but before tx2)
    txs = [
        _make_tx("0xwallet_a", "0xwallet_b", "5.0", "0xtx_a_b_1", "2026-10-01T10:00:00Z"),
        _make_tx("0xwallet_a", "0xwallet_b", "3.0", "0xtx_a_b_2", "2026-10-01T12:00:00Z"),
        _make_tx("0xwallet_b", "0xwallet_d", "1.0", "0xtx_b_d", "2026-10-01T11:00:00Z"),
        _make_tx("0xwallet_b", "0xwallet_c", "2.0", "0xtx_b_c", "2026-10-01T13:00:00Z"),
    ]
    connector = MockConnector(transactions=txs)
    tracer = MultiHopTracer(connector=connector, max_hops=5)
    paths = tracer.trace("0xwallet_a")

    # Distinct paths expected:
    # 1. tx_a_b_1 -> tx_b_d (valid: 11:00 >= 10:00)
    # 2. tx_a_b_1 -> tx_b_c (valid: 13:00 >= 10:00)
    # 3. tx_a_b_2 -> tx_b_c (valid: 13:00 >= 12:00)
    # (tx_a_b_2 -> tx_b_d is invalid because 11:00 < 12:00!)
    assert len(paths) == 3

    path_tx_hashes = [[tx.tx_hash for tx in p.transactions] for p in paths]
    assert ["0xtx_a_b_1", "0xtx_b_d"] in path_tx_hashes
    assert ["0xtx_a_b_1", "0xtx_b_c"] in path_tx_hashes
    assert ["0xtx_a_b_2", "0xtx_b_c"] in path_tx_hashes
    assert ["0xtx_a_b_2", "0xtx_b_d"] not in path_tx_hashes


def test_tracer_target_address_stopping():
    connector = MockConnector()
    # Mock data has A -> B -> C -> D -> EXCHANGE_HOT
    # If we set target_addresses = {"0xmock_wallet_c"}, tracing must stop at C
    tracer = MultiHopTracer(
        connector=connector,
        max_hops=5,
        target_addresses={"0xmock_wallet_c"},
    )
    paths = tracer.trace("0xmock_wallet_a")

    # The main branch should stop at 0xmock_wallet_c instead of continuing to D and EXCHANGE_HOT
    c_path = next(p for p in paths if p.end_address == "0xmock_wallet_c")
    assert c_path.hop_count == 2
    assert "0xmock_exchange_hot" not in [p.end_address for p in paths]


def test_tracer_end_time_cutoff():
    connector = MockConnector()
    # In mock data, A -> E is at 09:30, E -> F is at 12:00
    # Setting end_time = 11:00 means E -> F will not be traversed
    end_dt = datetime.fromisoformat("2026-10-01T11:00:00+00:00")
    tracer = MultiHopTracer(connector=connector, max_hops=5, end_time=end_dt)
    paths = tracer.trace("0xmock_wallet_a")

    # E -> F must not be in paths
    assert "0xmock_wallet_f" not in [p.end_address for p in paths]
    assert any(p.end_address == "0xmock_wallet_e" for p in paths)


def test_tracer_intermediate_and_discovered_addresses():
    connector = MockConnector()
    tracer = MultiHopTracer(connector=connector, max_hops=5)
    paths = tracer.trace("0xmock_wallet_a")

    # Root address is 0xmock_wallet_a
    assert "0xmock_wallet_a" in tracer.discovered_addresses
    assert "0xmock_wallet_a" not in tracer.intermediate_addresses

    # Intermediate addresses must include B, C, D, E
    assert "0xmock_wallet_b" in tracer.intermediate_addresses
    assert "0xmock_wallet_c" in tracer.intermediate_addresses
    assert "0xmock_wallet_d" in tracer.intermediate_addresses
    assert "0xmock_wallet_e" in tracer.intermediate_addresses

    # Check TracePath helper properties
    longest_path = paths[0]  # A -> B -> C -> D -> EXCHANGE_HOT
    assert longest_path.intermediate_addresses == [
        "0xmock_wallet_b",
        "0xmock_wallet_c",
        "0xmock_wallet_d",
    ]
    assert longest_path.all_addresses == [
        "0xmock_wallet_a",
        "0xmock_wallet_b",
        "0xmock_wallet_c",
        "0xmock_wallet_d",
        "0xmock_exchange_hot",
    ]


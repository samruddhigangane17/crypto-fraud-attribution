"""Tests for Wallet Clustering Heuristics and Bridge Continuation (TC-05, TC-07, TC-08)."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from backend.bridges.detector import BridgeDetector, KNOWN_BRIDGES
from backend.clustering.engine import WalletClusteringEngine
from backend.schemas.path import TracePath
from backend.schemas.transaction import NormalizedTransaction


def make_tx(tx_hash, src, dst, amount, minute=0):
    return NormalizedTransaction(
        chain="ethereum",
        tx_hash=tx_hash,
        from_address=src.lower(),
        to_address=dst.lower(),
        amount=Decimal(str(amount)),
        asset_symbol="ETH",
        timestamp=datetime(2026, 10, 1, 12, minute, tzinfo=timezone.utc),
        block_number=100 + minute,
    )


# --- TC-08: Bitcoin Multi-Input Transaction Clustered with Stated Confidence ---
def test_tc08_bitcoin_common_input_ownership():
    engine = WalletClusteringEngine()
    btc_inputs = [
        ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX"],
        ["bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", "bc1q9d8c3z5v3k52c0spu2q5t0a2ypt496d09r8n6t"],
    ]
    links = engine.cluster_bitcoin_inputs(btc_inputs)
    assert len(links) == 2
    assert links[0].heuristic == "common_input_ownership"
    assert links[0].confidence_level == "HIGH"
    assert links[0].confidence_score == 0.90
    assert links[0].is_low_confidence is False


# --- Shared Funding Source & Deposit Sweep Heuristics ---
def test_shared_funding_and_deposit_sweep_clustering():
    engine = WalletClusteringEngine()

    funder = "0x" + "f" * 40
    mule1 = "0x" + "1" * 40
    mule2 = "0x" + "2" * 40
    collector = "0x" + "c" * 40

    tx_fund1 = make_tx("0xf1", funder, mule1, "0.05", minute=0)
    tx_fund2 = make_tx("0xf2", funder, mule2, "0.05", minute=2)
    tx_sweep1 = make_tx("0xs1", mule1, collector, "5.0", minute=10)
    tx_sweep2 = make_tx("0xs2", mule2, collector, "8.0", minute=12)

    all_txs = [tx_fund1, tx_fund2, tx_sweep1, tx_sweep2]

    funding_links = engine.cluster_shared_funding(all_txs)
    assert len(funding_links) == 1
    assert funding_links[0].heuristic == "shared_funding_source"
    assert funding_links[0].confidence_score == 0.70

    sweep_links = engine.cluster_deposit_sweeps(all_txs)
    assert len(sweep_links) == 1
    assert sweep_links[0].heuristic == "deposit_sweep_pattern"
    assert sweep_links[0].confidence_score >= 0.75


# --- TC-07: Transfer Through Known Bridge -> Continuation or Review Flag ---
def test_tc07_bridge_detection_and_continuation():
    bridge_addr = "0x5c7bcab86633e49280d3586ce9082d33be317704"  # Across Protocol
    detector = BridgeDetector()
    assert detector.is_bridge_contract(bridge_addr)

    victim = "0x" + "a" * 40
    tx_deposit = make_tx("0xbridge_dep", victim, bridge_addr, 10.0, minute=0)

    events = detector.detect_bridge_transfers([tx_deposit])
    assert len(events) == 1
    event = events[0]
    assert event.bridge_name == "Across Protocol"
    assert event.status == "review_required"  # Initially flagged for review

    # Simulate matched release on destination chain (arbitrum)
    recipient_dest = "0x" + "b" * 40
    tx_release = NormalizedTransaction(
        chain="arbitrum",
        tx_hash="0xarb_rel",
        from_address=bridge_addr,
        to_address=recipient_dest,
        amount=Decimal("9.95"),  # Small bridge fee deducted
        asset_symbol="ETH",
        timestamp=datetime(2026, 10, 1, 12, 10, tzinfo=timezone.utc),  # 10 mins later
        block_number=5000,
    )

    correlated = detector.correlate_bridge_release(event, [tx_release])
    assert correlated.is_matched_on_destination is True
    assert correlated.status == "continued"
    assert correlated.destination_tx_hash == "0xarb_rel"
    assert correlated.destination_recipient == recipient_dest

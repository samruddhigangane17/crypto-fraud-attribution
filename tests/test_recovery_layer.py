"""Tests for Golden Hour Recovery Layer (Features #15 - #23 and TC-13 to TC-22)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from backend.recovery.context_filter import ContextFilter
from backend.recovery.extended_signals import ExtendedLaunderingDetector
from backend.recovery.ranking import RecoverabilityRankingEngine
from backend.recovery.clock import RecoveryClockManager
from backend.recovery.typology import RecoveryPathEngine
from backend.recovery.convergence import CrossCaseConvergenceEngine
from backend.recovery.summary import GroundedCaseSummaryGenerator
from backend.schemas.attribution import AddressLabel, EndpointMatchResult, EntityCategory, VerificationStatus
from backend.schemas.path import TracePath
from backend.schemas.transaction import NormalizedTransaction


def make_tx(tx_hash, src, dst, amount, minute=0, block=1):
    return NormalizedTransaction(
        chain="ethereum",
        tx_hash=tx_hash,
        from_address=src.lower(),
        to_address=dst.lower(),
        amount=Decimal(str(amount)),
        asset_symbol="ETH",
        timestamp=datetime(2026, 10, 1, 10, minute, tzinfo=timezone.utc),
        block_number=block,
    )


# --- TC-13: Recoverability Ranking ---
def test_tc13_recoverability_ranking():
    """Case with two destinations: large recent amount with no onward transfer,
    and small old amount already moved on -> First ranked 'Act now', second 'Monitor'.
    """
    engine = RecoverabilityRankingEngine()
    now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    wallet_victim = "0x" + "1" * 40
    wallet_inter = "0x" + "2" * 40
    dest_large_recent = "0x" + "a" * 40
    dest_small_old = "0x" + "b" * 40
    dest_moved_on = "0x" + "c" * 40

    # Path 1: Large recent amount (50 ETH) reaching dest_large_recent, no onward transfer
    tx1 = make_tx("0x101", wallet_victim, dest_large_recent, 50.0, minute=0)
    p1 = TracePath(investigation_id="t1", hop_count=1, transactions=[tx1], end_address=dest_large_recent)

    # Path 2: Small amount (0.5 ETH) reaching dest_small_old 5 days ago, then moved onward to dest_moved_on
    old_time = now - timedelta(days=5)
    tx2a = NormalizedTransaction(
        chain="ethereum", tx_hash="0x201", from_address=wallet_victim, to_address=dest_small_old,
        amount=Decimal("0.5"), asset_symbol="ETH", timestamp=old_time, block_number=10,
    )
    tx2b = NormalizedTransaction(
        chain="ethereum", tx_hash="0x202", from_address=dest_small_old, to_address=dest_moved_on,
        amount=Decimal("0.48"), asset_symbol="ETH", timestamp=old_time + timedelta(hours=1), block_number=15,
    )
    p2 = TracePath(investigation_id="t1", hop_count=2, transactions=[tx2a, tx2b], end_address=dest_small_old)

    # Dest 1 has high VASP confidence
    ep1 = EndpointMatchResult(
        chain="ethereum", address=dest_large_recent, is_matched=True,
        label=AddressLabel(id="vasp-1", chain="ethereum", address=dest_large_recent, entity_name="Binance Hot Wallet", entity_category=EntityCategory.EXCHANGE_VASP, source="PoR", confidence=0.99, verification_status=VerificationStatus.VERIFIED),
        match_type="EXACT", hop_distance=1, confidence=0.99,
    )

    rankings = engine.rank_destinations(paths=[p1, p2], endpoints=[ep1], reference_time=now)
    assert len(rankings) >= 2

    # Find the two destinations
    r_large = next(r for r in rankings if r.destination_address == dest_large_recent)
    r_small = next(r for r in rankings if r.destination_address == dest_small_old)

    assert r_large.tier == "Act now"
    assert r_small.tier == "Monitor"
    assert r_large.wording_label == "last observed destination"


# --- TC-14 & TC-15 & TC-16: Recovery Clock & Rules Table ---
def test_tc14_recovery_clock_initialization():
    clock_mgr = RecoveryClockManager()
    steps = clock_mgr.create_clock_for_case("CASE-101")
    assert len(steps) == 5
    assert steps[0].step_type == "i4c_report_logged"
    assert steps[0].status == "pending"


def test_tc15_edit_timing_rule_as_admin():
    clock_mgr = RecoveryClockManager()
    clock_mgr.update_rule("i4c_report_logged", due_hours=1.5, actor="admin_user")
    rules = clock_mgr.get_rules()
    updated = next(r for r in rules if r.step_type == "i4c_report_logged")
    assert updated.due_hours == 1.5

    # New cases use the new rule
    new_steps = clock_mgr.create_clock_for_case("CASE-102")
    assert new_steps[0].due_rule_hours == 1.5


def test_tc16_overdue_step_alert():
    clock_mgr = RecoveryClockManager()
    start_time = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
    steps = clock_mgr.create_clock_for_case("CASE-OVERDUE", start_time=start_time)

    # Check clock 10 hours later (step 1 due in 2h, step 2 due in 6h)
    eval_time = start_time + timedelta(hours=10)
    checked_steps = clock_mgr.get_case_clock("CASE-OVERDUE", check_overdue=True, reference_time=eval_time)

    step1 = checked_steps[0]
    assert step1.status == "overdue"


# --- TC-17: Seeded cases of each Typology ---
def test_tc17_typology_engine():
    engine = RecoveryPathEngine()

    inv_scam = engine.classify_case(complaint_category="Cryptocurrency investment task scam")
    assert inv_scam.typology_id == "investment_scam"
    assert "Victim deposit" in inv_scam.evidence_checklist[0]

    sextortion = engine.classify_case(complaint_category="Extortion demanding bitcoin or will leak photos")
    assert sextortion.typology_id == "sextortion"

    ransom = engine.classify_case(complaint_category="Lockbit ransomware attack demand")
    assert ransom.typology_id == "ransomware"

    phishing = engine.classify_case(complaint_category="Unauthorized wallet drainer phishing hack")
    assert phishing.typology_id == "phishing"


# --- TC-18: Cross-Case Convergence ---
def test_tc18_cross_case_convergence():
    conv_engine = CrossCaseConvergenceEngine()
    shared_deposit = "0x" + "d" * 40

    # Seed Case 1
    conv_engine.index_case(
        case_id="CASE-ALPHA",
        reported_address="0xvictim1",
        all_traced_addresses=["0xvictim1", "0xmule1", shared_deposit],
        endpoints=[{"address": shared_deposit, "entity_name": "Kraken Deposit"}],
    )

    # Seed Case 2 ending at the same deposit address
    links = conv_engine.index_case(
        case_id="CASE-BETA",
        reported_address="0xvictim2",
        all_traced_addresses=["0xvictim2", "0xmule2", shared_deposit],
        endpoints=[{"address": shared_deposit, "entity_name": "Kraken Deposit"}],
    )

    assert len(links) == 1
    assert links[0].link_type == "shared_endpoint"
    assert "CASE-ALPHA" in links[0].case_ids
    assert "CASE-BETA" in links[0].case_ids

    # Both cases reflect the link in their network view
    net_view_a = conv_engine.get_network_view("CASE-ALPHA")
    net_view_b = conv_engine.get_network_view("CASE-BETA")
    assert net_view_a["converged_cases_count"] == 1
    assert "CASE-BETA" in net_view_a["linked_case_ids"]
    assert "CASE-ALPHA" in net_view_b["linked_case_ids"]


# --- TC-19: Context Filter Excludes High-Volume Hot Wallets ---
def test_tc19_context_filter_excludes_exchange_hot_wallet():
    filt = ContextFilter()
    # Binance hot wallet 14 from verified seed data
    binance_hot = "0x28c6c06298d514db089934071355e5743bf21d60"
    decision = filt.evaluate_address(binance_hot, chain="ethereum")
    assert decision.is_excluded_from_laundering is True
    assert "legitimate high-volume entity" in decision.reason.lower()


# --- TC-20: Wallet Showing Fragmentation and Dormant-to-Active Behaviour ---
def test_tc20_extended_laundering_signals():
    detector = ExtendedLaunderingDetector()
    addr_splitter = "0x" + "e" * 40
    dest_a = "0x" + "f" * 40
    dest_b = "0x" + "9" * 40

    # Inflow: 10 ETH
    tx_in = make_tx("0xin", "0xvictim", addr_splitter, 10.0, minute=0)
    # Outflow: split into two transfers within 30 minutes
    tx_out1 = make_tx("0xout1", addr_splitter, dest_a, 4.8, minute=15)
    tx_out2 = make_tx("0xout2", addr_splitter, dest_b, 5.0, minute=25)

    p1 = TracePath(investigation_id="t2", end_address=dest_a, hop_count=2, transactions=[tx_in, tx_out1])
    p2 = TracePath(investigation_id="t2", end_address=dest_b, hop_count=2, transactions=[tx_in, tx_out2])

    signals = detector.detect_signals([p1, p2], chain="ethereum")
    sig_types = [s.signal_type for s in signals]
    assert "amount_fragmentation" in sig_types
    frag_sig = next(s for s in signals if s.signal_type == "amount_fragmentation")
    assert frag_sig.evidence["outflow_count"] == 2
    assert frag_sig.evidence["inflow_amount"] == 10.0


# --- TC-21: Grounded AI Case Summary ---
def test_tc21_grounded_case_summary():
    gen = GroundedCaseSummaryGenerator()
    reported = "0x" + "1" * 40
    tx1 = make_tx("0x111", reported, "0xendpoint", 5.0)
    p = TracePath(investigation_id="t3", end_address="0xendpoint", hop_count=1, transactions=[tx1])

    summary = gen.generate_summary(
        case_id="CASE-SUM",
        reported_address=reported,
        chain="ethereum",
        paths=[p],
        endpoints=[],
    )

    assert len(summary.sentences) >= 2
    for s in summary.sentences:
        assert s.fact_or_finding in ("FACT", "FINDING")
        assert len(s.source_record_ids) > 0

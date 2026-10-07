"""Mock investigation case and multi-hop transaction dataset.

Enables Member 1 (Tracing), Member 2 (Attribution), and Member 3 (Frontend/DB)
to develop and integrate in parallel with consistent test scenarios.
"""

from datetime import datetime, timezone
from decimal import Decimal
from backend.schemas.attribution import EndpointMatchResult, EntityCategory
from backend.schemas.monitoring import Alert, AlertSeverity, AlertStatus, AlertType
from backend.schemas.report import EvidenceReportRequest
from backend.schemas.risk import (
    AttributionConfidenceAssessment,
    AttributionConfidenceFactor,
    ConfidenceLevel,
    RiskAssessment,
    RiskFactor,
    RiskLevel,
)
from backend.schemas.transaction import NormalizedTransaction, TraceHop, TracePath

# Wallet Addresses in Demonstration Flow
WALLET_A = "0x71c8564a59f0f9b6a1240173693e5077464d621e"  # Reported wallet (suspected scam)
WALLET_B = "0x92b34a6e8721c0fd3814022bc69107ef4187ac2b"  # Intermediary peeling hop 1
WALLET_C = "0x38e889ab8c0192803b90214a1a7c3905e94b29f0"  # Intermediary relay hop 2
TORNADO_POOL = "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf"  # Tornado Cash 10 ETH pool
BINANCE_HOT = "0x28c6c06298d514db089934071355e5743bf21d60"  # Binance Hot Wallet 14

MOCK_TRANSACTIONS: list[NormalizedTransaction] = [
    # Hop 1: Wallet A -> Wallet B (Initial theft outflow)
    NormalizedTransaction(
        chain="ethereum",
        tx_hash="0xaa11bb22cc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66",
        from_address=WALLET_A,
        to_address=WALLET_B,
        amount=Decimal("15.50"),
        asset_symbol="ETH",
        timestamp=datetime(2026, 10, 2, 10, 15, 0, tzinfo=timezone.utc),
        block_number=21054320,
        source="etherscan_api",
    ),
    # Hop 2a: Wallet B -> Tornado Cash (Obfuscation branch)
    NormalizedTransaction(
        chain="ethereum",
        tx_hash="0xbb22cc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77",
        from_address=WALLET_B,
        to_address=TORNADO_POOL,
        amount=Decimal("10.00"),
        asset_symbol="ETH",
        timestamp=datetime(2026, 10, 2, 10, 22, 0, tzinfo=timezone.utc),
        block_number=21054355,
        source="etherscan_api",
    ),
    # Hop 2b: Wallet B -> Wallet C (Peeling residual)
    NormalizedTransaction(
        chain="ethereum",
        tx_hash="0xcc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88",
        from_address=WALLET_B,
        to_address=WALLET_C,
        amount=Decimal("5.45"),
        asset_symbol="ETH",
        timestamp=datetime(2026, 10, 2, 10, 25, 0, tzinfo=timezone.utc),
        block_number=21054370,
        source="etherscan_api",
    ),
    # Hop 3: Wallet C -> Binance Hot Wallet (Liquidation cash-out attempt)
    NormalizedTransaction(
        chain="ethereum",
        tx_hash="0xdd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66ee77ff88aa99",
        from_address=WALLET_C,
        to_address=BINANCE_HOT,
        amount=Decimal("5.40"),
        asset_symbol="ETH",
        timestamp=datetime(2026, 10, 2, 10, 32, 0, tzinfo=timezone.utc),
        block_number=21054405,
        source="etherscan_api",
    ),
]

MOCK_PATHS: list[TracePath] = [
    # Path 1: A -> B -> Tornado Cash
    TracePath(
        path_id="path-eth-01",
        investigation_id="DEMO-INVESTIGATION-001",
        chain="ethereum",
        start_address=WALLET_A,
        end_address=TORNADO_POOL,
        hop_count=2,
        transactions=[MOCK_TRANSACTIONS[0], MOCK_TRANSACTIONS[1]],
        total_volume=Decimal("10.00"),
        is_terminal_endpoint=True,
    ),
    # Path 2: A -> B -> C -> Binance Hot Wallet
    TracePath(
        path_id="path-eth-02",
        investigation_id="DEMO-INVESTIGATION-001",
        chain="ethereum",
        start_address=WALLET_A,
        end_address=BINANCE_HOT,
        hop_count=3,
        transactions=[MOCK_TRANSACTIONS[0], MOCK_TRANSACTIONS[2], MOCK_TRANSACTIONS[3]],
        total_volume=Decimal("5.40"),
        is_terminal_endpoint=True,
    ),
]


def create_mock_investigation_request(case_id: str = "DEMO-INVESTIGATION-001") -> EvidenceReportRequest:
    """Constructs a fully populated mock case request for demo and verification."""
    from backend.attribution.matcher import EndpointMatcher, global_registry
    from backend.monitoring.alerts import AlertEngine
    from backend.schemas.monitoring import MonitoringConfig
    from backend.scoring.confidence_engine import AttributionConfidenceEngine
    from backend.scoring.risk_engine import RiskScoringEngine

    matcher = EndpointMatcher(global_registry)
    endpoints = matcher.match_trace_paths("ethereum", MOCK_PATHS, include_unverified=True)

    risk_engine = RiskScoringEngine()
    risk_assessment = risk_engine.evaluate_risk(
        investigation_id=case_id,
        reported_address=WALLET_A,
        chain="ethereum",
        paths=MOCK_PATHS,
        matched_endpoints=endpoints,
    )

    conf_engine = AttributionConfidenceEngine()
    binance_match = next((ep for ep in endpoints if ep.address.lower() == BINANCE_HOT.lower()), endpoints[0])
    confidence_assessment = conf_engine.evaluate_confidence(
        investigation_id=case_id,
        target_address=BINANCE_HOT,
        chain="ethereum",
        match=binance_match,
        paths=[MOCK_PATHS[1]],
    )

    alert_engine = AlertEngine()
    mon_config = MonitoringConfig(
        investigation_id=case_id,
        chain="ethereum",
        watched_addresses=[WALLET_A, WALLET_B, WALLET_C],
        alert_on_exchange_deposit=True,
        alert_on_mixer=True,
    )

    alerts: list[Alert] = []
    hop_map = {
        MOCK_TRANSACTIONS[0].tx_hash: 1,
        MOCK_TRANSACTIONS[1].tx_hash: 2,
        MOCK_TRANSACTIONS[2].tx_hash: 2,
        MOCK_TRANSACTIONS[3].tx_hash: 3,
    }

    for tx in MOCK_TRANSACTIONS:
        match = matcher.match_address("ethereum", tx.to_address, hop_distance=hop_map[tx.tx_hash], associated_tx_hash=tx.tx_hash)
        generated = alert_engine.evaluate_transaction_for_alerts(
            investigation_id=case_id,
            tx=tx,
            hop_number=hop_map[tx.tx_hash],
            match=match,
            config=mon_config,
        )
        alerts.extend(generated)

    return EvidenceReportRequest(
        investigation_id=case_id,
        reported_wallet=WALLET_A,
        chain="ethereum",
        investigator_name="Agent Forensic Unit 2",
        time_window_start="2026-10-02T10:00:00Z",
        time_window_end="2026-10-02T12:00:00Z",
        paths=MOCK_PATHS,
        endpoints=endpoints,
        risk_assessment=risk_assessment,
        confidence_assessment=confidence_assessment,
        alerts=alerts,
        missing_data_notes="Full 3-hop trace resolved with 100% block history coverage.",
        investigator_notes="Priority subpoena recommendation for Binance Hot Wallet 14 deposit transaction.",
    )

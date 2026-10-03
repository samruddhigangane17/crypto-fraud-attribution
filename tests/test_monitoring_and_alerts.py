"""Unit tests for continuous monitoring and alert deduplication (Member 2 Deliverable)."""

import pytest

from backend.mock_data.mock_case import (
    BINANCE_HOT,
    MOCK_TRANSACTIONS,
    TORNADO_POOL,
    WALLET_A,
    WALLET_B,
    WALLET_C,
)
from backend.monitoring.alerts import AlertEngine
from backend.monitoring.service import MonitoringService
from backend.schemas.attribution import EndpointMatchResult, EntityCategory, VerificationStatus, AddressLabel
from backend.schemas.monitoring import AlertSeverity, AlertType, MonitoringConfig
from backend.schemas.transaction import NormalizedTransaction


@pytest.fixture
def alert_engine():
    return AlertEngine()


@pytest.fixture
def monitoring_service(alert_engine):
    return MonitoringService(alert_engine=alert_engine)


def test_alert_generation_and_deduplication(alert_engine):
    """CRITICAL TEST: Verify repeated checks do NOT generate duplicate alerts."""
    investigation_id = "INV-TEST-DEDUP"
    config = MonitoringConfig(
        investigation_id=investigation_id,
        chain="ethereum",
        watched_addresses=[WALLET_A, WALLET_B],
        alert_on_mixer=True,
    )

    mixer_label = AddressLabel(
        id="m-1",
        chain="ethereum",
        address=TORNADO_POOL,
        entity_name="Tornado Cash 10 ETH",
        entity_category=EntityCategory.MIXER,
        source="OFAC",
        confidence=1.0,
        verification_status=VerificationStatus.VERIFIED,
    )
    match = EndpointMatchResult(
        chain="ethereum",
        address=TORNADO_POOL,
        is_matched=True,
        label=mixer_label,
        match_type="EXACT",
        hop_distance=2,
    )

    tx = MOCK_TRANSACTIONS[1]  # B -> Tornado Cash

    # Cycle 1: First check should generate 2 alerts (MIXER_INTERACTION and NEW_TRANSACTION)
    alerts_cycle_1 = alert_engine.evaluate_transaction_for_alerts(
        investigation_id=investigation_id,
        tx=tx,
        hop_number=2,
        match=match,
        config=config,
    )
    assert len(alerts_cycle_1) == 2
    types = [a.alert_type for a in alerts_cycle_1]
    assert AlertType.MIXER_INTERACTION in types
    assert AlertType.NEW_TRANSACTION in types

    # Cycle 2: Identical transaction re-scanned in the next polling cycle
    alerts_cycle_2 = alert_engine.evaluate_transaction_for_alerts(
        investigation_id=investigation_id,
        tx=tx,
        hop_number=2,
        match=match,
        config=config,
    )
    # MUST BE ZERO - Deduplication active!
    assert len(alerts_cycle_2) == 0

    # Cycle 3: Re-verify total alerts stored in investigation is still exactly 2
    total_stored = alert_engine.get_alerts_by_investigation(investigation_id)
    assert len(total_stored) == 2


def test_monitoring_service_registration_and_polling(monitoring_service):
    """Test full cycle in monitoring service with active case filter."""
    config = MonitoringConfig(
        investigation_id="INV-ACTIVE-01",
        chain="ethereum",
        watched_addresses=[WALLET_C],
        is_active=True,
    )
    monitoring_service.register_case(config)
    assert len(monitoring_service.list_active_configs()) == 1

    # Feed transaction C -> Binance
    tx = MOCK_TRANSACTIONS[3]
    hop_map = {tx.tx_hash: 3}

    alerts = monitoring_service.check_investigation("INV-ACTIVE-01", [tx], hop_lookup=hop_map)
    assert len(alerts) >= 1
    assert any(a.alert_type == AlertType.ENDPOINT_HIT for a in alerts)

    # Repeat check with same tx - should produce 0 alerts
    repeated_alerts = monitoring_service.check_investigation("INV-ACTIVE-01", [tx], hop_lookup=hop_map)
    assert len(repeated_alerts) == 0


def test_monitoring_deactivation(monitoring_service):
    config = MonitoringConfig(
        investigation_id="INV-DEACTIVATE",
        chain="ethereum",
        watched_addresses=[WALLET_A],
        is_active=True,
    )
    monitoring_service.register_case(config)
    assert monitoring_service.get_config("INV-DEACTIVATE").is_active is True

    monitoring_service.unregister_case("INV-DEACTIVATE")
    assert monitoring_service.get_config("INV-DEACTIVATE").is_active is False
    assert len(monitoring_service.list_active_configs()) == 0


def test_exchange_deposit_hop_1_and_hop_2_severity_high(alert_engine):
    """Test Issue 1 fix: Funds reaching an exchange at hop 1 or hop 2 generate AlertSeverity.HIGH without crashing."""
    investigation_id = "INV-HOP-SEVERITY"
    config = MonitoringConfig(
        investigation_id=investigation_id,
        chain="ethereum",
        watched_addresses=["0xwallet_test"],
        alert_on_exchange_deposit=True,
    )
    exchange_label = AddressLabel(
        id="ex-1",
        chain="ethereum",
        address=BINANCE_HOT,
        entity_name="Binance Hot Wallet 14",
        entity_category=EntityCategory.EXCHANGE_VASP,
        source="Etherscan Official Directory",
        confidence=0.99,
        verification_status=VerificationStatus.VERIFIED,
    )

    # Test Hop 1: Direct deposit
    tx_hop1 = NormalizedTransaction(
        chain="ethereum",
        tx_hash="0xhop1txhash1111111111111111111111111111111111111111111111111111111111",
        from_address="0xwallet_test",
        to_address=BINANCE_HOT,
        amount="5.0",
        asset_symbol="ETH",
        timestamp="2026-10-02T11:00:00Z",
    )
    match_hop1 = EndpointMatchResult(
        chain="ethereum",
        address=BINANCE_HOT,
        is_matched=True,
        label=exchange_label,
        match_type="EXACT",
        hop_distance=1,
    )
    alerts_hop1 = alert_engine.evaluate_transaction_for_alerts(
        investigation_id=investigation_id,
        tx=tx_hop1,
        hop_number=1,
        match=match_hop1,
        config=config,
    )
    endpoint_alert_hop1 = next(a for a in alerts_hop1 if a.alert_type == AlertType.ENDPOINT_HIT)
    assert endpoint_alert_hop1.severity == AlertSeverity.HIGH

    # Test Hop 2: Two hops to exchange
    tx_hop2 = NormalizedTransaction(
        chain="ethereum",
        tx_hash="0xhop2txhash2222222222222222222222222222222222222222222222222222222222",
        from_address="0xintermediate",
        to_address=BINANCE_HOT,
        amount="4.9",
        asset_symbol="ETH",
        timestamp="2026-10-02T11:15:00Z",
    )
    match_hop2 = EndpointMatchResult(
        chain="ethereum",
        address=BINANCE_HOT,
        is_matched=True,
        label=exchange_label,
        match_type="EXACT",
        hop_distance=2,
    )
    alerts_hop2 = alert_engine.evaluate_transaction_for_alerts(
        investigation_id=investigation_id,
        tx=tx_hop2,
        hop_number=2,
        match=match_hop2,
        config=config,
    )
    endpoint_alert_hop2 = next(a for a in alerts_hop2 if a.alert_type == AlertType.ENDPOINT_HIT)
    assert endpoint_alert_hop2.severity == AlertSeverity.HIGH

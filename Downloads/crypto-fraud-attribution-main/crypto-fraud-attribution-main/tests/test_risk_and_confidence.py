"""Unit tests for Explainable Risk Assessment and Separate Attribution Confidence."""

import pytest

from backend.mock_data.mock_case import (
    BINANCE_HOT,
    MOCK_PATHS,
    MOCK_TRANSACTIONS,
    TORNADO_POOL,
    WALLET_A,
)
from backend.schemas.attribution import EndpointMatchResult, EntityCategory, VerificationStatus, AddressLabel
from backend.schemas.risk import ConfidenceLevel, RiskLevel
from backend.scoring.confidence_engine import AttributionConfidenceEngine
from backend.scoring.risk_engine import RiskScoringEngine


@pytest.fixture
def risk_engine():
    return RiskScoringEngine()


@pytest.fixture
def conf_engine():
    return AttributionConfidenceEngine()


def test_clean_wallet_low_risk(risk_engine):
    """A wallet with no mixer exposure or illicit proximity should have low risk."""
    assessment = risk_engine.evaluate_risk(
        investigation_id="INV-CLEAN",
        reported_address="0xcleanwallet123",
        chain="ethereum",
        paths=[],
        matched_endpoints=[],
    )
    assert assessment.overall_score == 0.0
    assert assessment.risk_level == RiskLevel.LOW
    assert len(assessment.factors) == 5
    assert not any(f.triggered for f in assessment.factors)


def test_mixer_exposure_triggers_risk(risk_engine):
    """Mixer exposure should contribute up to 30 points and explainable rationale."""
    mixer_label = AddressLabel(
        id="mixer-1",
        chain="ethereum",
        address=TORNADO_POOL,
        entity_name="Tornado Cash 10 ETH Pool",
        entity_category=EntityCategory.MIXER,
        source="OFAC SDN",
        confidence=1.0,
        verification_status=VerificationStatus.VERIFIED,
    )
    mixer_match = EndpointMatchResult(
        chain="ethereum",
        address=TORNADO_POOL,
        is_matched=True,
        label=mixer_label,
        match_type="EXACT",
        hop_distance=2,
    )

    assessment = risk_engine.evaluate_risk(
        investigation_id="INV-MIXER",
        reported_address=WALLET_A,
        chain="ethereum",
        paths=MOCK_PATHS,
        matched_endpoints=[mixer_match],
    )

    mixer_factor = next(f for f in assessment.factors if f.factor_name == "Mixer Exposure")
    assert mixer_factor.triggered is True
    assert mixer_factor.score_contribution == 20.0
    assert "Mixer exposure is an obfuscation indicator, not proof of wrongdoing" in mixer_factor.rationale
    assert assessment.overall_score >= 20.0


def test_sanctioned_wallet_triggers_critical_risk(risk_engine):
    """Sanctioned wallet proximity should give high score contribution."""
    sanction_label = AddressLabel(
        id="sanc-1",
        chain="ethereum",
        address="0x098b716b8aaf21512996dc57eb0615e2383e2f96",
        entity_name="Lazarus Associated",
        entity_category=EntityCategory.SANCTIONED,
        source="OFAC",
        confidence=1.0,
        verification_status=VerificationStatus.VERIFIED,
    )
    match = EndpointMatchResult(
        chain="ethereum",
        address="0x098b716b8aaf21512996dc57eb0615e2383e2f96",
        is_matched=True,
        label=sanction_label,
        match_type="EXACT",
        hop_distance=1,
    )

    assessment = risk_engine.evaluate_risk(
        investigation_id="INV-SANC",
        reported_address="0xsuspicious",
        chain="ethereum",
        paths=[],
        matched_endpoints=[match],
    )

    sanc_factor = next(f for f in assessment.factors if f.factor_name == "Proximity to Flagged Wallets")
    assert sanc_factor.triggered is True
    assert sanc_factor.score_contribution == 35.0


def test_attribution_confidence_separation_from_risk(conf_engine):
    """Test Rule 20: Confidence is evaluated separately from risk score."""
    binance_label = AddressLabel(
        id="binance-1",
        chain="ethereum",
        address=BINANCE_HOT,
        entity_name="Binance Hot Wallet 14",
        entity_category=EntityCategory.EXCHANGE_VASP,
        source="Etherscan Official Directory",
        confidence=0.99,
        verification_status=VerificationStatus.VERIFIED,
    )
    match = EndpointMatchResult(
        chain="ethereum",
        address=BINANCE_HOT,
        is_matched=True,
        label=binance_label,
        match_type="EXACT",
        hop_distance=3,
    )

    conf = conf_engine.evaluate_confidence(
        investigation_id="INV-2026-9041",
        target_address=BINANCE_HOT,
        chain="ethereum",
        match=match,
        paths=MOCK_PATHS,
    )

    assert conf.primary_entity == "Binance Hot Wallet 14"
    assert 0.60 <= conf.overall_confidence <= 0.85
    assert len(conf.limitations) >= 3

    # Check hop attenuation metric
    hop_factor = next(f for f in conf.factors if f.factor_name == "Graph Hop Proximity")
    assert hop_factor.score_contribution == 0.60  # Attenuated at hop 3

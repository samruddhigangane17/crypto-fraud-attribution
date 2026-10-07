"""Tests for USP 1: Freeze-Point Finder & Law Enforcement Freeze Notice Generator."""

from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.recovery.freeze_point_finder import (
    FreezePointFinder,
    SELECTOR_ADD_BLACKLIST_TETHER,
    SELECTOR_BLACKLIST_CIRCLE,
    SELECTOR_IS_BLACKLISTED_TETHER,
    global_freeze_point_finder,
)
from backend.recovery.ranking import RecoverabilityDestination, RecoverabilityRankingEngine
from backend.reports.freeze_notice_generator import (
    FreezeNoticeData,
    FreezeNoticeRequest,
    build_freeze_notice_data,
    global_freeze_notice_generator,
)
from decimal import Decimal
from backend.schemas.attribution import AddressLabel, EndpointMatchResult, EntityCategory
from backend.schemas.path import TracePath
from backend.schemas.transaction import NormalizedTransaction


@pytest.fixture
def client():
    return TestClient(app)


class TestFreezePointIntelligence:
    """Tests the FreezePointFinder and Issuer Registry across multi-chain endpoints."""

    def test_abi_function_selectors(self):
        finder = FreezePointFinder()
        assert finder.match_selector(SELECTOR_ADD_BLACKLIST_TETHER)["issuer"] == "Tether"
        assert finder.match_selector(SELECTOR_BLACKLIST_CIRCLE)["issuer"] == "Circle"
        assert finder.match_selector(SELECTOR_IS_BLACKLISTED_TETHER)["issuer"] == "Tether"
        assert finder.match_selector("0x12345678") is None

    def test_stablecoin_contract_lookup(self):
        finder = FreezePointFinder()
        # Ethereum USDT
        match_eth_usdt = finder.match_contract_by_address("0xdAC17F958D2ee523a2206206994597C13D831ec7")
        assert match_eth_usdt is not None
        assert match_eth_usdt[0] == "USDT"
        assert match_eth_usdt[1] == "ethereum"

        # Polygon USDC
        match_poly_usdc = finder.match_contract_by_address("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359")
        assert match_poly_usdc is not None
        assert match_poly_usdc[0] == "USDC"
        assert match_poly_usdc[1] == "polygon"

    def test_unhosted_usdt_freezable_by_tether(self):
        finder = FreezePointFinder()
        info = finder.evaluate_endpoint(
            address="0x1111111111111111111111111111111111111111",
            asset="USDT",
            chain="ethereum",
            entity_category="NON_CUSTODIAL_WALLET",
            confidence=0.85,
        )
        assert info.freezable_by == "Tether"
        assert "addBlackList" in info.freeze_mechanism
        assert "t3fcu@tether.to" in info.issuer_contact_portal
        assert info.confidence_gate_passed is True
        assert info.actionability_tier == "Act Now"

    def test_unhosted_usdc_freezable_by_circle(self):
        finder = FreezePointFinder()
        info = finder.evaluate_endpoint(
            address="0x2222222222222222222222222222222222222222",
            asset="USDC",
            chain="polygon",
            entity_category="NON_CUSTODIAL_WALLET",
            confidence=0.90,
        )
        assert info.freezable_by == "Circle"
        assert "blacklist" in info.freeze_mechanism
        assert "legal@circle.com" in info.issuer_contact_portal
        assert info.confidence_gate_passed is True

    def test_vasp_deposit_holding_usdt_freezable_by_both(self):
        finder = FreezePointFinder()
        info = finder.evaluate_endpoint(
            address="0x3333333333333333333333333333333333333333",
            asset="USDT",
            chain="ethereum",
            entity_category="exchange_vasp",
            entity_name="Binance Deposit",
            confidence=0.88,
        )
        assert info.freezable_by == "Exchange + Tether"
        assert "VASP Account Freeze" in info.freeze_mechanism
        assert "addBlackList" in info.freeze_mechanism
        assert "binance" in info.issuer_contact_portal.lower()
        assert info.confidence_gate_passed is True

    def test_vasp_deposit_holding_native_eth_freezable_by_exchange_only(self):
        finder = FreezePointFinder()
        info = finder.evaluate_endpoint(
            address="0x4444444444444444444444444444444444444444",
            asset="ETH",
            chain="ethereum",
            entity_category="exchange_vasp",
            entity_name="CoinDCX",
            confidence=0.80,
        )
        assert info.freezable_by == "Exchange"
        assert info.freeze_mechanism == "VASP Account Freeze"
        assert "coindcx" in info.issuer_contact_portal.lower()
        assert info.confidence_gate_passed is True

    def test_unhosted_native_eth_unfreezable(self):
        finder = FreezePointFinder()
        info = finder.evaluate_endpoint(
            address="0x5555555555555555555555555555555555555555",
            asset="ETH",
            chain="ethereum",
            entity_category="NON_CUSTODIAL_WALLET",
            confidence=0.95,
        )
        assert info.freezable_by == "none"
        assert info.freeze_mechanism == "None (Unhosted Native Asset)"
        assert info.confidence_gate_passed is False
        assert info.actionability_tier == "Monitor"

    def test_minimum_confidence_gate_enforcement(self):
        finder = FreezePointFinder()
        # Even though VASP has freezable USDT, confidence is 60% (< 75% statutory threshold)
        info = finder.evaluate_endpoint(
            address="0x6666666666666666666666666666666666666666",
            asset="USDT",
            entity_category="exchange_vasp",
            entity_name="WazirX",
            confidence=0.60,
        )
        assert info.freezable_by == "Exchange + Tether"
        assert info.confidence_gate_passed is False
        assert info.actionability_tier == "Act Soon"
        assert "below the statutory 75% threshold" in info.why_this_tier


class TestRecoverabilityRankingIntegration:
    """Verifies RecoverabilityRankingEngine produces full USP 1 fields."""

    def test_ranking_engine_populates_usp1_fields(self):
        engine = RecoverabilityRankingEngine()

        paths = [
            TracePath(
                investigation_id="P1",
                hop_count=1,
                end_address="0xbinance_dest",
                transactions=[
                    NormalizedTransaction(
                        chain="ethereum",
                        tx_hash="0xabc123",
                        from_address="0xvictim",
                        to_address="0xbinance_dest",
                        amount=Decimal("15000.0"),
                        asset_symbol="USDT",
                        timestamp=datetime.now(timezone.utc),
                        block_number=12345,
                    )
                ],
            )
        ]

        endpoints = [
            EndpointMatchResult(
                chain="ethereum",
                address="0xbinance_dest",
                is_matched=True,
                match_type="EXACT",
                label=AddressLabel(
                    id="L1",
                    chain="ethereum",
                    address="0xbinance_dest",
                    entity_name="Binance Hot Wallet",
                    entity_category=EntityCategory.EXCHANGE_VASP,
                    source="Etherscan Registry",
                    confidence=0.92,
                ),
            )
        ]

        ranked = engine.rank_destinations(paths, endpoints)
        assert len(ranked) == 1
        top = ranked[0]

        assert top.destination_address == "0xbinance_dest"
        assert top.freezable_by == "Exchange + Tether"
        assert "VASP Account Freeze" in top.freeze_mechanism
        assert top.confidence_gate_passed is True
        assert top.actionability_tier == "Act Now"
        assert len(top.why_this_tier) > 0
        assert top.token_contract is not None
        assert top.blacklist_selector == SELECTOR_ADD_BLACKLIST_TETHER


class TestFreezeNoticePDFGeneration:
    """Tests the court-ready PDF generation and BSA 2023 Section 63 certificate."""

    def test_pdf_builds_with_bsa_certificate(self):
        generator = global_freeze_notice_generator
        data = FreezeNoticeData(
            case_id="DEMO-FRZ-001",
            ncrp_ack_no="NCRP-2024-998822",
            destination_address="0x28c6c06298d514db089934071355e5743bf21d60",
            entity_name="Binance Settlement Cluster",
            freezable_by="Exchange + Tether",
            freeze_mechanism="VASP Account Freeze + Smart Contract Blacklist (addBlackList)",
            traced_amount=25000.0,
            asset="USDT",
            chain="ethereum",
            attribution_confidence=0.94,
            confidence_gate_passed=True,
            hop_count=2,
            tx_hashes=["0x88f912a76b91c..."],
        )

        pdf_bytes = generator.generate_notice_pdf(data)
        assert len(pdf_bytes) > 2000
        # Check PDF Magic Bytes
        assert pdf_bytes[:4] == b"%PDF"


class TestFreezeNoticeEndpoints:
    """Verifies API endpoints for statutory freeze notice generation."""

    def test_generate_freeze_notice_json(self, client):
        payload = {
            "case_id": "DEMO-FRZ-ENDPOINT",
            "destination_address": "0x1234567890abcdef1234567890abcdef12345678",
            "target_entity": "Binance Deposit",
            "freezable_by": "Exchange + Tether",
            "freeze_mechanism": "VASP Account Freeze",
            "traced_amount": 5000.0,
            "asset": "USDT",
            "attribution_confidence": 0.88,
            "format": "json",
        }
        res = client.post("/api/freeze-notice/generate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["case_id"] == "DEMO-FRZ-ENDPOINT"
        assert data["confidence_gate_passed"] is True
        assert data["bsa_section_63_certificate"]["status"] == "Attested"

    def test_generate_freeze_notice_pdf(self, client):
        payload = {
            "case_id": "DEMO-FRZ-PDF",
            "destination_address": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            "target_entity": "Tether T3 FCU",
            "freezable_by": "Tether",
            "freeze_mechanism": "Smart Contract Blacklist (addBlackList)",
            "traced_amount": 10000.0,
            "asset": "USDT",
            "attribution_confidence": 0.95,
            "format": "pdf",
        }
        res = client.post("/api/freeze-notice/generate", json=payload)
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        assert "Freeze_Notice_DEMO-FRZ-PDF_" in res.headers["content-disposition"]
        assert len(res.content) > 1000

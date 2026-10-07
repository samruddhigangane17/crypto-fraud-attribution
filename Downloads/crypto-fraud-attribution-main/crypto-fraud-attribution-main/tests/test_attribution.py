"""Unit tests for Address Registry and Endpoint Matching (Member 2 Deliverable)."""

import pytest

from backend.attribution.matcher import EndpointMatcher
from backend.attribution.registry import KnownAddressRegistry
from backend.schemas.attribution import (
    AddressLabelCreate,
    EntityCategory,
    VerificationStatus,
)
from backend.schemas.transaction import NormalizedTransaction, TraceHop, TracePath


@pytest.fixture
def registry():
    return KnownAddressRegistry(load_seed_data=True)


@pytest.fixture
def matcher(registry):
    return EndpointMatcher(registry)


def test_registry_seeds_loaded(registry):
    stats = registry.get_stats()
    assert stats["verified_count"] >= 8
    assert stats["unverified_community_count"] >= 2
    assert stats["total_count"] >= 10


def test_verified_vs_community_separation(registry):
    """Test that community unverified labels are strictly isolated unless requested."""
    # Known community address in seed data
    comm_addr = "0x71c8564a59f0f9b6a1240173693e5077464d621e"

    # Default lookup must NOT return unverified community labels
    res_default = registry.lookup("ethereum", comm_addr, include_unverified=False)
    assert res_default is None

    # Lookup with include_unverified=True returns the community label
    res_comm = registry.lookup("ethereum", comm_addr, include_unverified=True)
    assert res_comm is not None
    assert res_comm.verification_status == VerificationStatus.UNVERIFIED_COMMUNITY
    assert "Reported Phishing" in res_comm.entity_name


def test_exact_address_matching_case_insensitive_evm(matcher):
    """EVM addresses should match regardless of checksum casing."""
    binance_lower = "0x28c6c06298d514db089934071355e5743bf21d60"
    binance_upper = "0x28C6C06298D514DB089934071355E5743BF21D60"

    match_res = matcher.match_address("ethereum", binance_upper, hop_distance=2)
    assert match_res.is_matched is True
    assert match_res.match_type == "EXACT"
    assert match_res.label is not None
    assert "Binance" in match_res.label.entity_name
    assert match_res.label.entity_category == EntityCategory.EXCHANGE_VASP
    assert match_res.hop_distance == 2


def test_unmatched_endpoint_marked_unknown(matcher):
    """Rule: Mark unmatched endpoints as unknown rather than assuming they are suspicious."""
    unknown_addr = "0x1111222233334444555566667777888899990000"
    res = matcher.match_address("ethereum", unknown_addr)

    assert res.is_matched is False
    assert res.label is None
    assert res.match_type == "UNKNOWN"
    assert "UNKNOWN" in res.investigative_note


def test_data_provenance_fields(registry):
    """Verify all labels contain complete provenance metadata."""
    labels = registry.get_all(include_unverified=True)
    for l in labels:
        assert l.id is not None
        assert l.chain in ["ethereum", "bitcoin", "tron", "bsc"]
        assert len(l.source) > 0
        assert 0.0 <= l.confidence <= 1.0


def test_multi_chain_lookups(registry):
    """Look up addresses on Bitcoin, TRON, and BSC."""
    btc_label = registry.lookup("bitcoin", "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo")
    assert btc_label is not None
    assert btc_label.entity_category == EntityCategory.EXCHANGE_VASP

    trx_label = registry.lookup("tron", "TWd4WrZ9wn84f5x1hZhL4DHvk738ns5jwb")
    assert trx_label is not None
    assert trx_label.chain == "tron"
    assert trx_label.entity_category == EntityCategory.EXCHANGE_VASP


def test_register_new_custom_label(registry):
    new_label = registry.register(
        AddressLabelCreate(
            chain="ethereum",
            address="0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            entity_name="Test Compliance Wallet",
            entity_category=EntityCategory.DEFI_PROTOCOL,
            source="Internal Compliance Manual Audit",
            confidence=0.95,
            verification_status=VerificationStatus.VERIFIED,
        )
    )
    assert new_label.id is not None
    found = registry.lookup("ethereum", "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd")
    assert found is not None
    assert found.entity_name == "Test Compliance Wallet"

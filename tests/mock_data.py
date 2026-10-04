"""FAKE data for development. Addresses are obviously not real.

Flow (all ethereum, native ETH):
  A -> B -> C -> D -> EXCHANGE_HOT
  A -> E -> F            (dead end)
  B -> G                 (branch)
"""
from backend.schemas.transaction import NormalizedTransaction

MOCK_INVESTIGATION = {
    "id": "00000000-0000-0000-0000-000000000001",
    "chain": "ethereum",
    "reported_address": "0xmock_wallet_a",
    "status": "created",
}

_EDGES = [
    ("0xmock_wallet_a", "0xmock_wallet_b", "10.0", "0xmocktx01", "2026-10-01T09:00:00Z", 1000),
    ("0xmock_wallet_b", "0xmock_wallet_c", "9.9", "0xmocktx02", "2026-10-01T10:00:00Z", 1010),
    ("0xmock_wallet_c", "0xmock_wallet_d", "9.8", "0xmocktx03", "2026-10-01T11:30:00Z", 1025),
    ("0xmock_wallet_d", "0xmock_exchange_hot", "9.7", "0xmocktx04", "2026-10-01T13:00:00Z", 1040),
    ("0xmock_wallet_a", "0xmock_wallet_e", "2.5", "0xmocktx05", "2026-10-01T09:30:00Z", 1005),
    ("0xmock_wallet_e", "0xmock_wallet_f", "2.4", "0xmocktx06", "2026-10-01T12:00:00Z", 1030),
    ("0xmock_wallet_b", "0xmock_wallet_g", "0.5", "0xmocktx07", "2026-10-01T10:20:00Z", 1012),
]

MOCK_TRANSACTIONS = [
    NormalizedTransaction(
        chain="ethereum", tx_hash=h, from_address=f, to_address=t,
        amount=amt, asset_symbol="ETH", timestamp=ts, block_number=blk,
        source="mock",
    )
    for f, t, amt, h, ts, blk in _EDGES
]

MOCK_ADDRESS_LABELS = [
    {
        "chain": "ethereum",
        "address": "0xmock_exchange_hot",
        "entity_name": "MockExchange",
        "source": "mock_registry",
        "confidence": "medium",
        "verified_at": "2026-09-01",
    },
]
# ---------------------------------------------------------------------
# Member 2 fixtures (used by tests/test_schema.py and attribution tests)
# ---------------------------------------------------------------------
from datetime import datetime, timezone
from decimal import Decimal

from backend.schemas.attribution import AddressLabel, EntityCategory, VerificationStatus
from backend.schemas.transaction import NormalizedTransaction, TracePath

SAMPLE_TRANSACTION_DICT = {
    "chain": "ethereum",
    "tx_hash": "0x1111222233334444555566667777888899990000111122223333444455556666",
    "from_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "to_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "amount": "12.3456",
    "asset_symbol": "ETH",
    "timestamp": "2026-10-02T10:30:00Z",
    "block_number": 21000000,
    "source": "etherscan_api",
}

SAMPLE_NORMALIZED_TX = NormalizedTransaction(
    chain="ethereum",
    tx_hash="0x1111222233334444555566667777888899990000111122223333444455556666",
    from_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    to_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    amount=Decimal("12.3456"),
    asset_symbol="ETH",
    timestamp=datetime(2026, 10, 2, 10, 30, 0, tzinfo=timezone.utc),
    block_number=21000000,
    source="etherscan_api",
)

SAMPLE_TRACE_PATH = TracePath(
    investigation_id="TEST-CASE-001",
    chain="ethereum",
    start_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    end_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    hop_count=1,
    transactions=[SAMPLE_NORMALIZED_TX],
    total_volume=Decimal("12.3456"),
    is_terminal_endpoint=True,
)

SAMPLE_LABEL = AddressLabel(
    id="lbl-test-01",
    chain="ethereum",
    address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    entity_name="Test Exchange",
    entity_category=EntityCategory.EXCHANGE_VASP,
    source="Verified Test Source",
    source_url="https://example.com",
    confidence=0.99,
    verified_at="2026-01-01T00:00:00Z",
    verification_status=VerificationStatus.VERIFIED,
)
